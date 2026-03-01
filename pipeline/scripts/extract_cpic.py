"""
Task 1: Extract CPIC PostgreSQL dump into clean CSV files.

Parses tab-separated COPY blocks from cpic_db_dump-v1_54_0.sql
and writes 5 CSV files to data/processed/.
"""

import csv
import json
import re
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
SQL_FILE = BASE_DIR / "data" / "raw" / "cpic_db_dump-v1.54.0.sql"
OUT_DIR = BASE_DIR / "data" / "processed"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def parse_copy_block(filepath: Path, table_name: str) -> list[list[str]]:
    """Extract all rows from a COPY cpic.<table_name> ... FROM stdin; block."""
    rows = []
    header_pattern = f"COPY cpic.{table_name} "
    inside_block = False

    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            if not inside_block:
                if line.startswith(header_pattern):
                    inside_block = True
                continue
            # End of COPY block
            if line.strip() == "\\.":
                break
            rows.append(line.rstrip("\n").split("\t"))

    print(f"  {table_name}: {len(rows)} rows extracted")
    return rows


def clean_val(val: str) -> str:
    """Replace \\N with empty string."""
    return "" if val == "\\N" else val


def parse_pg_json(val: str) -> dict:
    """Parse PostgreSQL JSON-like dict: {"key": "value", ...}"""
    val = clean_val(val)
    if not val or val in ("{}", "\\N"):
        return {}
    try:
        return json.loads(val)
    except json.JSONDecodeError:
        return {}


def strip_braces(val: str) -> str:
    """Strip curly braces from PostgreSQL array literals like {a,b,c}."""
    val = clean_val(val)
    if val.startswith("{") and val.endswith("}") and '"' not in val[:3]:
        return val[1:-1]
    return val


# ─── DRUG TABLE (needed for drug name lookups) ──────────────────────────────

def extract_drugs(rows) -> dict:
    """Extract drugs.csv and return drug_id -> drug_name mapping."""
    # Columns: drugid, name, pharmgkbid, rxnormid, drugbankid, atcid, umlscui, flowchart, version, guidelineid
    drug_map = {}
    csv_rows = []

    for r in rows:
        drug_id = clean_val(r[0])
        drug_name = clean_val(r[1])
        pharmgkb_id = clean_val(r[2])
        rxnorm_id = clean_val(r[3])
        drugbank_id = clean_val(r[4])

        drug_map[drug_id] = drug_name
        csv_rows.append([drug_id, drug_name, pharmgkb_id, rxnorm_id, drugbank_id])

    outpath = OUT_DIR / "drugs.csv"
    with open(outpath, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["drug_id", "drug_name", "pharmgkb_id", "rxnorm_id", "drugbank_id"])
        w.writerows(csv_rows)

    print(f"  -> drugs.csv: {len(csv_rows)} rows written")
    return drug_map


# ─── RECOMMENDATIONS TABLE ──────────────────────────────────────────────────

