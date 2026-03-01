<h1 align="center">GeneAI</h1>

<p align="center">
  <strong>Pharmacogenomics Drug Risk Analysis</strong><br>
  Gene profile + drug &rarr; personalized risk score + CPIC clinical recommendation
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.11+-blue?logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white" alt="FastAPI">
  <img src="https://img.shields.io/badge/PyTorch-2.0+-ee4c2c?logo=pytorch&logoColor=white" alt="PyTorch">
  <img src="https://img.shields.io/badge/HackIllinois-2026-orange" alt="HackIllinois 2026">
</p>

<p align="center">
  <strong>Link:</strong> <a href="http://geneai.tech/">http://geneai.tech/</a>
</p>

---

## Problem

**1.3 million emergency room admissions per year** in the U.S. are caused by adverse drug reactions. Most drugs are prescribed based on symptoms alone — not genetics. Patients with certain gene variants metabolize drugs too quickly, too slowly, or not at all, leading to toxicity or treatment failure.

CPIC pharmacogenomic guidelines exist, but they're buried in academic tables clinicians don't have time to look up mid-appointment.

## Solution

GeneAI is an API + UI that takes a patient's **gene profile** and a **drug name**, and returns:

- **Per-gene activity scores** from a trained Set Transformer model
- **CPIC clinical recommendation text** (e.g., "Avoid codeine use" or "Use standard dosing")
- **Plain-English explanation** suitable for patients
- Supports both structured JSON and **natural language input**

## Architecture

Two prediction paths:

1. **Natural Language** — User query → OpenAI parses to structured JSON → model pipeline
2. **Structured** — Direct JSON `{"genes": [...], "drug": "..."}` → model pipeline

Model pipeline:
- **Gene embeddings** via ESM-2 protein language model
- **Drug embeddings** via Morgan fingerprints from SMILES
- **Target flags** from DrugBank drug-gene interactions
- **Cross-Attention Set Transformer** fuses multi-gene + drug features → per-gene risk scores

Post-prediction, CPIC recommendation text is looked up and optionally enriched by GPT-4o-mini.

## Tech Stack

| Component | Technology |
|-----------|-----------|
| API | FastAPI + Uvicorn |
| Model | PyTorch (Set Transformer) |
| Gene Embeddings | ESM-2 (Meta protein language model) |
| Drug Embeddings | RDKit Morgan fingerprints from SMILES |
| NLP | OpenAI gpt-4o-mini |
| Data | CPIC database, DrugBank, PubChem |
| Frontend | React + Three.js (3D DNA helix) |

## Project Structure

```
├── api/                 # FastAPI backend
│   ├── routes/          # health, drugs, genes, predict, explain
│   ├── services/        # data_service, model_service, openai_service
│   ├── models/          # request/response schemas
│   └── static/          # docs + demo HTML pages
├── model/               # Set Transformer model
│   ├── model_api.py     # PharmaRiskModel interface
│   ├── model.py         # PharmaSetTransformer architecture
│   ├── set_transformer.pt
│   └── embeddings/      # gene_embeddings.pkl, drug_embeddings.pkl, target_flags.pkl
├── pipeline/            # Data pipeline + processed CPIC data
├── frontend/            # React + Three.js UI (GeneAI app)
└── requirements.txt     # Python dependencies
```

## Live

