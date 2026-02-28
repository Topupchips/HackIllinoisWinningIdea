# Claude Code — Task List

## PharmaRisk: What to delegate to Claude Code

**Repo:** https://github.com/Topupchips/HackIllinoisWinningIdea
**Branch strategy:** `main` has placeholder README → all work on `dev` branch → merge to `main` before submission

---

## STEP 0 — Branch Setup (do this manually first)

```bash

# Make sure main has something so it stays default
echo "# PharmaRisk" > README.md
echo "Pharmacogenomics Drug Risk API — HackIllinois 2026" >> README.md
echo "" >> README.md
echo "🚧 Under construction — check back after March 1st!" >> README.md
git add README.md
git commit -m "init: placeholder readme"
git push origin main

# Now create dev branch — ALL work happens here
git checkout -b dev
git push origin dev

# Now you're on dev. Stay here until submission time.
# Before 6 AM Sunday: merge dev → main
```

---

## TASKS FOR CLAUDE CODE

### Task 1 — Extract CPIC Data into Clean CSVs

**Prompt:**
```
I have a CPIC PostgreSQL dump at ./data/cpic_db_dump-v1_54_0.sql

Extract these tables into clean CSV files in ./data/processed/:

1. recommendations.csv — from the COPY cpic.recommendation block
   Columns: id, drug_id, drug_name, gene, phenotype, implications_text,
   recommendation_text, strength, activity_score, allele_status, population,
   dosing_information, comments
   
   IMPORTANT: The training data format is (gene, drug, text). The text columns
   (implications_text, recommendation_text, dosing_information, comments) are
   critical training inputs — NOT just labels. Preserve the FULL text, do not
   truncate or summarize. These will be embedded as features for the model.

2. pairs.csv — from the COPY cpic.pair block  
   Columns: pair_id, gene, drug_id, cpic_level, pgx_testing, citations

3. alleles.csv — from the COPY cpic.allele block
   Columns: id, gene, allele_name, function_status, clinical_function, 
   activity_value, citations, strength, findings

4. drugs.csv — from the COPY cpic.drug block
   Columns: drug_id, drug_name, pharmgkb_id, rxnorm_id, drugbank_id

5. gene_results.csv — from the COPY cpic.gene_result block
   Columns: id, gene, phenotype_result, activity_score, ehr_priority, 
   consultation_text

The SQL dump uses tab-separated COPY blocks. Parse them correctly.
Handle \N as None/empty. Strip curly braces from JSON-like fields.
Preserve all text fields in full — they are training features, not just metadata.
```

**Expected output:** 5 clean CSV files in `./data/processed/`

---

### Task 2 — Engineer Risk Score Labels + Text Embeddings

**Prompt:**
```
Read ./data/processed/recommendations.csv

Two things to do:

PART A — Add risk_score column (1-10) based on recommendation_text and strength:

Mapping logic:
- Text contains "not recommended" or "do not use" + Strong → 10
- Text contains "not recommended" or "do not use" + Moderate → 9
- Text contains "contraindicated" → 10
- Text contains "consider alternative" + Strong → 8
- Text contains "consider alternative" + Moderate → 7  
- Text contains "reduce dose" and mentions 50%+ reduction → 7
- Text contains "reduce dose" + Strong → 6
- Text contains "reduce dose" + Moderate → 5
- Text contains "caution" or "monitor" → 4
- Text contains "standard dosing" or "per standard" or "no change" → 1-2
- Text contains "no action" → 1

Case insensitive matching. If multiple rules match, use the highest score.
If no rule matches, default to 5 (medium/uncertain).

PART B — Create a combined_text column that concatenates:
  implications_text + " | " + recommendation_text + " | " + dosing_information + " | " + comments
  Skip any that are empty/None. This combined text is a TRAINING FEATURE —
  the model training format is (gene, drug, text) where text carries clinical 
  meaning about WHY a gene-drug pair is risky.

  The text will be embedded (via sentence transformer or OpenAI embeddings) 
  and used as an input feature alongside gene and drug embeddings.

Save as ./data/processed/recommendations_scored.csv
Print the distribution of risk scores.
Print 3 example rows showing gene, drug, combined_text, risk_score.
```

---

### Task 3 — Fetch SMILES from PubChem

