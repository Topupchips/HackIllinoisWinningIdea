"""
Task 3: Fetch SMILES strings from PubChem REST API for each drug.

Reads drugs.csv, queries PubChem for CanonicalSMILES, saves drug_smiles.csv.
"""

import csv
import json
import re
import time
import urllib.request
import urllib.error
import urllib.parse
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
INPUT_FILE = BASE_DIR / "data" / "processed" / "drugs.csv"
OUTPUT_FILE = BASE_DIR / "data" / "processed" / "drug_smiles.csv"

PUBCHEM_URL = "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{}/property/CanonicalSMILES/JSON"
DELAY = 0.3  # seconds between requests


def fetch_smiles(drug_name: str) -> str | None:
    """Try to fetch SMILES from PubChem. Returns SMILES string or None."""
    variants = [drug_name]

    # Try without spaces/hyphens if the original fails
    cleaned = re.sub(r"[\s\-]", "", drug_name)
    if cleaned != drug_name:
        variants.append(cleaned)

    # Try first word only for combo drugs (e.g. "fluticasone/salmeterol")
    if "/" in drug_name:
        variants.append(drug_name.split("/")[0].strip())

    for name in variants:
        try:
            url = PUBCHEM_URL.format(urllib.parse.quote(name))
            req = urllib.request.Request(url, headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode())
                props = data["PropertyTable"]["Properties"][0]
                # PubChem may return key as CanonicalSMILES or ConnectivitySMILES
                smiles = props.get("CanonicalSMILES") or props.get("ConnectivitySMILES")
                if smiles:
                    return smiles
        except (urllib.error.HTTPError, urllib.error.URLError, KeyError, IndexError, json.JSONDecodeError):
            continue
        except Exception:
            continue

    return None


def main():
    print(f"Reading: {INPUT_FILE}")

    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        drugs = list(reader)

    print(f"Fetching SMILES for {len(drugs)} drugs from PubChem...\n")

    results = []
    success = 0
    failed = 0
    failed_names = []

    for i, drug in enumerate(drugs):
        drug_id = drug["drug_id"]
        drug_name = drug["drug_name"]

        smiles = fetch_smiles(drug_name)

        if smiles:
            results.append([drug_id, drug_name, smiles])
            success += 1
            status = "OK"
        else:
            failed += 1
            failed_names.append(drug_name)
            status = "FAILED"

        print(f"  [{i+1:3d}/{len(drugs)}] {drug_name:30s} {status}")
        time.sleep(DELAY)

    # Write output
    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["drug_id", "drug_name", "smiles"])
        w.writerows(results)

    print(f"\nResults:")
    print(f"  Success: {success}")
    print(f"  Failed:  {failed}")
    print(f"  Saved:   {OUTPUT_FILE}")

    if failed_names:
        print(f"\nFailed drugs:")
        for name in failed_names:
            print(f"  - {name}")


if __name__ == "__main__":
    main()
