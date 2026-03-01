from fastapi import APIRouter

from api.models.responses import HealthResponse, ValidateResponse
from api.services import model_service
from api.services.data_service import data_service

router = APIRouter(tags=["Health"])


@router.get("/health", response_model=HealthResponse)
async def health_check():
    return HealthResponse(
        status="healthy",
        model_loaded=model_service.is_model_loaded(),
        data_loaded=len(data_service.drugs) > 0,
        drug_count=len(data_service.drugs),
        gene_count=len(data_service.genes),
    )


@router.get("/validate", response_model=ValidateResponse)
async def validate_data():
    return ValidateResponse(
        valid=len(data_service.drugs) > 0 and len(data_service.recommendations) > 0,
        drugs_loaded=len(data_service.drugs),
        recommendations_loaded=len(data_service.recommendations),
        genes_available=sorted(data_service.genes.keys()),
    )
