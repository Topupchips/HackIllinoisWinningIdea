"""
model.py

PharmaSetTransformer — Cross-Attention Set Transformer for pharmacogenomics risk prediction.

Architecture:
  1. Project frozen ESM-2 gene vectors (1280) + Morgan FP drug vectors (1024) → shared dim (128)
  2. Scale protein vectors by activity_level (how strongly is this protein functioning?)
  3. Add DrugBank target flag embedding to gene projections
  4. Protein self-attention  — proteins attend to each other (gene-gene interactions)
  5. Chemical-protein cross-attention — drug queries proteins (which proteins matter for this drug?)
  6. Prediction head → risk score 1-10

Input at inference:
  - gene_embeddings:  Tensor[n_genes, 1280]  (frozen ESM-2 vectors)
  - drug_embedding:   Tensor[1, 1024]        (frozen Morgan FP vector)
  - activity_levels:  Tensor[n_genes]        (float: how active is each protein? 0.0-2.0)
  - target_flags:     Tensor[n_genes]        (binary: drug known to target this gene?)
  - gene_mask:        Tensor[n_genes]        (optional: mask for padding)

Output:
  - risk_score:      float in [1, 10]
  - attn_weights:    Tensor[n_genes]        (interpretability: which genes drove the score)
"""

import torch
import torch.nn as nn


