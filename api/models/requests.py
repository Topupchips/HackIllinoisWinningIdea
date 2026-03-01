from pydantic import BaseModel, Field


class GeneInput(BaseModel):
    name: str = Field(..., example="CYP2D6")
    phenotype: str = Field(..., example="Poor Metabolizer")

    model_config = {"json_schema_extra": {"examples": [{"name": "CYP2D6", "phenotype": "Poor Metabolizer"}]}}


class PredictRequest(BaseModel):
    genes: list[GeneInput] = Field(..., min_length=1)
    drug: str = Field(..., example="codeine")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "genes": [{"name": "CYP2D6", "phenotype": "Poor Metabolizer"}],
                    "drug": "codeine",
                }
            ]
        }
    }


class NaturalPredictRequest(BaseModel):
    query: str = Field(
        ...,
        example="I'm a CYP2D6 poor metabolizer taking codeine",
    )


class ExplainRequest(BaseModel):
    drug: str = Field(..., example="codeine")
    risk_score: float = Field(..., ge=0, le=10, example=8.5)
    gene_contributions: dict[str, float] = Field(
        ...,
        example={"CYP2D6": 0.85, "CYP3A4": 0.12},
    )
