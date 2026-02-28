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
        {"risk_score": float, "gene_contributions": {gene: float}, "risk_label": str}
    """
    if _real_model and not _using_mock:
        try:
            result = _real_model.predict(genes, drug)
            return result
        except Exception as e:
            logger.error(f"Real model predict failed: {e}, falling back to mock")

    return _mock_predict(genes, drug)


def _mock_predict(genes: list[dict], drug: str) -> dict:
    """Deterministic mock that returns plausible scores based on phenotype keywords."""
    total_score = 5.0
    contributions = {}

    for gene in genes:
        phenotype = gene.get("phenotype", "").lower()
        name = gene["name"]

        if "poor" in phenotype or "no function" in phenotype:
            contrib = 0.8
            total_score = max(total_score, 7.5)
        elif "intermediate" in phenotype or "decreased" in phenotype:
            contrib = 0.5
            total_score = max(total_score, 5.5)
        elif "rapid" in phenotype or "ultrarapid" in phenotype:
            contrib = 0.6
            total_score = max(total_score, 6.5)
        elif "normal" in phenotype:
            contrib = 0.1
            total_score = min(total_score, 3.0)
        else:
            contrib = 0.3

        contributions[name] = contrib

    total_score = round(min(10.0, max(1.0, total_score)), 1)

    if total_score >= 8:
        label = "High Risk"
    elif total_score >= 6:
        label = "Moderate Risk"
    elif total_score >= 4:
        label = "Low-Moderate Risk"
    else:
        label = "Low Risk"

    return {
        "risk_score": total_score,
        "gene_contributions": contributions,
        "risk_label": label,
    }


def is_model_loaded() -> bool:
    return not _using_mock
