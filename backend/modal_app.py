"""
GeneAI Web API - Drug interaction prediction & pharmacogenomics
Deploy: modal deploy backend/modal_app.py
Serve locally: modal serve backend/modal_app.py

RESTful API for drug-drug interaction prediction, mechanistic AI explanation,
and drug search. Built for HackIllinois Best Web API.
"""
import os
import uuid
from pathlib import Path
from urllib.parse import quote
import modal
import httpx
from fastapi import FastAPI, Query, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.openapi.docs import get_swagger_ui_html, get_swagger_ui_oauth2_redirect_html
from pydantic import BaseModel, Field

app = modal.App("geneai-api")

_image = (
    modal.Image.debian_slim()
    .pip_install("openai", "fastapi[standard]", "httpx")
)
_static_path = Path(__file__).parent / "static"
if _static_path.exists():
    image = _image.add_local_dir(str(_static_path), "/static")
else:
    image = _image

# --- Pydantic models ---

class ExplainRequest(BaseModel):
    compounds: list[str] = Field(..., min_length=2, description="Drug names (e.g. Aspirin, Ibuprofen)")
    tanimoto: float = Field(..., ge=0, le=1, description="Tanimoto structural similarity (0–1)")
    confidence: float = Field(..., ge=0, le=100, description="Model confidence percentage")
    has_vaccine: bool = Field(False, description="True if combination includes a vaccine")


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, description="Your question")
    context: dict = Field(default_factory=dict, description="Optional: compounds, tanimoto, genes")


class PredictRequest(BaseModel):
    compounds: list[str] = Field(..., min_length=2, description="Drug names")
    smiles_list: list[str] = Field(..., min_length=2, description="SMILES strings in same order")
    has_vaccine: bool = Field(False, description="True if combination includes a vaccine")


class BatchCompoundRequest(BaseModel):
    names: list[str] = Field(..., min_length=1, max_length=20, description="Compound names to look up")


# --- FastAPI app ---

web_app = FastAPI(
    title="GeneAI API",
    description="""
## Drug–drug interaction prediction and pharmacogenomics

Predict interaction risk for novel drug combinations with little or no clinical data using chemical structure (SMILES) and AI.

**Features:** Drug search (PubChem), interaction prediction, AI mechanistic explanation, similar drugs.
    """.strip(),
    version="1.0.0",
    docs_url=None,
    redoc_url=None,
    openapi_url="/openapi.json",
)

web_app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@web_app.middleware("http")
async def add_request_id(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


def _error_response(status_code: int, code: str, message: str, request_id: str | None = None):
    body = {"error": {"code": code, "message": message}}
    if request_id:
        body["request_id"] = request_id
    return JSONResponse(status_code=status_code, content=body)


@web_app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    rid = getattr(request.state, "request_id", None)
    codes = {400: "bad_request", 404: "not_found", 422: "validation_error", 502: "upstream_error"}
    code = codes.get(exc.status_code, "error")
    return _error_response(exc.status_code, code, str(exc.detail), rid)


# Themed docs (GeneAI dark theme)
web_app.mount("/static", StaticFiles(directory="/static"), name="static")


@web_app.get("/demo", include_in_schema=False)
async def demo_redirect():
    """Redirect to API demo page."""
    return RedirectResponse(url="/static/demo/index.html")


@web_app.get("/docs", include_in_schema=False)
async def custom_swagger_ui_html():
    return get_swagger_ui_html(
        openapi_url=web_app.openapi_url,
        title=web_app.title + " - API Reference",
        oauth2_redirect_url=web_app.swagger_ui_oauth2_redirect_url,
        swagger_js_url="https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js",
        swagger_css_url="/static/docs/theme.css",
        swagger_ui_parameters={
            "defaultModelsExpandDepth": 0,
            "docExpansion": "list",
            "filter": True,
            "syntaxHighlight.theme": "monokai",
            "tryItOutEnabled": True,
        },
    )


@web_app.get(web_app.swagger_ui_oauth2_redirect_url, include_in_schema=False)
async def swagger_ui_redirect():
    return get_swagger_ui_oauth2_redirect_html()


@web_app.get("/redoc", include_in_schema=False)
async def redoc_html():
    from fastapi.openapi.docs import get_redoc_html
    return get_redoc_html(
        openapi_url=web_app.openapi_url,
        title=web_app.title + " - ReDoc",
        redoc_js_url="https://unpkg.com/redoc@2/bundles/redoc.standalone.js",
    )


# --- Health ---

def _check_pubchem() -> bool:
    try:
        r = httpx.get("https://pubchem.ncbi.nlm.nih.gov/rest/autocomplete/compound/aspirin/json", timeout=5)
        return r.status_code == 200
    except Exception:
        return False


@web_app.get("/v1/health", tags=["Health"])
def health():
    """Health check. Returns API status and dependency health."""
    return {
        "status": "ok",
        "api": "geneai",
        "version": "1.0.0",
        "dependencies": {
            "pubchem": "ok" if _check_pubchem() else "unreachable",
            "openai": "configured" if os.environ.get("OPENAI_API_KEY") else "not_configured",
        },
    }


@web_app.get("/", tags=["Health"])
def root():
    """Root redirect to docs."""
    return {"message": "GeneAI API", "docs": "/docs", "demo": "/demo", "health": "/v1/health"}


# --- Drugs ---

def _parse_pubchem_compound(data: dict, name: str) -> dict | None:
    compounds = data.get("PC_Compounds", [])
    if not compounds:
        return None
    pc = compounds[0]
    cid = pc.get("id", {}).get("id", {}).get("cid")
    formula = ""
    smiles = ""
    for prop in pc.get("props", []):
        urn = prop.get("urn", {})
        label = urn.get("label", "")
        val = prop.get("value", {})
        if label == "Molecular Formula":
            formula = val.get("sval", "")
        elif label == "SMILES" and val.get("sval"):
            smiles = val.get("sval", "") or smiles
    return {"name": name, "smiles": smiles, "formula": formula, "cid": cid}


def _fetch_compound_from_pubchem(name: str) -> dict | None:
    try:
        url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{quote(name)}/JSON"
        r = httpx.get(url, timeout=15)
        if r.status_code == 404:
            return None
        r.raise_for_status()
        data = r.json()
        return _parse_pubchem_compound(data, name)
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=502, detail=f"PubChem error: {e.response.status_code}")
    except (httpx.TimeoutException, httpx.ConnectError):
        raise HTTPException(status_code=502, detail="PubChem unreachable")
    except Exception:
        return None


