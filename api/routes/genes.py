from fastapi import APIRouter, HTTPException, Query

from api.config import DEFAULT_LIMIT, DEFAULT_PAGE, MAX_LIMIT
from api.models.responses import (
    AlleleInfo,
    ErrorResponse,
    GeneDetailResponse,
    GeneListResponse,
    GeneResponse,
)
from api.services.data_service import data_service

router = APIRouter(tags=["Genes"])


@router.get(
    "/genes",
    response_model=GeneListResponse,
    responses={400: {"model": ErrorResponse}},
)
async def list_genes(
    search: str | None = Query(None, description="Search gene symbols"),
    page: int = Query(DEFAULT_PAGE, ge=1),
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
):
    if search:
        results = data_service.search_genes(search)
        suggestion = data_service.suggest_gene(search) if not results else None
    else:
        results = list(data_service.genes.values())
        suggestion = None

    total = len(results)
    start = (page - 1) * limit
    page_results = results[start : start + limit]

    return GeneListResponse(
        genes=[
            GeneResponse(
                symbol=g["symbol"],
                phenotypes=g["phenotypes"],
                recommendation_count=g["recommendation_count"],
            )
            for g in page_results
        ],
        total=total,
        page=page,
        limit=limit,
        suggestion=f"Did you mean '{suggestion}'?" if suggestion else None,
    )


@router.get(
    "/genes/{symbol}",
    response_model=GeneDetailResponse,
    responses={404: {"model": ErrorResponse}},
)
async def get_gene(symbol: str):
    gene = data_service.genes.get(symbol.upper())
    if not gene:
        suggestion = data_service.suggest_gene(symbol)
        detail = f"Did you mean '{suggestion}'?" if suggestion else None
        raise HTTPException(status_code=404, detail=detail or "Gene not found")

    alleles = data_service.alleles_by_gene.get(symbol.upper(), [])
    return GeneDetailResponse(
        symbol=gene["symbol"],
        phenotypes=gene["phenotypes"],
        recommendation_count=gene["recommendation_count"],
        alleles=[
            AlleleInfo(
                allele_name=a.get("allele_name", ""),
                function_status=a.get("function_status", ""),
                clinical_function=a.get("clinical_function", ""),
                activity_value=a.get("activity_value", ""),
            )
            for a in alleles
        ],
    )


@router.get(
    "/genes/{symbol}/alleles",
    response_model=list[AlleleInfo],
    responses={404: {"model": ErrorResponse}},
)
async def get_gene_alleles(symbol: str):
    if symbol.upper() not in data_service.genes:
        raise HTTPException(status_code=404, detail="Gene not found")

    alleles = data_service.alleles_by_gene.get(symbol.upper(), [])
    return [
        AlleleInfo(
            allele_name=a.get("allele_name", ""),
            function_status=a.get("function_status", ""),
            clinical_function=a.get("clinical_function", ""),
            activity_value=a.get("activity_value", ""),
        )
        for a in alleles
    ]
