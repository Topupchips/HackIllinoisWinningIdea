"""
validation.py

Evaluates the trained PharmaSetTransformer on the held-out 20% test set.

Metrics reported:
  - RMSE               (Root Mean Squared Error)
  - Spearman           (rank correlation — does the model rank risk correctly?)
  - ±1 Accuracy        (% of predictions within 1 point of true score)

Results saved to: validation_results.json

Usage:
    python validation.py \
        --labeled_data  labeled_data.json \
        --gene_emb      embeddings/gene_embeddings.pkl \
        --drug_emb      embeddings/drug_embeddings.pkl \
        --target_flags  embeddings/target_flags.pkl \
        --model_path    set_transformer.pt \
        --output        validation_results.json
"""

import json
import argparse
import numpy as np
import torch
from torch.utils.data import random_split, DataLoader
from scipy.stats import spearmanr

from dataset import PharmaDataset
from model import PharmaSetTransformer


# ── Metrics ───────────────────────────────────────────────────────────────────

def rmse(preds: list, labels: list) -> float:
    p = np.array(preds)
    l = np.array(labels)
    return float(np.sqrt(np.mean((p - l) ** 2)))


def spearman(preds: list, labels: list) -> float:
    corr, _ = spearmanr(preds, labels)
    return float(corr)


def within_one_accuracy(preds: list, labels: list) -> float:
    p = np.array(preds)
    l = np.array(labels)
    return float(np.mean(np.abs(p - l) <= 1.0))


# ── Inference on single sample ────────────────────────────────────────────────

@torch.no_grad()
def run_inference(model, loader, device):
    """Run model over all samples in loader, return (preds, labels, details)."""
    model.eval()

    all_preds  = []
    all_labels = []
    all_details = []

    for gene_emb, activity, drug_emb, flag, risk_score in loader:
        gene_emb   = gene_emb.to(device)
        drug_emb   = drug_emb.to(device)
        activity   = activity.to(device)
        flag       = flag.to(device)
        risk_score = risk_score.to(device)

        for i in range(gene_emb.shape[0]):
            g_emb = gene_emb[i].unsqueeze(0)    # [1, 1280]
            d_emb = drug_emb[i].unsqueeze(0)    # [1, 1024]
            act   = activity[i].unsqueeze(0)    # [1]
            f     = flag[i].unsqueeze(0)        # [1]

            risk, attn = model(g_emb, d_emb, act, f)

            pred  = float(risk.cpu().item())
            label = float(risk_score[i].cpu().item())

            all_preds.append(pred)
            all_labels.append(label)
            all_details.append({
                "predicted":  round(pred, 2),
                "actual":     round(label, 2),
                "error":      round(abs(pred - label), 2),
                "within_one": abs(pred - label) <= 1.0,
            })

    return all_preds, all_labels, all_details


# ── Main ──────────────────────────────────────────────────────────────────────

def validate(args):
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Using device: {device}")

    # ── Load full dataset and reproduce the same 80/20 split as training ──────
    # IMPORTANT: same random seed (42) as train.py to ensure the val set
    # is truly held-out and not contaminated with training samples
    full_dataset = PharmaDataset(
        labeled_path      = args.labeled_data,
        gene_emb_path     = args.gene_emb,
        drug_emb_path     = args.drug_emb,
        target_flags_path = args.target_flags,
    )

    val_size   = int(len(full_dataset) * 0.2)
    train_size = len(full_dataset) - val_size
    _, val_dataset = random_split(
        full_dataset,
        [train_size, val_size],
        generator=torch.Generator().manual_seed(42)   # must match train.py
    )

    val_loader = DataLoader(val_dataset, batch_size=32, shuffle=False)
    print(f"Validation samples: {val_size}")

    # ── Load trained model ────────────────────────────────────────────────────
    checkpoint = torch.load(args.model_path, map_location=device)
    saved_args = checkpoint["args"]

    model = PharmaSetTransformer(
        gene_dim = saved_args.get("gene_dim", 128),
        drug_dim = saved_args.get("gene_dim", 128),
        n_heads  = saved_args.get("n_heads",  4),
        dropout  = 0.0,   # no dropout at validation
    ).to(device)

    model.load_state_dict(checkpoint["model_state"])
    print(f"Model loaded from {args.model_path} (epoch {checkpoint['epoch']})")

    # ── Run inference ─────────────────────────────────────────────────────────
    preds, labels, details = run_inference(model, val_loader, device)

    # ── Compute metrics ───────────────────────────────────────────────────────
    rmse_score     = rmse(preds, labels)
    spearman_score = spearman(preds, labels)
    within_one     = within_one_accuracy(preds, labels)

    # Risk level breakdown (LOW/MEDIUM/HIGH)
    def to_level(s):
        if s >= 7.0: return "HIGH"
        if s >= 4.0: return "MEDIUM"
        return "LOW"

    level_correct = sum(
        1 for p, l in zip(preds, labels)
        if to_level(p) == to_level(l)
    )
    level_accuracy = level_correct / len(preds)

    # ── Print results ─────────────────────────────────────────────────────────
    print("\n" + "="*50)
    print("VALIDATION RESULTS")
    print("="*50)
    print(f"Samples evaluated : {len(preds)}")
    print(f"RMSE              : {rmse_score:.4f}")
    print(f"Spearman          : {spearman_score:.4f}  (target: > 0.70)")
    print(f"±1 Accuracy       : {within_one*100:.1f}%")
    print(f"Risk Level Acc    : {level_accuracy*100:.1f}%  (LOW/MEDIUM/HIGH)")

    if spearman_score >= 0.7:
        print("\n✓ Spearman target met (> 0.70)")
    else:
        print(f"\n✗ Spearman target not met — current: {spearman_score:.4f}")
    print("="*50)

    # ── Save results ──────────────────────────────────────────────────────────
    results = {
        "model_path":       args.model_path,
        "val_samples":      len(preds),
        "metrics": {
            "rmse":             round(rmse_score, 4),
            "spearman":         round(spearman_score, 4),
            "within_one_acc":   round(within_one, 4),
            "risk_level_acc":   round(level_accuracy, 4),
        },
        "targets": {
            "spearman_target":  0.70,
            "spearman_met":     spearman_score >= 0.70,
        },
        "per_sample": details,
    }

    with open(args.output, "w") as f:
        json.dump(results, f, indent=2)

    print(f"\nResults saved to: {args.output}")


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Validate PharmaSetTransformer")
    parser.add_argument("--labeled_data",  required=True)
    parser.add_argument("--gene_emb",      required=True)
    parser.add_argument("--drug_emb",      required=True)
    parser.add_argument("--target_flags",  required=True)
    parser.add_argument("--model_path",    default="set_transformer.pt")
    parser.add_argument("--output",        default="validation_results.json")
    args = parser.parse_args()

    validate(args)
