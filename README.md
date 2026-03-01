# Pharmagen

Pharmacogenomics drug risk prediction API. Gene profile + drug → personalized risk score + clinical recommendation. Also supports drug–drug interaction prediction via PubChem.

**HackIllinois** — Best Web API track

---

## Quick Start (Your Workflow)

### 1. Install dependencies

```bash
# Frontend
npm install

# Backend (Python 3.10+)
pip install -r backend/requirements.txt
pip install -r requirements.txt
```

### 2. Run the API locally

```bash
python backend/run_local.py
```

API runs at **http://127.0.0.1:8000**  
Docs: **http://127.0.0.1:8000/docs**

### 3. Run the frontend

```bash
npm run dev
```

App uses `VITE_API_URL` from `.env` (default: `http://127.0.0.1:8000`).

---

## Two Modes

| Mode | When | Endpoints |
|------|------|-----------|
| **PharmaRisk (full)** | `data/processed/drugs.csv` exists | `/v1/health`, `/v1/drugs`, `/v1/genes`, `/v1/predict`, `/v1/predict/natural`, `/v1/explain` — CPIC data + ML model |
| **PubChem fallback** | No data or model | Same `/v1/*` endpoints — PubChem lookup, Tanimoto similarity, OpenAI explain |

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/v1/health` | Health check |
| GET | `/v1/validate` | Validate data |
| GET | `/v1/drugs` | List drugs (searchable) |
| GET | `/v1/drugs/{id}` | Get drug by name or CID |
| GET | `/v1/genes` | List genes |
| GET | `/v1/genes/{symbol}` | Gene details |
| GET | `/v1/genes/{symbol}/alleles` | Gene alleles |
| POST | `/v1/predict` | Predict risk (genes + drug) |
| POST | `/v1/predict/natural` | Predict from natural language |
| POST | `/v1/explain` | AI explanation |
| POST | `/v1/interactions/predict` | Drug–drug interaction (frontend) |

---

## Project Structure

```
├── api/                 # PharmaRisk API (dev branch)
│   ├── routes/          # health, drugs, genes, predict, explain
│   ├── services/        # data_service, model_service
│   └── models/
├── backend/             # Entry point + docs
│   ├── run_local.py     # Main: python backend/run_local.py
│   ├── static/docs/     # Docs pages
│   └── requirements.txt
├── data/processed/      # CPIC, drugs, genes (from dev)
├── embeddings/          # Gene/drug embeddings
├── src/                 # React frontend
├── docs/                # API.md, etc.
└── requirements.txt     # Root deps (PyTorch, etc.)
```

---

## Deploy

- **Modal:** `modal deploy backend/modal_app.py`
- **Frontend:** `npm run build && npx wrangler pages deploy dist --project-name pharmagen`

---

## Configuration

| Variable | Purpose |
|----------|---------|
| `API_KEY` | Require X-API-Key (optional) |
| `OPENAI_API_KEY` | Natural language + explain |
| `VITE_API_URL` | Frontend API URL |
