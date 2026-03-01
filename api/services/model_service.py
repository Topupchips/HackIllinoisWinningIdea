"""Wraps model.predict() with mock fallback."""

import logging

logger = logging.getLogger(__name__)

_real_model = None
_using_mock = True


def load_model():
    """Try to load the real model; fall back to mock."""
    global _real_model, _using_mock
    try:
        from model.model import PharmaRiskModel
        from api.config import MODEL_DIR

        _real_model = PharmaRiskModel(
            transformer_path=str(MODEL_DIR / "set_transformer.pt"),
            xgboost_path=str(MODEL_DIR / "xgboost_baseline.json"),
            gene_embeddings_path=str(MODEL_DIR / "gene_embeddings.pkl"),
            drug_embeddings_path=str(MODEL_DIR / "drug_embeddings.pkl"),
            target_flags_path=str(MODEL_DIR / "target_flags.pkl"),
        )
        _using_mock = False
        logger.info("Real model loaded successfully")
    except Exception as e:
        logger.warning(f"Could not load real model ({e}), using mock")
        _real_model = None
        _using_mock = True


def predict(genes: list[dict], drug: str) -> dict:
    """Return risk prediction. Uses real model if available, else mock.

    Args:
        genes: List of {"name": "CYP2D6", "phenotype": "Poor Metabolizer"}
        drug: Drug name string

    Returns:
        {
          "results": [{"gene", "activity_level", "medicine", "text", "risk_score", "contribution"}, ...],
          "overall_risk_score": float,
          "risk_label": str
        }
    """
    if _real_model and not _using_mock:
        try:
            result = _real_model.predict(genes, drug)
            return result
        except Exception as e:
            logger.error(f"Real model predict failed: {e}, falling back to mock")

    return _mock_predict(genes, drug)


# Phenotype -> activity level mapping (CPIC convention)
_ACTIVITY_MAP = {
    "no function": 0.0,
    "poor metabolizer": 0.0,
    "decreased function": 0.5,
    "intermediate metabolizer": 1.0,
    "normal metabolizer": 1.0,
    "normal function": 1.0,
    "rapid metabolizer": 1.5,
    "ultrarapid metabolizer": 2.0,
    "increased function": 2.0,
}


def _phenotype_to_activity(phenotype: str) -> float:
    """Map phenotype string to CPIC activity level (0.0 - 2.0)."""
    p = phenotype.lower().strip()
    for key, val in _ACTIVITY_MAP.items():
        if key in p:
            return val
    return 1.0  # default normal


def _mock_predict(genes: list[dict], drug: str) -> dict:
    """Deterministic mock returning per-gene results with activity levels."""
    results = []

    for gene in genes:
        phenotype = gene.get("phenotype", "").lower()
        name = gene["name"]
        activity = _phenotype_to_activity(phenotype)

        if "poor" in phenotype or "no function" in phenotype:
            risk = 8.0
            contrib = 0.8
            text = f"Contraindicated. {name} poor/no function significantly alters metabolism of {drug}."
        elif "intermediate" in phenotype or "decreased" in phenotype:
            risk = 5.5
            contrib = 0.5
            text = f"Consider dose reduction. {name} intermediate function may reduce metabolism of {drug}."
        elif "rapid" in phenotype or "ultrarapid" in phenotype:
            risk = 7.0
            contrib = 0.6
            text = f"Increased risk. {name} ultrarapid function may cause rapid conversion of {drug}."
        elif "normal" in phenotype:
            risk = 2.0
            contrib = 0.1
            text = f"Standard dosing recommended. No significant pharmacogenomic interaction expected for {name} and {drug}."
        else:
            risk = 5.0
            contrib = 0.3
            text = f"Indeterminate. Insufficient data for {name} interaction with {drug}."

        results.append({
            "gene": name,
            "activity_level": activity,
            "medicine": drug,
            "text": text,
            "risk_score": risk,
            "contribution": contrib,
        })

    # Overall score = max of individual gene risks
    overall = max(r["risk_score"] for r in results) if results else 5.0
    overall = round(min(10.0, max(1.0, overall)), 1)

    if overall >= 8:
        label = "High Risk"
    elif overall >= 6:
        label = "Moderate Risk"
    elif overall >= 4:
        label = "Low-Moderate Risk"
    else:
        label = "Low Risk"

    return {
        "results": results,
        "overall_risk_score": overall,
        "risk_label": label,
    }


def is_model_loaded() -> bool:
    return not _using_mock
