# ACE Buying Intelligence Platform

A two-layer B2B lead scoring system that predicts whether a lead will be accepted by a client before it is delivered. Built on 150,000 labeled leads from real campaign data, trained with LightGBM (AUC-ROC 0.748, KS 0.378).

---

## Table of Contents

1. [How It Works](#how-it-works)
2. [Quick Start — Running the Service](#quick-start)
3. [Scoring a Lead — Step by Step](#scoring-a-lead)
4. [Score Interpretation](#score-interpretation)
5. [Retraining the Model — What Data Is Required](#retraining-the-model)
6. [How to Interpret Training Data](#how-to-interpret-training-data)
7. [Architecture Overview](#architecture-overview)
8. [API Reference](#api-reference)

---

## How It Works

The platform has two layers that work together on every lead:

### Layer 1 — Lead Quality Score (0–100)

Predicts the probability that a client will accept this lead. The score is derived from 14 feature signals built from the lead's profile, engagement history, partner track record, and campaign alignment. A trained LightGBM model converts these signals into a calibrated approval probability.

**Decision output from the score:**

| Score Range | Decision | Meaning |
|-------------|----------|---------|
| 68–100 | **DELIVER** | High confidence — send to client |
| 50–67 | **REVIEW** | Borderline — human review recommended |
| 0–49 | **HOLD** | Likely rejection — do not deliver |

### Layer 2 — Buying Group Signal (Account-Level)

Across all leads from the same company domain and campaign, the system tracks how many distinct job functions have engaged (e.g. Finance + IT + Operations = 3). When 2 or more functions are active, a **BDR trigger** fires — indicating a real buying committee is forming and the account is ready for sales handoff.

---

## Quick Start

### Prerequisites

```bash
# Install dependencies
pip install -e .

# Verify LightGBM is available
python3 -c "import lightgbm; print('LightGBM OK')"
```

### Start the API server

```bash
uvicorn lead_scoring.api.app:app --reload --port 8000
```

Open [http://localhost:8000](http://localhost:8000) in your browser for the operator portal.

API docs available at [http://localhost:8000/docs](http://localhost:8000/docs).

### Check which model is active

```bash
curl http://localhost:8000/health
```

Expected response when the promoted LightGBM model is loaded:
```json
{
  "status": "healthy",
  "runtime_model": "promoted-model",
  "architecture": "two-layer-buying-intelligence"
}
```

If `runtime_model` is `"heuristic-baseline"`, the model file is missing — run the retrain step below.

### Score leads via the portal UI

1. Start the API (see above)
2. Open [http://localhost:8000](http://localhost:8000)
3. Fill in the campaign context fields (campaign ID, client ID, asset name, ICP)
4. Upload a CSV — use `sample_data/portal_leads_sample.csv` to test with real data
5. Results appear with color-coded scores, feature breakdowns, and a distribution chart

### Score leads via the API

```bash
# Single lead
curl -X POST http://localhost:8000/score \
  -H "Content-Type: application/json" \
  -d @data/prd_sample_payloads.py

# Batch upload via portal
curl -X POST http://localhost:8000/portal/import-score \
  -F "file=@sample_data/portal_leads_sample.csv" \
  -F 'campaign_context={"campaign_id":"HC-BOFU-2026-01","client_id":"client-001","asset_name":"2026 Healthcare ROI Guide","taxonomy":{"topic":"roi","asset_type":"guide","audience":"director"}}'
```

---

## Scoring a Lead — Step by Step

When a lead arrives (via portal upload or API), this is the exact sequence:

### 1. Parse and normalize the lead record

The lead's job title is parsed by `TitleNormalizer` → job function (finance, it, operations, etc.) + seniority (executive, vp, director, manager, practitioner). The asset name is classified into a funnel stage (TOFU / MOFU / BOFU).

### 2. Build the buying group context

The system looks up all previously scored leads from the same company domain and campaign from the audit database. It counts unique approved job functions and checks whether required personas for the campaign's vertical are covered.

### 3. Compute 14 feature signals

| Feature | Source | What it captures |
|---|---|---|
| `fit_score` | Title + firmographics vs campaign ICP | How well the lead's profile matches the intended audience |
| `intent_score` | Engagement events + content stage + buying group | How actively the prospect is evaluating |
| `partner_signal_score` | Partner's 6-month approval rates | Historical quality of the lead source |
| `client_history_score` | Client's 6-month acceptance rate at this account | Whether this client historically accepts leads from this domain |
| `campaign_history_score` | Campaign's prior approval rate | Whether this campaign has been performing well |
| `data_quality_score` | Email domain, job title, company size, geography | Lead record completeness and validity |
| `icp_match_score` | Industry + geography + role match to brief | Precision of alignment to the campaign's stated ICP |
| `authority_score` | Seniority level from title parsing | Seniority and decision-making influence |
| `buying_group_score` | Persona count + completeness + journey stage | Account-level buying committee signal |
| `unique_persona_count` | Count of distinct functions at account | Breadth of stakeholder engagement |
| `late_stage_signal` | Content stage weight | BOFU content = stronger purchase signal |
| `email_engagement_score` | Email opens/clicks/downloads | Depth of content engagement |
| `second_touch_signal` | Second email engagement | Re-engagement indicates sustained interest |
| `recency_score` | Days since last interaction | Recent engagement decays with 21-day half-life |

**Engagement event weights** (from `config/platform_config.yaml`):

| Event | Weight | Notes |
|-------|--------|-------|
| Email open | 8 | Base signal |
| Email click | 16 | Strong intent |
| Download | 22 | Strongest engagement signal |
| Page visit | 10 | Mid-level signal |
| Second email multiplier | 1.5× | Re-engagement bonus |

**BOFU content gets 4.5× the weight of TOFU content** because late-stage consumption is a much stronger purchase signal.

### 4. Predict approval probability (LightGBM model)

The 14 features feed into the promoted LightGBM model:

```
approval_score = model.predict_proba(features)[class=1] × 100
```

The model was trained on 150,000 labeled leads with out-of-fold encoding to prevent data leakage. It outputs a calibrated probability — a score of 75 means approximately 75% historical approval rate for leads with this profile.

**Model performance (current LightGBM):**

| Metric | Value | Interpretation |
|--------|-------|---------------|
| AUC-ROC | 0.748 | Model separates approved from rejected 74.8% of the time |
| KS Statistic | 0.378 | Max separation between approved/rejected probability distributions |
| Brier Score | 0.182 | Calibration quality (lower = better; 0 = perfect) |
| Lift @ Top 10% | 1.09× | Top-scored leads approve at 1.09× the base rate |
| CV AUC (5-fold) | 0.752 ± 0.003 | Stable — not overfit |

### 5. Apply thresholds and return results

Three outputs are returned for every lead:

- **`approval_score`** (0–100): the core score
- **`delivery_decision`**: DELIVER / REVIEW / HOLD
- **`predicted_outcome`**: APPROVED / REJECTED (threshold: 55)
- **`quadrant`**: PRIORITY / NURTURE / CHAMPION / MONITOR
- **`breakdown`**: all 7 primary feature scores
- **`top_reasons`**: 3 plain-English explanations of what drove the score
- **`buying_group`**: account-level persona and BDR trigger status

---

## Score Interpretation

### Approval score bands

```
90–100   Exceptional    Deliver immediately. Client acceptance nearly certain.
75–89    Strong         Deliver with confidence. Minor risk factors only.
68–74    Acceptable     Deliver. At or above threshold but worth monitoring partner quality.
50–67    Borderline     Queue for human review. Score is above "reject" but below "deliver".
35–49    Weak           Hold. Profile or data quality gaps likely to cause rejection.
0–34     Poor           Hold. Investigate partner quality or lead data integrity.
```

### Lead quadrant

The 2×2 quadrant uses `fit_score` (threshold: 65) and `intent_score` (threshold: 55):

| Quadrant | Fit | Intent | Action |
|----------|-----|--------|--------|
| **PRIORITY** | High | High | Deliver now — ideal lead |
| **NURTURE** | High | Low | Good profile, re-engage with MOFU/BOFU content |
| **CHAMPION** | Low | High | Engaged but outside ICP — watch for title/company change |
| **MONITOR** | Low | Low | Deprioritize — neither profile nor engagement is compelling |

### Feature score interpretation

| Feature | Below 40 | 40–65 | Above 65 |
|---------|----------|-------|----------|
| `fit_score` | Title or company mismatches ICP | Partial alignment | Strong ICP alignment |
| `intent_score` | No engagement signal | Passive engagement | Active evaluation behavior |
| `partner_signal_score` | Partner has poor approval history | Average partner | High-quality partner source |
| `data_quality_score` | Missing fields, generic email, review flagged | Acceptable quality | Complete, validated record |
| `client_history_score` | Client rarely accepts from this account | Neutral | Client has strong acceptance pattern here |

### BDR trigger

Fires when **2 or more distinct job functions** have approved leads at the same account in the same campaign. This means:
- Finance + IT engaged → buying committee is forming → BDR should reach out
- Only one function engaged → too early for sales, continue nurturing

---

## Retraining the Model

### What data is required

The model requires a **PRD feature table** — a CSV where each row is one labeled lead with these exact columns:

| Column | Type | Description |
|--------|------|-------------|
| `status` | string | **Required.** `approved` or `rejected` — the ground truth label |
| `authority_score` | float 0–100 | Seniority score derived from job title |
| `fit_score` | float 0–100 | Firmographic + title alignment to ICP |
| `intent_score` | float 0–100 | Engagement depth composite |
| `partner_signal_score` | float 0–100 | Partner's historical approval rate |
| `client_history_score` | float 0–100 | Client acceptance rate at account |
| `campaign_history_score` | float 0–100 | Campaign-level prior approval rate |
| `data_quality_score` | float 0–100 | Lead record completeness score |
| `icp_match_score` | float 0–100 | Industry + geography + role ICP match |
| `buying_group_score` | float 0–100 | Account-level persona completeness |
| `unique_persona_count` | int | Number of distinct functions at account |
| `late_stage_signal` | float 0–100 | Content funnel stage signal |
| `email_engagement_score` | float 0–100 | Email open/click/download engagement |
| `second_touch_signal` | float 0–100 | Second-email re-engagement signal |
| `recency_score` | float 0–100 | Days-since-last-engagement score |

**Optional columns that improve split quality:**

| Column | Description |
|--------|-------------|
| `submitted_at` | Timestamp — enables time-based train/test split (prevents temporal leakage) |
| `partner_id` | Partner identifier — used to build signal lookup tables |
| `client_id` | Client identifier — used to build approval rate tables |
| `campaign_id` | Campaign identifier — used to build per-campaign approval tables |

### Minimum viable dataset

| Requirement | Minimum | Recommended |
|-------------|---------|-------------|
| Total labeled rows | 100 | 10,000+ |
| Approved leads | 10 | Proportional to real distribution |
| Rejected leads | 10 | At least 5–10% of total |
| Feature columns present | 5 of 14 | All 14 |

With fewer than 60 training samples, calibration is skipped (raw GBC probabilities used instead of Platt-scaled). With fewer than 30, cross-validation is skipped.

### Building a feature table from raw data

If you have raw CRM/MAP export data instead of pre-computed scores, build the feature table first:

```bash
# From cleaned_data.xlsx (150K rows from real campaigns)
python3 scripts/build_prd_feature_table.py

# Output lands at:
# data_processed/prd_feature_table_full.csv
```

**Required columns in the source Excel/CSV for the feature builder:**

| Source Column | Used For |
|--------------|---------|
| `LEAD_STATUS` | Label (Accepted → approved, Rejected → rejected) |
| `PUBLISHER_NAME` | partner_signal_score (OOF target-encoded per publisher) |
| `JOB_FUNCTION` | authority_score, fit_score, icp_match_score |
| `INDUSTRY` | fit_score, icp_match_score |
| `COMPANY_SIZE` | fit_score, icp_match_score |
| `REGION` / `COUNTRY` | fit_score |
| `EMAIL_VALIDATION_STATUS` | data_quality_score |
| `LINKEDIN_URL` | data_quality_score (0 = no LinkedIn = -15 pts) |
| `IS_REQUIRE_REVIEW` | data_quality_score (1 = flagged = -20 pts) |
| `TOTAL_CLICKS` | email_engagement_score |
| `TOTAL_IMPRESSION` | email_engagement_score |
| `ASSET_PREDICTED_BUYER_STAGE` | late_stage_signal |
| `ACCOUNT_PREDICTED_STAGE` | buying_group_score |
| `ACCOUNT_TOTAL_TRENDING_TOPIC` | buying_group_score |

### Running the retrain

```bash
# Option 1 — from the command line
python3 scripts/run_monthly_retrain.py data_processed/prd_feature_table_full.csv

# Option 2 — force promote even if AUC does not improve
python3 scripts/run_monthly_retrain.py data_processed/prd_feature_table_full.csv --force-promote

# Option 3 — via API
curl -X POST http://localhost:8000/operations/retrain \
  -H "Content-Type: application/json" \
  -d '{"dataset_path": "data_processed/prd_feature_table_full.csv", "force_promote": false}'
```

The model is automatically promoted if the new AUC-ROC equals or exceeds the current baseline. Model artifacts land at:

```
models/prd_runtime/lead_quality_model.pkl      ← the trained model
models/prd_runtime/model_metadata.json         ← AUC, KS, Brier, Lift metrics
models/prd_runtime/signal_tables.json          ← per-partner/client approval rate lookups
```

### Comparing algorithms before promoting

```bash
# Benchmark all algorithms — no model change
python3 scripts/compare_models.py

# Benchmark and promote the winner
python3 scripts/compare_models.py --promote
```

**Current benchmark results (150K leads, LightGBM wins):**

```
Model                   AUC     CV AUC        KS      Brier   Lift@10
LightGBM             0.7481  0.7520±0.0027  0.3778   0.1820   1.0897  ← BEST
XGBoost              0.7408  0.7475±0.0031  0.3593   0.1963   1.0920
GradientBoosting     0.7326  0.7375±0.0034  0.3428   0.2033   1.0890
RandomForest         0.7264  0.7330±0.0037  0.3371   0.2031   1.0868
LogisticRegression   0.7138  0.7213±0.0043  0.3154   0.2101   1.0846
```

---

## How to Interpret Training Data

### Understanding the label distribution

The real dataset is heavily imbalanced: **90.4% approved / 9.6% rejected**. This is normal for B2B lead programs — most delivered leads are accepted. The model handles this via balanced sample weights during training. Do not artificially balance the classes — the imbalance reflects real business operations.

### What makes a lead "approved" vs "rejected"

From analysis of the 150K training leads:

| Signal | Approved leads | Rejected leads |
|--------|---------------|----------------|
| Publisher approval rate | High (>70%) | Low (<30%) |
| Job function | Consulting (97.5%), Executive (85%+) | Security (16.7%), Unknown |
| Email engagement | Higher clicks and impressions | Lower or zero |
| Email validation | Mixed (invalid emails paradoxically show high approval — data anomaly) | Flagged as risky |
| Company size | Mid-market to enterprise | Micro/small companies for enterprise campaigns |

### Key data quality rules

**`EMAIL_VALIDATION_STATUS`** — counter-intuitive: "invalid" emails show 97.9% acceptance rate in this dataset. This likely reflects that email validation happens after delivery, so invalid status = already delivered = already accepted. Do not use raw email validity as a rejection signal — use it only as a data completeness flag.

**`PUBLISHER_NAME`** — the single strongest predictor. Publisher approval rates range from 0% to 100% across 27 publishers. Always exclude test publishers (`Prod_Test_*`, `EvolveBPM`) — they have 0% acceptance and are not real lead sources.

**`TOTAL_CLICKS` and `TOTAL_IMPRESSION`** — highly sparse. The 75th percentile of clicks is 0. Use `log1p()` scaling — raw click counts are skewed and will dominate a linear model.

**`ASSET_PREDICTED_BUYER_STAGE`** — weak in isolation. Decision vs Awareness stage differs by only ~2% in approval rate. Combine with engagement counts to make it meaningful.

### What signals are NOT in the current training data (known gaps)

These signals exist conceptually in the PRD but could not be computed from `cleaned_data.xlsx`:

| Missing signal | Default used | Impact |
|----------------|-------------|--------|
| `client_history_score` | 50 (neutral) | Cannot learn client-specific acceptance patterns |
| `campaign_history_score` | 50 (neutral) | Cannot learn campaign-level performance trends |
| `recency_score` | 80 (high) | No submission timestamp available for decay |
| `second_touch_signal` | 0 | No multi-touch sequence data |
| `unique_persona_count` | 1 | No account-level persona history |

To improve model accuracy: collect and provide these signals in retraining data. The model's AUC ceiling is limited by the fact that all 14 features are pre-aggregated scores rather than raw signals.

### Closing the feedback loop (how to improve the model over time)

After leads are delivered and clients accept or reject them, feed those outcomes back:

```bash
# Label an outcome via API
curl -X POST http://localhost:8000/outcomes/label \
  -H "Content-Type: application/json" \
  -d '{
    "lead_id": "ACE-PRD-001",
    "campaign_id": "HC-BOFU-2026-01",
    "outcome": "approved",
    "notes": "Client confirmed in CRM on 2026-04-01"
  }'
```

Outcomes are stored in `actual_outcome` on the `ScoreAuditRecord` table. Export leads with non-null outcomes periodically and retrain:

```bash
# Export labeled outcomes from the audit DB, build new feature table, retrain
python3 scripts/run_monthly_retrain.py /path/to/outcome_labeled_feature_table.csv
```

The more real outcome data collected, the more the model learns actual client acceptance patterns vs historical publisher proxies.

---

## Architecture Overview

```
Incoming lead
     │
     ▼
portal/ingest.py          ← Parse CSV/Excel, map flexible headers to LeadRecord
     │
     ▼
platform/engine.py        ← BuyingIntelligenceService
  ├── TitleNormalizer      ← job_function + seniority from title text
  ├── AssetClassifier      ← TOFU/MOFU/BOFU from asset name + taxonomy
  ├── CampaignBriefParser  ← ICP extraction from brief text
  ├── _build_feature_vector ← 14 numeric signals (0–100 each)
  └── _predict_approval    ← LightGBM.predict_proba() × 100
                             (falls back to weighted heuristic if no model)
     │
     ▼
LeadScoreResult
  ├── approval_score       ← 0–100
  ├── delivery_decision    ← DELIVER / REVIEW / HOLD
  ├── predicted_outcome    ← APPROVED / REJECTED
  ├── quadrant             ← PRIORITY / NURTURE / CHAMPION / MONITOR
  ├── breakdown            ← all 7 primary feature scores
  ├── top_reasons          ← 3 plain-English explanations
  └── buying_group         ← account-level BDR trigger + persona coverage
```

**Runtime model files:**

```
models/prd_runtime/
├── lead_quality_model.pkl      ← LightGBM model (promoted 2026-04-02)
├── model_metadata.json         ← AUC 0.748, KS 0.378, algorithm: LightGBM
└── signal_tables.json          ← per-partner/client/vertical approval lookups
```

**Key source files:**

| File | Purpose |
|------|---------|
| `src/lead_scoring/api/app.py` | FastAPI endpoints |
| `src/lead_scoring/platform/engine.py` | Core scoring logic |
| `src/lead_scoring/platform/training.py` | Model training pipeline |
| `src/lead_scoring/platform/contracts.py` | All Pydantic data models |
| `src/lead_scoring/portal/ingest.py` | CSV/Excel intake and header aliasing |
| `scripts/build_prd_feature_table.py` | Build training data from raw CRM export |
| `scripts/compare_models.py` | Benchmark multiple algorithms |
| `scripts/run_monthly_retrain.py` | Trigger monthly model retrain |
| `config/platform_config.yaml` | Thresholds, weights, keyword mappings |

---

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Service status + active model mode |
| POST | `/score` | Score a single lead |
| POST | `/score/batch` | Score a list of leads |
| POST | `/portal/import-score` | Upload CSV, score all leads, return report |
| POST | `/buying-group/preview` | Preview buying group signal without scoring |
| GET | `/reports/campaign/{id}` | Account-level campaign report with BDR triggers |
| POST | `/outcomes/label` | Attach client acceptance/rejection to a scored lead |
| POST | `/operations/retrain` | Trigger model retrain from a feature table |
