# Pharmacogen

Drug-drug interaction prediction and pharmacogenomics API. Predict interaction risk for novel combinations with little or no clinical data using chemical structure (SMILES) and AI.

**HackIllinois** — Best Web API track

---

## API Template Features

- **Documentation** — Docs (`/docs`), ReDoc (`/redoc`), interactive demo (`/demo`)
- **Error handling** — Standard `{error: {code, message}, request_id}` format
- **Security** — Optional API key auth (`X-API-Key`), configurable rate limiting
- **Extensibility** — Config via env vars (`backend/config.py`)
- **Naming** — RESTful `/v1/{resource}/{action}` convention

---

## Quick Start

### 1. Install dependencies

```bash
# Frontend
npm install

# Backend (Python 3.10+)
pip install -r backend/requirements.txt
```

### 2. Run the API locally

```bash
python backend/run_local.py
```

API runs at **http://127.0.0.1:8000**  
Interactive docs: **http://127.0.0.1:8000/docs**

### 3. Run the frontend

```bash
npm run dev
```

The app uses `VITE_API_URL` from `.env` (default: `http://127.0.0.1:8000`).

---

## Web API

RESTful API with versioned endpoints under `/v1/`.

| Category | Endpoints |
|----------|-----------|
| **Health** | `GET /v1/health`, `GET /` |
| **Drugs** | `GET /v1/drugs/search?q=`, `GET /v1/drugs/name/{name}`, `GET /v1/drugs/similar`, `GET /v1/drugs/structure/image` |
| **Interactions** | `POST /v1/interactions/predict`, `POST /v1/interactions/explain`, `POST /v1/interactions/ask` |

**Docs:** [API Reference](docs/API.md) | [Getting Started](docs/GETTING_STARTED.md) | [Data & Model Spec](docs/DATA_AND_MODEL_SPEC.md) | Docs at `/docs`

### Test an endpoint

```bash
curl http://127.0.0.1:8000/v1/health
curl "http://127.0.0.1:8000/v1/drugs/search?q=aspirin"
```

---

## Deploy

### Modal (API)

```bash
pip install modal
modal token new   # one-time auth
modal deploy backend/modal_app.py
modal secret create openai-api-key OPENAI_API_KEY=sk-...
```

Set `VITE_API_URL` to your Modal URL (e.g. `https://your-workspace--pharmacogen-api.modal.run`).

### Cloudflare Pages (Frontend)

```bash
npm run build
npx wrangler pages deploy dist --project-name pharmacogen
```

Or connect the repo in Cloudflare Pages and deploy on push to `main`.

---

## Project Structure

```
├── backend/
│   ├── config.py         # Env-based configuration
│   ├── auth.py           # Optional API key auth
│   ├── rate_limit.py     # Rate limiting
│   ├── modal_app.py      # Modal deployment (full API)
│   ├── run_local.py      # Local run (no Modal)
│   ├── static/           # Docs theme, demo page
│   └── requirements.txt
├── src/
│   ├── components/       # React UI
│   ├── services/         # API client, PubChem
│   └── utils/
├── docs/
│   └── API.md
└── .env                  # VITE_API_URL (create from .env.example)
```

---

## Configuration (Extensibility)

| Variable | Purpose |
|----------|---------|
| `API_KEY` | Require `X-API-Key` header (optional) |
| `RATE_LIMIT_REQUESTS` | Max requests per window (default: 100) |
| `RATE_LIMIT_WINDOW_SEC` | Window in seconds (default: 60) |
| `CORS_ORIGINS` | Allowed origins (default: `*`) |
| `OPENAI_API_KEY` | For AI explain/ask |

---

## Tech Stack

- **Frontend:** React, Vite, Recharts, Three.js
- **API:** FastAPI, Modal
- **Data:** PubChem, OpenAI (optional)
