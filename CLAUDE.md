# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

> **Inherits**: `~/.claude/CLAUDE.md` (global AI CTO rules — quality bar, pushback patterns, Think→Build→Prove workflow). All global rules apply here.

---

# ACE Buying Intelligence Platform

This file is the authoritative guide for Claude Code when working in this repository.
Read it before making any changes.

---

## What This Repo Does

A **two-layer B2B lead scoring platform** that:
1. **Layer 1 — Lead Quality**: scores an individual lead (0–100) across fit, intent, partner history, data quality, and ICP alignment.
2. **Layer 2 — Buying Group**: aggregates approved personas at the account level to detect multi-stakeholder buying signals and trigger BDR handoffs.

Deployed as a FastAPI service backed by PostgreSQL (SQLite in dev). Supports single-lead scoring, batch scoring, and a CSV portal import flow.

---

## Architecture Overview

```
src/lead_scoring/
├── api/app.py              ← FastAPI entry point (primary endpoints)
├── platform/
│   ├── engine.py           ← BuyingIntelligenceService (score_lead, score_batch)
│   ├── training.py         ← Monthly retraining pipeline (GBC + calibration)
│   ├── contracts.py        ← All Pydantic data models (LeadRecord, LeadScoreResult, …)
│   ├── classifiers.py      ← TitleNormalizer, AssetClassifier, CampaignModeInferrer
│   ├── brief_parser.py     ← CampaignBriefParser (extracts ICP from brief text)
│   ├── audit.py            ← AuditRepository (persist/query ScoreAuditRecord)
│   └── config.py           ← Loads config/platform_config.yaml
├── database/
│   ├── models.py           ← SQLAlchemy ORM (ScoreAuditRecord is the key table)
│   └── connection.py       ← Session management, init_db()
└── portal/ingest.py        ← CSV/Excel import with flexible header aliasing
```

**Legacy code** (do not touch unless explicitly asked):
`src/lead_scoring/features/`, `src/lead_scoring/scoring/`, `src/lead_scoring/models/`,
`src/lead_scoring/explainability/`, `src/lead_scoring/feedback/`

---

## Running the Service

```bash
# Install deps
pip install -e .

# Start API (dev)
uvicorn lead_scoring.api.app:app --reload --port 8000

# Docs
open http://localhost:8000/docs
```

---

## Running Tests

```bash
pytest tests/test_prd_api.py          # primary PRD test suite
pytest tests/                         # all tests
pytest tests/test_prd_api.py::test_health_check  # single test
```

---

## Retraining the Model

```bash
# Uses verify_prd_training.csv by default
python scripts/run_monthly_retrain.py

# Pass a custom PRD feature table (must have 'status' column)
python scripts/run_monthly_retrain.py /path/to/feature_table.csv

# Force-promote even if new AUC < current baseline
python scripts/run_monthly_retrain.py --force-promote
```

Or via API:
```
POST /operations/retrain
{"dataset_path": "/path/to/feature_table.csv", "force_promote": false}
```

**Promoted model artifact** lands at: `models/prd_runtime/lead_quality_model.pkl`
**Metadata** (AUC, Brier, KS, Lift) at: `models/prd_runtime/model_metadata.json`

---

## Key Scoring Thresholds (config/platform_config.yaml)

| Threshold | Value | Meaning |
|-----------|-------|---------|
| `delivery_score` | 68 | Score ≥ 68 → **deliver** |
| `review_score` | 50 | Score ≥ 50 → **review** |
| `predicted_approval_score` | 55 | Score ≥ 55 → `predicted_outcome = approved` |

**Heuristic weights** (active when no promoted model exists):
```yaml
approval:
  fit: 0.28 | intent: 0.22 | partner: 0.18 | client_history: 0.10
  campaign_history: 0.08 | data_quality: 0.08 | icp_match: 0.06
```

These weights are **business-defined, not data-derived**. Once a promoted model exists they are unused for scoring but still define penalty thresholds.

---

## Runtime Modes

| Mode | When | How |
|------|------|-----|
| `heuristic-baseline` | No `lead_quality_model.pkl` | Weighted linear sum from config |
| `promoted-model` | `.pkl` file present in `models/prd_runtime/` | `CalibratedClassifierCV` wrapping GBC |

Check active mode: `GET /health` → `runtime_model` field.

---

## ML Model Details (training.py)

**Algorithm**: `LGBMClassifier` (LightGBM) — produces calibrated probabilities natively, so no `CalibratedClassifierCV` wrapper is needed.

