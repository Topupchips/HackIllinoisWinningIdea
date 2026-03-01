"""
llm_relabel.py

Reads data/processed/recommendations_scored.csv, sends each recommendation
to GPT-4o-mini for a continuous risk score (1.0-10.0), and saves:
  1. data/processed/recommendations_llm_scored.csv  (original + llm_risk_score column)
  2. labeled_data.json                              (regenerated with LLM scores)

Usage:
    python scripts/llm_relabel.py \
        --input  data/processed/recommendations_scored.csv \
        --api_key sk-...
"""

import os
import csv
import json
import time
import argparse
import asyncio
from pathlib import Path
from openai import AsyncOpenAI

# ── Configuration ─────────────────────────────────────────────────────────────

MAX_CONCURRENT = 1
RETRY_LIMIT    = 5
RETRY_DELAY    = 10.0

SYSTEM_PROMPT = """
You are a clinical pharmacogenomics expert. Your job is to read a gene-drug
recommendation text and assign a continuous risk score from 1 to 10.

Scoring guide:
  1-3  : Low risk. Standard dosing, no significant interaction expected.
  4-6  : Moderate risk. Use with caution, consider dose adjustment or monitoring.
  7-8  : High risk. Strong recommendation to adjust dose or consider alternative.
  9-10 : Critical risk. Contraindicated or life-threatening interaction known.

Rules:
- Return ONLY a single number between 1.0 and 10.0 (one decimal place).
- No explanation, no punctuation, no extra text.
- Valid response examples: 2.0, 5.5, 9.0
""".strip()

USER_TEMPLATE = """
Gene: {gene}
Activity Level: {activity_level}
Drug: {medicine}
Recommendation: {text}

Risk score (1.0-10.0):
""".strip()


# ── Activity level parsing ────────────────────────────────────────────────────

def parse_activity_level(gene: str, activity_score_raw: str) -> float:
    if not activity_score_raw or not activity_score_raw.strip():
        return 1.0
    try:
        parsed = json.loads(activity_score_raw)
        if isinstance(parsed, dict):
            val = parsed.get(gene.strip().upper())
            if val and val not in ("n/a", "No Result"):
                val_str = str(val).replace("\u2265", "")  # handle ≥ prefix
                return float(val_str)
    except (json.JSONDecodeError, ValueError, TypeError):
        pass
    return 1.0


# ── Async single label ────────────────────────────────────────────────────────

async def label_row_async(client: AsyncOpenAI,
                          semaphore: asyncio.Semaphore,
                          row: dict,
                          index: int,
                          total: int) -> tuple:
    gene           = row["gene"]
    activity_level = parse_activity_level(gene, row["activity_score"])
    medicine       = row["drug_name"]
    text           = row["combined_text"]

    user_message = USER_TEMPLATE.format(
        gene=gene,
        activity_level=activity_level,
        medicine=medicine,
        text=text,
    )

    async with semaphore:
        # Small fixed delay between requests to stay under rate limits
        await asyncio.sleep(0.5)

        for attempt in range(RETRY_LIMIT):
            try:
                response = await client.chat.completions.create(
                    model="gpt-4o-mini",
                    temperature=0,
                    max_tokens=5,
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user",   "content": user_message},
                    ],
                )
                raw   = response.choices[0].message.content.strip()
                score = float(raw)
                assert 1.0 <= score <= 10.0, f"Out of range: {score}"

                print(f"[{index+1}/{total}] {gene} | {medicine} -> {score}")
                return score, activity_level

            except (ValueError, AssertionError) as e:
                print(f"  [warn] Bad response for {gene}|{medicine} attempt {attempt+1}: {e}")
                await asyncio.sleep(2)

            except Exception as e:
                error_str = str(e).lower()
                if "rate limit" in error_str or "429" in error_str:
                    wait = RETRY_DELAY * (attempt + 1)
                    print(f"  [rate limit] Waiting {wait:.0f}s before retry...")
                    await asyncio.sleep(wait)
                else:
                    print(f"  [error] {gene}|{medicine} attempt {attempt+1}: {e}")
                    await asyncio.sleep(2)

    print(f"  [failed] {gene} | {medicine}")
    return -1.0, activity_level


# ── Main async runner ─────────────────────────────────────────────────────────

async def run(input_path: str, api_key: str):
    base_dir   = Path(__file__).resolve().parent.parent
    output_csv = base_dir / "data" / "processed" / "recommendations_llm_scored.csv"
    output_json = base_dir / "labeled_data.json"

    # Read CSV
    with open(input_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows   = list(reader)

    total = len(rows)
    print(f"Loaded {total} records from {input_path}")
    print(f"Running with {MAX_CONCURRENT} concurrent requests (gpt-4o-mini)...")

    client    = AsyncOpenAI(api_key=api_key)
    semaphore = asyncio.Semaphore(MAX_CONCURRENT)

    start = time.time()

    tasks   = [
        label_row_async(client, semaphore, row, i, total)
        for i, row in enumerate(rows)
    ]
    results = await asyncio.gather(*tasks)

    elapsed = time.time() - start

    # Attach LLM scores and build labeled_data.json
    labeled_data = []
    failed = 0

    for row, (llm_score, activity_level) in zip(rows, results):
        row["llm_risk_score"] = str(llm_score)
        if llm_score == -1.0:
            failed += 1

        labeled_data.append({
            "gene":           row["gene"].strip().upper(),
            "activity_level": activity_level,
            "medicine":       row["drug_name"].strip().lower(),
            "risk_score":     round(llm_score, 1),
        })

    # Save CSV
    fieldnames = list(rows[0].keys())
    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    # Save labeled_data.json
    with open(output_json, "w") as f:
        json.dump(labeled_data, f, indent=2)

    print(f"\nDone in {elapsed/60:.1f} minutes.")
    print(f"Saved CSV:  {output_csv}")
    print(f"Saved JSON: {output_json}")
    print(f"Total: {total} | Failed: {failed}")


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Relabel risk scores with GPT-4o-mini")
    parser.add_argument("--input",   required=True, help="Path to recommendations_scored.csv")
    parser.add_argument("--api_key", required=True, help="OpenAI API key")
    args = parser.parse_args()

    asyncio.run(run(args.input, args.api_key))
