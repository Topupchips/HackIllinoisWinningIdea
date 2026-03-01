# Data & Machine Learning Model Specification

## Overview

This document specifies data types, sources, and model approaches for building a production-quality drug interaction prediction system. It serves as both a technical specification for future ML integration and a reference for the current API implementation.

---

## Current API Implementation (as of v1.0)

The Pharmagen API implements a **hybrid approach**: deterministic logic today, with clear extension points for ML models.

| Spec Concept | Current Implementation | Endpoint |
|--------------|------------------------|----------|
| Drug lookup by name | PubChem REST (`/compound/name/{name}/JSON`) | `GET /v1/drugs/name/{name}` |
| Drug search | PubChem autocomplete | `GET /v1/drugs/search` |
| Batch compound lookup | Sequential PubChem calls | `POST /v1/drugs/batch` |
| Tanimoto similarity | N-gram approximation (3-char) on SMILES | `POST /v1/interactions/predict` |
| DDI prediction | Heuristic: Tanimoto + compound count + vaccine flag | `POST /v1/interactions/predict` |
| Timeline (72h risk/concentration) | Parametric model (compound count, vaccine, Tanimoto) | `GET /v1/interactions/timeline` |
| Similar drugs | Placeholder (demo list) | `GET /v1/drugs/similar` |
| AI explanation | OpenAI GPT-4o-mini or fallback | `POST /v1/interactions/explain` |
| Q&A | OpenAI with context | `POST /v1/interactions/ask` |

**Planned upgrades:** RDKit-based Morgan fingerprints for true Tanimoto; NCATS/HODDI for known-DDI lookup; Actian VectorAI for similar-drug search; trained DDINet/CYP models for confidence scoring.

---

## 1. Data Types Required

### 1.1 Drug-Drug Interaction (DDI)

| Field | Type | Description |
|-------|------|-------------|
| `drug_a_id` | string | PubChem CID or DrugBank ID |
| `drug_b_id` | string | PubChem CID or DrugBank ID |
| `drug_a_smiles` | string | SMILES notation |
| `drug_b_smiles` | string | SMILES notation |
| `interaction_type` | enum | metabolic_competition, enzyme_inhibition, enzyme_induction, etc. |
| `severity` | enum | major, moderate, minor |
| `evidence_level` | enum | known, predicted, novel |
| `clinical_evidence` | string | Description from literature |

### 1.2 Drug-Gene (Pharmacogenomics)

| Field | Type | Description |
|-------|------|-------------|
| `drug_id` | string | PubChem CID or DrugBank ID |
| `gene` | string | CYP2C19, CYP2D6, CYP3A4, etc. |
| `relationship` | enum | substrate, inhibitor, inducer |
| `phenotype_impact` | object | { poor: string, intermediate: string, extensive: string } |
| `dosing_guidance` | string | CPIC guideline text |

### 1.3 Molecular Features (for ML)

| Feature | Type | Source | Description |
|---------|------|--------|-------------|
| `smiles` | string | Input | Canonical SMILES |
| `morgan_fingerprint` | number[] | RDKit | 2048-bit Morgan fingerprint |
| `molecular_formula` | string | PubChem/RDKit | C9H8O4 |
| `pubchem_fingerprint` | number[] | PubChem | 881-bit structural fingerprint |
| `tanimoto_similarity` | number | Computed | Pairwise similarity (0-1) |

---

## 2. Data Sources (Free & Public)

### 2.1 Drug-Drug Interactions

| Source | URL | Format | Size | Notes |
|--------|-----|--------|------|-------|
| **NCATS Inxight FRDB** | https://drugs.ncats.io/downloads-public | TSV (zip) | ~4,500 drugs | `frdb-ddi.tsv` - drug–drug interactions, clinical evidence |
| **HODDI** | GitHub (arxiv 2502.06274) | CSV/JSON | 109K records | High-order (3+ drug) interactions from FAERS |
| **DDINet** | GitHub | CSV | Benchmark | Paired with model code |

### 2.2 Drug-Gene / CYP450

| Source | URL | Format | Notes |
|--------|-----|--------|-------|
| **Curated CYP450 Dataset** | https://figshare.com/articles/dataset/Comprehensively-Curated_Dataset_of_CYP450_Interactions_Enhancing_Predictive_Models_for_Drug_Metabolism/26630515 | CSV | ~2,000 compounds × 6 enzymes | SMILES + labels (1=substrate, 0=non-substrate) |
| **PharmGKB API** | https://api.pharmgkb.org | JSON | Drug-gene annotations, dosing guidelines |
| **CPIC API** | https://api.cpicpgx.org | JSON | Gene-drug guideline data |

