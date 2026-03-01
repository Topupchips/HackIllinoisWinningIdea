"""
GeneAI API - Drug interaction prediction & pharmacogenomics.
Run: python backend/run_local.py
Docs: http://127.0.0.1:8000/docs

Uses PharmaRisk (dev) data + model when data/processed/drugs.csv exists.
Falls back to PubChem when not.
"""
import os
import sys
import uuid
from pathlib import Path
from urllib.parse import quote
import uvicorn
from fastapi import FastAPI, Query, HTTPException, Request

# Add project root for api imports, backend for config
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).parent))
from config import API_KEY, CORS_ORIGINS

# Try loading PharmaRisk (dev) data + model
PHARMARISK_LOADED = False
try:
    if (ROOT / "data" / "processed" / "drugs.csv").exists():
        from api.services.data_service import data_service
        data_service.load_all()
        if len(data_service.drugs) > 0:
            from api.services import model_service
            model_service.load_model()
            PHARMARISK_LOADED = True
except Exception:
    pass
from rate_limit import check_rate_limit
from fastapi.responses import Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.openapi.docs import (
    get_redoc_html,
    get_swagger_ui_html,
    get_swagger_ui_oauth2_redirect_html,
)
from pydantic import BaseModel, Field
import httpx

# --- Standard error format ---
def error_response(status_code: int, code: str, message: str, request_id: str | None = None):
    body = {"error": {"code": code, "message": message}}
    if request_id:
        body["request_id"] = request_id
    return JSONResponse(status_code=status_code, content=body)


ERROR_RESPONSES = {
    400: {"description": "Bad request", "content": {"application/json": {"example": {"error": {"code": "bad_request", "message": "Invalid input"}}}}},
    401: {"description": "Unauthorized", "content": {"application/json": {"example": {"error": {"code": "unauthorized", "message": "Invalid or missing API key"}}}}},
    404: {"description": "Not found", "content": {"application/json": {"example": {"error": {"code": "not_found", "message": "Compound not found"}}}}},
    422: {"description": "Validation error", "content": {"application/json": {"example": {"error": {"code": "validation_error", "message": "Invalid request body"}}}}},
    429: {"description": "Rate limit exceeded", "content": {"application/json": {"example": {"error": {"code": "rate_limit_exceeded", "message": "Too many requests"}}}}},
    502: {"description": "Upstream error", "content": {"application/json": {"example": {"error": {"code": "upstream_error", "message": "PubChem unreachable"}}}}},
}

app = FastAPI(
    title="GeneAI API",
    description="""
Pharmacogenomics drug risk prediction API. Takes a patient's gene profile and a drug, returns a risk score with clinical recommendations from CPIC guidelines.

**Features:**
- **Drugs** — List and lookup drugs via PubChem
- **Genes** — Gene symbols, alleles, pharmacogenomics data
- **Predict** — Risk prediction (SMILES or natural language)
- **Explain** — AI mechanistic insights (OpenAI, optional)

**Auth:** When `API_KEY` is set, include `X-API-Key` header. **Rate limit:** 100 req/min per IP (configurable).

**Error format:** All errors return `{"error": {"code": "...", "message": "..."}, "request_id": "..."}`.
    """.strip(),
    version="1.0.0",
    docs_url=None,
    redoc_url=None,
    openapi_url="/openapi.json",
)
app.add_middleware(CORSMiddleware, allow_origins=CORS_ORIGINS, allow_methods=["*"], allow_headers=["*"])


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    """Apply rate limiting. Skip for docs/static."""
    path = request.url.path
    if path in ("/", "/docs", "/redoc", "/openapi.json", "/demo", "/v1/health", "/v1/validate") or path.startswith("/static") or path.startswith("/backend-static"):
        return await call_next(request)
    try:
        check_rate_limit(request)
    except HTTPException:
        raise
    return await call_next(request)


