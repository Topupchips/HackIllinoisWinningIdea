"""
train.py

Training loop for PharmaSetTransformer.

Note: Training runs on single (gene, drug) pairs — one gene per sample.
      Multi-gene patient aggregation with self/cross-attention happens at inference.
      During training, self-attention and cross-attention operate on a single gene,
      which still trains the projection layers, attention weights, and prediction head.

Usage:
    python train.py \
        --labeled_data   labeled_data.json \
        --gene_emb       embeddings/gene_embeddings.pkl \
        --drug_emb       embeddings/drug_embeddings.pkl \
        --target_flags   embeddings/target_flags.pkl \
        --epochs         100 \
        --save_path      set_transformer.pt
"""

import argparse
import numpy as np
import torch
import torch.nn as nn
from torch.optim import Adam
from torch.optim.lr_scheduler import ReduceLROnPlateau, LinearLR
from torch.utils.data import random_split, DataLoader
from scipy.stats import spearmanr

from dataset import PharmaDataset
from model import PharmaSetTransformer, count_parameters


# ── Training utilities ────────────────────────────────────────────────────────

def train_one_epoch(model, loader, optimizer, criterion, device):
    model.train()
    total_loss = 0.0
    total      = 0

    for gene_emb, activity, drug_emb, flag, risk_score in loader:
        gene_emb   = gene_emb.to(device)    # [batch, 1280]
        drug_emb   = drug_emb.to(device)    # [batch, 1024]
        flag       = flag.to(device)        # [batch]
        risk_score = risk_score.to(device)  # [batch, 1]

        optimizer.zero_grad()

        # Process each sample individually (variable n_genes at inference,
        # but single gene per training sample)
        batch_preds = []
        for i in range(gene_emb.shape[0]):
            g_emb = gene_emb[i].unsqueeze(0)   # [1, 1280]
            d_emb = drug_emb[i].unsqueeze(0)   # [1, 1024]
            f     = flag[i].unsqueeze(0)        # [1]

            act   = activity[i].squeeze()       # scalar → [1] after unsqueeze in model
            act   = act.unsqueeze(0)            # [1]
            risk, _ = model(g_emb, d_emb, act, f)
            batch_preds.append(risk.unsqueeze(0))

        preds = torch.cat(batch_preds).unsqueeze(1)   # [batch, 1]
        loss  = criterion(preds, risk_score)

        loss.backward()
        nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
        optimizer.step()

        total_loss += loss.item() * gene_emb.shape[0]
        total      += gene_emb.shape[0]

    return total_loss / total


@torch.no_grad()
def evaluate(model, loader, criterion, device):
    model.eval()
    total_loss = 0.0
    total      = 0
    all_preds  = []
    all_labels = []

    for gene_emb, activity, drug_emb, flag, risk_score in loader:
        gene_emb   = gene_emb.to(device)
        drug_emb   = drug_emb.to(device)
        flag       = flag.to(device)
        risk_score = risk_score.to(device)

        batch_preds = []
        for i in range(gene_emb.shape[0]):
            g_emb = gene_emb[i].unsqueeze(0)
            d_emb = drug_emb[i].unsqueeze(0)
            f     = flag[i].unsqueeze(0)

            act   = activity[i].squeeze().unsqueeze(0)   # [1]
            risk, _ = model(g_emb, d_emb, act, f)
            batch_preds.append(risk.unsqueeze(0))

        preds = torch.cat(batch_preds).unsqueeze(1)
        loss  = criterion(preds, risk_score)

        total_loss += loss.item() * gene_emb.shape[0]
        total      += gene_emb.shape[0]
        all_preds.extend(preds.cpu().squeeze().tolist())
        all_labels.extend(risk_score.cpu().squeeze().tolist())

    spearman, _ = spearmanr(all_preds, all_labels)

    return total_loss / total, spearman


# ── Main ──────────────────────────────────────────────────────────────────────

