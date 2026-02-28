"""
embed.py

Pre-computes and saves all frozen embeddings:
  1. Gene embeddings  — ESM-2 on UniProt protein sequences → gene_embeddings.pkl
  2. Drug embeddings  — Morgan Fingerprints on SMILES      → drug_embeddings.pkl
  3. Target flags     — DrugBank binary lookup             → target_flags.pkl

Run ONCE before training. These are frozen — not updated during training.

Usage:
    python embed.py \
        --drug_smiles    data/processed/drug_smiles.csv \
        --drug_targets   data/processed/drug_gene_targets.csv \
        --labeled_data   labeled_data.json \
        --output_dir     embeddings/
"""

import os
import json
import pickle
import argparse
import numpy as np
import pandas as pd

# ── Gene embedding via ESM-2 ──────────────────────────────────────────────────

def fetch_uniprot_sequence(gene_symbol: str) -> str | None:
    """
    Fetch the canonical human protein sequence for a gene symbol from UniProt.
    Uses UniProt REST API — requires internet access.
    """
    import urllib.request

    # Map gene symbol to UniProt reviewed human entry
    url = (
        f"https://rest.uniprot.org/uniprotkb/search"
        f"?query=gene:{gene_symbol}+AND+organism_id:9606+AND+reviewed:true"
        f"&fields=sequence&format=json&size=1"
    )
    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            data = json.loads(response.read())
            results = data.get("results", [])
            if results:
                return results[0]["sequence"]["value"]
    except Exception as e:
        print(f"  [warn] Could not fetch sequence for {gene_symbol}: {e}")
    return None


def compute_gene_embeddings(gene_symbols: list[str], device: str = "cuda") -> dict:
    """
    For each gene symbol:
      1. Fetch protein sequence from UniProt
      2. Run through ESM-2
      3. Mean-pool across residue dimension → 1280-dim vector

    Returns dict: gene_symbol → numpy array [1280]
    """
    import torch
    import esm

    print("Loading ESM-2 model (facebook/esm2_t33_650M_UR50D)...")
    model, alphabet = esm.pretrained.esm2_t33_650M_UR50D()
    model = model.to(device)
    model.eval()
    batch_converter = alphabet.get_batch_converter()

    gene_embeddings = {}

    for gene in gene_symbols:
        print(f"  Embedding gene: {gene}")
        sequence = fetch_uniprot_sequence(gene)

        if sequence is None:
            print(f"  [skip] No sequence found for {gene}")
            continue

        # ESM-2 has a max token limit — truncate very long sequences
        sequence = sequence[:1022]

        data         = [(gene, sequence)]
        _, _, tokens = batch_converter(data)
        tokens       = tokens.to(device)

        with torch.no_grad():
            results = model(tokens, repr_layers=[33], return_contacts=False)

        # Mean-pool across residue positions (exclude BOS/EOS tokens)
        token_reps = results["representations"][33]   # [1, seq_len, 1280]
        mean_rep   = token_reps[0, 1:-1].mean(dim=0)  # [1280]

        gene_embeddings[gene] = mean_rep.cpu().numpy()

    print(f"Gene embeddings computed: {len(gene_embeddings)}/{len(gene_symbols)}")
    return gene_embeddings


# ── Drug embedding via Morgan Fingerprints ────────────────────────────────────

def compute_drug_embeddings(drug_smiles_path: str) -> dict:
    """
    For each drug in drug_smiles.csv:
      1. Parse SMILES string with RDKit
      2. Compute Morgan Fingerprint (radius=2, 1024 bits)

    Returns dict: drug_name → numpy array [1024]
    """
    from rdkit import Chem
    from rdkit.Chem import AllChem

    df = pd.read_csv(drug_smiles_path)
    drug_embeddings = {}
    failed = 0

    for _, row in df.iterrows():
        drug_name = str(row["drug_name"]).strip().lower()
        smiles    = str(row["smiles"]).strip()

        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            print(f"  [warn] Invalid SMILES for {drug_name}: {smiles}")
            failed += 1
            continue

        fp = AllChem.GetMorganFingerprintAsBitVect(mol, radius=2, nBits=1024)
        drug_embeddings[drug_name] = np.array(fp, dtype=np.float32)

    print(f"Drug embeddings computed: {len(drug_embeddings)} | Failed: {failed}")
    return drug_embeddings