@app.middleware("http")
async def add_request_id(request: Request, call_next):
    """Add X-Request-ID to all requests/responses."""
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    """Optional API key auth when API_KEY is set. Skip docs/health/static."""
    if API_KEY:
        path = request.url.path
        if path not in ("/", "/docs", "/redoc", "/openapi.json", "/demo", "/v1/health", "/v1/validate") and not path.startswith("/static") or path.startswith("/backend-static"):
            key = request.headers.get("X-API-Key")
            if key != API_KEY:
                rid = getattr(request.state, "request_id", None)
                return error_response(401, "unauthorized", "Invalid or missing API key. Provide X-API-Key header.", rid)
    return await call_next(request)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    rid = getattr(request.state, "request_id", None)
    codes = {400: "bad_request", 404: "not_found", 422: "validation_error", 429: "rate_limit_exceeded", 502: "upstream_error", 503: "service_unavailable"}
    code = codes.get(exc.status_code, "error")
    return error_response(exc.status_code, code, str(exc.detail), rid)


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    rid = getattr(request.state, "request_id", None)
    return error_response(500, "internal_error", "An unexpected error occurred.", rid)

# Static files for themed docs + demo (use /backend-static to avoid conflict with frontend's /static)
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/backend-static", StaticFiles(directory=str(static_dir)), name="backend-static")

# Include PharmaRisk (dev) routers when data loaded
if PHARMARISK_LOADED:
    from api.routes import drugs, explain, genes, health, predict
    app.include_router(health.router, prefix="/v1")
    app.include_router(drugs.router, prefix="/v1")
    app.include_router(genes.router, prefix="/v1")
    app.include_router(predict.router, prefix="/v1")
    app.include_router(explain.router, prefix="/v1")
    # Main branch compatibility: /predict (no prefix) for GeneAI
    app.include_router(predict.router)


@app.get("/demo", include_in_schema=False)
async def demo_redirect():
    """Redirect to API demo page."""
    return RedirectResponse(url="/backend-static/demo/index.html")


@app.get("/docs", include_in_schema=False)
async def docs_home():
    """Serve docs home page directly (no redirect)."""
    return FileResponse(static_dir / "docs" / "index.html")


@app.get("/docs/api", include_in_schema=False)
async def docs_endpoints():
    """Serve API endpoints page (Swagger UI with site header)."""
    return FileResponse(static_dir / "docs" / "endpoints.html")


@app.get(app.swagger_ui_oauth2_redirect_url, include_in_schema=False)
async def swagger_ui_redirect():
    return get_swagger_ui_oauth2_redirect_html()


@app.get("/redoc", include_in_schema=False)
async def redoc_html():
    return get_redoc_html(
        openapi_url=app.openapi_url,
        title=app.title + " - ReDoc",
        redoc_js_url="https://unpkg.com/redoc@2/bundles/redoc.standalone.js",
        redoc_favicon_url="https://fastapi.tiangolo.com/img/favicon.png",
    )


# --- Models ---

class ExplainRequest(BaseModel):
    """Request body for AI mechanistic explanation."""
    compounds: list[str] = Field(..., min_length=2, description="Drug names (e.g. Aspirin, Ibuprofen)")
    tanimoto: float = Field(..., ge=0, le=1, description="Tanimoto structural similarity (0–1)")
    confidence: float = Field(..., ge=0, le=100, description="Model confidence percentage")
    has_vaccine: bool = Field(False, description="True if combination includes a vaccine")

    model_config = {"json_schema_extra": {"example": {"compounds": ["Aspirin", "Ibuprofen"], "tanimoto": 0.45, "confidence": 85, "has_vaccine": False}}}


class AskRequest(BaseModel):
    """Request body for Q&A about drug interactions."""
    question: str = Field(..., min_length=1, description="Your question (e.g. What CYP enzymes are involved?)")
    context: dict = Field(default_factory=dict, description="Optional: compounds, tanimoto, genes")

    model_config = {"json_schema_extra": {"example": {"question": "What CYP enzymes metabolize these drugs?", "context": {"compounds": ["Aspirin", "Ibuprofen"], "tanimoto": 0.45}}}}