### 2.3 Compound Metadata

| Source | URL | Use |
|--------|-----|-----|
| **PubChem** | https://pubchem.ncbi.nlm.nih.gov/rest/pug | SMILES, formula, structure images |
| **DrugBank** | go.drugbank.com (requires license for full) | DDI, targets |

---

## 3. Feature Representations for ML

### 3.1 Molecular Fingerprints

```
SMILES → RDKit → Morgan Fingerprint (radius=2, nBits=2048)
SMILES → RDKit → Morgan Fingerprint → Tanimoto(A, B)
```

**Tanimoto:** `intersection(A, B) / union(A, B)` — range 0–1

### 3.2 Input Features for DDI Model

- **Drug pair:** `[fingerprint_a, fingerprint_b]` or concatenated
- **Optional:** `tanimoto_similarity`, `molecular_formula_length`, `atom_count`

### 3.3 Input Features for Drug-Gene Model

- **Per enzyme:** Binary classification (substrate vs non-substrate)
- **Input:** `[fingerprint]` or `[graph_representation]`

---

## 4. Model Architectures (Literature)

### 4.1 DDINet (2025)

- **Architecture:** 5 fully connected layers
- **Input:** Morgan fingerprints from SMILES
- **Output:** Binary (interaction / no interaction)
- **Pros:** Lightweight, fast, good generalization
- **Code:** GitHub (search "DDINet drug interaction")

### 4.2 Graph Convolutional Networks (GCN)

- **Architecture:** GraphConvModel (DeepChem)
- **Input:** Molecular graph from SMILES (ConvMolFeaturizer)
- **Output:** Substrate classification per CYP
- **Pros:** Captures structural patterns; MCC 0.51–0.72 on CYP450
- **Dataset:** Curated CYP450 (Figshare)

### 4.3 Hybrid

- **Known pairs:** Lookup in DDI database
- **Novel pairs:** ML model (fingerprint-based or GCN)
- **Confidence:** High if in DB; lower if predicted

---

## 5. Implementation Roadmap

### Phase 1: Data Layer

1. Download NCATS `frdb-ddi.tsv` and parse into `DDIRecord[]`
2. Download Curated CYP450 CSVs from Figshare
3. Create `src/data/` with typed loaders

### Phase 2: Deterministic Logic

1. Replace `Math.random()` Tanimoto with real RDKit.js fingerprint + Tanimoto
2. Add known-DDI lookup from NCATS data
3. Add drug-gene lookup from CYP450 dataset

### Phase 3: ML Backend (Python)

1. Train DDINet-style model on NCATS/HODDI
2. Train CYP substrate classifier on Curated CYP450
3. Export to ONNX or TensorFlow.js for browser, or serve via API

### Phase 4: Integration

1. Frontend calls backend API for predictions
2. Or: Use RDKit.js in browser for fingerprints + Tanimoto; call API only for heavy ML

---

## 6. File Structure for Data

```
/data
  /ncats
    frdb-ddi.tsv
    frdb-drugs.tsv
  /cyp450
    CYP1A2_trainingset.csv
    CYP1A2_testingset.csv
    ... (CYP2C9, CYP2C19, CYP2D6, CYP2E1, CYP3A4)
  /models
    ddi_model.onnx
    cyp_substrate_model.onnx
```

---

## 7. API Endpoints (Proposed)

| Endpoint | Input | Output |
|----------|-------|--------|
| `POST /predict/ddi` | `{ drug_a_smiles, drug_b_smiles }` | `{ confidence, severity, known }` |
| `POST /predict/cyp` | `{ smiles, enzyme }` | `{ is_substrate, confidence }` |
| `GET /lookup/ddi` | `?cid_a=&cid_b=` | Known DDI record or 404 |

---

## 8. References

- NCATS Inxight: https://drugs.ncats.io/downloads-public
- Curated CYP450: https://figshare.com/articles/dataset/Comprehensively-Curated_Dataset_of_CYP450_Interactions_Enhancing_Predictive_Models_for_Drug_Metabolism/26630515
- PharmGKB API: https://api.pharmgkb.org
- CPIC API: https://api.cpicpgx.org
- RDKit.js: https://www.rdkitjs.com/
- PubChem REST: https://pubchem.ncbi.nlm.nih.gov/docs/pug-rest

---

## 9. Related Documentation

| Document | Description |
|----------|-------------|
| [API.md](API.md) | Full API reference: endpoints, schemas, examples, error codes |
| [GETTING_STARTED.md](GETTING_STARTED.md) | Setup, run locally, deploy, integrate in your app |
| [README](../README.md) | Project overview, quick start, configuration |