# ── Target flags via DrugBank ─────────────────────────────────────────────────

def compute_target_flags(drug_targets_path: str) -> dict:
    """
    Build binary lookup from drug_gene_targets.csv:
      target_flags[drug_name][gene_symbol] = 1 if relationship exists, else 0

    Returns nested dict: drug_name → gene_symbol → int (0 or 1)
    """
    df = pd.read_csv(drug_targets_path)

    target_flags = {}

    for _, row in df.iterrows():
        drug = str(row["drug_name"]).strip().lower()
        gene = str(row["gene_name"]).strip().upper()

        if drug not in target_flags:
            target_flags[drug] = {}
        target_flags[drug][gene] = 1

    print(f"Target flags built: {len(target_flags)} drugs with known gene targets")
    return target_flags


# ── Main ──────────────────────────────────────────────────────────────────────

def main(args):
    os.makedirs(args.output_dir, exist_ok=True)

    # Load labeled data to extract all unique gene symbols and drug names
    with open(args.labeled_data, "r") as f:
        labeled = json.load(f)

    gene_symbols = sorted(set(r["gene"].strip().upper() for r in labeled if r["risk_score"] != -1.0))
    drug_names   = sorted(set(r["medicine"].strip().lower() for r in labeled if r["risk_score"] != -1.0))

    print(f"Unique genes: {len(gene_symbols)}")
    print(f"Unique drugs: {len(drug_names)}")

    # ── 1. Gene embeddings ────────────────────────────────────────────────────
    print("\n── Computing gene embeddings (ESM-2) ──")
    gene_embeddings = compute_gene_embeddings(gene_symbols)
    gene_out = os.path.join(args.output_dir, "gene_embeddings.pkl")
    with open(gene_out, "wb") as f:
        pickle.dump(gene_embeddings, f)
    print(f"Saved: {gene_out}")

    # Verify
    for gene, vec in gene_embeddings.items():
        assert vec.shape == (1280,), f"Bad shape for {gene}: {vec.shape}"
        assert not np.isnan(vec).any(), f"NaN in embedding for {gene}"
    print("Gene embedding verification passed.")

    # ── 2. Drug embeddings ────────────────────────────────────────────────────
    print("\n── Computing drug embeddings (Morgan FP) ──")
    drug_embeddings = compute_drug_embeddings(args.drug_smiles)
    drug_out = os.path.join(args.output_dir, "drug_embeddings.pkl")
    with open(drug_out, "wb") as f:
        pickle.dump(drug_embeddings, f)
    print(f"Saved: {drug_out}")

    # Verify
    for drug, vec in drug_embeddings.items():
        assert vec.shape == (1024,), f"Bad shape for {drug}: {vec.shape}"
    print("Drug embedding verification passed.")

    # ── 3. Target flags ───────────────────────────────────────────────────────
    print("\n── Building target flags (DrugBank) ──")
    target_flags = compute_target_flags(args.drug_targets)
    flags_out = os.path.join(args.output_dir, "target_flags.pkl")
    with open(flags_out, "wb") as f:
        pickle.dump(target_flags, f)
    print(f"Saved: {flags_out}")

    print("\nAll embeddings pre-computed successfully.")
    print(f"Output directory: {args.output_dir}")


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Pre-compute frozen embeddings")
    parser.add_argument("--drug_smiles",  required=True, help="Path to drug_smiles.csv")
    parser.add_argument("--drug_targets", required=True, help="Path to drug_gene_targets.csv")
    parser.add_argument("--labeled_data", required=True, help="Path to labeled JSON file")
    parser.add_argument("--output_dir",   default="embeddings/", help="Where to save .pkl files")
    args = parser.parse_args()

    main(args)
