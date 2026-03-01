"""OpenAI integration for natural language parsing and risk explanation."""

import json
import logging
import os

import httpx

from api.config import OPENAI_API_KEY, OPENAI_MODEL

logger = logging.getLogger(__name__)

VALID_GENES = [
    "ABCG2", "CACNA1S", "CFTR", "CYP2B6", "CYP2C19", "CYP2C9", "CYP2D6",
    "CYP3A5", "DPYD", "G6PD", "HLA-A", "HLA-B", "MT-RNR1", "NAT2",
    "NUDT15", "RYR1", "SLCO1B1", "TPMT", "UGT1A1",
]

VALID_PHENOTYPES = [
    "Normal Metabolizer", "Intermediate Metabolizer", "Poor Metabolizer",
    "Rapid Metabolizer", "Ultrarapid Metabolizer", "Indeterminate",
    "Normal Function", "Decreased Function", "No Function",
    "Deficient", "Variable",
]

_explain_cache: dict[str, str] = {}


async def parse_natural_input(query: str) -> dict | None:
    """Parse natural language into structured gene/drug data via OpenAI."""
    if not OPENAI_API_KEY:
        logger.warning("OPENAI_API_KEY not set, cannot parse natural input")
        return None

    system_prompt = f"""You are a pharmacogenomics parser. Extract gene names and drug from the user's input.

Valid genes: {', '.join(VALID_GENES)}
Valid phenotypes: {', '.join(VALID_PHENOTYPES)}

Respond ONLY with valid JSON (no markdown):
{{"genes": [{{"name": "GENE_SYMBOL", "phenotype": "Phenotype"}}], "drug": "drug_name"}}

If you cannot parse the input, respond with: {{"error": "Could not parse input"}}"""

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {OPENAI_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": OPENAI_MODEL,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": query},
                    ],
                    "temperature": 0,
                },
            )
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
            parsed = json.loads(content)
            if "error" in parsed:
                return None
            return parsed
    except Exception as e:
        logger.error(f"OpenAI parse_natural_input failed: {e}")
        return None


async def explain_risk(
    drug: str, risk_score: float, gene_contributions: dict[str, float]
) -> str | None:
    """Generate plain English explanation of risk via OpenAI."""
    cache_key = f"{drug}:{risk_score}:{sorted(gene_contributions.items())}"
    if cache_key in _explain_cache:
        return _explain_cache[cache_key]

    if not OPENAI_API_KEY:
        logger.warning("OPENAI_API_KEY not set, returning template explanation")
        return _fallback_explanation(drug, risk_score, gene_contributions)

    genes_str = ", ".join(
        f"{gene} (contribution: {score:.0%})"
        for gene, score in gene_contributions.items()
    )

    system_prompt = (
        "You are a pharmacogenomics counselor. Explain drug risk in plain English. "
        "2-3 sentences, under 100 words. No medical jargon. "
        "Mention what could happen and what to discuss with their doctor."
    )
    user_prompt = (
        f"Drug: {drug}, Risk score: {risk_score}/10, "
        f"Contributing genes: {genes_str}"
    )

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {OPENAI_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": OPENAI_MODEL,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "temperature": 0.3,
                    "max_tokens": 150,
                },
            )
            resp.raise_for_status()
            explanation = resp.json()["choices"][0]["message"]["content"].strip()
            _explain_cache[cache_key] = explanation
            return explanation
    except Exception as e:
        logger.error(f"OpenAI explain_risk failed: {e}")
        return _fallback_explanation(drug, risk_score, gene_contributions)


def _fallback_explanation(
    drug: str, risk_score: float, gene_contributions: dict[str, float]
) -> str:
    """Template explanation when OpenAI is unavailable."""
    top_gene = max(gene_contributions, key=gene_contributions.get) if gene_contributions else "your genes"
    if risk_score >= 7:
        return (
            f"Your genetic profile suggests a higher risk with {drug}. "
            f"Your {top_gene} gene variant may cause your body to process this drug "
            f"differently, potentially leading to adverse effects. "
            f"Please discuss alternative options with your doctor."
        )
    elif risk_score >= 4:
        return (
            f"Your genetic profile shows moderate considerations for {drug}. "
            f"Your {top_gene} gene may affect how you respond to this medication. "
            f"Talk to your doctor about whether dose adjustments might be helpful."
        )
    else:
        return (
            f"Based on your genetic profile, {drug} appears to be a standard option. "
            f"No major genetic factors were identified that would significantly alter "
            f"your response. Follow your doctor's prescribed dosing."
        )
