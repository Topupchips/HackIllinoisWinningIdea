from fastapi import APIRouter, HTTPException

from api.models.requests import ExplainRequest
from api.models.responses import ErrorResponse, ExplainResponse
from api.services import openai_service

router = APIRouter(tags=["Explain"])


@router.post(
    "/explain",
    response_model=ExplainResponse,
    responses={500: {"model": ErrorResponse}},
)
async def explain_risk(req: ExplainRequest):
    explanation = await openai_service.explain_risk(
        drug=req.drug,
        risk_score=req.risk_score,
        gene_contributions=req.gene_contributions,
    )
    if not explanation:
        raise HTTPException(status_code=500, detail="Could not generate explanation")

    return ExplainResponse(explanation=explanation)