class PredictRequest(BaseModel):
    """Request body for interaction risk prediction."""
    compounds: list[str] = Field(..., min_length=2, description="Drug names")
    smiles_list: list[str] = Field(..., min_length=2, description="SMILES strings in same order as compounds")
    has_vaccine: bool = Field(False, description="True if combination includes a vaccine")

    model_config = {"json_schema_extra": {"example": {"compounds": ["Aspirin", "Ibuprofen"], "smiles_list": ["CC(=O)OC1=CC=CC=C1C(=O)O", "CC(C)Cc1ccc(cc1)C(C)C(O)=O"], "has_vaccine": False}}}


class BatchCompoundRequest(BaseModel):
    """Request body for batch compound lookup."""
    names: list[str] = Field(..., min_length=1, max_length=20, description="Compound names to look up")

    model_config = {"json_schema_extra": {"example": {"names": ["Aspirin", "Ibuprofen", "Metformin"]}}}


class TimelineRequest(BaseModel):
    compound_count: int = Field(2, ge=1, le=10)
    has_vaccine: bool = False
    tanimoto_avg: float = Field(0.5, ge=0, le=1)


class GeneInput(BaseModel):
    """Input for gene-based prediction."""
    symbol: str = Field(..., description="Gene symbol (e.g. CYP2C19)")
    alleles: list[str] = Field(default_factory=list, description="Allele IDs")


class NaturalPredictRequest(BaseModel):
    """Natural language prediction request."""
    query: str = Field(..., min_length=1, description="e.g. 'Aspirin and Ibuprofen risk' or 'CYP2C19 *2 with clopidogrel'")


# --- Response schemas (for OpenAPI) ---

class HealthResponse(BaseModel):
    status: str
    api: str
    version: str
    dependencies: dict


class DrugResponse(BaseModel):
    id: str
    name: str
    smiles: str
    formula: str
    cid: int | None = None


class DrugListResponse(BaseModel):
    drugs: list
    total: int


class GeneResponse(BaseModel):
    symbol: str
    name: str
    chromosome: str
    function: str


class GeneDetailResponse(GeneResponse):
    alleles: list
    cpic_guidelines: list[str] = []


class AlleleInfo(BaseModel):
    id: str
    function: str
    phenotype: str


class GeneListResponse(BaseModel):
    genes: list
    total: int


class GeneDrugResult(BaseModel):
    drug: str
    gene: str
    risk_score: float
    recommendation: str


class ExplainResponse(BaseModel):
    explanation: str
    source: str


class ValidateResponse(BaseModel):
    valid: bool
    message: str


# --- Helpers ---

def _tanimoto(smiles_a: str, smiles_b: str) -> float:
    def ngrams(s: str, n: int):
        return set(s[i:i+n] for i in range(len(s) - n + 1)) if s else set()
    a, b = ngrams(smiles_a, 3), ngrams(smiles_b, 3)
    if not a and not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


def _fallback_explanation(compounds: list[str], tanimoto: float, confidence: float, has_vaccine: bool) -> str:
    base = f"Based on structural analysis of {' + '.join(compounds)}, the model identifies metabolic competition at shared CYP450 enzyme sites. Tanimoto similarity ({tanimoto:.2f}) indicates overlapping pharmacophores. Confidence: {confidence}%."
    if has_vaccine:
        base += " Vaccine present: immune activation may modulate CYP expression; LNP components could interact with drug-binding proteins."
    return base


# --- Health ---

def _check_pubchem() -> bool:
    try:
        r = httpx.get("https://pubchem.ncbi.nlm.nih.gov/rest/autocomplete/compound/aspirin/json", timeout=5)
        return r.status_code == 200
    except Exception:
        return False


def _check_openai() -> bool:
    return bool(os.environ.get("OPENAI_API_KEY"))


