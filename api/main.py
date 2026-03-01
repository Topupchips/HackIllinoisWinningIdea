import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from api.routes import drugs, explain, genes, health, predict
from api.services import model_service
from api.services.data_service import data_service

STATIC_DIR = Path(__file__).resolve().parent / "static"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Loading data...")
    data_service.load_all()
    logger.info(
        f"Data loaded: {len(data_service.drugs)} drugs, "
        f"{len(data_service.genes)} genes, "
        f"{len(data_service.recommendations)} recommendations"
    )

    logger.info("Loading model...")
    model_service.load_model()

    yield

    logger.info("Shutting down")


app = FastAPI(
    title="PharmaRisk API",
    description=(
        "Pharmacogenomics drug risk prediction API. "
        "Takes a patient's gene profile and a drug, returns a risk score "
        "with clinical recommendations from CPIC guidelines."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# X-Response-Time + request logging middleware
@app.middleware("http")
async def add_response_time(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = (time.perf_counter() - start) * 1000
    response.headers["X-Response-Time"] = f"{elapsed_ms:.1f}ms"
    logger.info(f"{request.method} {request.url.path} -> {response.status_code} ({elapsed_ms:.1f}ms)")
    return response


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled error on {request.url.path}: {exc}")
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "detail": str(exc)},
    )


# Include routers
app.include_router(health.router)
app.include_router(drugs.router)
app.include_router(genes.router)
app.include_router(predict.router)
app.include_router(explain.router)

# Static files + custom docs
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

@app.get("/apidocs", include_in_schema=False)
async def apidocs():
    return FileResponse(STATIC_DIR / "docs" / "index.html")

@app.get("/apidocs/endpoints", include_in_schema=False)
async def apidocs_endpoints():
    return FileResponse(STATIC_DIR / "docs" / "endpoints.html")
