"""
llm_labeler.py

Converts raw JSON (gene, activity_level, medicine, text) into
labeled JSON (gene, activity_level, medicine, risk_score) using GPT-4.

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
from openai import OpenAI

# ── Prompts ───────────────────────────────────────────────────────────────────

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

# ── Core labeling function ────────────────────────────────────────────────────

def label_single(client: OpenAI, gene: str, activity_level: float,
                 medicine: str, text: str, retries: int = 3) -> float:
    """Call GPT-4 to assign a 1-10 risk score to one record."""
    user_message = USER_TEMPLATE.format(
        gene=gene,
        activity_level=activity_level,
        medicine=medicine,
        text=text
    )

    for attempt in range(retries):
        try:
            response = client.chat.completions.create(
                model="gpt-4",
                temperature=0,
                max_tokens=5,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user",   "content": user_message},
                ]
            )
            raw   = response.choices[0].message.content.strip()
            score = float(raw)
            assert 1.0 <= score <= 10.0, f"Score out of range: {score}"
            return round(score, 1)

        except (ValueError, AssertionError) as e:
            print(f"  [warn] Bad response on attempt {attempt+1}: {e}")
            time.sleep(1)
        except Exception as e:
            print(f"  [error] API error on attempt {attempt+1}: {e}")
            time.sleep(2)

    print(f"  [failed] Could not label: gene={gene}, medicine={medicine}")
    return -1.0


def label_dataset(input_path: str, output_path: str, api_key: str):
    """Load raw JSON, label every row with a risk score, save labeled JSON."""
    client = OpenAI(api_key=api_key)

    with open(input_path, "r") as f:
        raw_data = json.load(f)

    print(f"Loaded {len(raw_data)} records from {input_path}")

    labeled = []
    failed  = 0

    for i, record in enumerate(raw_data):
        gene           = record["gene"]
        activity_level = record["activity_level"]
        medicine       = record["medicine"]
        text           = record["text"]

        print(f"[{i+1}/{len(raw_data)}] {gene} (activity={activity_level}) | {medicine}")

        score = label_single(client, gene, activity_level, medicine, text)
        if score == -1.0:
            failed += 1

        labeled.append({
            "gene":           gene,
            "activity_level": activity_level,
            "medicine":       medicine,
            "risk_score":     score,
        })

        time.sleep(0.3)  # rate limit buffer

    with open(output_path, "w") as f:
        json.dump(labeled, f, indent=2)

    print(f"\nDone. {len(labeled)} records saved to {output_path}")
    print(f"Failed / flagged for review: {failed}")


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Label pharmacogenomics data with GPT-4")
    parser.add_argument("--input",   required=True, help="Path to raw JSON file")
    parser.add_argument("--output",  required=True, help="Path to save labeled JSON file")
    parser.add_argument("--api_key", required=True, help="OpenAI API key")
    args = parser.parse_args()

    label_dataset(args.input, args.output, args.api_key)
