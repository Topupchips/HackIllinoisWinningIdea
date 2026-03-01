from fastapi import APIRouter, HTTPException, Query

from api.config import DEFAULT_LIMIT, DEFAULT_PAGE, MAX_LIMIT
from api.models.responses import DrugListResponse, DrugResponse, ErrorResponse
from api.services.data_service import data_service

router = APIRouter(tags=["Drugs"])


def _drug_to_response(d: dict) -> DrugResponse:
    return DrugResponse(
        drug_id=d["drug_id"],
        drug_name=d["drug_name"],
        pharmgkb_id=d.get("pharmgkb_id", ""),
        rxnorm_id=d.get("rxnorm_id", ""),
        drugbank_id=d.get("drugbank_id", ""),
        smiles=data_service.smiles_by_id.get(d["drug_id"]),
    )


@router.get(
    "/drugs",
    response_model=DrugListResponse,
    responses={400: {"model": ErrorResponse}},
)
async def list_drugs(
    search: str | None = Query(None, description="Search drug names"),
    page: int = Query(DEFAULT_PAGE, ge=1),
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
):
    if search:
        results = data_service.search_drugs(search)
        suggestion = (
            data_service.suggest_drug(search) if not results else None
        )
    else:
        results = data_service.drugs
        suggestion = None

    total = len(results)
    start = (page - 1) * limit
    page_results = results[start : start + limit]

    return DrugListResponse(
        drugs=[_drug_to_response(d) for d in page_results],
        total=total,
        page=page,
        limit=limit,
        suggestion=f"Did you mean '{suggestion}'?" if suggestion else None,
    )


@router.get(
    "/drugs/{drug_id}",
    response_model=DrugResponse,
    responses={404: {"model": ErrorResponse}},
)
async def get_drug(drug_id: str):
    drug = data_service.drug_by_id.get(drug_id)
    if not drug:
        # Try by name
        drug = data_service.drug_by_name.get(drug_id.lower())
    if not drug:
        suggestion = data_service.suggest_drug(drug_id)
        detail = f"Did you mean '{suggestion}'?" if suggestion else None
        raise HTTPException(status_code=404, detail=detail or "Drug not found")
    return _drug_to_response(drug)
