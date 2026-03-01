"""
model_api.py  —  THE HANDOFF FILE

Sanjavan imports this into the FastAPI app.

Usage:
    from model_api import PharmaRiskModel

    model = PharmaRiskModel()
    result = model.predict(
        genes=[
            {"name": "CYP2D6", "activity_level": 0.0},
            {"name": "CYP2C19", "activity_level": 1.0}
        ],
        drug="codeine"
    )

    # result:
    # {
    #     "risk_score": 9.2,
    #     "risk_level": "HIGH",
    #     "gene_contributions": {"CYP2D6": 0.89, "CYP2C19": 0.11},
    #     "attention_weights": [0.89, 0.11],
    #     "model_used": "set_transformer"
    # }
"""

import os
import pickle
import numpy as np
import torch

from model import PharmaSetTransformer


# ── Risk level thresholds ─────────────────────────────────────────────────────

def score_to_level(score: float) -> str:
    if score >= 7.0:
        return "HIGH"
    elif score >= 4.0:
        return "MEDIUM"
    else:
        return "LOW"


# ── Main model class ──────────────────────────────────────────────────────────

class PharmaRiskModel:
    def __init__(self,
                 model_path:        str = "set_transformer.pt",
                 gene_emb_path:     str = "embeddings/gene_embeddings.pkl",
                 drug_emb_path:     str = "embeddings/drug_embeddings.pkl",
                 target_flags_path: str = "embeddings/target_flags.pkl",
                 xgboost_path:      str = "xgboost_baseline.json"):

        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

        # ── Load pre-computed embeddings ──────────────────────────────────────
        with open(gene_emb_path, "rb") as f:
            self.gene_embeddings = pickle.load(f)   # gene_symbol → np[1280]

        with open(drug_emb_path, "rb") as f:
            self.drug_embeddings = pickle.load(f)   # drug_name → np[1024]

        with open(target_flags_path, "rb") as f:
            self.target_flags = pickle.load(f)      # drug → gene → 0/1

        # ── Load Set Transformer ──────────────────────────────────────────────
        self.transformer = None
        if os.path.exists(model_path):
            checkpoint = torch.load(model_path, map_location=self.device)
            args       = checkpoint["args"]

            self.transformer = PharmaSetTransformer(
                gene_dim = args.get("gene_dim", 128),
                drug_dim = args.get("gene_dim", 128),
                n_heads  = args.get("n_heads",  4),
                dropout  = 0.0,   # no dropout at inference
            ).to(self.device)

            self.transformer.load_state_dict(checkpoint["model_state"])
            self.transformer.eval()
            print(f"[model_api] Set Transformer loaded from {model_path}")
        else:
            print(f"[model_api] WARNING: Set Transformer not found at {model_path}")

        # ── Load XGBoost fallback ─────────────────────────────────────────────
        self.xgboost = None
        if os.path.exists(xgboost_path):
            import xgboost as xgb
            self.xgboost = xgb.XGBRegressor()
            self.xgboost.load_model(xgboost_path)
            print(f"[model_api] XGBoost fallback loaded from {xgboost_path}")

    def _predict_transformer(self,
                             genes: list[dict],
                             drug:  str) -> dict:
        """
        Run full Set Transformer inference on a multi-gene patient.

        Args:
            genes: list of {"name": str, "activity_level": float}
            drug:  drug name string
        """
        drug_key = drug.strip().lower()

        # ── Collect valid genes ───────────────────────────────────────────────
        valid_genes     = []
        gene_emb_list   = []
        flag_list       = []
        activity_list   = []

        for g in genes:
            gene_symbol = g["name"].strip().upper()

            if gene_symbol not in self.gene_embeddings:
                print(f"  [skip] No embedding for gene: {gene_symbol}")
                continue

            gene_emb_list.append(self.gene_embeddings[gene_symbol])
            flag_val = self.target_flags.get(drug_key, {}).get(gene_symbol, 0)
            flag_list.append(flag_val)
            activity_list.append(float(g.get("activity_level", 1.0)))
            valid_genes.append(gene_symbol)

        if not valid_genes:
            return None   # no valid genes — trigger fallback

        if drug_key not in self.drug_embeddings:
            return None   # unknown drug — trigger fallback

        # ── Build tensors ─────────────────────────────────────────────────────
        gene_tensor = torch.tensor(
            np.stack(gene_emb_list), dtype=torch.float32
        ).to(self.device)                                    # [n_genes, 1280]

        drug_tensor = torch.tensor(
            self.drug_embeddings[drug_key], dtype=torch.float32
        ).unsqueeze(0).to(self.device)                       # [1, 1024]

        activity_tensor = torch.tensor(
            activity_list, dtype=torch.float32
        ).to(self.device)                                    # [n_genes]

        flag_tensor = torch.tensor(
            flag_list, dtype=torch.long
        ).to(self.device)                                    # [n_genes]

        # ── Inference ─────────────────────────────────────────────────────────
        with torch.no_grad():
            risk_score, attn_weights = self.transformer(
                gene_tensor, drug_tensor, flag_tensor
            )

        score        = float(risk_score.cpu().item())
        attn_np      = attn_weights.cpu().numpy().tolist()
        contributions = {
            gene: round(float(w), 4)
            for gene, w in zip(valid_genes, attn_np)
        }

        return {
            "risk_score":        round(score, 2),
            "risk_level":        score_to_level(score),
            "gene_contributions": contributions,
            "attention_weights": attn_np,
            "model_used":        "set_transformer",
        }

    def _predict_xgboost(self, genes: list[dict], drug: str) -> dict:
        """XGBoost fallback — uses mean gene embedding + drug embedding as features."""
        if self.xgboost is None:
            return {
                "error":      "Both Set Transformer and XGBoost are unavailable.",
                "risk_score": None,
                "risk_level": None,
            }

        drug_key = drug.strip().lower()

        gene_vecs = [
            self.gene_embeddings[g["name"].strip().upper()]
            for g in genes
            if g["name"].strip().upper() in self.gene_embeddings
        ]

        if not gene_vecs or drug_key not in self.drug_embeddings:
            return {"error": "Insufficient data for XGBoost fallback."}

        mean_gene  = np.mean(gene_vecs, axis=0)
        drug_vec   = self.drug_embeddings[drug_key]
        features   = np.concatenate([mean_gene, drug_vec]).reshape(1, -1)

        raw_score = float(self.xgboost.predict(features)[0])
        score     = float(np.clip(raw_score, 1.0, 10.0))

        return {
            "risk_score":        round(score, 2),
            "risk_level":        score_to_level(score),
            "gene_contributions": {},
            "attention_weights": [],
            "model_used":        "xgboost_fallback",
        }

    def predict(self, genes: list[dict], drug: str) -> dict:
        """
        THE MAIN FUNCTION — Sanjavan calls this from FastAPI.

        Args:
            genes: list of {"name": str, "activity_level": float}
                   Unknown genes are skipped gracefully.
            drug:  drug name string.
                   Unknown drug returns error dict, does not crash.

        Returns:
            {
                "risk_score":         float (1-10),
                "risk_level":         str ("LOW" | "MEDIUM" | "HIGH"),
                "gene_contributions": dict (gene → attention weight),
                "attention_weights":  list[float],
                "model_used":         str
            }
        """
        if not genes:
            return {"error": "No genes provided.", "risk_score": None, "risk_level": None}

        if not drug or not drug.strip():
            return {"error": "No drug provided.", "risk_score": None, "risk_level": None}

        # Try Set Transformer first
        if self.transformer is not None:
            try:
                result = self._predict_transformer(genes, drug)
                if result is not None:
                    return result
            except Exception as e:
                print(f"  [warn] Set Transformer failed: {e}. Falling back to XGBoost.")

        # Fall back to XGBoost
        return self._predict_xgboost(genes, drug)


# ── Quick test ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    model = PharmaRiskModel()

    test_cases = [
        {
            "genes": [
                {"name": "CYP2D6",  "activity_level": 0.0},
                {"name": "CYP2C19", "activity_level": 1.0},
            ],
            "drug": "codeine"
        },
        {
            "genes": [{"name": "HLA-B", "activity_level": 1.0}],
            "drug": "abacavir"
        },
        {
            "genes": [{"name": "TPMT", "activity_level": 0.0}],
            "drug": "azathioprine"
        },
    ]

    for i, case in enumerate(test_cases):
        result = model.predict(case["genes"], case["drug"])
        print(f"\nTest {i+1}: genes={[g['name'] for g in case['genes']]}, drug={case['drug']}")
        print(f"  Risk score : {result.get('risk_score')}")
        print(f"  Risk level : {result.get('risk_level')}")
        print(f"  Model used : {result.get('model_used')}")
        print(f"  Gene contributions: {result.get('gene_contributions')}")