def train(args):
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Using device: {device}")

    # ── Data ──────────────────────────────────────────────────────────────────
    full_dataset = PharmaDataset(
        labeled_path      = args.labeled_data,
        gene_emb_path     = args.gene_emb,
        drug_emb_path     = args.drug_emb,
        target_flags_path = args.target_flags,
    )

    val_size   = int(len(full_dataset) * 0.2)
    train_size = len(full_dataset) - val_size
    train_dataset, val_dataset = random_split(
        full_dataset,
        [train_size, val_size],
        generator=torch.Generator().manual_seed(42)
    )

    train_loader = DataLoader(train_dataset, batch_size=args.batch_size, shuffle=True)
    val_loader   = DataLoader(val_dataset,   batch_size=args.batch_size, shuffle=False)

    print(f"Train: {train_size} | Val: {val_size}")

    # ── Model ─────────────────────────────────────────────────────────────────
    model = PharmaSetTransformer(
        gene_dim = args.gene_dim,
        drug_dim = args.gene_dim,   # must match gene_dim
        n_heads  = args.n_heads,
        dropout  = args.dropout,
    ).to(device)

    print(f"Trainable parameters: {count_parameters(model):,}")

    # ── Optimizer & loss ──────────────────────────────────────────────────────
    optimizer = Adam(model.parameters(), lr=args.lr, weight_decay=1e-4)
    criterion = nn.SmoothL1Loss()   # robust to outliers, good for regression

    # LR warmup: ramp from lr/10 to lr over first 5 epochs, then ReduceLROnPlateau
    warmup_epochs = 5
    warmup_scheduler  = LinearLR(optimizer, start_factor=0.1, end_factor=1.0, total_iters=warmup_epochs)
    plateau_scheduler = ReduceLROnPlateau(optimizer, patience=10, factor=0.5)

    # ── Training loop ─────────────────────────────────────────────────────────
    best_val_loss = float("inf")
    patience_counter = 0

    for epoch in range(1, args.epochs + 1):
        train_loss            = train_one_epoch(model, train_loader, optimizer, criterion, device)
        val_loss, spearman    = evaluate(model, val_loader, criterion, device)

        if epoch <= warmup_epochs:
            warmup_scheduler.step()
        else:
            plateau_scheduler.step(val_loss)

        current_lr = optimizer.param_groups[0]["lr"]
        print(f"Epoch {epoch:3d}/{args.epochs} | "
              f"Train Loss: {train_loss:.4f} | "
              f"Val Loss: {val_loss:.4f} | "
              f"Spearman: {spearman:.3f} | "
              f"LR: {current_lr:.2e}")

        if val_loss < best_val_loss:
            best_val_loss    = val_loss
            patience_counter = 0
            torch.save({
                "epoch":       epoch,
                "model_state": model.state_dict(),
                "val_loss":    best_val_loss,
                "spearman":    spearman,
                "args":        vars(args),
            }, args.save_path)
            print(f"  --> Saved best model (val_loss={best_val_loss:.4f}, spearman={spearman:.3f})")
        else:
            patience_counter += 1
            if patience_counter >= args.patience:
                print(f"Early stopping at epoch {epoch} (no improvement for {args.patience} epochs)")
                break

    print(f"\nTraining complete. Best val loss: {best_val_loss:.4f}")
    print(f"Model saved to: {args.save_path}")

    # ── Final evaluation on best checkpoint ───────────────────────────────────
    print("\n" + "=" * 60)
    print("FINAL EVALUATION (best checkpoint)")
    print("=" * 60)

    best_ckpt = torch.load(args.save_path, map_location=device, weights_only=False)
    model.load_state_dict(best_ckpt["model_state"])
    model.eval()

    all_preds  = []
    all_labels = []

    with torch.no_grad():
        for gene_emb, activity, drug_emb, flag, risk_score in val_loader:
            gene_emb   = gene_emb.to(device)
            drug_emb   = drug_emb.to(device)
            flag       = flag.to(device)
            risk_score = risk_score.to(device)

            for i in range(gene_emb.shape[0]):
                g_emb = gene_emb[i].unsqueeze(0)
                d_emb = drug_emb[i].unsqueeze(0)
                f     = flag[i].unsqueeze(0)
                act   = activity[i].squeeze().unsqueeze(0)
                risk, _ = model(g_emb, d_emb, act, f)
                all_preds.append(float(risk.cpu().item()))
                all_labels.append(float(risk_score[i].cpu().item()))

    preds_np  = np.array(all_preds)
    labels_np = np.array(all_labels)

    rmse_val        = float(np.sqrt(np.mean((preds_np - labels_np) ** 2)))
    spearman_val, _ = spearmanr(all_preds, all_labels)
    within_one      = float(np.mean(np.abs(preds_np - labels_np) <= 1.0))

    def _to_level(s):
        if s >= 7.0: return "HIGH"
        if s >= 4.0: return "MEDIUM"
        return "LOW"

    level_correct = sum(1 for p, l in zip(all_preds, all_labels) if _to_level(p) == _to_level(l))
    level_acc     = level_correct / len(all_preds)

    print(f"  Samples        : {len(all_preds)}")
    print(f"  RMSE           : {rmse_val:.4f}")
    print(f"  Spearman       : {spearman_val:.4f}")
    print(f"  +/-1 Accuracy  : {within_one*100:.1f}%")
    print(f"  Risk Level Acc : {level_acc*100:.1f}%")
    print("=" * 60)


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train PharmaSetTransformer")
    parser.add_argument("--labeled_data",  required=True)
    parser.add_argument("--gene_emb",      required=True)
    parser.add_argument("--drug_emb",      required=True)
    parser.add_argument("--target_flags",  required=True)
    parser.add_argument("--epochs",        type=int,   default=200)
    parser.add_argument("--patience",      type=int,   default=20)
    parser.add_argument("--batch_size",    type=int,   default=32)
    parser.add_argument("--gene_dim",      type=int,   default=128)
    parser.add_argument("--n_heads",       type=int,   default=4)
    parser.add_argument("--dropout",       type=float, default=0.2)
    parser.add_argument("--lr",            type=float, default=5e-4)
    parser.add_argument("--save_path",     default="set_transformer.pt")
    args = parser.parse_args()

    train(args)