**Hyperparameters**: `n_estimators=500`, `learning_rate=0.05`, `max_depth=6`, `num_leaves=31`, `subsample=0.8`, `colsample_bytree=0.8`, `min_child_samples=20`, `class_weight="balanced"`, `random_state=42`.

**Training pipeline**:
- **Time-based split**: if the dataset has `submitted_at`/`created_date`/`created_at`/`scored_at`, the oldest 80% trains, newest 20% tests (prevents temporal leakage).
- **Class imbalance**: handled via `class_weight="balanced"` directly in LightGBM.
- **Cross-validation**: 5-fold stratified CV for AUC reporting when ≥ 30 samples (3-fold when < 60).
- **Extended metrics stored in metadata**: `auc_roc`, `pr_auc`, `brier_score`, `ks_statistic`, `lift_at_10pct`, `lift_at_20pct`, `top_decile_precision`.
- **Signal tables** (score distribution lookup tables) are always written to `models/prd_runtime/signal_tables.json`, even when model training is skipped (e.g., no `status` column or fewer than 5 matching features).

**14 input features** (all 0–100 unless noted):
`authority_score`, `fit_score`, `intent_score`, `partner_signal_score`,
`client_history_score`, `campaign_history_score`, `data_quality_score`,
`icp_match_score`, `buying_group_score`, `unique_persona_count`,
`late_stage_signal`, `email_engagement_score`, `second_touch_signal`, `recency_score`

**Known architectural limitation**: all 14 features are derived heuristic scores — the ML model never sees raw signals. Future work: feed raw features (raw engagement counts, exact title text, domain flags) directly into the model.

---

## Feedback Loop (Close the Loop)

Client outcomes (accepted/rejected) can be attached to any scored lead:
```
POST /outcomes/label
{
  "lead_id": "ACE-PRD-001",
  "campaign_id": "HC-BOFU-2026-01",
  "outcome": "approved",
  "notes": "Client confirmed in CRM"
}
```

This writes to `ScoreAuditRecord.actual_outcome`. Run retraining against the
audit table export (filtered to rows with non-null `actual_outcome`) to close
the learning loop.

---

## Known Gaps (Do Not Silently Paper Over)

1. **`models/prd_runtime/` is empty** — no model has been trained in production yet. Service runs in heuristic mode.
2. **Heuristic weights are unvalidated** — they are business intuition, not fitted to outcome data.
3. **Score-of-scores anti-pattern** — the GBC trains on compressed heuristic scores, not raw signals.
4. **No model monitoring** — no drift detection, no score distribution tracking, no alerting.
5. **No automated feedback ingestion** — outcomes must be POSTed manually; no CRM sync.
6. **No hyperparameter tuning** — GBC uses preset values (`n_estimators=200`, `learning_rate=0.05`, `max_depth=4`, `subsample=0.8`).

---

## Data Files

| File | Purpose |
|------|---------|
| `data_processed/verify_prd_training.csv` | 20-row synthetic PRD feature table for smoke-testing retraining |
| `data_processed/crm_historical_leads.csv` | Raw CRM export (no PRD features — needs feature extraction before use) |
| `data/prd_sample_payloads.py` | Sample `LeadRecord` JSON payloads for API testing |
| `config/platform_config.yaml` | Runtime thresholds, weights, keyword mappings |
| `config/scoring_config.yaml` | Legacy ACE model config (unused in PRD v2) |

---

## Root-Level Clutter (Ignore)

The repo root contains ~30 `.md` status files (`PHASE1_COMPLETE.md`, `STEP7_RESULTS.md`, etc.) and many loose `.py` scripts (`train_xgb_simple.py`, `phase2_retrain_models.py`, `test_api.py`, etc.) from earlier development sessions. **These are not part of the active codebase.** The canonical source lives exclusively under `src/lead_scoring/`, `tests/`, `scripts/`, and `config/`.

---

## Contribution Guidelines

- **Do not edit legacy modules** (`features/`, `scoring/`, `models/`, etc.) — they are deprecated.
- **All scoring changes** go through `platform/engine.py` and `platform/training.py`.
- **Config changes** (thresholds, weights, keywords) go in `config/platform_config.yaml`.
- **Before adding a new feature**: check if a heuristic in `engine.py` already computes a related signal.
- **ML experiments**: create a branch, run `python scripts/run_monthly_retrain.py`, capture `model_metadata.json` AUC and KS stat, and compare against the current baseline before promoting.
- **Tests**: add cases to `tests/test_prd_api.py` for any new endpoint or scoring logic.
