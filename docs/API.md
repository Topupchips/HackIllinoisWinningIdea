# Pharmacogen API Reference

Pharmacogenomics drug risk prediction API. Takes a patient's gene profile and a drug, returns a risk score with clinical recommendations from CPIC guidelines.

**Built for HackIllinois — Best Web API track**

---

## Table of Contents

- [Overview](#overview)
- [Base URL & Documentation](#base-url--documentation)
- [Quick Start](#quick-start)
- [Authentication](#authentication)
- [Rate Limiting](#rate-limiting)
- [Error Handling](#error-handling)
- [Endpoints](#endpoints)
  - [Health](#health)
  - [Drugs](#drugs)
  - [Genes](#genes)
  - [Predict](#predict)
  - [Explain](#explain)
  - [Interactions](#interactions)
- [Configuration](#configuration)
- [Workflows & Examples](#workflows--examples)
- [Best Practices](#best-practices)

---

## Overview

The Pharmacogen API enables developers to:

| Capability | Description |
|------------|-------------|
| **Health & Validate** | API status, dependency health, data validation |
| **Drugs** | List drugs, get by ID, search, batch lookup, similar drugs |
| **Genes** | List pharmacogenomics genes, get gene details, alleles |
| **Predict** | Risk prediction (SMILES or natural language) |
| **Explain** | AI mechanistic risk explanation (OpenAI, optional) |
| **Interactions** | Legacy endpoints: predict, explain, timeline, ask |

All endpoints are versioned under `/v1/` for stable, backward-compatible evolution.

---

## Base URL & Documentation

| Environment | Base URL |
|-------------|----------|
| **Local** | `http://127.0.0.1:8000` |
| **Modal** | `https://your-workspace--pharmacogen-api.modal.run` |

| Resource | URL |
|----------|-----|
| **Docs** | `/docs` |
| **ReDoc** | `/redoc` |
| **Interactive demo** | `/demo` |
| **OpenAPI JSON** | `/openapi.json` |

---

## Quick Start

```bash
# Health check
curl http://127.0.0.1:8000/v1/health

# Search drugs
curl "http://127.0.0.1:8000/v1/drugs/search?q=aspirin"

# Get compound details
curl "http://127.0.0.1:8000/v1/drugs/name/Aspirin"

# Predict (SMILES)
curl -X POST http://127.0.0.1:8000/v1/predict \
  -H "Content-Type: application/json" \
  -d '{"compounds":["Aspirin","Ibuprofen"],"smiles_list":["CC(=O)OC1=CC=CC=C1C(=O)O","CC(C)Cc1ccc(cc1)C(C)C(O)=O"],"has_vaccine":false}'

# Predict (natural language)
curl -X POST http://127.0.0.1:8000/v1/predict/natural \
  -H "Content-Type: application/json" \
  -d '{"query":"Aspirin and Ibuprofen risk"}'

# List genes
curl "http://127.0.0.1:8000/v1/genes"
```

---

## Authentication

Authentication is **optional**. When `API_KEY` is set in the environment, protected endpoints require the `X-API-Key` header:

```bash
curl -H "X-API-Key: your-secret-key" "http://127.0.0.1:8000/v1/drugs/search?q=aspirin"
```

**Exempt endpoints** (no API key required):

- `GET /` — API info
- `GET /docs`, `/redoc`, `/demo` — Documentation
- `GET /v1/health` — Health check
- `/static/*` — Static assets

---

## Rate Limiting

| Setting | Default | Description |
|---------|---------|-------------|
| **Limit** | 100 requests | Per client IP per window |
| **Window** | 60 seconds | Sliding window |

**Configurable via environment:**

- `RATE_LIMIT_REQUESTS` — Max requests per window
- `RATE_LIMIT_WINDOW_SEC` — Window duration in seconds

**Response when exceeded:** `429 Too Many Requests`

```json
{
  "error": {
    "code": "rate_limit_exceeded",
    "message": "Rate limit exceeded. Try again later."
  },
  "request_id": "uuid"
}
```

**Exempt paths:** `/`, `/docs`, `/redoc`, `/demo`, `/openapi.json`, `/static/*`

---

## Error Handling

All errors use a consistent structure:

```json
{
  "error": {
    "code": "not_found",
    "message": "Compound not found"
  },
  "request_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
}
```

| Code | HTTP | Description |
|------|------|-------------|
| `bad_request` | 400 | Invalid input or malformed request |
| `unauthorized` | 401 | Missing or invalid API key |
| `not_found` | 404 | Resource not found (e.g. compound) |
| `validation_error` | 422 | Request body validation failed |
| `rate_limit_exceeded` | 429 | Too many requests |
| `upstream_error` | 502 | External service (PubChem, OpenAI) unreachable |
| `service_unavailable` | 503 | Temporary outage |
| `internal_error` | 500 | Unexpected server error |

**Debugging:** Include `X-Request-ID` in your request; responses echo it for correlation.

---

## Endpoints

### Health

#### `GET /v1/health`

Returns API status and dependency health (PubChem, OpenAI).

**Response:**

```json
{
  "status": "ok",
  "api": "pharmacogen",
  "version": "1.0.0",
  "dependencies": {
    "pubchem": "ok",
    "openai": "configured"
  }
}
```

| Field | Values | Description |
|-------|--------|-------------|
| `pubchem` | `ok`, `unreachable` | PubChem REST API reachability |
| `openai` | `configured`, `not_configured` | Whether `OPENAI_API_KEY` is set |

---

#### `GET /v1/validate`

Validate API data sources (PubChem, config).

**Response:**

```json
{
  "valid": true,
  "message": "OK"
}
```

---

#### `GET /`

Root endpoint with links to documentation and health.

**Response:**

```json
{
  "message": "Pharmacogen API",
  "docs": "/docs",
  "demo": "/demo",
  "health": "/v1/health"
}
```

---

### Drugs

#### `GET /v1/drugs`

List drugs. With `q`, searches via PubChem autocomplete.

**Query parameters:** `q` (optional), `limit`, `offset`

**Response:** `{"drugs": [{"id": "...", "name": "..."}], "total": N}`

---

#### `GET /v1/drugs/{drug_id}`

Get drug by name or PubChem CID.

**Response:** `{"id": "...", "name": "...", "smiles": "...", "formula": "...", "cid": N}`

---

#### `GET /v1/drugs/search`

Search drugs by name using PubChem autocomplete.

**Query parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `q` | string | Yes | — | Search query (e.g. aspirin, ibuprofen) |
| `limit` | int | No | 10 | Max results (1–20) |
| `offset` | int | No | 0 | Skip first N results (pagination) |

**Example:**

```bash
curl "http://127.0.0.1:8000/v1/drugs/search?q=metformin&limit=5&offset=0"
```

**Response:**

```json
{
  "query": "metformin",
  "results": ["Metformin", "Metformin hydrochloride", "Metformin succinate"],
  "total": 10,
  "limit": 5,
  "offset": 0
}
```

---

#### `GET /v1/drugs/name/{name}`

Get compound details by name from PubChem. Returns SMILES, molecular formula, and PubChem CID.

**Path parameters:**

| Parameter | Description |
|-----------|-------------|
| `name` | Compound name (e.g. Aspirin, Ibuprofen) |

**Response headers:** `Cache-Control: public, max-age=3600` (1 hour cache)

**Response:**

```json
{
  "name": "Aspirin",
  "smiles": "CC(=O)OC1=CC=CC=C1C(=O)O",
  "formula": "C9H8O4",
  "cid": 2244
}
```

**404** when compound is not found in PubChem.

---

#### `POST /v1/drugs/batch`

Look up multiple compounds by name in a single request. Missing compounds are omitted from the response.

**Request body:**

```json
{
  "names": ["Aspirin", "Ibuprofen", "Metformin"]
}
```

| Field | Type | Constraints | Description |
|-------|------|--------------|-------------|
| `names` | string[] | 1–20 items | Compound names to look up |

**Response:**

```json
{
  "compounds": [
    {
      "name": "Aspirin",
      "smiles": "CC(=O)OC1=CC=CC=C1C(=O)O",
      "formula": "C9H8O4",
      "cid": 2244
    },
    {
      "name": "Ibuprofen",
      "smiles": "CC(C)Cc1ccc(cc1)C(C)C(O)=O",
      "formula": "C13H18O2",
      "cid": 3672
    }
  ],
  "requested": 3,
  "found": 2
}
```

---

#### `GET /v1/drugs/similar`

Find structurally similar drugs. Uses Tanimoto similarity (placeholder: returns demo list; Actian VectorAI integration planned).

**Query parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `smiles` | string | Yes | — | SMILES string of reference compound |
| `limit` | int | No | 5 | Max results (1–20) |
| `offset` | int | No | 0 | Pagination offset |

**Response:**

```json
{
  "smiles": "CC(=O)OC1=CC=CC=C1C(=O)O",
  "similar": [
    { "name": "Aspirin", "smiles": "" },
    { "name": "Ibuprofen", "smiles": "" }
  ],
  "total": 5,
  "limit": 5,
  "offset": 0,
  "source": "demo"
}
```

---

#### `GET /v1/drugs/structure/image`

Get PubChem URL for 2D structure image of a compound.

**Query parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `smiles` | string | Yes | — | SMILES string |
| `size` | int | No | 150 | Image size in pixels (50–500) |

**Response:**

```json
{
  "url": "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/smiles/.../PNG?image_size=150x150",
  "smiles": "CC(=O)OC1=CC=CC=C1C(=O)O"
}
```

---

### Genes

#### `GET /v1/genes`

List pharmacogenomics genes (CYP2C19, CYP2D6, CYP3A4, CYP2C9, NAT2).

**Response:** `{"genes": [{"symbol": "CYP2C19", "name": "..."}], "total": N}`

---

#### `GET /v1/genes/{symbol}`

Get gene details by symbol.

**Response:** `{"symbol": "...", "name": "...", "chromosome": "...", "function": "...", "alleles": [...], "cpic_guidelines": [...]}`

---

#### `GET /v1/genes/{symbol}/alleles`

Get alleles for a gene.

**Response:** `{"symbol": "...", "alleles": [{"id": "*1", "function": "Normal", "phenotype": "Extensive"}, ...]}`

---

### Predict

#### `POST /v1/predict`

Predict interaction risk from SMILES.

**Request body:** `{"compounds": ["A","B"], "smiles_list": ["...","..."], "has_vaccine": false}`

**Response:** `{"compounds": [...], "tanimoto_avg": 0.45, "confidence": 80, "risk_score": 0.52, "recommendation": "...", "pairs": [...]}`

---

#### `POST /v1/predict/natural`

Predict risk from natural language (e.g. "Aspirin and Ibuprofen risk" or "CYP2C19 *2 with clopidogrel").

**Request body:** `{"query": "Aspirin and Ibuprofen risk"}`

**Response:** `{"risk_score": 0.5, "confidence": 70, "recommendation": "...", "compounds": [...], "source": "openai"}`

---

### Explain

#### `POST /v1/explain`

Generate mechanistic AI explanation of predicted risk.

**Request body:** `{"compounds": ["A","B"], "tanimoto": 0.45, "confidence": 85, "has_vaccine": false}`

**Response:** `{"explanation": "...", "source": "openai"}`

---

### Interactions

#### `GET /v1/interactions/timeline`

Returns 72-hour risk and concentration curve data for the prediction timeline graph.

**Query parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `compound_count` | int | No | 2 | Number of compounds (1–10) |
| `has_vaccine` | bool | No | false | Whether combination includes a vaccine |
| `tanimoto_avg` | float | No | 0.5 | Average Tanimoto similarity (0–1) |

**Response:**

```json
{
  "timeline": [
    {
      "hour": 0,
      "risk": 45,
      "concentration": 100,
      "label": "0h"
    },
    {
      "hour": 2,
      "risk": 52,
      "concentration": 92,
      "label": "2h"
    }
  ]
}
```

Data points every 2 hours from 0h to 72h. Use with charts (e.g. SVG, Recharts) for visualization.

---

#### `POST /v1/interactions/timeline`

Same as GET, but accepts parameters in the request body (useful for complex queries).

**Request body:**

```json
{
  "compound_count": 2,
  "has_vaccine": false,
  "tanimoto_avg": 0.45
}
```

---

#### `POST /v1/interactions/predict`

Predict interaction risk for a drug combination. Returns Tanimoto similarity per pair and overall confidence.

**Request body:**

```json
{
  "compounds": ["Aspirin", "Ibuprofen"],
  "smiles_list": ["CC(=O)OC1=CC=CC=C1C(=O)O", "CC(C)Cc1ccc(cc1)C(C)C(O)=O"],
  "has_vaccine": false
}
```

| Field | Type | Constraints | Description |
|-------|------|--------------|-------------|
| `compounds` | string[] | ≥2 items | Drug names (for display) |
| `smiles_list` | string[] | ≥2 items, same order as compounds | SMILES strings |
| `has_vaccine` | bool | — | True if combination includes a vaccine |

**Response:**

```json
{
  "compounds": ["Aspirin", "Ibuprofen"],
  "tanimoto_avg": 0.4523,
  "confidence": 80,
  "has_vaccine": false,
  "pairs": [
    {
      "drugs": ["Aspirin", "Ibuprofen"],
      "tanimoto": 0.4523
    }
  ]
}
```

| Field | Description |
|-------|-------------|
| `tanimoto_avg` | Average pairwise Tanimoto similarity (0–1). Higher = more structural overlap. |
| `confidence` | Model confidence percentage (0–100). |
| `pairs` | Per-pair Tanimoto for each drug combination. |

---

#### `POST /v1/interactions/explain`

Generate mechanistic AI explanation of the predicted interaction. Uses OpenAI when configured; otherwise returns a fallback explanation.

**Request body:**

```json
{
  "compounds": ["Aspirin", "Ibuprofen"],
  "tanimoto": 0.45,
  "confidence": 85,
  "has_vaccine": false
}
```

| Field | Type | Description |
|-------|------|-------------|
| `compounds` | string[] | Drug names |
| `tanimoto` | float (0–1) | Tanimoto similarity |
| `confidence` | float (0–100) | Model confidence |
| `has_vaccine` | bool | Whether vaccine is in combination |

**Response (OpenAI configured):**

```json
{
  "explanation": "Aspirin and Ibuprofen both inhibit COX enzymes and are metabolized by CYP2C9. Concurrent use increases bleeding risk...",
  "source": "openai"
}
```

**Response (fallback):**

```json
{
  "explanation": "Based on structural analysis of Aspirin + Ibuprofen, the model identifies metabolic competition at shared CYP450 enzyme sites...",
  "source": "fallback"
}
```

---

#### `POST /v1/interactions/ask`

Answer questions about drug interactions using AI. Pass context for better answers.

**Request body:**

```json
{
  "question": "What CYP enzymes metabolize these drugs?",
  "context": {
    "compounds": ["Aspirin", "Ibuprofen"],
    "tanimoto": 0.45,
    "genes": ["CYP2C9", "CYP2C19"]
  }
}
```

| Field | Type | Description |
|-------|------|-------------|
| `question` | string | Your question |
| `context` | object | Optional: `compounds`, `tanimoto`, `genes` |

**Response:**

```json
{
  "answer": "Aspirin is primarily metabolized by CYP2C9. Ibuprofen is also a CYP2C9 substrate..."
}
```

**Note:** Requires `OPENAI_API_KEY`. Returns a message if not configured.

---

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `API_KEY` | (none) | When set, require `X-API-Key` header on protected endpoints |
| `RATE_LIMIT_REQUESTS` | 100 | Max requests per rate limit window |
| `RATE_LIMIT_WINDOW_SEC` | 60 | Rate limit window in seconds |
| `CORS_ORIGINS` | `*` | Allowed origins (comma-separated) |
| `OPENAI_API_KEY` | (none) | For AI explain/ask endpoints |

---

## Workflows & Examples

### End-to-end: Search → Lookup → Predict → Explain

```bash
# 1. Search for drugs
curl "http://127.0.0.1:8000/v1/drugs/search?q=aspirin"
# → Pick "Aspirin" from results

# 2. Get compound details (SMILES)
curl "http://127.0.0.1:8000/v1/drugs/name/Aspirin"
curl "http://127.0.0.1:8000/v1/drugs/name/Ibuprofen"

# 3. Or use batch for both
curl -X POST http://127.0.0.1:8000/v1/drugs/batch \
  -H "Content-Type: application/json" \
  -d '{"names":["Aspirin","Ibuprofen"]}'

# 4. Predict interaction
curl -X POST http://127.0.0.1:8000/v1/interactions/predict \
  -H "Content-Type: application/json" \
  -d '{"compounds":["Aspirin","Ibuprofen"],"smiles_list":["CC(=O)OC1=CC=CC=C1C(=O)O","CC(C)Cc1ccc(cc1)C(C)C(O)=O"],"has_vaccine":false}'

# 5. Get timeline for chart (use tanimoto_avg from step 4)
curl "http://127.0.0.1:8000/v1/interactions/timeline?compound_count=2&tanimoto_avg=0.45"

# 6. AI explanation
curl -X POST http://127.0.0.1:8000/v1/interactions/explain \
  -H "Content-Type: application/json" \
  -d '{"compounds":["Aspirin","Ibuprofen"],"tanimoto":0.45,"confidence":85,"has_vaccine":false}'
```

### Pagination

```bash
# First page
curl "http://127.0.0.1:8000/v1/drugs/search?q=drug&limit=10&offset=0"

# Second page
curl "http://127.0.0.1:8000/v1/drugs/search?q=drug&limit=10&offset=10"
```

### With API key

```bash
export API_KEY="your-secret-key"
curl -H "X-API-Key: $API_KEY" "http://127.0.0.1:8000/v1/drugs/search?q=aspirin"
```

---

## Best Practices

1. **Cache compound lookups** — Responses include `Cache-Control: max-age=3600`; respect it client-side when possible.
2. **Use batch for multiple compounds** — `POST /v1/drugs/batch` is more efficient than N separate `GET /v1/drugs/name/{name}` calls.
3. **Include X-Request-ID** — For debugging, send a unique ID; responses echo it.
4. **Handle rate limits** — Implement exponential backoff on 429 responses.
5. **Check health first** — Call `/v1/health` before heavy usage to verify PubChem/OpenAI status.
6. **Validate SMILES** — Ensure SMILES are valid before predict/explain; invalid input returns 422.
