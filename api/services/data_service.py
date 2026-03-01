"""Loads CSV data at startup and provides lookup helpers."""

import csv
from difflib import get_close_matches
from pathlib import Path

from api.config import DATA_DIR


class DataService:
    def __init__(self):
        self.drugs: list[dict] = []
        self.drug_by_id: dict[str, dict] = {}
        self.drug_by_name: dict[str, dict] = {}
        self.smiles_by_id: dict[str, str] = {}

        self.recommendations: list[dict] = []
        self.rec_by_gene_drug: dict[str, list[dict]] = {}

        self.genes: dict[str, dict] = {}  # symbol -> {phenotypes, rec_count}
        self.alleles: list[dict] = []
        self.alleles_by_gene: dict[str, list[dict]] = {}

        self.gene_results: list[dict] = []
        self.pairs: list[dict] = []
        self.targets: list[dict] = []

    def load_all(self):
        self._load_drugs()
        self._load_smiles()
        self._load_recommendations()
        self._load_alleles()
        self._load_gene_results()
        self._load_pairs()
        self._load_targets()
        self._build_gene_index()

    def _load_csv(self, filename: str) -> list[dict]:
        path = DATA_DIR / filename
        if not path.exists():
            return []
        with open(path, "r", encoding="utf-8") as f:
            return list(csv.DictReader(f))

    def _load_drugs(self):
        self.drugs = self._load_csv("drugs.csv")
        for d in self.drugs:
            self.drug_by_id[d["drug_id"]] = d
            self.drug_by_name[d["drug_name"].lower()] = d

    def _load_smiles(self):
        for row in self._load_csv("drug_smiles.csv"):
            self.smiles_by_id[row["drug_id"]] = row["smiles"]

    def _load_recommendations(self):
        self.recommendations = self._load_csv("recommendations_scored.csv")
        for rec in self.recommendations:
            key = f"{rec.get('gene', '').upper()}:{rec.get('drug_name', '').lower()}"
            self.rec_by_gene_drug.setdefault(key, []).append(rec)

    def _load_alleles(self):
        self.alleles = self._load_csv("alleles.csv")
        for a in self.alleles:
            gene = a.get("gene", "")
            self.alleles_by_gene.setdefault(gene, []).append(a)

    def _load_gene_results(self):
        self.gene_results = self._load_csv("gene_results.csv")

    def _load_pairs(self):
        self.pairs = self._load_csv("pairs.csv")

    def _load_targets(self):
        self.targets = self._load_csv("drug_gene_targets.csv")

    def _build_gene_index(self):
        gene_phenotypes: dict[str, set[str]] = {}
        gene_rec_count: dict[str, int] = {}

        for rec in self.recommendations:
            gene = rec.get("gene", "")
            if not gene:
                continue
            gene_phenotypes.setdefault(gene, set())
            phenotype = rec.get("phenotype", "")
            if phenotype:
                gene_phenotypes[gene].add(phenotype)
            gene_rec_count[gene] = gene_rec_count.get(gene, 0) + 1

        for symbol, phenotypes in gene_phenotypes.items():
            self.genes[symbol] = {
                "symbol": symbol,
                "phenotypes": sorted(phenotypes),
                "recommendation_count": gene_rec_count.get(symbol, 0),
            }

    # --- Lookup helpers ---

    def search_drugs(self, query: str) -> list[dict]:
        q = query.lower()
        return [d for d in self.drugs if q in d["drug_name"].lower()]

    def suggest_drug(self, query: str) -> str | None:
        names = [d["drug_name"].lower() for d in self.drugs]
        matches = get_close_matches(query.lower(), names, n=1, cutoff=0.5)
        return matches[0] if matches else None

    def search_genes(self, query: str) -> list[dict]:
        q = query.upper()
        return [g for sym, g in self.genes.items() if q in sym]

    def suggest_gene(self, query: str) -> str | None:
        symbols = list(self.genes.keys())
        matches = get_close_matches(query.upper(), symbols, n=1, cutoff=0.5)
        return matches[0] if matches else None

    def get_recommendation(self, gene: str, drug: str) -> dict | None:
        key = f"{gene.upper()}:{drug.lower()}"
        recs = self.rec_by_gene_drug.get(key, [])
        return recs[0] if recs else None

    def get_recommendations_for_drug(self, gene: str, drug: str) -> list[dict]:
        key = f"{gene.upper()}:{drug.lower()}"
        return self.rec_by_gene_drug.get(key, [])


# Singleton
data_service = DataService()