**Prompt:**
```
Read ./data/processed/drugs.csv

For each drug_name, fetch the SMILES string from PubChem REST API:
https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{drug_name}/property/CanonicalSMILES/JSON

Save as ./data/processed/drug_smiles.csv with columns: drug_id, drug_name, smiles

Handle errors gracefully:
- If drug not found, try removing spaces/hyphens
- If still not found, log it and skip
- Add 0.3s delay between requests to avoid rate limiting
- Print success/fail count at the end
```

---

### Task 4 — Extract DrugBank Targets

**Prompt:**
```
I have a DrugBank XML file at ./data/full_database_2.xml (1.9GB)

Extract drug-gene target mappings using streaming XML parsing (ET.iterparse).
For each drug, extract from targets, enzymes, carriers, and transporters.

Save as ./data/processed/drug_gene_targets.csv with columns:
drugbank_id, drug_name, relationship_type, target_name, gene_name, uniprot_id, action

Use this parsing approach:
- NS = "{http://www.drugbank.ca}"
- Get primary drugbank_id, drug name
- For each of targets/enzymes/carriers/transporters, extract polypeptide gene-name and actions
- elem.clear() after each drug to manage memory

Then cross-reference with our drugs.csv to only keep drugs we care about.
Print total rows and unique drug-gene pairs.
```

---

### Task 5 — FastAPI Scaffold

**Prompt:**
```
Create a FastAPI application for PharmaRisk — a pharmacogenomics drug risk API.

Project structure:
api/
├── main.py              # FastAPI app with CORS, middleware, router includes
├── routes/
│   ├── predict.py       # POST /predict, POST /predict/natural  
│   ├── drugs.py         # GET /drugs, GET /drugs/{drug_id}
│   ├── genes.py         # GET /genes, GET /genes/{symbol}, GET /genes/{symbol}/alleles
│   ├── explain.py       # POST /explain
│   └── health.py        # GET /validate, GET /health
├── models/
│   ├── requests.py      # Pydantic request models
│   └── responses.py     # Pydantic response models  
├── services/
│   ├── openai_service.py    # parse_natural_input(), explain_risk()
│   ├── model_service.py     # wraps model.predict(), with mock fallback
│   └── data_service.py      # loads CSVs, provides drug/gene lookups
└── config.py            # settings, env vars

Requirements:
- All data loaded from CSV files in ./data/processed/ at startup
- The core training data format is (gene, drug, text) — the recommendation text
  is a feature, not just a label. The /predict endpoint should return the matched
  CPIC recommendation text alongside the model's risk score.
- Mock model in model_service.py (returns hardcoded risk_score=5.0)
- OpenAI calls are async using httpx
- Proper error handling: 400, 404, 422, 500 with consistent ErrorResponse
- Pagination on list endpoints (?page=1&limit=20)
- Search on /drugs and /genes (?search=metop)
- Fuzzy matching on drug/gene names for "did you mean" suggestions
- CORS enabled for all origins
- X-Response-Time header on all responses
- Request logging middleware
- Tags on all endpoints for Swagger grouping
- Example values on all Pydantic models for Swagger docs

Every endpoint should work with the mock model. 
I will swap in the real model later.
```

---

### Task 6 — OpenAI Service

**Prompt:**
```
Create api/services/openai_service.py with two async functions:

1. parse_natural_input(query: str) -> dict
   - Takes natural language like "I'm a CYP2D6 poor metabolizer taking codeine"
   - Calls OpenAI gpt-4o-mini to extract structured data
   - Returns {"genes": [{"name": "CYP2D6", "phenotype": "Poor Metabolizer"}], "drug": "codeine"}
   - System prompt should include list of valid gene symbols and phenotypes
   - Handle parse failures: return None, let caller handle 422

2. explain_risk(drug: str, risk_score: float, gene_contributions: dict) -> str
   - Takes model output and generates plain English explanation
   - 2-3 sentences, under 100 words, no medical jargon
   - Mentions what could happen and what to discuss with doctor
   - Cache results for identical inputs (simple dict cache)

Both functions:
- Use httpx.AsyncClient
- Use OPENAI_API_KEY from environment
- Timeout after 10 seconds
- Return None on any error (never crash the API)
- Model: gpt-4o-mini
```

---

### Task 7 — Wire Real Model

