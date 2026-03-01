# Getting Started with Pharmacogen

A step-by-step guide to running the Pharmacogen API and frontend, and integrating with your application.

---

## What is Pharmacogen?

Pharmacogen is a **drug–drug interaction prediction API** that helps developers:

- **Search** and **look up** drugs by name (powered by PubChem)
- **Predict** interaction risk for novel drug combinations using structural similarity (SMILES)
- **Visualize** risk over time with 72-hour timeline data
- **Explain** interactions with AI-generated mechanistic insights (optional OpenAI)

Built for **HackIllinois Best Web API** track, with production-ready features: versioning, auth, rate limiting, and comprehensive documentation.

---

## Prerequisites

- **Node.js** 18+ (for frontend)
- **Python** 3.10+ (for API)
- **Git**

---

## 1. Clone and Install

```bash
git clone https://github.com/Topupchips/HackIllinoisWinningIdea.git
cd HackIllinoisWinningIdea
```

### Backend dependencies

```bash
pip install -r backend/requirements.txt
```

### Frontend dependencies

```bash
npm install
```

---

## 2. Run Locally

### Start the API

```bash
python backend/run_local.py
```

The API runs at **http://127.0.0.1:8000**.

### Start the frontend

In a new terminal:

```bash
npm run dev
```

The app runs at **http://localhost:5173** (or the port Vite assigns).

### Configure API URL (optional)

Create `.env` from `.env.example`:

```bash
cp .env.example .env
```

Edit `.env` and set:

```
VITE_API_URL=http://127.0.0.1:8000
```

This tells the frontend where to find the API. The default is `http://127.0.0.1:8000` when running locally.

---

## 3. Explore the API

### Interactive documentation

| Resource | URL |
|----------|-----|
| **Docs** | http://127.0.0.1:8000/docs |
| **ReDoc** | http://127.0.0.1:8000/redoc |
| **Demo page** | http://127.0.0.1:8000/demo |

The demo page lets you try each endpoint with a single click.

### Quick test

```bash
# Health check
curl http://127.0.0.1:8000/v1/health

# Search drugs
curl "http://127.0.0.1:8000/v1/drugs/search?q=aspirin"

# Predict interaction (Aspirin + Ibuprofen)
curl -X POST http://127.0.0.1:8000/v1/interactions/predict \
  -H "Content-Type: application/json" \
  -d '{"compounds":["Aspirin","Ibuprofen"],"smiles_list":["CC(=O)OC1=CC=CC=C1C(=O)O","CC(C)Cc1ccc(cc1)C(C)C(O)=O"],"has_vaccine":false}'
```

---

## 4. Optional: AI Features

For **AI explanation** and **Q&A** endpoints, set your OpenAI API key:

```bash
export OPENAI_API_KEY=sk-your-key-here
python backend/run_local.py
```

Without it, the explain endpoint returns a fallback (non-AI) explanation.

---

## 5. Optional: API Key & Rate Limiting

### Require API key

```bash
export API_KEY=your-secret-key
python backend/run_local.py
```

Then include the header in requests:

```bash
curl -H "X-API-Key: your-secret-key" "http://127.0.0.1:8000/v1/drugs/search?q=aspirin"
```

### Adjust rate limits

```bash
export RATE_LIMIT_REQUESTS=200
export RATE_LIMIT_WINDOW_SEC=60
python backend/run_local.py
```

---

## 6. Deploy

### API (Modal)

```bash
pip install modal
modal token new   # one-time auth
modal deploy backend/modal_app.py
modal secret create openai-api-key OPENAI_API_KEY=sk-...
```

Set `VITE_API_URL` to your Modal URL (e.g. `https://your-workspace--pharmacogen-api.modal.run`).

### Frontend (Cloudflare Pages)

```bash
npm run build
npx wrangler pages deploy dist --project-name pharmacogen
```

Or connect the repo in [Cloudflare Pages](https://dash.cloudflare.com/pages) and deploy on push to `main`.

---

## 7. Integrate in Your App

### JavaScript / TypeScript

```javascript
const BASE = 'http://127.0.0.1:8000';

// Search drugs
const search = await fetch(`${BASE}/v1/drugs/search?q=aspirin`);
const { results } = await search.json();

// Get compound
const compound = await fetch(`${BASE}/v1/drugs/name/Aspirin`);
const { smiles, formula, cid } = await compound.json();

// Predict interaction
const predict = await fetch(`${BASE}/v1/interactions/predict`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    compounds: ['Aspirin', 'Ibuprofen'],
    smiles_list: ['CC(=O)OC1=CC=CC=C1C(=O)O', 'CC(C)Cc1ccc(cc1)C(C)C(O)=O'],
    has_vaccine: false
  })
});
const { tanimoto_avg, confidence, pairs } = await predict.json();
```

### Python

```python
import httpx

BASE = "http://127.0.0.1:8000"

# Search drugs
r = httpx.get(f"{BASE}/v1/drugs/search", params={"q": "aspirin"})
results = r.json()["results"]

# Predict interaction
r = httpx.post(
    f"{BASE}/v1/interactions/predict",
    json={
        "compounds": ["Aspirin", "Ibuprofen"],
        "smiles_list": [
            "CC(=O)OC1=CC=CC=C1C(=O)O",
            "CC(C)Cc1ccc(cc1)C(C)C(O)=O"
        ],
        "has_vaccine": False
    }
)
data = r.json()
print(f"Tanimoto: {data['tanimoto_avg']}, Confidence: {data['confidence']}%")
```

---

## Next Steps

- **[API Reference](API.md)** — Full endpoint documentation, schemas, and examples
- **[Data & Model Spec](DATA_AND_MODEL_SPEC.md)** — Data sources, ML models, and roadmap
- **[README](../README.md)** — Project overview and configuration

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| **Port 8000 in use** | Stop the process using port 8000, or change the port in `run_local.py` |
| **PubChem 502** | PubChem may be temporarily down; retry later |
| **Compound not found** | Try alternate spellings or use the search endpoint first |
| **OpenAI errors** | Check `OPENAI_API_KEY`; explain/ask fall back gracefully if unset |
| **CORS errors** | Set `CORS_ORIGINS` to your frontend origin (comma-separated) |
