from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    error: str = Field(..., example="Drug not found")
    detail: str | None = Field(None, example="No drug matching 'xyz' was found")


class GeneDrugResult(BaseModel):
    gene: str = Field(..., example="CYP2D6")
    activity_level: float = Field(..., ge=0.0, example=0.0)
    medicine: str = Field(..., example="codeine")
    text: str = Field(
        ...,
        example="Avoid codeine use because of possibility of diminished analgesia.",
    )


PredictResponse = list[GeneDrugResult]


class DrugResponse(BaseModel):
    drug_id: str = Field(..., example="RxNorm:2670")
    drug_name: str = Field(..., example="codeine")
    pharmgkb_id: str = Field("", example="PA449088")
    rxnorm_id: str = Field("", example="2670")
    drugbank_id: str = Field("", example="DB00318")
    smiles: str | None = Field(None, example="COC1=CC=C2C(=C1)C3=CC=C(O)C=C3CC2N")


class DrugListResponse(BaseModel):
    drugs: list[DrugResponse]
    total: int = Field(..., example=323)
    page: int = Field(..., example=1)
    limit: int = Field(..., example=20)
    suggestion: str | None = Field(None, example="Did you mean 'codeine'?")


class AlleleInfo(BaseModel):
    allele_name: str = Field(..., example="*4")
    function_status: str = Field("", example="No function")
    clinical_function: str = Field("", example="No function")
    activity_value: str = Field("", example="0.0")


class GeneResponse(BaseModel):
    symbol: str = Field(..., example="CYP2D6")
    phenotypes: list[str] = Field(
        ...,
        example=["Normal Metabolizer", "Poor Metabolizer"],
    )
    recommendation_count: int = Field(..., example=42)


class GeneDetailResponse(GeneResponse):
    alleles: list[AlleleInfo] = Field(default_factory=list)


class GeneListResponse(BaseModel):
    genes: list[GeneResponse]
    total: int = Field(..., example=17)
    page: int = Field(..., example=1)
    limit: int = Field(..., example=20)
    suggestion: str | None = None


class ExplainResponse(BaseModel):
    explanation: str = Field(
        ...,
        example="Your genetic profile suggests a higher risk with codeine. "
        "Your body may process this drug differently, which could lead to "
        "reduced effectiveness or increased side effects. "
        "Discuss alternatives with your doctor.",
    )


class HealthResponse(BaseModel):
    status: str = Field(..., example="healthy")
    model_loaded: bool = Field(..., example=True)
    data_loaded: bool = Field(..., example=True)
    drug_count: int = Field(..., example=323)
    gene_count: int = Field(..., example=17)


class ValidateResponse(BaseModel):
    valid: bool = Field(..., example=True)
    drugs_loaded: int = Field(..., example=323)
    recommendations_loaded: int = Field(..., example=2129)
    genes_available: list[str] = Field(..., example=["CYP2D6", "CYP2C19"])
