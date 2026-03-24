# Revised Architecture

This codebase now follows the March 2026 PRD as a two-layer platform.

Canonical project memory: [PROJECT_CONTEXT.md](PROJECT_CONTEXT.md)

## Layer 1: Lead Quality Engine

Runtime flow:
1. Normalize job title into seniority and function.
2. Classify the engaged asset into `TOFU`, `MOFU`, or `BOFU`.
3. Parse the campaign brief into an inferred target profile.
4. Calculate ICP alignment, partner history, campaign history, client history, engagement, and data-quality signals.
5. Produce:
   - `approval_score`
   - `predicted_outcome`
   - `delivery_decision`
   - `quadrant`
   - top 3 plain-English reasons

Implementation:
- `src/lead_scoring/platform/classifiers.py`
- `src/lead_scoring/platform/brief_parser.py`
- `src/lead_scoring/platform/engine.py`

## Layer 2: Buying Group Signal Engine

Runtime flow:
1. Merge account personas supplied in the request with persisted score audits.
2. Count unique approved personas over the account window.
3. Measure function coverage, seniority spread, and persona completeness by vertical.
4. Identify missing personas for targeted nurture.
5. Trigger BDR follow-up when threshold conditions are met.

Implementation:
- `src/lead_scoring/platform/engine.py`
- `src/lead_scoring/platform/audit.py`
- `config/platform_config.yaml`

## Persistence

Every scored lead writes a queryable audit row to `score_audit_records`:
- request payload
- response payload
- feature payload
- model version
- lead id
- campaign id
- client id

Implementation:
- `src/lead_scoring/database/models.py`
- `src/lead_scoring/platform/audit.py`

## Retraining

The retraining flow is designed around the PRD Phase 1 feature table. It:
- refreshes signal tables
- trains a promoted model when the required runtime feature columns are present
- compares AUC against the current baseline
- writes promoted artifacts under `models/prd_runtime/`

Implementation:
- `src/lead_scoring/platform/training.py`
- `scripts/run_monthly_retrain.py`

## API Surface

The API is now PRD-native:
- `POST /score`
- `POST /score/batch`
- `POST /buying-group/preview`
- `GET /reports/campaign/{campaign_id}`
- `POST /outcomes/label`
- `POST /operations/retrain`
- `GET /health`

Implementation:
- `src/lead_scoring/api/app.py`
- `src/lead_scoring/api/schemas.py`