if not PHARMARISK_LOADED:
    @app.get("/v1/health", tags=["Health"], summary="Health check", responses={200: {"content": {"application/json": {"example": {"status": "ok", "api": "geneai", "version": "1.0.0", "dependencies": {"pubchem": "ok", "openai": "configured"}}}}}})
    def health():
        """Returns API status and dependency health (PubChem, OpenAI)."""
        pubchem_ok = _check_pubchem()
        openai_configured = _check_openai()
        return {
            "status": "ok",
            "api": "geneai",
            "version": "1.0.0",
            "dependencies": {
                "pubchem": "ok" if pubchem_ok else "unreachable",
                "openai": "configured" if openai_configured else "not_configured",
            },
        }

    @app.get("/v1/validate", tags=["Health"], summary="Validate data")
    def validate_data():
        """Validate API data sources (PubChem, config)."""
        pubchem_ok = _check_pubchem()
        return {"valid": pubchem_ok, "message": "OK" if pubchem_ok else "PubChem unreachable"}


# Root: serve GeneAI app when frontend/build exists, else API info JSON
FRONTEND_BUILD = ROOT / "frontend" / "build"
if not FRONTEND_BUILD.exists():
    @app.get("/", tags=["Health"], summary="API info")
    def root():
        """Root endpoint with links to docs, demo, and health."""
        return {"message": "GeneAI API", "docs": "/docs", "demo": "/demo", "health": "/v1/health"}


# --- Drugs ---

