"""
Task 2: Engineer risk score labels + combined text column.

Part A: Add risk_score (1-10) based on recommendation_text and strength.
Part B: Create combined_text column concatenating all text fields.

Saves to data/processed/recommendations_scored.csv
"""

import csv
import re
from collections import Counter
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
INPUT_FILE = BASE_DIR / "data" / "processed" / "recommendations.csv"
OUTPUT_FILE = BASE_DIR / "data" / "processed" / "recommendations_scored.csv"


def compute_risk_score(recommendation_text: str, strength: str) -> int:
    """Assign risk score 1-10 based on recommendation text and strength.

    Rules are applied in priority order. If multiple match, highest score wins.
    """
    text = recommendation_text.lower()
    strength_lower = strength.lower().strip()

    scores = []

    # Contraindicated -> 10 (regardless of strength)
    if "contraindicated" in text:
        scores.append(10)

    # "not recommended" or "do not use"
    if "not recommended" in text or "do not use" in text:
        if strength_lower == "strong":
            scores.append(10)
        elif strength_lower == "moderate":
            scores.append(9)
        else:
            scores.append(9)

    # "avoid" (common in this dataset — treat similar to "not recommended")
    if "avoid" in text:
        if strength_lower == "strong":
            scores.append(9)
        elif strength_lower == "moderate":
            scores.append(8)
        else:
            scores.append(7)

    # "consider alternative"
    if "consider alternative" in text or "consider an alternative" in text:
        if strength_lower == "strong":
            scores.append(8)
        elif strength_lower == "moderate":
            scores.append(7)
        else:
            scores.append(7)

    # "reduce dose" with large reduction
    if "reduce dose" in text or "dose reduction" in text or "reduced dose" in text or "lower dose" in text:
        if re.search(r"(50|60|70|75|80|90)\s*%", text):
            scores.append(7)
        elif strength_lower == "strong":
            scores.append(6)
        elif strength_lower == "moderate":
            scores.append(5)
        else:
            scores.append(5)

    # "caution" or "monitor"
    if "caution" in text or "monitor" in text:
        scores.append(4)

    # "standard dosing" or "per standard" or "no change"
    if "standard dosing" in text or "per standard" in text or "no change" in text:
        scores.append(2)

    # "no action"
    if "no action" in text:
        scores.append(1)

    # If multiple rules matched, use highest score
    if scores:
        return max(scores)

    # Default for uncertain/unmatched
    return 5


def build_combined_text(row: dict) -> str:
    """Concatenate text fields with ' | ' separator, skipping empty ones."""
    parts = []
    for field in ["implications_text", "recommendation_text", "dosing_information", "comments"]:
        val = row.get(field, "").strip()
        if val and val.lower() not in ("n/a", "none", ""):
            parts.append(val)
    return " | ".join(parts)


def main():
    print(f"Reading: {INPUT_FILE}")

    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    print(f"Processing {len(rows)} recommendations...\n")

    score_counts = Counter()

    for row in rows:
        # Part A: risk score
        score = compute_risk_score(row["recommendation_text"], row["strength"])
        row["risk_score"] = score
        score_counts[score] += 1

        # Part B: combined text
        row["combined_text"] = build_combined_text(row)

    # Write output
    fieldnames = list(rows[0].keys())
    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Saved: {OUTPUT_FILE}\n")

    # Print risk score distribution
    print("Risk Score Distribution:")
    print("-" * 30)
    for score in sorted(score_counts.keys()):
        count = score_counts[score]
        bar = "#" * (count // 10)
        print(f"  Score {score:2d}: {count:4d} rows  {bar}")
    print(f"  Total:   {sum(score_counts.values()):4d} rows\n")

    # Print 3 example rows
    print("Example Rows:")
    print("=" * 80)
    examples_shown = 0
    for row in rows:
        if row["gene"] and row["drug_name"] and row["combined_text"]:
            print(f"\n  Gene: {row['gene']}")
            print(f"  Drug: {row['drug_name']}")
            print(f"  Risk Score: {row['risk_score']}")
            combined = row["combined_text"]
            if len(combined) > 200:
                combined = combined[:200] + "..."
            print(f"  Combined Text: {combined}")
            examples_shown += 1
            if examples_shown >= 3:
                break


if __name__ == "__main__":
    main()