> **[geneai.tech](https://geneai.tech)** — UI live
> **[geneai.tech/docs](https://geneai.tech/docs)** — Documentation
> **[geneai.tech/demo](https://geneai.tech/demo)** — Interactive demo

## Quickstart

```bash
# Clone
git clone https://github.com/Topupchips/HackIllinoisWinningIdea.git
cd HackIllinoisWinningIdea

# Install Python dependencies
pip install -r requirements.txt

# (Optional) Set OpenAI key for natural language + explain
export OPENAI_API_KEY=sk-...

# Run API
python -m uvicorn api.main:app --reload --port 8000

# Run frontend (separate terminal)
cd frontend && npm install && npm start
```

- **http://localhost:3000** — GeneAI React app
- **http://localhost:8000/docs** — Documentation
- **http://localhost:8000/docs/api** — Interactive API explorer
- **http://localhost:8000/demo** — Live endpoint demo

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Health check — model/data status |
| `GET` | `/validate` | Validate loaded data, list available genes |
| `GET` | `/drugs` | List all drugs (paginated, searchable) |
| `GET` | `/drugs/{drug_id}` | Get drug details + SMILES |
| `GET` | `/genes` | List all genes (paginated, searchable) |
| `GET` | `/genes/{symbol}` | Gene details + recommendation count |
| `GET` | `/genes/{symbol}/alleles` | All alleles for a gene |
| `POST` | `/predict` | Predict risk from structured gene/drug input |
| `POST` | `/predict/natural` | Predict risk from natural language |
| `POST` | `/explain` | Generate plain-English explanation |

All list endpoints support `?search=`, `?page=`, `?limit=` and return fuzzy "did you mean" suggestions on no results.

## Curl Examples

**Health check:**
```bash
curl http://localhost:8000/health
```
```json
{"status": "healthy", "model_loaded": true, "data_loaded": true, "drug_count": 323, "gene_count": 17}
```

**Predict risk (structured):**
```bash
curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{"genes": [{"name": "CYP2D6", "phenotype": "Poor Metabolizer"}], "drug": "codeine"}'
```
```json
[
  {
    "gene": "CYP2D6",
    "activity_level": 0.0,
    "medicine": "codeine",
    "text": "Avoid codeine use because of possibility of diminished analgesia."
  }
]
```

**Predict risk (natural language):**
```bash
curl -X POST http://localhost:8000/predict/natural \
  -H "Content-Type: application/json" \
  -d '{"query": "I am a CYP2D6 poor metabolizer taking codeine"}'
```

**Explain risk:**
```bash
curl -X POST http://localhost:8000/explain \
  -H "Content-Type: application/json" \
  -d '{"drug": "codeine", "risk_score": 8.5, "gene_contributions": {"CYP2D6": 0.85}}'
```

## Data Sources

| Source | License | Description |
|--------|---------|-------------|
| [CPIC](https://cpicpgx.org/) | CC0 (public domain) | Clinical pharmacogenomics guidelines (Stanford/NIH) |
| [PharmGKB](https://www.pharmgkb.org/) | CC BY-SA 4.0 | Pharmacogenomics knowledge base |
| [PubChem](https://pubchem.ncbi.nlm.nih.gov/) | Public domain | Drug SMILES / molecular structures |
| [DrugBank](https://go.drugbank.com/) | CC BY-NC 4.0 | Drug-gene target interactions |
| [ESM-2](https://github.com/facebookresearch/esm) | MIT | Protein language model for gene embeddings |

## AI Disclosure

*Required by HackIllinois rules.*

| Tool | Usage |
|------|-------|
| **OpenAI gpt-4o-mini** | Runtime: parses natural language input, generates patient-facing explanations |
| **ESM-2 (Meta)** | Gene sequence embeddings used as model features |
| **Claude Code (Anthropic)** | Development: code scaffolding, data pipeline scripts, API boilerplate |

**What we built ourselves:**
- Data extraction and cleaning pipeline (CPIC SQL, DrugBank XML, PubChem API)
- Risk score engineering and labeling logic
- Model architecture design (Cross-Attention Set Transformer)
- Training pipeline and feature engineering
- API design, endpoint logic, and service layer
- React + Three.js frontend

## Team

- [Sanjavan Ghodasara](https://www.linkedin.com/in/sanjavan-ghodasara-854138235/)
- [Suhaan Khan](https://www.linkedin.com/in/suhaankhan/)

## License

MIT

---

<p align="center">
  Built for <a href="https://hackillinois.org">HackIllinois 2026</a>
</p>
