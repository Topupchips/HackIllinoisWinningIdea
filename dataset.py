"""
dataset.py

PyTorch Dataset for the PharmaSetTransformer.

Loads:
  - labeled_data.json       — (gene, activity_level, medicine, risk_score)
  - gene_embeddings.pkl     — ESM-2 vectors: gene_symbol → numpy[1280]
  - drug_embeddings.pkl     — Morgan FP vectors: drug_name → numpy[1024]
  - target_flags.pkl        — DrugBank binary: drug_name → gene_symbol → 0/1

Each sample returns:
  - gene_embedding:  Tensor[1280]
  - activity_level:  Tensor[1]      (float, from alleles.csv via Sanjavan)
  - drug_embedding:  Tensor[1024]
  - target_flag:     Tensor[1]      (long, 0 or 1)
  - risk_score:      Tensor[1]      (float, 1-10)

Note: This dataset is for TRAINING on single (gene, drug) pairs.
      Multi-gene patient aggregation happens at inference time in model_api.py.
"""

import json
import pickle
import numpy as np
import torch
from torch.utils.data import Dataset, DataLoader
from typing import Tuple


class PharmaDataset(Dataset):
    def __init__(self,
                 labeled_path:    str,
                 gene_emb_path:   str,
                 drug_emb_path:   str,
                 target_flags_path: str):
        """
        Args:
            labeled_path:       Path to labeled JSON (output of llm_labeler.py)
            gene_emb_path:      Path to gene_embeddings.pkl
            drug_emb_path:      Path to drug_embeddings.pkl
            target_flags_path:  Path to target_flags.pkl
        """
        # ── Load pre-computed embeddings ──────────────────────────────────────
        with open(gene_emb_path, "rb") as f:
            self.gene_embeddings = pickle.load(f)   # dict: gene_symbol → np[1280]

        with open(drug_emb_path, "rb") as f:
            self.drug_embeddings = pickle.load(f)   # dict: drug_name → np[1024]

        with open(target_flags_path, "rb") as f:
            self.target_flags = pickle.load(f)      # dict: drug → gene → 0/1

        # ── Load and filter labeled data ──────────────────────────────────────
        with open(labeled_path, "r") as f:
            raw = json.load(f)

        self.data = []
        skipped   = 0

        for record in raw:
            gene     = record["gene"].strip().upper()
            medicine = record["medicine"].strip().lower()
            score    = record["risk_score"]

            # Skip failed LLM labels
            if score == -1.0:
                skipped += 1
                continue

            # Skip if embeddings are missing
            if gene not in self.gene_embeddings:
                print(f"  [skip] No gene embedding for: {gene}")
                skipped += 1
                continue

            if medicine not in self.drug_embeddings:
                print(f"  [skip] No drug embedding for: {medicine}")
                skipped += 1
                continue

            self.data.append({
                "gene":           gene,
                "activity_level": float(record["activity_level"]),
                "medicine":       medicine,
                "risk_score":     float(score),
            })

        print(f"[dataset] Loaded: {len(self.data)} records | Skipped: {skipped}")

    def __len__(self) -> int:
        return len(self.data)

    def __getitem__(self, idx: int) -> Tuple:
        record   = self.data[idx]
        gene     = record["gene"]
        medicine = record["medicine"]

        gene_emb   = torch.tensor(self.gene_embeddings[gene],   dtype=torch.float32)  # [1280]
        drug_emb   = torch.tensor(self.drug_embeddings[medicine], dtype=torch.float32) # [1024]
        activity   = torch.tensor([record["activity_level"]],   dtype=torch.float32)  # [1]
        risk_score = torch.tensor([record["risk_score"]],       dtype=torch.float32)  # [1]

        # Target flag: does this drug target this gene? (0 or 1)
        flag_val = self.target_flags.get(medicine, {}).get(gene, 0)
        flag     = torch.tensor(flag_val, dtype=torch.long)   # scalar

        return gene_emb, activity, drug_emb, flag, risk_score


# ── Convenience dataloader factory ───────────────────────────────────────────

def get_dataloader(labeled_path:      str,
                   gene_emb_path:     str,
                   drug_emb_path:     str,
                   target_flags_path: str,
                   batch_size:        int = 32,
                   shuffle:           bool = True) -> Tuple[DataLoader, PharmaDataset]:

    dataset = PharmaDataset(labeled_path, gene_emb_path, drug_emb_path, target_flags_path)
    loader  = DataLoader(dataset, batch_size=batch_size, shuffle=shuffle)
    return loader, dataset