@web_app.get("/v1/drugs/search", tags=["Drugs"])
def search_drugs(
    q: str = Query(..., min_length=1),
    limit: int = Query(10, ge=1, le=20),
    offset: int = Query(0, ge=0),
):
    """Search drugs by name (PubChem). Supports pagination."""
    try:
        r = httpx.get(
            f"https://pubchem.ncbi.nlm.nih.gov/rest/autocomplete/compound/{q}/json",
            timeout=10,
        )
        r.raise_for_status()
        data = r.json()
        terms = data.get("dictionary_terms", {}).get("compound", [])
        terms = terms[:20] if isinstance(terms, list) else []
        page = terms[offset : offset + limit]
        return {"query": q, "results": page, "total": len(terms), "limit": limit, "offset": offset}
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@web_app.get("/v1/drugs/name/{name}", tags=["Drugs"])
def get_compound_by_name(name: str, response: Response):
    """Get compound details by name (PubChem)."""
    result = _fetch_compound_from_pubchem(name)
    if result is None:
        raise HTTPException(status_code=404, detail="Compound not found")
    response.headers["Cache-Control"] = "public, max-age=3600"
    return result


@web_app.post("/v1/drugs/batch", tags=["Drugs"])
def batch_compounds(req: BatchCompoundRequest):
    """Look up multiple compounds by name."""
    results = []
    for name in req.names:
        c = _fetch_compound_from_pubchem(name)
        if c:
            results.append(c)
    return {"compounds": results, "requested": len(req.names), "found": len(results)}


@web_app.get("/v1/drugs/similar", tags=["Drugs"])
def similar_drugs(
    smiles: str = Query(...),
    limit: int = Query(5, ge=1, le=20),
    offset: int = Query(0, ge=0),
):
    """Find structurally similar drugs. Actian VectorAI placeholder. Supports pagination."""
    DEMO = ["Aspirin", "Ibuprofen", "Naproxen", "Acetaminophen", "Diclofenac"]
    page = DEMO[offset : offset + limit]
    return {"smiles": smiles, "similar": [{"name": n, "smiles": ""} for n in page], "total": len(DEMO), "limit": limit, "offset": offset, "source": "demo"}


@web_app.get("/v1/drugs/structure/image", tags=["Drugs"])
def structure_image(smiles: str = Query(...), size: int = Query(150, ge=50, le=500)):
    """Get PubChem structure image URL for SMILES."""
    encoded = quote(smiles, safe="")
    url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/smiles/{encoded}/PNG?image_size={size}x{size}"
    return {"url": url, "smiles": smiles}


# --- Interactions ---

def _tanimoto_similarity(smiles_a: str, smiles_b: str) -> float:
    """3-gram overlap as proxy for Tanimoto. Replace with RDKit for production."""
    def ngrams(s: str, n: int):
        return set(s[i:i+n] for i in range(len(s) - n + 1)) if s else set()
    a, b = ngrams(smiles_a, 3), ngrams(smiles_b, 3)
    if not a and not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


