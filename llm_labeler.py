"""
llm_labeler.py

Converts raw JSON (gene, activity_level, medicine, text) into
labeled JSON (gene, activity_level, medicine, risk_score) using GPT-4.

Uses async parallel requests (5 concurrent) to speed up processing.
Safely handles OpenAI rate limits with automatic retry.

Input JSON format:
[
    {"gene": "CYP2D6", "activity_level": 0.0, "medicine": "codeine", "text": "Contraindicated..."},
    ...
]

Output JSON format:
[
    {"gene": "CYP2D6", "activity_level": 0.0, "medicine": "codeine", "risk_score": 9.5},
    ...
]

Usage:
    python llm_labeler.py --input raw_data.json --output labeled_data.json --api_key YOUR_KEY
"""

import json
import time
import argparse
import asyncio
from openai import AsyncOpenAI

# ── Configuration ─────────────────────────────────────────────────────────────

MAX_CONCURRENT = 5      # safe for GPT-4 rate limits
RETRY_LIMIT    = 3
RETRY_DELAY    = 2.0    # seconds to wait after a rate limit error

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


# ── Async single label ────────────────────────────────────────────────────────

async def label_single_async(client: AsyncOpenAI,
                              semaphore: asyncio.Semaphore,
                              record: dict,
                              index: int,
                              total: int) -> dict:
    """
    Label one record asynchronously.
    Semaphore limits to MAX_CONCURRENT requests at a time.
    """
    gene           = record["gene"]
    activity_level = record["activity_level"]
    medicine       = record["medicine"]
    text           = record["text"]

    user_message = USER_TEMPLATE.format(
        gene=gene,
        activity_level=activity_level,
        medicine=medicine,
        text=text
    )

    async with semaphore:
        for attempt in range(RETRY_LIMIT):
            try:
                response = await client.chat.completions.create(
                    model="gpt-4o-mini",
                    temperature=0,
                    max_tokens=5,
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user",   "content": user_message},
                    ]
                )
                raw   = response.choices[0].message.content.strip()
                score = float(raw)
                assert 1.0 <= score <= 10.0, f"Out of range: {score}"

                print(f"[{index+1}/{total}] {gene} | {medicine} → {score}")
                return {
                    "gene":           gene,
                    "activity_level": activity_level,
                    "medicine":       medicine,
                    "risk_score":     round(score, 1),
                }

            except (ValueError, AssertionError) as e:
                print(f"  [warn] Bad response for {gene}|{medicine} attempt {attempt+1}: {e}")
                await asyncio.sleep(1)

            except Exception as e:
                error_str = str(e).lower()
                if "rate limit" in error_str or "429" in error_str:
                    print(f"  [rate limit] Waiting {RETRY_DELAY}s before retry...")
                    await asyncio.sleep(RETRY_DELAY)
                else:
                    print(f"  [error] {gene}|{medicine} attempt {attempt+1}: {e}")
                    await asyncio.sleep(1)

    # All retries failed
    print(f"  [failed] {gene} | {medicine}")
    return {
        "gene":           gene,
        "activity_level": activity_level,
        "medicine":       medicine,
        "risk_score":     -1.0,
    }


# ── Main async runner ─────────────────────────────────────────────────────────

async def label_dataset_async(input_path: str, output_path: str, api_key: str):
    client    = AsyncOpenAI(api_key=api_key)
    semaphore = asyncio.Semaphore(MAX_CONCURRENT)

    with open(input_path, "r") as f:
        raw_data = json.load(f)

    total = len(raw_data)
    print(f"Loaded {total} records from {input_path}")
    print(f"Running with {MAX_CONCURRENT} concurrent requests...")

    start = time.time()

    tasks   = [
        label_single_async(client, semaphore, record, i, total)
        for i, record in enumerate(raw_data)
    ]
    labeled = await asyncio.gather(*tasks)

    elapsed = time.time() - start
    failed  = sum(1 for r in labeled if r["risk_score"] == -1.0)

    with open(output_path, "w") as f:
        json.dump(labeled, f, indent=2)

    print(f"\nDone in {elapsed/60:.1f} minutes.")
    print(f"{total} records saved to {output_path}")
    print(f"Failed / flagged for review: {failed}")


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Label pharmacogenomics data with GPT-4")
    parser.add_argument("--input",   required=True, help="Path to raw JSON file")
    parser.add_argument("--output",  required=True, help="Path to save labeled JSON file")
    parser.add_argument("--api_key", required=True, help="OpenAI API key")
    args = parser.parse_args()

    asyncio.run(label_dataset_async(args.input, args.output, args.api_key))