class PharmaSetTransformer(nn.Module):
    def __init__(self,
                 gene_dim:   int = 128,
                 drug_dim:   int = 128,
                 n_heads:    int = 4,
                 dropout:    float = 0.2):
        """
        Args:
            gene_dim:  Projected dimension for gene (protein) vectors.
            drug_dim:  Projected dimension for drug (chemical) vectors.
                       Must equal gene_dim for cross-attention compatibility.
            n_heads:   Number of attention heads.
            dropout:   Dropout rate in attention layers.
        """
        super().__init__()

        assert gene_dim == drug_dim, "gene_dim and drug_dim must be equal for cross-attention."

        self.gene_dim = gene_dim

        # ── Projection layers (trained) ───────────────────────────────────────
        # Compress frozen high-dim embeddings into shared working dimension
        self.gene_proj  = nn.Linear(1280, gene_dim)   # ESM-2 1280 → 128
        self.drug_proj  = nn.Linear(1024, drug_dim)   # Morgan FP 1024 → 128

        # DrugBank binary target flag: 0 or 1 → learnable 128-dim vector
        # Adds "known interaction" signal directly into protein representation
        self.target_embed = nn.Embedding(2, gene_dim)

        # ── Protein self-attention (trained) ──────────────────────────────────
        # Proteins attend to each other — captures gene-gene interactions
        # e.g. "CYP2D6 is more dangerous when CYP2C19 is also impaired"
        self.gene_self_attn = nn.MultiheadAttention(
            embed_dim=gene_dim,
            num_heads=n_heads,
            dropout=dropout,
            batch_first=False   # expects (seq, batch, dim)
        )
        self.gene_norm = nn.LayerNorm(gene_dim)

        # ── Chemical-protein cross-attention (trained) ────────────────────────
        # Drug (chemical) acts as query, proteins are keys and values
        # Learns: "given this molecule's structure, which proteins are relevant?"
        self.cross_attn = nn.MultiheadAttention(
            embed_dim=gene_dim,
            num_heads=n_heads,
            dropout=dropout,
            batch_first=False
        )
        self.cross_norm = nn.LayerNorm(gene_dim)

        # ── Prediction head (trained) ─────────────────────────────────────────
        # Combines drug context vector + mean-pooled protein vectors → risk score
        self.head = nn.Sequential(
            nn.Linear(gene_dim * 2, 64),
            nn.GELU(),
            nn.Dropout(0.3),
            nn.Linear(64, 1),
            nn.Sigmoid()   # output in [0, 1], scaled to [1, 10] at the end
        )

        self._init_weights()

    def _init_weights(self):
        nn.init.xavier_uniform_(self.gene_proj.weight)
        nn.init.zeros_(self.gene_proj.bias)
        nn.init.xavier_uniform_(self.drug_proj.weight)
        nn.init.zeros_(self.drug_proj.bias)
        nn.init.xavier_uniform_(self.head[0].weight)
        nn.init.xavier_uniform_(self.head[3].weight)

    def forward(self,
                gene_embeddings:  torch.Tensor,
                drug_embedding:   torch.Tensor,
                activity_levels:  torch.Tensor,
                target_flags:     torch.Tensor,
                gene_mask:        torch.Tensor = None):
        """
        Args:
            gene_embeddings:  Tensor[n_genes, 1280]  — frozen ESM-2 protein vectors
            drug_embedding:   Tensor[1, 1024]        — frozen Morgan FP drug vector
            activity_levels:  Tensor[n_genes]        — protein activity (0.0=none, 1.0=normal, 2.0=ultrarapid)
            target_flags:     Tensor[n_genes]        — binary DrugBank flags (long)
            gene_mask:        Tensor[n_genes]        — True = ignore (padding mask)

        Returns:
            risk_score:   Tensor[1]         — predicted risk in [1, 10]
            attn_weights: Tensor[n_genes]   — cross-attention weights per gene
        """

        # ── 1. Project to shared dimension ────────────────────────────────────
        genes = self.gene_proj(gene_embeddings)           # [n_genes, 128]

        # Scale each protein vector by its activity level BEFORE attention.
        # This encodes how strongly each protein is functioning in this patient.
        # A CYP2D6 with activity=0.0 (poor metabolizer) contributes a zero vector —
        # effectively absent from the interaction. activity=2.0 (ultrarapid) amplifies it.
        genes = genes * activity_levels.unsqueeze(-1)     # [n_genes, 128]

        genes = genes + self.target_embed(target_flags)   # inject DrugBank prior
        drug  = self.drug_proj(drug_embedding)            # [1, 128]

        # Reshape for MultiheadAttention: expects (seq_len, batch=1, dim)
        genes = genes.unsqueeze(1)   # [n_genes, 1, 128]
        drug  = drug.unsqueeze(0)    # [1, 1, 128]

        # ── 2. Protein self-attention ─────────────────────────────────────────
        # Proteins query, key, value = themselves
        # Activity-scaled vectors mean impaired proteins have less influence
        # on their neighbors' representations
        genes_attended, _ = self.gene_self_attn(
            genes, genes, genes,
            key_padding_mask=gene_mask
        )
        genes_attended = self.gene_norm(genes + genes_attended)   # residual connection

        # ── 3. Chemical-protein cross-attention ───────────────────────────────
        # Drug is query, proteins are keys and values
        drug_context, attn_weights = self.cross_attn(
            drug,            # query:  [1, 1, 128]
            genes_attended,  # key:    [n_genes, 1, 128]
            genes_attended,  # value:  [n_genes, 1, 128]
            key_padding_mask=gene_mask
        )
        drug_context = self.cross_norm(drug + drug_context)   # residual connection

        # ── 4. Prediction head ────────────────────────────────────────────────
        # Mean-pool protein representations + drug context → concat → predict
        pooled_genes = genes_attended.mean(dim=0)              # [1, 128]
        combined     = torch.cat(
            [drug_context.squeeze(0), pooled_genes], dim=-1    # [1, 256]
        )

        risk_raw   = self.head(combined)                       # [1, 1] in [0, 1]
        risk_score = risk_raw * 9.0 + 1.0                     # scale to [1, 10]

        # attn_weights: [1, 1, n_genes] → [n_genes]
        attn_weights = attn_weights.squeeze(0).squeeze(0)

        return risk_score.squeeze(), attn_weights


# ── Parameter count utility ───────────────────────────────────────────────────

def count_parameters(model: nn.Module) -> int:
    return sum(p.numel() for p in model.parameters() if p.requires_grad)


if __name__ == "__main__":
    import torch
    model = PharmaSetTransformer(gene_dim=128, drug_dim=128, n_heads=4)
    print(f"Trainable parameters: {count_parameters(model):,}")

    # Simulate a patient with 3 genes, different activity levels
    n_genes  = 3
    gene_emb = torch.randn(n_genes, 1280)
    drug_emb = torch.randn(1, 1024)
    activity = torch.tensor([0.0, 1.0, 2.0], dtype=torch.float32)  # poor, normal, ultrarapid
    flags    = torch.tensor([1, 0, 1], dtype=torch.long)

    risk, attn = model(gene_emb, drug_emb, activity, flags)
    print(f"Risk score: {risk.item():.2f}")
    print(f"Attention weights: {attn.detach().numpy()}")
    print(f"Attention sums to: {attn.sum().item():.4f}")