**Prompt:**
```
Charles has delivered his model files in ./model/:
- model.py (contains PharmaRiskModel class with predict() method)
- set_transformer.pt
- xgboost_baseline.json  
- gene_embeddings.pkl
- drug_embeddings.pkl
- target_flags.pkl

Update api/services/model_service.py to:
1. Import PharmaRiskModel from model.model
2. Initialize it at startup with all the .pt and .pkl paths
3. Call model.predict(genes, drug) in the predict endpoint
4. Keep the mock as fallback: if model fails to load, use mock
5. Log which model is being used (real vs mock)

Test with:
- CYP2D6 Poor Metabolizer + codeine → should be high risk
- CYP2D6 Normal Metabolizer + codeine → should be low risk
- Unknown drug → should return graceful error
```

---

### Task 8 — README

**Prompt:**
```
Create a comprehensive README.md for PharmaRisk.

Sections:
1. Project title + one-line description
2. Problem (1.3M ER admissions from adverse drug reactions, 
   drugs prescribed based on symptoms not genetics)
3. Solution (API that takes gene profile + drug → risk score)
4. Architecture diagram (embed the eraser.io image)
5. Tech stack (FastAPI, PyTorch, ESM-2, RDKit, OpenAI, CPIC database)
6. API Endpoints — table listing all endpoints with method, path, description
7. Quickstart (clone, install, set env, run, open docs)
8. Curl examples for every endpoint with example responses
9. Validation results (placeholder — I'll fill in real numbers)
10. Data sources — CPIC (CC0, Stanford/NIH), PharmGKB (CC BY-SA), 
    PubChem (public domain), DrugBank (CC BY-NC), ESM-2 (MIT)
11. AI Disclosure (required by HackIllinois):
    - OpenAI: input parsing + output explanation
    - ESM-2: gene embeddings
    - Claude Code: code scaffolding assistance
    - What we built: data pipeline, model architecture, API design, validation
12. Team — Sanjavan Ghodasara, Charles [last name]
13. License

Make it clean, scannable, professional. Include badges for Python, FastAPI, PyTorch.
This README is being judged by Stripe on developer experience.
```

---

### Task 9 — Deployment

**Prompt:**
```
Create deployment configuration for PharmaRisk API.

Option A — Railway (preferred, easiest):
- Create Procfile: web: uvicorn api.main:app --host 0.0.0.0 --port $PORT
- Create railway.toml with build settings
- requirements.txt with all dependencies pinned

Option B — Docker:
- Dockerfile: python:3.11-slim base
- Install system deps for rdkit
- Copy code, install pip requirements
- Expose port 8000
- CMD uvicorn api.main:app --host 0.0.0.0 --port 8000

Option C — Modal:
- modal_app.py wrapping the FastAPI app
- Deploy with modal deploy

Create all three options so we can pick whichever works fastest.
```

---

### Task 10 — Pre-submission Merge

**Prompt:**
```
Help me prepare for merging dev into main.

1. Make sure all files are committed on dev
2. Update README.md with final validation results
3. Clean up any debug code / print statements
4. Verify .gitignore covers: .env, __pycache__, *.pkl, *.pt, .DS_Store
5. Create a clean requirements.txt with all dependencies
6. Merge dev into main:
   git checkout main
   git merge dev
   git push origin main
```

---

## TASK ORDER (follow this sequence)

| Order | Task | Blocked by | Gives to |
|---|---|---|---|
| 1 | Branch Setup | Nothing | Everything |
| 2 | Task 1 — Extract CPIC | Branch setup | Charles + Task 2 |
| 3 | Task 2 — Risk Scores | Task 1 | Charles |
| 4 | Task 3 — PubChem SMILES | Task 1 | Charles |
| 5 | Task 4 — DrugBank Targets | Nothing (can parallel) | Charles |
| 6 | Task 5 — FastAPI Scaffold | Nothing (can parallel) | Tasks 6-8 |
| 7 | Task 6 — OpenAI Service | Task 5 | API ready |
| 8 | Task 7 — Wire Real Model | Charles delivers model.py | Full API |
| 9 | Task 8 — README | Tasks 5-7 done | Submission |
| 10 | Task 9 — Deploy | API working | Submission |
| 11 | Task 10 — Merge | Everything done | Submit |

---

## TIPS FOR USING CLAUDE CODE

- Copy-paste each task prompt above directly into Claude Code
- Let it write the full file, review, then commit
- If something breaks, give Claude Code the error message — it'll fix it
- Commit after EVERY task (don't batch — you'll lose work)
- Use `git commit -m "task-X: description"` naming convention

---

*Last updated: Saturday Feb 28, 2026*
