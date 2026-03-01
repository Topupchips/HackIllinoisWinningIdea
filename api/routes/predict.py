from fastapi import APIRouter, HTTPException

from api.models.requests import NaturalPredictRequest, PredictRequest
from api.models.responses import (
    ErrorResponse,
    GeneDrugResult,
    PredictResponse,
)
from api.services import model_service, openai_service
from api.services.data_service import data_service

router = APIRouter(tags=["Predict"])


def _enrich_with_cpic(result: dict, req_genes: list) -> dict:
    """Override mock text with real CPIC recommendation if available."""
    drug = result["medicine"]
    gene = result["gene"]

    # Find the phenotype the user submitted for this gene
    phenotype = ""
    for g in req_genes:
        if g.name.upper() == gene.upper():
            phenotype = g.phenotype
            break

    recs = data_service.get_recommendations_for_drug(gene, drug)
    if not recs:
        return result

    # Try matching by phenotype first
    for r in recs:
        phenotype_field = r.get("phenotype", "").lower()
        if phenotype.lower() in phenotype_field:
            cpic_text = r.get("recommendation_text", "")
            if cpic_text:
                result["text"] = cpic_text
            return result

    # Fallback to first recommendation
    cpic_text = recs[0].get("recommendation_text", "")
    if cpic_text:
        result["text"] = cpic_text
    return result


@router.post(
    "/predict",
    response_model=PredictResponse,
    responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
async def predict(req: PredictRequest):
    # Validate drug exists
    drug = data_service.drug_by_name.get(req.drug.lower())
    if not drug:
        suggestion = data_service.suggest_drug(req.drug)
        detail = f"Did you mean '{suggestion}'?" if suggestion else "Drug not found"
        raise HTTPException(status_code=404, detail=detail)

    # Validate genes
    for gene in req.genes:
        if gene.name.upper() not in data_service.genes:
            suggestion = data_service.suggest_gene(gene.name)
            detail = f"Did you mean '{suggestion}'?" if suggestion else f"Gene '{gene.name}' not found"
            raise HTTPException(status_code=400, detail=detail)

    # Run prediction
    genes_input = [{"name": g.name, "phenotype": g.phenotype} for g in req.genes]
    result = model_service.predict(genes_input, req.drug)

    # Enrich each gene result with CPIC text when available
    enriched = []
    for r in result["results"]:
        r = _enrich_with_cpic(r, req.genes)
        enriched.append(
            GeneDrugResult(
                gene=r["gene"],
                activity_level=r["activity_level"],
                medicine=r["medicine"],
                text=r["text"],
                risk_score=r["risk_score"],
                contribution=r["contribution"],
            )
        )

    return PredictResponse(
        results=enriched,
        overall_risk_score=result["overall_risk_score"],
        risk_label=result["risk_label"],
    )


@router.post(
    "/predict/natural",
    response_model=PredictResponse,
    responses={422: {"model": ErrorResponse}},
)
async def predict_natural(req: NaturalPredictRequest):
    parsed = await openai_service.parse_natural_input(req.query)
    if not parsed or "genes" not in parsed or "drug" not in parsed:
        raise HTTPException(
            status_code=422,
            detail="Could not parse your input. Try: 'I'm a CYP2D6 poor metabolizer taking codeine'",
        )

    from api.models.requests import GeneInput, PredictRequest as PR

    predict_req = PR(
        genes=[GeneInput(name=g["name"], phenotype=g["phenotype"]) for g in parsed["genes"]],
        drug=parsed["drug"],
    )
    return await predict(predict_req)
