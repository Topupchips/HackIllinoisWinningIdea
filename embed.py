"""
embed.py

Pre-computes and saves all frozen embeddings:
  1. Gene embeddings  — ESM-2 on Modal GPU          → gene_embeddings.pkl
  2. Drug embeddings  — Morgan Fingerprints (local)  → drug_embeddings.pkl
  3. Target flags     — DrugBank binary (local)      → target_flags.pkl

Only the ESM-2 step runs on Modal (GPU-heavy).
Drug embeddings and target flags run locally — they're cheap.

Run ONCE before training.

Usage:
    # Redeem Modal credits first: modal.com/credits → code: VVN-YQS-E55
    pip install modal
    modal setup

    modal run embed.py \
        --drug-smiles    data/processed/drug_smiles.csv \
        --drug-targets   data/processed/drug_gene_targets.csv \
        --labeled-data   labeled_data.json \
        --output-dir     embeddings/
"""

import os
import json
import pickle
import numpy as np
import pandas as pd

# ── Modal setup ───────────────────────────────────────────────────────────────

import modal

app = modal.App("pharma-embed")

# Docker image with all dependencies needed on the Modal GPU machine
image = (
    modal.Image.debian_slim()
    .pip_install(
        "torch",
        "fair-esm",
        "numpy",
        "requests",
    )
)


# ── Gene embedding via ESM-2 (runs on Modal GPU) ──────────────────────────────

@app.function(
    image=image,
    gpu="A10G",       # Modal GPU — fast enough for ESM-2 650M
    timeout=1800,     # 30 min max, well enough for ~20 genes
)
def compute_gene_embeddings_remote(gene_symbols: list) -> dict:
    """
    Runs on Modal GPU. For each gene symbol:
      1. Fetch protein sequence from UniProt
      2. Run through ESM-2 (facebook/esm2_t33_650M_UR50D)
      3. Mean-pool across residues → 1280-dim vector

    Returns dict: gene_symbol → list[float] (converted back to numpy locally)
    """
    import json as _json
    import urllib.request
    import torch
    import esm

    def fetch_uniprot_sequence(gene_symbol):
        url = (
            f"https://rest.uniprot.org/uniprotkb/search"
            f"?query=gene:{gene_symbol}+AND+organism_id:9606+AND+reviewed:true"
            f"&fields=sequence&format=json&size=1"
        )
        try:
            with urllib.request.urlopen(url, timeout=10) as response:
                data    = _json.loads(response.read())
                results = data.get("results", [])
                if results:
                    return results[0]["sequence"]["value"]
        except Exception as e:
            print(f"  [warn] Could not fetch sequence for {gene_symbol}: {e}")
        return None

    device = "cuda"
    print("Loading ESM-2 model...")
    model, alphabet = esm.pretrained.esm2_t33_650M_UR50D()
    model = model.to(device)
    model.eval()
    batch_converter = alphabet.get_batch_converter()

    gene_embeddings = {}

    for gene in gene_symbols:
        print(f"  Embedding: {gene}")
        sequence = fetch_uniprot_sequence(gene)

        if sequence is None:
            print(f"  [skip] No sequence for {gene}")
            continue

        sequence     = sequence[:1022]   # ESM-2 token limit
        data         = [(gene, sequence)]
        _, _, tokens = batch_converter(data)
        tokens       = tokens.to(device)

        with torch.no_grad():
            results = model(tokens, repr_layers=[33], return_contacts=False)

        token_reps = results["representations"][33]   # [1, seq_len, 1280]
        mean_rep   = token_reps[0, 1:-1].mean(dim=0)  # [1280]

        # Convert to list for Modal serialization
        gene_embeddings[gene] = mean_rep.cpu().numpy().tolist()

    print(f"Done. {len(gene_embeddings)}/{len(gene_symbols)} genes embedded.")
    return gene_embeddings


# ── Drug embedding via Morgan Fingerprints (runs locally) ────────────────────

