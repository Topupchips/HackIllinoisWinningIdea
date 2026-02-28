# Pharmacogen API

RESTful API for drug-drug interaction prediction and pharmacomics. Built for HackIllinois Best Web API.

**Base URL:** `http://127.0.0.1:8000` (local) or your Modal deployment URL.

**Interactive docs:** `/docs` (Swagger UI) | `/redoc` (ReDoc) | `/demo` (Try it)

---

## Quick Start

```bash
curl http://127.0.0.1:8000/v1/health
curl "http://127.0.0.1:8000/v1/drugs/search?q=aspirin"
```

---

## Authentication (Optional)

When `API_KEY` is set, protected endpoints require the `X-API-Key` header:

```bash
curl -H "X-API-Key: your-secret-key" "http://127.0.0.1:8000/v1/drugs/search?q=aspirin"
```

**Exempt:** `/`, `/docs`, `/redoc`, `/demo`, `/v1/health`, `/static/*`

---

## Rate Limiting

- **Default:** 100 requests per 60 seconds per client IP
- **Config:** `RATE_LIMIT_REQUESTS`, `RATE_LIMIT_WINDOW_SEC`
- **Response:** 429 with `{"error": {"code": "rate_limit_exceeded", "message": "..."}}`

---

## Error Format

All errors use a standard structure:

```json
{
  "error": {
    "code": "not_found",
    "message": "Compound not found"
  },
  "request_id": "uuid"
}
```

| Code | HTTP | Description |
|------|------|-------------|
| `bad_request` | 400 | Invalid input |
| `unauthorized` | 401 | Missing/invalid API key |
| `not_found` | 404 | Resource not found |
| `validation_error` | 422 | Request body validation failed |
| `rate_limit_exceeded` | 429 | Too many requests |
| `upstream_error` | 502 | PubChem/OpenAI unreachable |
| `internal_error` | 500 | Server error |

Include `X-Request-ID` in requests for debugging; responses echo it.

---

## Endpoints

### Health

| Method | Path | Description |
|--------|------|-------------|
| GET | `/v1/health` | Health check + dependency status |
| GET | `/` | API info |

### Drugs

| Method | Path | Description |
|--------|------|-------------|
| GET | `/v1/drugs/search?q=&limit=&offset=` | Search drugs (PubChem) |
| GET | `/v1/drugs/name/{name}` | Get compound by name |
| POST | `/v1/drugs/batch` | Batch compound lookup |
| GET | `/v1/drugs/similar?smiles=&limit=&offset=` | Similar drugs |
| GET | `/v1/drugs/structure/image?smiles=&size=` | Structure image URL |

### Interactions

| Method | Path | Description |
|--------|------|-------------|
| GET | `/v1/interactions/timeline?compound_count=&has_vaccine=&tanimoto_avg=` | 72h risk/concentration curve |
| POST | `/v1/interactions/predict` | Predict interaction risk |
| POST | `/v1/interactions/explain` | AI mechanistic explanation |
| POST | `/v1/interactions/ask` | Q&A about interactions |

---

## Configuration

| Variable | Default | Description |
|----------|--------|-------------|
| `API_KEY` | (none) | Require X-API-Key when set |
| `RATE_LIMIT_REQUESTS` | 100 | Max requests per window |
| `RATE_LIMIT_WINDOW_SEC` | 60 | Rate limit window (seconds) |
| `CORS_ORIGINS` | * | Allowed origins (comma-separated) |
| `OPENAI_API_KEY` | (none) | For AI explain/ask |

---

## Examples

### Predict + Timeline

```bash
# Predict
curl -X POST http://127.0.0.1:8000/v1/interactions/predict \
  -H "Content-Type: application/json" \
  -d '{"compounds":["Aspirin","Ibuprofen"],"smiles_list":["CC(=O)OC1=CC=CC=C1C(=O)O","CC(C)Cc1ccc(cc1)C(C)C(O)=O"],"has_vaccine":false}'

# Get timeline graph data
curl "http://127.0.0.1:8000/v1/interactions/timeline?compound_count=2&tanimoto_avg=0.45"
```

### Explain

```bash
curl -X POST http://127.0.0.1:8000/v1/interactions/explain \
  -H "Content-Type: application/json" \
  -d '{"compounds":["Aspirin","Ibuprofen"],"tanimoto":0.45,"confidence":85,"has_vaccine":false}'
```