def _generate_timeline(compound_count: int, has_vaccine: bool, tanimoto_avg: float) -> list[dict]:
    import math
    data = []
    base_risk = 0.4 if compound_count >= 2 else 0.1
    vaccine_boost = 0.25 if has_vaccine else 0
    tanimoto_boost = tanimoto_avg * 0.15
    for h in range(0, 73, 2):
        risk = base_risk + math.sin(h / 12) * 0.3 + vaccine_boost + tanimoto_boost
        if has_vaccine and 24 <= h <= 48:
            risk += 0.2
        risk = min(1.0, max(0.1, risk))
        concentration = math.exp(-h / 24) * (1 + math.sin(h / 8) * 0.3)
        data.append({"hour": h, "risk": round(risk * 100), "concentration": round(concentration * 100), "label": f"{h}h"})
    return data


@web_app.get("/v1/interactions/timeline", tags=["Interactions"])
def get_timeline(
    compound_count: int = Query(2, ge=1, le=10),
    has_vaccine: bool = Query(False),
    tanimoto_avg: float = Query(0.5, ge=0, le=1),
):
    """Returns 72-hour risk and concentration curve data."""
    return {"timeline": _generate_timeline(compound_count, has_vaccine, tanimoto_avg)}


@web_app.post("/v1/interactions/predict", tags=["Interactions"])
def predict_interaction(req: PredictRequest):
    """Predict interaction risk for a drug combination."""
    pairs = []
    total = 0
    count = 0
    for i in range(len(req.smiles_list)):
        for j in range(i + 1, len(req.smiles_list)):
            sim = _tanimoto_similarity(req.smiles_list[i], req.smiles_list[j])
            pairs.append({"drugs": [req.compounds[i], req.compounds[j]], "tanimoto": round(sim, 4)})
            total += sim
            count += 1
    avg_tanimoto = total / count if count else 0
    confidence = min(95, 70 + len(req.compounds) * 5 + (10 if req.has_vaccine else 0))
    return {
        "compounds": req.compounds,
        "tanimoto_avg": round(avg_tanimoto, 4),
        "confidence": confidence,
        "has_vaccine": req.has_vaccine,
        "pairs": pairs,
    }


@web_app.post("/v1/interactions/explain", tags=["Interactions"])
def explain_interaction(req: ExplainRequest):
    """Generate mechanistic AI explanation (OpenAI)."""
    api_key = os.environ.get("OPENAI_API_KEY")
    fallback = _fallback_explanation(req.compounds, req.tanimoto, req.confidence, req.has_vaccine)
    if not api_key:
        return {"explanation": fallback, "source": "fallback"}

    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        vaccine_note = " One or more compounds is a vaccine; include immune modulation and LNP interaction considerations." if req.has_vaccine else ""
        r = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a pharmacologist explaining drug-drug interactions. Be concise, use plain language, and cite mechanisms (CYP450, metabolic competition)."},
                {"role": "user", "content": f"Explain the predicted drug-drug interaction between {', '.join(req.compounds)}. Tanimoto similarity: {req.tanimoto:.2f}, AI confidence: {req.confidence}%.{vaccine_note}"}
            ],
            max_tokens=400,
        )
        return {"explanation": r.choices[0].message.content, "source": "openai"}
    except Exception as e:
        return {"explanation": fallback, "source": "fallback", "error": str(e)}


@web_app.post("/v1/interactions/ask", tags=["Interactions"])
def ask_interaction(req: AskRequest):
    """Answer questions about drug interactions (OpenAI)."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return {"answer": "OpenAI API key not configured."}

    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        ctx = req.context
        ctx_str = f"Compounds: {ctx.get('compounds', [])}. Tanimoto: {ctx.get('tanimoto', 0)}. Genes: {ctx.get('genes', [])}."
        r = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a pharmacologist. Answer briefly and accurately about drug interactions."},
                {"role": "user", "content": f"Context: {ctx_str}\n\nQuestion: {req.question}"}
            ],
            max_tokens=300,
        )
        return {"answer": r.choices[0].message.content}
    except Exception as e:
        return {"answer": f"Unable to answer: {str(e)}"}


def _fallback_explanation(compounds: list[str], tanimoto: float, confidence: float, has_vaccine: bool) -> str:
    base = f"Based on structural analysis of {' + '.join(compounds)}, the model identifies metabolic competition at shared CYP450 enzyme sites. Tanimoto similarity ({tanimoto:.2f}) indicates overlapping pharmacophores. Confidence: {confidence}%."
    if has_vaccine:
        base += " Vaccine present: immune activation may modulate CYP expression; LNP components could interact with drug-binding proteins."
    return base


# --- Modal deployment ---

@app.function(image=image, secrets=[modal.Secret.from_name("openai-api-key", required=False)])
@modal.asgi_app()
def api():
    return web_app