def compute_drug_embeddings(drug_smiles_path: str) -> dict:
    """
    Runs locally — RDKit is cheap, no GPU needed.
    Returns dict: drug_name → numpy array [1024]
    """
    from rdkit import Chem
    from rdkit.Chem import AllChem

    df     = pd.read_csv(drug_smiles_path)
    result = {}
    failed = 0

    for _, row in df.iterrows():
        drug_name = str(row["drug_name"]).strip().lower()
        smiles    = str(row["smiles"]).strip()

        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            print(f"  [warn] Invalid SMILES for {drug_name}")
            failed += 1
            continue

        fp = AllChem.GetMorganFingerprintAsBitVect(mol, radius=2, nBits=1024)
        result[drug_name] = np.array(fp, dtype=np.float32)

    print(f"Drug embeddings: {len(result)} computed | {failed} failed")
    return result


# ── Target flags via DrugBank (runs locally) ──────────────────────────────────

def compute_target_flags(drug_targets_path: str) -> dict:
    """
    Runs locally — just CSV parsing.
    Returns nested dict: drug_name → gene_symbol → 1
    """
    df           = pd.read_csv(drug_targets_path)
    target_flags = {}

    for _, row in df.iterrows():
        drug = str(row["drug_name"]).strip().lower()
        gene = str(row["gene_name"]).strip().upper()

        if drug not in target_flags:
            target_flags[drug] = {}
        target_flags[drug][gene] = 1

    print(f"Target flags: {len(target_flags)} drugs with known gene targets")
    return target_flags


# ── Main ──────────────────────────────────────────────────────────────────────

@app.local_entrypoint()
def main(
    drug_smiles:  str = "data/processed/drug_smiles.csv",
    drug_targets: str = "data/processed/drug_gene_targets.csv",
    labeled_data: str = "labeled_data.json",
    output_dir:   str = "embeddings/",
):
    os.makedirs(output_dir, exist_ok=True)

    # Extract unique gene symbols from labeled data
    with open(labeled_data, "r") as f:
        labeled = json.load(f)

    gene_symbols = sorted(set(
        r["gene"].strip().upper()
        for r in labeled if r["risk_score"] != -1.0
    ))
    print(f"Unique genes to embed: {len(gene_symbols)}")

    # ── 1. Gene embeddings — Modal GPU ────────────────────────────────────────
    print("\n── Computing gene embeddings on Modal GPU (ESM-2) ──")
    raw = compute_gene_embeddings_remote.remote(gene_symbols)

    # Convert lists back to numpy arrays
    gene_embeddings = {
        gene: np.array(vec, dtype=np.float32)
        for gene, vec in raw.items()
    }

    # Verify
    for gene, vec in gene_embeddings.items():
        assert vec.shape == (1280,), f"Bad shape for {gene}: {vec.shape}"
        assert not np.isnan(vec).any(), f"NaN in embedding for {gene}"
    print("Gene embedding verification passed.")

    gene_out = os.path.join(output_dir, "gene_embeddings.pkl")
    with open(gene_out, "wb") as f:
        pickle.dump(gene_embeddings, f)
    print(f"Saved: {gene_out}")

    # ── 2. Drug embeddings — local ────────────────────────────────────────────
    print("\n── Computing drug embeddings locally (Morgan FP) ──")
    drug_embeddings = compute_drug_embeddings(drug_smiles)

    for drug, vec in drug_embeddings.items():
        assert vec.shape == (1024,), f"Bad shape for {drug}: {vec.shape}"
    print("Drug embedding verification passed.")

    drug_out = os.path.join(output_dir, "drug_embeddings.pkl")
    with open(drug_out, "wb") as f:
        pickle.dump(drug_embeddings, f)
    print(f"Saved: {drug_out}")

    # ── 3. Target flags — local ───────────────────────────────────────────────
    print("\n── Building target flags locally (DrugBank) ──")
    target_flags = compute_target_flags(drug_targets)

    flags_out = os.path.join(output_dir, "target_flags.pkl")
    with open(flags_out, "wb") as f:
        pickle.dump(target_flags, f)
    print(f"Saved: {flags_out}")

    print("\nAll embeddings pre-computed successfully.")
    print(f"Output directory: {output_dir}")
