from fastapi import APIRouter, HTTPException

from api.models.requests import NaturalPredictRequest, PredictRequest
from api.models.responses import (
    ErrorResponse,
    GeneContribution,
    PredictResponse,
)
from api.services import model_service, openai_service
from api.services.data_service import data_service

router = APIRouter(tags=["Predict"])


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

    # Find matching CPIC recommendation text
    cpic_rec = None
    rec_text = ""
    for gene in req.genes:
        recs = data_service.get_recommendations_for_drug(gene.name, req.drug)
        if recs:
            # Find best match by phenotype
            for r in recs:
                phenotype_field = r.get("phenotype", "").lower()
                if gene.phenotype.lower() in phenotype_field:
                    cpic_rec = r.get("recommendation_text", "")
                    rec_text = r.get("combined_text", "")
                    break
            if not cpic_rec and recs:
                cpic_rec = recs[0].get("recommendation_text", "")
                rec_text = recs[0].get("combined_text", "")

    return PredictResponse(
        drug=req.drug,
        risk_score=result["risk_score"],
        risk_label=result["risk_label"],
        gene_contributions=[
            GeneContribution(
                gene=gene,
                phenotype=next(
                    (g.phenotype for g in req.genes if g.name == gene), ""
                ),
                contribution=contrib,
            )
            for gene, contrib in result["gene_contributions"].items()
        ],
        recommendation_text=rec_text,
        cpic_recommendation=cpic_rec,
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

    # Build a PredictRequest and delegate
    from api.models.requests import GeneInput, PredictRequest as PR

    predict_req = PR(
        genes=[GeneInput(name=g["name"], phenotype=g["phenotype"]) for g in parsed["genes"]],
        drug=parsed["drug"],
    )
    return await predict(predict_req)
