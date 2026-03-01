"""Wraps model.predict() with mock fallback."""

import logging

logger = logging.getLogger(__name__)

_real_model = None
_using_mock = True


def load_model():
    """Try to load Charles's PharmaRiskModel; fall back to mock."""
    global _real_model, _using_mock
    try:
        import sys
        from api.config import BASE_DIR

        # model_api.py and embeddings/ are at repo root
        if str(BASE_DIR) not in sys.path:
            sys.path.insert(0, str(BASE_DIR))

        from model_api import PharmaRiskModel

        _real_model = PharmaRiskModel(
            model_path=str(BASE_DIR / "set_transformer.pt"),
            gene_emb_path=str(BASE_DIR / "embeddings" / "gene_embeddings.pkl"),
            drug_emb_path=str(BASE_DIR / "embeddings" / "drug_embeddings.pkl"),
            target_flags_path=str(BASE_DIR / "embeddings" / "target_flags.pkl"),
            xgboost_path=str(BASE_DIR / "xgboost_baseline.json"),
        )
        _using_mock = False
        logger.info("Real model loaded successfully")
    except Exception as e:
        logger.warning(f"Could not load real model ({e}), using mock")
        _real_model = None
        _using_mock = True


def predict(genes: list[dict], drug: str) -> dict:
    """Return per-gene CPIC results. Uses real model if available, else mock.

    Args:
        genes: List of {"name": "CYP2D6", "phenotype": "Poor Metabolizer"}
        drug: Drug name string

    Returns:
        {"results": [{"gene", "activity_level", "medicine", "text"}, ...]}
    """
    if _real_model and not _using_mock:
        try:
            return _predict_real(genes, drug)
        except Exception as e:
            logger.error(f"Real model predict failed: {e}, falling back to mock")

    return _mock_predict(genes, drug)


def _predict_real(genes: list[dict], drug: str) -> dict:
    """Call Charles's model and build per-gene results."""
    model_genes = [
        {"name": g["name"], "activity_level": _phenotype_to_activity(g.get("phenotype", ""))}
        for g in genes
    ]

    raw = _real_model.predict(model_genes, drug)

    if raw.get("error") or raw.get("risk_score") is None:
        raise ValueError(raw.get("error", "Model returned no score"))

    results = []
    for g in genes:
        results.append({
            "gene": g["name"],
            "activity_level": _phenotype_to_activity(g.get("phenotype", "")),
            "medicine": drug,
            "text": "",  # enriched with CPIC text by the route
        })

    return {"results": results}


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
    """Deterministic mock returning per-gene results with CPIC-style text."""
    results = []

    for gene in genes:
        phenotype = gene.get("phenotype", "").lower()
        name = gene["name"]
        activity = _phenotype_to_activity(phenotype)

        if "poor" in phenotype or "no function" in phenotype:
            text = f"Contraindicated. {name} poor/no function significantly alters metabolism of {drug}."
        elif "intermediate" in phenotype or "decreased" in phenotype:
            text = f"Consider dose reduction. {name} intermediate function may reduce metabolism of {drug}."
        elif "rapid" in phenotype or "ultrarapid" in phenotype:
            text = f"Increased risk. {name} ultrarapid function may cause rapid conversion of {drug}."
        elif "normal" in phenotype:
            text = f"Standard dosing recommended. No significant pharmacogenomic interaction expected for {name} and {drug}."
        else:
            text = f"Indeterminate. Insufficient data for {name} interaction with {drug}."

        results.append({
            "gene": name,
            "activity_level": activity,
            "medicine": drug,
            "text": text,
        })

    return {"results": results}


def is_model_loaded() -> bool:
    return not _using_mock