def extract_recommendations(rows, drug_map: dict):
    """Extract recommendations.csv with full text columns preserved."""
    # Columns: id, guidelineid, drugid, implications, drugrecommendation,
    #   classification, phenotypes, activityscore, allelestatus, lookupkey,
    #   population, comments, version, dosinginformation, alternatedrugavailable,
    #   otherprescribingguidance
    csv_rows = []

    for r in rows:
        rec_id = clean_val(r[0])
        drug_id = clean_val(r[2])
        drug_name = drug_map.get(drug_id, "")

        # implications is a JSON dict {gene: text}
        implications_dict = parse_pg_json(r[3])
        # phenotypes is a JSON dict {gene: phenotype}
        phenotypes_dict = parse_pg_json(r[6])
        # allelestatus is a JSON dict {gene: status}
        allelestatus_dict = parse_pg_json(r[8])

        # Gene comes from the key of the implications or phenotypes dict
        gene = ""
        if implications_dict:
            gene = list(implications_dict.keys())[0]
        elif phenotypes_dict:
            gene = list(phenotypes_dict.keys())[0]
        elif allelestatus_dict:
            gene = list(allelestatus_dict.keys())[0]

        # Flatten JSON values to text
        implications_text = "; ".join(f"{k}: {v}" for k, v in implications_dict.items()) if implications_dict else ""
        phenotype = "; ".join(f"{k}: {v}" for k, v in phenotypes_dict.items()) if phenotypes_dict else ""
        allele_status = "; ".join(f"{k}: {v}" for k, v in allelestatus_dict.items()) if allelestatus_dict else ""

        recommendation_text = clean_val(r[4])
        strength = clean_val(r[5])
        activity_score = strip_braces(clean_val(r[7]))
        population = clean_val(r[10])
        comments = clean_val(r[11])
        # dosinginformation (index 13) is a boolean column in this dump (always "f")
        # so we treat it as empty; real clinical text lives in comments/implications
        raw_dosing = clean_val(r[13]) if len(r) > 13 else ""
        dosing_information = "" if raw_dosing in ("f", "t") else raw_dosing

        csv_rows.append([
            rec_id, drug_id, drug_name, gene, phenotype,
            implications_text, recommendation_text, strength,
            activity_score, allele_status, population,
            dosing_information, comments
        ])

    outpath = OUT_DIR / "recommendations.csv"
    with open(outpath, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([
            "id", "drug_id", "drug_name", "gene", "phenotype",
            "implications_text", "recommendation_text", "strength",
            "activity_score", "allele_status", "population",
            "dosing_information", "comments"
        ])
        w.writerows(csv_rows)

    print(f"  -> recommendations.csv: {len(csv_rows)} rows written")


# ─── PAIRS TABLE ────────────────────────────────────────────────────────────

def extract_pairs(rows):
    """Extract pairs.csv."""
    # Columns: pairid, genesymbol, drugid, guidelineid, usedforrecommendation,
    #   version, cpiclevel, pgkbcalevel, pgxtesting, citations, removed, removeddate, removedreason
    csv_rows = []

    for r in rows:
        pair_id = clean_val(r[0])
        gene = clean_val(r[1])
        drug_id = clean_val(r[2])
        cpic_level = clean_val(r[6])
        pgx_testing = clean_val(r[8])
        citations = strip_braces(clean_val(r[9]))

        csv_rows.append([pair_id, gene, drug_id, cpic_level, pgx_testing, citations])

    outpath = OUT_DIR / "pairs.csv"
    with open(outpath, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["pair_id", "gene", "drug_id", "cpic_level", "pgx_testing", "citations"])
        w.writerows(csv_rows)

    print(f"  -> pairs.csv: {len(csv_rows)} rows written")


# ─── ALLELES TABLE ──────────────────────────────────────────────────────────

def extract_alleles(rows):
    """Extract alleles.csv."""
    # Columns: id, version, genesymbol, name, functionalstatus,
    #   clinicalfunctionalstatus, clinicalfunctionalsubstrate, activityvalue,
    #   definitionid, citations, strength, functioncomments, findings, frequency, inferredfrequency
    csv_rows = []

    for r in rows:
        allele_id = clean_val(r[0])
        gene = clean_val(r[2])
        allele_name = clean_val(r[3])
        function_status = clean_val(r[4])
        clinical_function = clean_val(r[5])
        activity_value = clean_val(r[7])
        citations = strip_braces(clean_val(r[9]))
        strength = clean_val(r[10])
        findings = clean_val(r[12])

        csv_rows.append([
            allele_id, gene, allele_name, function_status,
            clinical_function, activity_value, citations, strength, findings
        ])

    outpath = OUT_DIR / "alleles.csv"
    with open(outpath, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([
            "id", "gene", "allele_name", "function_status",
            "clinical_function", "activity_value", "citations", "strength", "findings"
        ])
        w.writerows(csv_rows)

    print(f"  -> alleles.csv: {len(csv_rows)} rows written")


# ─── GENE RESULTS TABLE ────────────────────────────────────────────────────

def extract_gene_results(rows):
    """Extract gene_results.csv."""
    # Columns: id, genesymbol, result, activityscore, ehrpriority,
    #   consultationtext, version, frequency
    csv_rows = []

    for r in rows:
        result_id = clean_val(r[0])
        gene = clean_val(r[1])
        phenotype_result = clean_val(r[2])
        activity_score = clean_val(r[3])
        ehr_priority = clean_val(r[4])
        consultation_text = clean_val(r[5])

        csv_rows.append([
            result_id, gene, phenotype_result, activity_score,
            ehr_priority, consultation_text
        ])

    outpath = OUT_DIR / "gene_results.csv"
    with open(outpath, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([
            "id", "gene", "phenotype_result", "activity_score",
            "ehr_priority", "consultation_text"
        ])
        w.writerows(csv_rows)

    print(f"  -> gene_results.csv: {len(csv_rows)} rows written")


# ─── MAIN ───────────────────────────────────────────────────────────────────

def main():
    print(f"Reading SQL dump: {SQL_FILE}")
    print(f"Output directory: {OUT_DIR}\n")

    if not SQL_FILE.exists():
        print(f"ERROR: SQL file not found at {SQL_FILE}")
        sys.exit(1)

    # Extract all COPY blocks
    print("Extracting COPY blocks...")
    drug_rows = parse_copy_block(SQL_FILE, "drug")
    rec_rows = parse_copy_block(SQL_FILE, "recommendation")
    pair_rows = parse_copy_block(SQL_FILE, "pair")
    allele_rows = parse_copy_block(SQL_FILE, "allele")
    gene_result_rows = parse_copy_block(SQL_FILE, "gene_result")

    print("\nWriting CSV files...")
    drug_map = extract_drugs(drug_rows)
    extract_recommendations(rec_rows, drug_map)
    extract_pairs(pair_rows)
    extract_alleles(allele_rows)
    extract_gene_results(gene_result_rows)

    print("\nDone! All 5 CSV files written to data/processed/")


if __name__ == "__main__":
    main()
