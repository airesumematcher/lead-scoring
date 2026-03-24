# ACE Buying Intelligence Platform

Re-architected against the revised March 2026 PRD.

Canonical project memory: [PROJECT_CONTEXT.md](PROJECT_CONTEXT.md)

This repo is now a two-layer buying-intelligence system:
- Layer 1: pre-delivery lead quality scoring
- Layer 2: account-level buying-group signal detection
- Lightweight upload portal: CSV intake, batch scoring trigger, scored output export
- Backend file ingestion for CSV and Excel with header interpretation

## What Changed

The older ACE baseline in this repo focused on composite ACE scoring and model-comparison utilities. The revised product now centers on:
- campaign-scoped scoring for every lead
- partner/client/campaign history signals
- ICP extraction from campaign briefs
- buying-group coverage and BDR triggers
- score audit persistence per lead and per campaign
- retraining hooks for the PRD feature table

## Primary Endpoints

- `POST /score`
- `POST /score/batch`
- `POST /portal/import-score`
- `POST /buying-group/preview`
- `GET /reports/campaign/{campaign_id}`
- `POST /outcomes/label`
- `POST /operations/retrain`
- `GET /health`

## Local Setup

```bash
cd /Users/schadha/Desktop/lead-scoring
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
python verify_setup.py
uvicorn lead_scoring.api.app:app --host 0.0.0.0 --port 8000
```

Open:
- `http://127.0.0.1:8000`
- `http://127.0.0.1:8000/docs`

The root URL now serves a lightweight lead upload portal that:
- accepts CSV and Excel uploads
- accepts one-row campaign-context CSV uploads
- applies shared campaign metadata
- triggers `/portal/import-score`
- returns a downloadable scored output file

## Operating Guides

- [Project Context](PROJECT_CONTEXT.md)
- [Quick Start](QUICK_START.md)
- [Revised Architecture](REVISED_ARCHITECTURE.md)

## Runtime Modes

The application boots in one of two modes:
- `heuristic-baseline`: the default PRD-aligned runtime when no promoted model is present
- `promoted-model`: loaded automatically after a successful retrain promotion under `models/prd_runtime/`

Check the active mode at `GET /health`.

## Retraining

Run retraining from the CLI:

```bash
python scripts/run_monthly_retrain.py /absolute/path/to/prd_feature_table.csv
```

The retrain job expects a PRD feature table with `status` plus the runtime feature columns described in [REVISED_ARCHITECTURE.md](REVISED_ARCHITECTURE.md).
