# Project Context

This is the canonical context file for the current state of the repository.

If you need to understand the live product, start here first.

## Current Product

The active application is the revised March 2026 PRD implementation of ACE:
- Layer 1: pre-delivery lead quality scoring
- Layer 2: buying-group signal aggregation
- Lightweight upload portal at `/`
- Backend-managed CSV / Excel lead ingestion
- API-first backend with audit persistence and retraining hooks

## Canonical Files

These are the primary source-of-truth files for the live system:
- `src/lead_scoring/api/app.py`
- `src/lead_scoring/api/schemas.py`
- `src/lead_scoring/platform/engine.py`
- `src/lead_scoring/platform/contracts.py`
- `src/lead_scoring/platform/training.py`
- `src/lead_scoring/platform/audit.py`
- `src/lead_scoring/portal/ingest.py`
- `config/platform_config.yaml`
- `index.html`
- `verify_setup.py`
- `scripts/run_monthly_retrain.py`
- `README.md`
- `QUICK_START.md`
- `REVISED_ARCHITECTURE.md`

## Runtime Entry Points

Backend:
- `uvicorn lead_scoring.api.app:app --host 0.0.0.0 --port 8000`

Frontend:
- `GET /` serves the upload portal

Key endpoints:
- `POST /score`
- `POST /score/batch`
- `POST /portal/import-score`
- `POST /buying-group/preview`
- `GET /reports/campaign/{campaign_id}`
- `POST /outcomes/label`
- `POST /operations/retrain`
- `GET /health`

## Live User Flow

Portal operator flow:
1. Open the root portal.
2. Optionally upload a campaign-context CSV.
3. Upload the lead CSV or Excel file.
4. The portal sends the raw file to `POST /portal/import-score`.
5. The backend interprets required fields from uploaded headers, normalizes rows, scores the batch, and returns the campaign report.
6. The portal displays scored leads and lets the operator download the scored output CSV.

Ops / ML flow:
1. Label accepted / rejected outcomes.
2. Build or refresh the PRD feature table.
3. Run monthly retraining.
4. Restart the API if a model was promoted.

## Setup And Ignore Files

The core setup / ignore files are already centralized at the repo root:
- `requirements.txt`
- `setup.py`
- `.gitignore`
- `.dockerignore`
- `.env.example`
- `Dockerfile`

Additional runtime parser dependencies:
- `python-multipart`
- `openpyxl`
- `xlrd`

## Verification

Primary checks:
- `python verify_setup.py`
- `pytest tests/test_prd_api.py`

Health:
- `GET /health`

## Documentation Policy

Use these docs for the current product:
- `PROJECT_CONTEXT.md`
- `README.md`
- `QUICK_START.md`
- `REVISED_ARCHITECTURE.md`

Treat most of the other root-level Markdown files as historical / legacy implementation records unless explicitly needed:
- `PHASE*.md`
- `STEP*.md`
- `*_REPORT.md`
- `*_SUMMARY.md`
- older model-comparison and prior-architecture docs

They are still useful as archive material, but they are not the current source of truth.