if not PHARMARISK_LOADED:
    @app.get("/v1/drugs", tags=["Drugs"], summary="List drugs")
    def list_drugs(
        q: str = Query("", description="Search query (optional)"),
        limit: int = Query(20, ge=1, le=50),
        offset: int = Query(0, ge=0),
    ):
        """List drugs. With q, searches via PubChem autocomplete; otherwise returns empty list."""
        if not q:
            return {"drugs": [], "total": 0}
        try:
            r = httpx.get(f"https://pubchem.ncbi.nlm.nih.gov/rest/autocomplete/compound/{q}/json", timeout=10)
            r.raise_for_status()
            terms = r.json().get("dictionary_terms", {}).get("compound", []) or []
            terms = terms[:50] if isinstance(terms, list) else []
            page = terms[offset : offset + limit]
            return {"drugs": [{"id": t, "name": t} for t in page], "total": len(terms)}
        except Exception:
            return {"drugs": [], "total": 0}

    @app.get("/v1/drugs/{drug_id}", tags=["Drugs"], summary="Get drug")
    def get_drug(drug_id: str, response: Response):
        """Get drug by name or PubChem CID."""
        if drug_id.isdigit():
            try:
                r = httpx.get(f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/{drug_id}/JSON", timeout=15)
                if r.status_code == 200:
                    data = r.json()
                    result = _parse_pubchem_compound(data, drug_id)
                    if result:
                        result["id"] = str(result.get("cid", drug_id))
                        result["cid"] = result.get("cid") or int(drug_id)
                        response.headers["Cache-Control"] = "public, max-age=3600"
                        return result
            except Exception:
                pass
        result = _fetch_compound_from_pubchem(drug_id)
        if result is None:
            raise HTTPException(status_code=404, detail="Drug not found")
        result["id"] = str(result.get("cid", drug_id))
        response.headers["Cache-Control"] = "public, max-age=3600"
        return result


@app.get("/v1/drugs/search", tags=["Drugs"], summary="Search drugs by name", responses={**ERROR_RESPONSES, 200: {"content": {"application/json": {"example": {"query": "aspirin", "results": ["Aspirin", "aspirin"], "total": 10, "limit": 10, "offset": 0}}}}})
def search_drugs(
    q: str = Query(..., min_length=1, example="aspirin", description="Search query (e.g. aspirin, ibuprofen)"),
    limit: int = Query(10, ge=1, le=20, description="Max results (1–20)"),
    offset: int = Query(0, ge=0, description="Skip first N results"),
):
    """Search drugs by name using PubChem autocomplete. Supports pagination via limit/offset."""
    try:
        r = httpx.get(
            f"https://pubchem.ncbi.nlm.nih.gov/rest/autocomplete/compound/{q}/json",
            timeout=10,
        )
        r.raise_for_status()
        data = r.json()
        terms = data.get("dictionary_terms", {}).get("compound", [])
        terms = terms[:20] if isinstance(terms, list) else []
        total = len(terms)
        page = terms[offset : offset + limit]
        return {"query": q, "results": page, "total": total, "limit": limit, "offset": offset}
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


def _parse_pubchem_compound(data: dict, name: str) -> dict | None:
    """Parse PubChem PC_Compounds JSON into our format."""
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
        prop_name = urn.get("name", "")
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


@app.get("/v1/drugs/name/{name}", tags=["Drugs"], summary="Get compound by name", responses={**ERROR_RESPONSES, 200: {"content": {"application/json": {"example": {"name": "Aspirin", "smiles": "CC(=O)OC1=CC=CC=C1C(=O)O", "formula": "C9H8O4", "cid": 2244}}}}})
def get_compound(name: str, response: Response):
    """
    Get compound details by name from PubChem.
    Returns SMILES, molecular formula, and PubChem CID.
    Name lookup is case-insensitive (tries as-is, then lowercase).
    """
    result = _fetch_compound_from_pubchem(name)
    if result is None and name != name.lower():
        result = _fetch_compound_from_pubchem(name.lower())
    if result is None:
        raise HTTPException(status_code=404, detail="Compound not found")
    response.headers["Cache-Control"] = "public, max-age=3600"
    return result


@app.post("/v1/drugs/batch", tags=["Drugs"], summary="Batch compound lookup", responses={**ERROR_RESPONSES, 200: {"content": {"application/json": {"example": {"compounds": [{"name": "Aspirin", "smiles": "CC(=O)OC1=CC=CC=C1C(=O)O", "formula": "C9H8O4", "cid": 2244}], "requested": 2, "found": 1}}}}})
def batch_compounds(req: BatchCompoundRequest):
    """Look up multiple compounds by name. Returns found compounds; missing ones are omitted."""
    results = []
    for name in req.names:
        c = _fetch_compound_from_pubchem(name)
        if c:
            results.append(c)
    return {"compounds": results, "requested": len(req.names), "found": len(results)}


@app.get("/v1/drugs/similar", tags=["Drugs"], summary="Find similar drugs")
def similar_drugs(
    smiles: str = Query(..., description="SMILES string of the reference compound"),
    limit: int = Query(5, ge=1, le=20, description="Max results (1–20)"),
    offset: int = Query(0, ge=0, description="Skip first N results"),
):
    """Find structurally similar drugs. Actian VectorAI placeholder; returns demo list. Supports pagination."""
    DEMO = ["Aspirin", "Ibuprofen", "Naproxen", "Acetaminophen", "Diclofenac"]
    page = DEMO[offset : offset + limit]
    return {"smiles": smiles, "similar": [{"name": n, "smiles": ""} for n in page], "total": len(DEMO), "limit": limit, "offset": offset, "source": "demo"}


# --- Genes (fallback when no PharmaRisk data) ---

if not PHARMARISK_LOADED:
    GENES_DATA = {
        "CYP2C19": {"symbol": "CYP2C19", "name": "Cytochrome P450 2C19", "chromosome": "10", "function": "Drug metabolism"},
        "CYP2D6": {"symbol": "CYP2D6", "name": "Cytochrome P450 2D6", "chromosome": "22", "function": "Drug metabolism"},
        "CYP3A4": {"symbol": "CYP3A4", "name": "Cytochrome P450 3A4", "chromosome": "7", "function": "Drug metabolism"},
        "CYP2C9": {"symbol": "CYP2C9", "name": "Cytochrome P450 2C9", "chromosome": "10", "function": "Drug metabolism"},
        "NAT2": {"symbol": "NAT2", "name": "N-acetyltransferase 2", "chromosome": "8", "function": "Drug acetylation"},
    }
    ALLELES_DATA = {
        "CYP2C19": [{"id": "*1", "function": "Normal", "phenotype": "Extensive"}, {"id": "*2", "function": "No function", "phenotype": "Poor"}, {"id": "*17", "function": "Increased", "phenotype": "Ultrarapid"}],
        "CYP2D6": [{"id": "*1", "function": "Normal", "phenotype": "Extensive"}, {"id": "*4", "function": "No function", "phenotype": "Poor"}],
        "CYP3A4": [{"id": "*1", "function": "Normal", "phenotype": "Extensive"}],
        "CYP2C9": [{"id": "*1", "function": "Normal", "phenotype": "Extensive"}, {"id": "*2", "function": "Decreased", "phenotype": "Intermediate"}],
        "NAT2": [{"id": "*4", "function": "Normal", "phenotype": "Fast"}, {"id": "*5", "function": "Decreased", "phenotype": "Slow"}],
    }

    @app.get("/v1/genes", tags=["Genes"], summary="List genes")
    def list_genes():
        """List pharmacogenomics genes."""
        genes = [{"symbol": g["symbol"], "name": g["name"]} for g in GENES_DATA.values()]
        return {"genes": genes, "total": len(genes)}

    @app.get("/v1/genes/{symbol}", tags=["Genes"], summary="Get gene")
    def get_gene(symbol: str):
        """Get gene details by symbol."""
        s = symbol.upper()
        if s not in GENES_DATA:
            raise HTTPException(status_code=404, detail="Gene not found")
        g = dict(GENES_DATA[s])
        g["alleles"] = ALLELES_DATA.get(s, [])
        g["cpic_guidelines"] = ["Clopidogrel", "PPIs", "Voriconazole"]
        return g

    @app.get("/v1/genes/{symbol}/alleles", tags=["Genes"], summary="Get gene alleles")
    def get_gene_alleles(symbol: str):
        """Get alleles for a gene."""
        s = symbol.upper()
        if s not in GENES_DATA:
            raise HTTPException(status_code=404, detail="Gene not found")
        return {"symbol": s, "alleles": ALLELES_DATA.get(s, [])}


# --- Drugs (continued) ---

@app.get("/v1/drugs/structure/image", tags=["Drugs"], summary="Get structure image URL")
def structure_image(smiles: str = Query(..., description="SMILES string"), size: int = Query(150, ge=50, le=500, description="Image size in pixels")):
    """Returns PubChem URL for 2D structure image of the compound."""
    encoded = quote(smiles, safe="")
    url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/smiles/{encoded}/PNG?image_size={size}x{size}"
    return {"url": url, "smiles": smiles}


# --- Interactions ---

def _generate_timeline(compound_count: int, has_vaccine: bool, tanimoto_avg: float) -> list[dict]:
    """Generate 72h risk/concentration timeline data."""
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
        data.append({
            "hour": h,
            "risk": round(risk * 100),
            "concentration": round(concentration * 100),
            "label": f"{h}h",
        })
    return data


@app.get("/v1/interactions/timeline", tags=["Interactions"], summary="Get prediction timeline")
def get_timeline(
    compound_count: int = Query(2, ge=1, le=10, description="Number of compounds"),
    has_vaccine: bool = Query(False),
    tanimoto_avg: float = Query(0.5, ge=0, le=1),
):
    """Returns 72-hour risk and concentration curve data for the interaction timeline graph."""
    return {"timeline": _generate_timeline(compound_count, has_vaccine, tanimoto_avg)}


@app.post("/v1/interactions/timeline", tags=["Interactions"], summary="Get prediction timeline (POST)")
def post_timeline(req: TimelineRequest):
    """Returns 72-hour risk and concentration curve data for the interaction timeline graph."""
    return {"timeline": _generate_timeline(req.compound_count, req.has_vaccine, req.tanimoto_avg)}


# --- Predict (fallback when no PharmaRisk) ---

if not PHARMARISK_LOADED:
    @app.post("/v1/predict", tags=["Predict"], summary="Predict")
    def predict(req: PredictRequest):
        """Predict interaction risk for a drug combination."""
        return predict_interaction_logic(req)

    @app.post("/v1/predict/natural", tags=["Predict"], summary="Predict Natural")
    def predict_natural(req: NaturalPredictRequest):
        """Predict risk from natural language (e.g. 'Aspirin and Ibuprofen' or 'CYP2C19 *2 with clopidogrel')."""
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            return {"risk_score": 0.5, "confidence": 70, "recommendation": "Add OPENAI_API_KEY for natural language prediction.", "compounds": [], "source": "fallback"}
        try:
            from openai import OpenAI
            client = OpenAI(api_key=api_key)
            r = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a pharmacogenomics risk assessor. Given a drug combination or gene-drug query, return a JSON with: risk_score (0-1), confidence (0-100), recommendation (short clinical text), compounds (list of drug names if any)."},
                    {"role": "user", "content": req.query}
                ],
                max_tokens=300,
            )
            import json
            text = r.choices[0].message.content
            try:
                if "```" in text:
                    text = text.split("```")[1].replace("json", "").strip()
                data = json.loads(text)
                return {**data, "source": "openai"}
            except json.JSONDecodeError:
                return {"risk_score": 0.5, "confidence": 70, "recommendation": text[:200], "compounds": [], "source": "openai"}
        except Exception as e:
            return {"risk_score": 0.5, "confidence": 50, "recommendation": f"Error: {str(e)}", "compounds": [], "source": "fallback"}


