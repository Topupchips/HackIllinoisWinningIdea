"""
Task 4: Extract drug-gene target mappings from DrugBank XML.

Uses streaming XML parsing (iterparse) to handle the 1.9GB file.
Cross-references with our drugs.csv to keep only relevant drugs.
"""

import csv
import xml.etree.ElementTree as ET
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
XML_FILE = BASE_DIR / "data" / "raw" / "full database 2.xml"
DRUGS_FILE = BASE_DIR / "data" / "processed" / "drugs.csv"
OUTPUT_FILE = BASE_DIR / "data" / "processed" / "drug_gene_targets.csv"

NS = "{http://www.drugbank.ca}"

RELATIONSHIP_SECTIONS = ["targets", "enzymes", "carriers", "transporters"]


def load_our_drugbank_ids() -> set[str]:
    """Load DrugBank IDs from our drugs.csv for filtering."""
    ids = set()
    with open(DRUGS_FILE, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            dbid = row.get("drugbank_id", "").strip()
            if dbid:
                ids.add(dbid)
    return ids


def extract_targets(xml_path: Path, our_ids: set[str]) -> list[list[str]]:
    """Stream-parse DrugBank XML and extract drug-gene relationships."""
    rows = []
    drug_count = 0
    matched_count = 0

    context = ET.iterparse(str(xml_path), events=("end",))

    for event, elem in context:
        if elem.tag != f"{NS}drug":
            continue

        # Get primary drugbank-id
        dbid_elem = elem.find(f"{NS}drugbank-id[@primary='true']")
        if dbid_elem is None:
            dbid_elem = elem.find(f"{NS}drugbank-id")
        if dbid_elem is None:
            elem.clear()
            continue

        drugbank_id = dbid_elem.text or ""
        drug_count += 1

        if drug_count % 2000 == 0:
            print(f"  Processed {drug_count} drugs...")

        # Filter: only keep drugs in our dataset
        if drugbank_id not in our_ids:
            elem.clear()
            continue

        matched_count += 1
        drug_name_elem = elem.find(f"{NS}name")
        drug_name = drug_name_elem.text if drug_name_elem is not None else ""

        # Extract from each relationship section
        for section in RELATIONSHIP_SECTIONS:
            container = elem.find(f"{NS}{section}")
            if container is None:
                continue

            for entry in container:
                # Get target name
                target_name_elem = entry.find(f"{NS}name")
                target_name = target_name_elem.text if target_name_elem is not None else ""

                # Get actions
                actions_elem = entry.find(f"{NS}actions")
                actions = []
                if actions_elem is not None:
                    actions = [a.text for a in actions_elem if a.text]
                action_str = "; ".join(actions) if actions else ""

                # Get polypeptide info (gene name, uniprot id)
                polypeptide = entry.find(f"{NS}polypeptide")
                if polypeptide is not None:
                    uniprot_id = polypeptide.attrib.get("id", "")
                    gene_elem = polypeptide.find(f"{NS}gene-name")
                    gene_name = gene_elem.text if gene_elem is not None else ""
                else:
                    uniprot_id = ""
                    gene_name = ""

                # Only keep rows that have a gene name
                if gene_name:
                    rows.append([
                        drugbank_id, drug_name, section.rstrip("s"),
                        target_name, gene_name, uniprot_id, action_str
                    ])

        elem.clear()

    print(f"  Total drugs in XML: {drug_count}")
    print(f"  Matched our dataset: {matched_count}")
    return rows


def main():
    print(f"Loading our drug IDs from: {DRUGS_FILE}")
    our_ids = load_our_drugbank_ids()
    print(f"  Our DrugBank IDs: {len(our_ids)}\n")

    print(f"Parsing DrugBank XML: {XML_FILE}")
    print(f"  (this may take a few minutes for 1.8GB...)\n")

    rows = extract_targets(XML_FILE, our_ids)

    # Write output
    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([
            "drugbank_id", "drug_name", "relationship_type",
            "target_name", "gene_name", "uniprot_id", "action"
        ])
        w.writerows(rows)

    # Stats
    unique_pairs = set((r[0], r[4]) for r in rows)
    unique_drugs = set(r[0] for r in rows)
    unique_genes = set(r[4] for r in rows)

    print(f"\nResults:")
    print(f"  Total rows: {len(rows)}")
    print(f"  Unique drug-gene pairs: {len(unique_pairs)}")
    print(f"  Unique drugs with targets: {len(unique_drugs)}")
    print(f"  Unique target genes: {len(unique_genes)}")
    print(f"  Saved: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