def predict_interaction_logic(req: PredictRequest):
    """Shared logic for predict."""
    pairs = []
    total = 0
    count = 0
    for i in range(len(req.smiles_list)):
        for j in range(i + 1, len(req.smiles_list)):
            sim = _tanimoto(req.smiles_list[i], req.smiles_list[j])
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
        "risk_score": round(avg_tanimoto * 0.5 + (1 - confidence/100) * 0.3, 2),
        "recommendation": "Monitor for metabolic competition. Consider genetic testing if poor metabolizer suspected." if avg_tanimoto > 0.4 else "Low structural overlap. Standard monitoring.",
    }


if not PHARMARISK_LOADED:
    @app.post("/v1/explain", tags=["Explain"], summary="Explain Risk")
    def explain(req: ExplainRequest):
        """Generate mechanistic explanation of predicted risk."""
        return explain_interaction_logic(req)


def explain_interaction_logic(req: ExplainRequest):
    """Shared logic for explain."""
    api_key = os.environ.get("OPENAI_API_KEY")
    fallback = _fallback_explanation(req.compounds, req.tanimoto, req.confidence, req.has_vaccine)
    if not api_key:
        return {"explanation": fallback, "source": "fallback"}
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        vaccine_note = " One or more compounds is a vaccine; include immune modulation." if req.has_vaccine else ""
        r = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a pharmacologist explaining drug-drug interactions. Be concise, use plain language, cite CYP450 and metabolic competition."},
                {"role": "user", "content": f"Explain the interaction between {', '.join(req.compounds)}. Tanimoto: {req.tanimoto:.2f}, confidence: {req.confidence}%.{vaccine_note}"}
            ],
            max_tokens=400,
        )
        return {"explanation": r.choices[0].message.content, "source": "openai"}
    except Exception as e:
        return {"explanation": fallback, "source": "fallback", "error": str(e)}


# --- Interactions (legacy) ---

@app.post("/v1/interactions/predict", tags=["Interactions"], summary="Predict interaction risk")
def predict_interaction(req: PredictRequest):
    """Predict interaction risk for a drug combination. Returns Tanimoto similarity per pair and overall confidence."""
    return predict_interaction_logic(req)


@app.post("/v1/interactions/explain", tags=["Interactions"], summary="AI mechanistic explanation")
def explain_interaction(req: ExplainRequest):
    """Generate mechanistic AI explanation of the predicted interaction."""
    return explain_interaction_logic(req)


@app.post("/v1/interactions/ask", tags=["Interactions"], summary="Ask AI about interactions")
def ask_interaction(req: AskRequest):
    """Answer questions about drug interactions using AI. Pass context (compounds, tanimoto, genes) for better answers."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return {"answer": "OpenAI API key not configured. Set OPENAI_API_KEY for AI answers."}
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


# Serve GeneAI app at / when frontend/build exists (must be last)
if FRONTEND_BUILD.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_BUILD), html=True), name="app")


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
