# ACE Buying Intelligence Platform

A two-layer B2B lead scoring system that predicts whether a lead will be accepted by a client before it is delivered. Built on 150,000 labeled leads from real campaign data, trained with LightGBM (AUC-ROC 0.748, KS 0.378).

---

## Table of Contents

1. [How It Works](#how-it-works)
2. [Quick Start — Running the Service](#quick-start)
3. [Campaign Spec Parsing — XLSX and CSV](#campaign-spec-parsing)
4. [Lead File Parsing — How Unformatted Data Is Read](#lead-file-parsing)
5. [Scoring a Lead — Step by Step](#scoring-a-lead)
6. [Score Interpretation](#score-interpretation)
7. [Getting Leads to Score 68+](#getting-leads-to-score-68)
8. [Retraining the Model — What Data Is Required](#retraining-the-model)
9. [How to Interpret Training Data](#how-to-interpret-training-data)
10. [Architecture Overview](#architecture-overview)
11. [API Reference](#api-reference)

---

## How It Works

The platform has two layers that work together on every lead:

### Layer 1 — Lead Quality Score (0–100)

Predicts the probability that a client will accept this lead. The score is derived from 12 feature signals built from the lead's profile, engagement history, partner track record, and campaign alignment. A trained LightGBM model converts these signals into a calibrated approval probability.

**Decision output from the score:**

| Score Range | Decision | Meaning |
|-------------|----------|---------|
| 68–100 | **DELIVER** | High confidence — send to client |
| 50–67 | **REVIEW** | Borderline — human review recommended |
| 0–49 | **HOLD** | Likely rejection — do not deliver |

### Layer 2 — Buying Group Signal (Account-Level)

Across all leads from the same company domain and campaign, the system tracks how many distinct job functions have engaged (e.g. Finance + IT + Operations = 3). When 2 or more functions are active, a **BDR trigger** fires — indicating a real buying committee is forming and the account is ready for sales handoff.

Each lead response also includes an **account score** (0–100) that measures the account's overall readiness to buy from external intent, firmographic trajectory, and buying group maturity signals.

---

## Quick Start

### Prerequisites

```bash
pip install -e .
python3 -c "import lightgbm; print('LightGBM OK')"
```

### Start the API server

```bash
uvicorn lead_scoring.api.app:app --reload --port 8000
```

Open [http://localhost:8000](http://localhost:8000) for the operator portal.  
API docs at [http://localhost:8000/docs](http://localhost:8000/docs).

### Check which model is active

```bash
curl http://localhost:8000/health
```

If `runtime_model` is `"heuristic-baseline"`, the model file is missing — run the retrain step below.

### Score leads via the portal UI

1. Open [http://localhost:8000](http://localhost:8000)
2. Upload a campaign spec XLSX (or fill the form manually)
3. Drop a leads CSV or Excel file onto the upload zone
4. Results appear with color-coded scores, feature breakdowns, buying group card, and account scores

### Score leads via the API

```bash
# Single lead
curl -X POST http://localhost:8000/score \
  -H "Content-Type: application/json" \
  -d @data/prd_sample_payloads.py

# Batch upload with JSON campaign context
curl -X POST http://localhost:8000/portal/import-score \
  -F "file=@leads.csv" \
  -F 'campaign_context={"campaign_id":"HC-BOFU-2026-01","client_id":"client-001","asset_name":"2026 Healthcare ROI Guide"}'

# Batch upload with campaign spec XLSX (takes precedence)
curl -X POST http://localhost:8000/portal/import-score \
  -F "file=@leads.csv" \
  -F "campaign_spec_file=@campaign_spec.xlsx"
```

---

## Campaign Spec Parsing

The portal accepts a campaign spec as either an **XLSX file** or a **CSV file**. Upload it via the portal UI or the `/portal/import-score` endpoint. When uploaded through the portal UI, the form fields are immediately auto-populated from the parsed spec — no manual entry needed.

A separate `/portal/parse-spec` endpoint returns the parsed campaign context as JSON, which is what the portal uses to pre-fill the form.

### File format detection

The parser inspects the file automatically:

- Files ending in `.xlsx` or `.xls` → XLSX parser (uses `python-calamine`, a Rust-based reader with no XML dependency)
- Files ending in `.csv` → CSV parser (uses Python's built-in `csv` module)
- Files with no extension → sniffs the first bytes; `PK` magic header = XLSX, otherwise treated as CSV

### Supported sheet layouts

**Key-value layout** (one field per row, two columns):

```
Column A             Column B
─────────────────────────────────────────
Campaign ID          HC-BOFU-2026-01
Client ID            client-health-01
Campaign Name        Clinical ROI Acceleration
Asset Name           Clinical ROI Case Study
Industry             Healthcare, Life Sciences
Geography            US, Canada
Personas             CFO, VP Finance, IT Director
Approval Rate        0.77
Brief                Target enterprise hospitals evaluating ROI...
```

**Header-row layout** (fields as column headers, values in row 2):

```
Campaign ID     | Client ID        | Campaign Name           | Industry   | Geography
HC-BOFU-2026-01 | client-health-01 | Clinical ROI Acceleration | Healthcare | US
```

The parser tries key-value first. If the first column contains numeric values or fewer than 2 text rows, it falls back to header-row.

### Field name mapping (full alias table)

Field names are normalised before matching: lowercased, underscores and hyphens converted to spaces. The following variations are all accepted:

| Canonical field | Accepted names in the spec file |
|---|---|
| `campaign_id` | Campaign ID, Campaign, ID, Campaign Number, Camp ID, Camp, Campaign Ref, Reference, Ref, Campaign Code, Code |
| `client_id` | Client ID, Client, Advertiser, Company, Brand, Account, Client Name, Company Name, Brand Name, Account Name, Organization, Org, Customer, Sponsor |
| `campaign_name` | Campaign Name, Name |
| `asset_name` | Asset, Asset Name |
| `brief_text` | Brief, Description, Campaign Brief, Objective |
| `industries` | Industry, Industries, Vertical, Target Industry, Target Industries |
| `geographies` | Geography, Geographies, Geo, Region, Target Geo, Target Geography |
| `company_sizes` | Company Size, Company Sizes, Firmographic, Employee Count, Employees |
| `job_functions` | Job Function, Job Functions, Function, Functions, Department |
| `seniorities` | Seniority, Seniorities, Level, Job Level |
| `required_personas` | Persona, Personas, Required Personas, Buying Committee, Target Personas |
| `history_approval_rate` | Approval Rate, Historical Rate, History Approval Rate |

**List fields** (`industries`, `geographies`, `company_sizes`, `job_functions`, `seniorities`, `required_personas`) accept comma-separated values in a single cell: `Healthcare, Life Sciences` → `["Healthcare", "Life Sciences"]`.

### Auto-generation of missing IDs

`campaign_id` and `client_id` are no longer hard-required. If absent from the spec:

- `campaign_id` is derived by slugifying `campaign_name` if present (e.g. `"Q2 Healthcare Push"` → `"q2-healthcare-push"`), otherwise a random `camp-xxxxxxxx` is generated
- `client_id` is derived from the first word of `campaign_name` if present, otherwise a random `client-xxxxxx` is generated

If the spec provides explicit values they are always used as-is.

### Open-ended / unrecognised fields

Any field name not in the alias table is captured as `extra_context` and appended to `brief_text`. This means free-form columns like `"Target Segment"`, `"Campaign Objective"`, or `"Key Message"` are not dropped — they flow into the ICP brief parser and can influence how the campaign vertical is inferred.

### How the parsed spec affects scoring

Once parsed, the spec populates:

- `campaign_id`, `client_id`, `campaign_name`, `asset_name` on every lead in the run
- `target_profile.industries`, `geographies`, `job_functions`, `seniorities`, `company_sizes` — these drive ICP match scoring and fit score calculations
- `target_profile.required_personas` — used to construct a `BuyingGroupDefinition` that activates structured persona coverage tracking (rather than inferred mode)
- `history_approval_rate` — used as the campaign-level partner signal baseline when per-lead rates are absent

---

## Lead File Parsing

The portal accepts CSV or Excel (.xlsx/.xls) lead files with flexible, real-world column names. The header interpretation pipeline normalises column names and maps them to canonical field names before building lead records.

### How headers are normalised

Before matching, every column name goes through this pipeline:

1. Strip BOM characters (`\ufeff`) and leading/trailing whitespace
2. Lowercase the entire string
3. Insert underscores between camelCase words (`JobTitle` → `job_title`)
4. Replace any non-alphanumeric character with underscore (`Job Title` → `job_title`)
5. Strip leading/trailing underscores

Then a collapsed version (all non-alphanumeric characters removed) is compared against the alias table to catch variations like `EmailAddress` → `emailaddress` → matches `email`.

### Required columns

The following 7 columns must be present (by name or alias) for the file to be accepted:

| Canonical name | Example aliases |
|---|---|
| `email` | email_address, work_email, business_email, contact_email |
| `first_name` | firstname, fname, given_name |
| `last_name` | lastname, lname, surname, family_name |
| `job_title` | title, designation, role, contact_title |
| `company_name` | company, account_name, organization, organisation, business_name |
| `industry` | vertical, company_industry, industry_name |
| `geography` | geo, location, region, country, market, territory |

### How the `domain` field is handled

`domain` is **not required**. The parser derives it automatically:

1. If a `domain` column is present (or one of its aliases: `company_domain`, `website`, `company_website`, `web_domain`, `domain_name`) — that value is used directly
2. If no domain column exists — the domain is extracted from the lead's email address by splitting on `@` and taking the right-hand side

**Examples:**

| Email | Domain column | Resolved domain |
|---|---|---|
| `j.smith@acme.com` | *(absent)* | `acme.com` |
| `j.smith@acme.com` | `acme.com` | `acme.com` |
| `j.smith@acme.com` | `healthcare.acme.com` | `healthcare.acme.com` |
| `j.smith@gmail.com` | *(absent)* | `gmail.com` *(triggers generic email penalty in data quality score)* |

The domain is used to group leads by account for buying group aggregation and account scoring.

### Full column alias table

Every recognised column name and its accepted variations:

| Canonical field | Accepted column names |
|---|---|
| `lead_id` | leadid, lead_identifier, record_id |
| `submitted_at` | submission_date, submitted_date, created_at, created_date, timestamp, date |
| `source_partner` | partner, partner_name, lead_source, source |
| `email` | email_address, e_mail, work_email, business_email, contact_email |
| `first_name` | firstname, first, fname, given_name |
| `last_name` | lastname, last, lname, surname, family_name |
| `job_title` | title, designation, role, contact_title |
| `linkedin_url` | linkedin, linkedin_profile, linkedin_link |
| `company_name` | company, account_name, organization, organisation, business_name |
| `domain` | company_domain, website, company_website, web_domain, domain_name |
| `industry` | vertical, company_industry, industry_name |
| `geography` | geo, location, region, country, market, territory |
| `company_size` | employee_band, employee_size, employees, size, company_headcount |
| `partner_id` | partner_identifier |
| `approval_rate_6m` | partner_approval_rate_6m, partner_approval_rate, approval_rate |
| `approval_rate_client_6m` | client_partner_approval_rate_6m, partner_client_approval_rate_6m |
| `approval_rate_vertical_6m` | vertical_partner_approval_rate_6m, partner_vertical_approval_rate_6m |
| `client_acceptance_rate_6m` | client_approval_rate_6m, client_acceptance_rate, account_acceptance_rate_6m |
| `account_id` | company_id, account_identifier |
| `email1_opened` | email_1_opened, email1_open, opened_email_1 |
| `email1_clicked` | email_1_clicked, email1_click, clicked_email_1 |
| `email2_opened` | email_2_opened, email2_open, opened_email_2 |
| `email2_clicked` | email_2_clicked, email2_click, clicked_email_2 |
| `download_count` | downloads, downloaded, asset_downloads |
| `visit_count` | visits, page_visits, web_visits |
| `asset_name` | asset, content_name, content_title, resource_name, asset_title, content_piece |
| `headcount_6m_delta` | headcount_delta, employee_growth, headcount_change, employee_delta |
| `latest_funding_date` | funding_date, last_funding_date, investment_date |
| `funding_stage` | funding_round, investment_stage, funding_series |
| `executive_change_90d` | exec_change, executive_change, leadership_change, cxo_change |
| `tech_stack` | technology_stack, technologies, tech_tools, martech |
| `account_visit_count` | account_visits, account_page_views, company_visits, org_visits |

### Date/time parsing

The `submitted_at` field accepts many common date formats including JavaScript's `Date.toString()` output:

| Format | Example |
|---|---|
| ISO 8601 | `2026-03-15T10:30:00Z` |
| ISO with offset | `2026-03-15T10:30:00+05:30` |
| JavaScript Date | `Mon Mar 23 2026 15:36:03 GMT+0000 (Coordinated Universal Time)` |
| Date only | `2026-03-15` |
| US date | `03/15/2026` |
| EU date | `15/03/2026` |
| Dashed EU | `15-03-2026` |

If parsing fails, the submission time defaults to the current UTC timestamp.

### Firmographic columns (feed the account score)

When the following columns are present, they are parsed into a `FirmographicTrajectory` and fed directly into the account score's firmographic component (+25% weight):

| Column | Type | Effect on account score |
|---|---|---|
| `headcount_6m_delta` | integer (positive = growing) | +10 pts if ≥10 growth, +20 pts if ≥50 growth, −15 pts if ≤−20 shrink |
| `latest_funding_date` | date | +20 pts if funded in last 6 months, +8 pts if 6–18 months ago |
| `funding_stage` | string | Stored in context (used for model enrichment) |
| `executive_change_90d` | 1/0, true/false, yes/no | +12 pts (new CXO = re-evaluation cycle) |
| `tech_stack` | comma-separated string | +5 pts data completeness bonus |

### Engagement columns (feed the intent score)

Engagement events have the largest single impact on the final score. With a BOFU campaign, one click + one download alone can add **+18 points** to the final score:

| Column | Type | Scoring weight | Notes |
|---|---|---|---|
| `email1_clicked` | 0/1 | 16 pts × BOFU multiplier (4.5×) | Strongest email signal |
| `email1_opened` | 0/1 | 8 pts × multiplier | Passive signal |
| `email2_clicked` | 0/1 | 16 pts × 1.5 (second-touch) × multiplier | Re-engagement bonus |
| `email2_opened` | 0/1 | 8 pts × 1.5 × multiplier | |
| `download_count` | integer | 22 pts each × multiplier | Strongest overall signal |
| `visit_count` | integer | 10 pts each × multiplier | |
| `account_visit_count` | integer | Feeds Moody's site_visits tier in account score | |

Content stage multipliers: BOFU = 4.5×, MOFU = 2.0×, TOFU = 1.0×. All engagement scores are capped at 100.

### Partner approval rate columns

These columns directly set the `partner_signal_score` component (22% weight in the final score). All three are decimals between 0.0 and 1.0:

| Column | Meaning | Default when missing |
|---|---|---|
| `approval_rate_6m` | This partner's overall approval rate across all campaigns in last 6 months | 50 (neutral) |
| `approval_rate_client_6m` | This partner's approval rate for this specific client in last 6 months | — |
| `approval_rate_vertical_6m` | This partner's approval rate in this vertical in last 6 months | — |

The engine averages all available rates. A single rate of `0.72` replaces the 50 neutral default and contributes `72 × 0.22 = 15.8 pts` instead of `50 × 0.22 = 11 pts` — a net gain of +4.8 pts.

### What happens to unrecognised columns

Columns that don't match any alias are listed in the `warnings` field of the API response:
```
"Unused columns ignored: Campaign_Week, Lead_Tier, Internal_Notes..."
```
They are not parsed into the lead record but are not treated as errors.

---

## Scoring a Lead — Step by Step

When a lead arrives (via portal upload or API), this is the exact sequence:

### 1. Parse and normalize the lead record

The lead's job title is parsed by `TitleNormalizer` → job function (finance, it, operations, etc.) + seniority (executive, vp, director, manager, practitioner). The asset name is classified into a funnel stage (TOFU / MOFU / BOFU) using the campaign taxonomy and keyword config.

### 2. Build the buying group context

The system looks up all previously scored leads from the same company domain and campaign from the audit database. It counts unique approved job functions and checks whether required personas for the campaign's vertical are covered.

When a `BuyingGroupDefinition` is available (from the campaign spec's `required_personas`), the engine enters **structured mode** and maps each lead's job title against specific persona slots (e.g. "CFO" → Decision-Maker, "VP Engineering" → Influencer). In **inferred mode** (no definition), the engine uses vertical-specific default personas from `config/platform_config.yaml`.

### 3. Compute 12 feature signals

| Feature | Source | What it captures |
|---|---|---|
| `fit_score` | Title + firmographics vs campaign ICP | How well the lead's profile matches the intended audience |
| `intent_score` | Engagement events + content stage + buying group | How actively the prospect is evaluating |
| `partner_signal_score` | Partner's 6-month approval rates | Historical quality of the lead source |
| `data_quality_score` | Email domain, job title, company size, geography | Lead record completeness and validity |
| `icp_match_score` | Industry + geography + role match to brief | Precision of alignment to the campaign's stated ICP |
| `authority_score` | Seniority level from title parsing | Seniority and decision-making influence |
| `buying_group_score` | Persona count + completeness + journey stage | Account-level buying committee signal |
| `unique_persona_count` | Count of distinct functions at account | Breadth of stakeholder engagement |
| `late_stage_signal` | Content stage weight | BOFU content = stronger purchase signal |
| `email_engagement_score` | Email opens/clicks/downloads | Depth of content engagement |
| `second_touch_signal` | Second email engagement | Re-engagement indicates sustained interest |
| `recency_score` | Days since last interaction | Recent engagement decays with 21-day half-life |

**Seniority → authority score mapping:**

| Title level | Authority score |
|---|---|
| C-Suite / Executive | 95 |
| Vice President | 85 |
| Director | 72 |
| Manager | 58 |
| Practitioner / Individual Contributor | 42 |
| Unknown | 35 |

**Data quality penalties** (score starts at 100):

| Condition | Penalty |
|---|---|
| Email at generic domain (gmail, yahoo, hotmail, etc.) | −20 |
| Job title missing | −15 |
| Job function unresolvable from title | −12 |
| Company size missing | −10 |
| Geography missing | −8 |

### 4. Predict approval probability

The 12 features feed into the promoted LightGBM model:

```
approval_score = model.predict_proba(features)[class=1] × 100
```

**Heuristic baseline weights** (active when no promoted model exists):

| Component | Weight |
|-----------|--------|
| `fit_score` | 0.34 |
| `intent_score` | 0.27 |
| `partner_signal_score` | 0.22 |
| `data_quality_score` | 0.10 |
| `icp_match_score` | 0.07 |

Additional penalties: −8 pts if `data_quality_score < 45`; −10 pts if `partner_signal_score < 40`.

**Model performance (current LightGBM):**

| Metric | Value |
|--------|-------|
| AUC-ROC | 0.748 |
| KS Statistic | 0.378 |
| Brier Score | 0.182 |
| CV AUC (5-fold) | 0.752 ± 0.003 |

### 5. Apply thresholds and return results

Every lead response includes:

- **`approval_score`** (0–100)
- **`delivery_decision`**: DELIVER / REVIEW / HOLD
- **`predicted_outcome`**: APPROVED / REJECTED (threshold: 55)
- **`quadrant`**: PRIORITY / NURTURE / CHAMPION / MONITOR
- **`breakdown`**: 5 primary feature scores
- **`top_reasons`**: 3 plain-English explanations
- **`buying_group`**: persona coverage, BDR trigger, buying group score
- **`account_score`**: account-level readiness (intent, firmographic, maturity, recommended action)

---

## Score Interpretation

### Approval score bands

```
90–100   Exceptional    Deliver immediately. Client acceptance nearly certain.
75–89    Strong         Deliver with confidence. Minor risk factors only.
68–74    Acceptable     Deliver. At threshold — monitor partner quality.
50–67    Borderline     Queue for human review.
35–49    Weak           Hold. Profile or data quality gaps likely to cause rejection.
0–34     Poor           Hold. Investigate partner quality or lead data integrity.
```

### Lead quadrant

| Quadrant | Fit (≥65) | Intent (≥55) | Action |
|----------|-----------|--------------|--------|
| **PRIORITY** | ✓ | ✓ | Deliver now |
| **NURTURE** | ✓ | ✗ | Good profile, re-engage with BOFU content |
| **CHAMPION** | ✗ | ✓ | Engaged but outside ICP |
| **MONITOR** | ✗ | ✗ | Deprioritize |

### Buying group score formula

| Component | Weight | Description |
|-----------|--------|-------------|
| Function coverage | 35% | Unique job functions engaged (capped at 4, scaled to 100) |
| Persona completeness | 25% | % of required persona slots covered |
| Journey stage | 20% | TOFU=35, MOFU=65, BOFU=90 |
| Account history | 20% | Client's historical acceptance rate for this account |

### Account score formula

| Component | Weight | What feeds it |
|-----------|--------|---------------|
| Intent | 40% | Third-party intent surges (Bombora/MLI) + site visit count |
| Firmographic | 25% | Headcount growth, funding recency, exec changes, tech stack |
| Buying group maturity | 25% | Early=20, Developing=55, Mature=90 |
| Data completeness | 10% | Bonus for providing firmographic enrichment |

**Recommended action**: `accelerate` (≥70), `engage` (≥45), `hold` (<45).

---

## Getting Leads to Score 68+

Without enrichment data, leads typically score in the **40–55 range**. Here is exactly why and how to fix it.

### Baseline score breakdown (no enrichment)

| Component | Typical value | Contribution |
|---|---|---|
| `fit_score` ≈ 42 (Manager title, no ICP defined) | × 0.34 | 14.3 |
| `intent_score` ≈ 22 (BOFU late-stage only, no engagement data) | × 0.27 | 5.9 |
| `partner_signal_score` = 50 (no rates provided → neutral default) | × 0.22 | 11.0 |
| `data_quality_score` ≈ 72 (missing company_size, geography) | × 0.10 | 7.2 |
| `icp_match_score` ≈ 60 (no ICP defined → 0.6 default match) | × 0.07 | 4.2 |
| **Total** | | **≈ 42.6** |

### The four levers, ranked by impact

**Lever 1: Add engagement columns to the leads file (+15 to +18 pts)**

This is the single largest swing. Add these columns with 0/1 values for email flags and integers for counts:

```
email1_opened, email1_clicked, email2_opened, email2_clicked, download_count, visit_count
```

One click + one download on a BOFU campaign: raw score `(16+22) × 4.5 = 171` → capped at 100. Intent score jumps from 22 → 89. Final impact: `(89-22) × 0.27 = +18.1 pts`.

**Lever 2: Define ICP in campaign spec (+8 to +10 pts)**

When `industries`, `geographies`, and `job_functions` are set in the spec, match scores go from the 0.6 default (no target defined) to 1.0 (matched) or 0.0 (mismatched). For a well-matched lead, `fit_score` rises from ≈42 to ≈72. Impact: `(72-42) × 0.34 = +10.2 pts`.

**Lever 3: Provide partner approval rates (+4 to +5 pts)**

Add `approval_rate_6m` (decimal 0.0–1.0) as a column in the leads file. Even a modest 0.70 rate replaces the neutral 50 default. Impact: `(70-50) × 0.22 = +4.4 pts`.

**Lever 4: Include company_size and geography (+2 pts)**

Both avoid data quality penalties. Impact: `(90-72) × 0.10 = +1.8 pts`.

### Expected score with all levers

```
fit=75 × 0.34 + intent=85 × 0.27 + partner=72 × 0.22 + dq=90 × 0.10 + icp=85 × 0.07
= 25.5 + 22.95 + 15.84 + 9.0 + 5.95 = 79.2 → DELIVER ✓
```

### If the threshold itself is miscalibrated

The 68 threshold assumes enriched data. If leads consistently arrive without engagement or partner data, options are:

1. **Lower `deliver_score`** in `config/platform_config.yaml` (e.g. `62`) — business decision, widens delivery
2. **Train the ML model on real outcomes** — once 200+ labeled outcomes are collected, LightGBM replaces the heuristic and the threshold becomes empirically calibrated to your actual acceptance rates
3. **Collect outcomes via the API** — `POST /outcomes/label` and `POST /deals/outcome` store actual client decisions for retraining

---

## Retraining the Model

### What data is required

The model requires a **PRD feature table** — a CSV where each row is one labeled lead:

| Column | Type | Description |
|--------|------|-------------|
| `status` | string | **Required.** `approved` or `rejected` |
| `authority_score` | float 0–100 | Seniority score from title |
| `fit_score` | float 0–100 | Firmographic + title alignment to ICP |
| `intent_score` | float 0–100 | Engagement depth composite |
| `partner_signal_score` | float 0–100 | Partner's historical approval rate |
| `data_quality_score` | float 0–100 | Lead record completeness |
| `icp_match_score` | float 0–100 | ICP match score |
| `buying_group_score` | float 0–100 | Account-level persona completeness |
| `unique_persona_count` | int | Distinct functions at account |
| `late_stage_signal` | float 0–100 | Content funnel stage signal |
| `email_engagement_score` | float 0–100 | Email engagement depth |
| `second_touch_signal` | float 0–100 | Second-email re-engagement |
| `recency_score` | float 0–100 | Days-since-last-engagement score |

**Optional columns:**

| Column | Description |
|--------|-------------|
| `submitted_at` | Enables time-based train/test split (prevents temporal leakage) |
| `partner_id` | Builds per-partner signal lookup tables |
| `client_id` | Builds per-client approval rate tables |
| `campaign_id` | Builds per-campaign approval tables |

### Minimum viable dataset

| Requirement | Minimum | Recommended |
|-------------|---------|-------------|
| Total labeled rows | 100 | 10,000+ |
| Approved leads | 10 | Proportional to real distribution |
| Feature columns present | 5 of 12 | All 12 |

### Running the retrain

```bash
# Command line
python3 scripts/run_monthly_retrain.py data_processed/prd_feature_table_full.csv

# Force promote even if AUC does not improve
python3 scripts/run_monthly_retrain.py data_processed/prd_feature_table_full.csv --force-promote

# Via API
curl -X POST http://localhost:8000/operations/retrain \
  -H "Content-Type: application/json" \
  -d '{"dataset_path": "data_processed/prd_feature_table_full.csv", "force_promote": false}'
```

Artifacts:

```
models/prd_runtime/lead_quality_model.pkl      ← trained model
models/prd_runtime/model_metadata.json         ← AUC, KS, Brier, Lift
models/prd_runtime/signal_tables.json          ← per-partner/client approval lookups
```

---

## How to Interpret Training Data

### Label distribution

The real dataset is **90.4% approved / 9.6% rejected**. This is normal — most delivered leads are accepted. The model handles this via balanced sample weights. Do not artificially balance the classes.

### Key data quality rules

**`PUBLISHER_NAME`** — the single strongest predictor. Publisher approval rates range from 0% to 100% across 27 publishers. Always exclude test publishers (`Prod_Test_*`, `EvolveBPM`).

**`TOTAL_CLICKS`** — highly sparse (75th percentile = 0). Use `log1p()` scaling.

**`EMAIL_VALIDATION_STATUS`** — counter-intuitive: "invalid" emails show 97.9% acceptance because validation happens post-delivery. Use as a completeness flag only, not a rejection signal.

### Closing the feedback loop

```bash
curl -X POST http://localhost:8000/outcomes/label \
  -H "Content-Type: application/json" \
  -d '{
    "lead_id": "ACE-PRD-001",
    "campaign_id": "HC-BOFU-2026-01",
    "outcome": "approved",
    "notes": "Client confirmed in CRM 2026-04-01"
  }'
```

Outcomes are stored in `actual_outcome` on `ScoreAuditRecord`. Export rows with non-null outcomes periodically and retrain.

---

## Architecture Overview

```
Incoming lead
     │
     ▼
portal/ingest.py          ← Parse CSV/Excel, normalise headers, derive domain from email,
     │                       parse firmographic + engagement columns, build LeadRecord
     ▼
platform/engine.py        ← BuyingIntelligenceService
  ├── TitleNormalizer       ← job_function + seniority from title text
  ├── AssetClassifier       ← TOFU/MOFU/BOFU from asset name + taxonomy
  ├── CampaignBriefParser   ← ICP extraction from brief text
  ├── CampaignSpecParser    ← XLSX/CSV campaign spec → CampaignContext
  ├── _build_feature_vector ← 12 numeric signals (0–100 each)
  ├── _predict_approval     ← LightGBM.predict_proba() × 100
  │                            (falls back to weighted heuristic if no model)
  ├── _build_buying_group_summary ← structured or inferred persona coverage + BDR trigger
  └── _get_account_score_for_lead ← per-domain account readiness score
     │
     ▼
LeadScoreResult
  ├── approval_score        ← 0–100
  ├── delivery_decision     ← DELIVER / REVIEW / HOLD
  ├── predicted_outcome     ← APPROVED / REJECTED
  ├── quadrant              ← PRIORITY / NURTURE / CHAMPION / MONITOR
  ├── breakdown             ← 5 primary feature scores
  ├── top_reasons           ← 3 plain-English explanations
  ├── buying_group          ← BDR trigger, persona coverage, buying group score
  └── account_score         ← account readiness: intent, firmographic, maturity, action
```

**Runtime model files:**

```
models/prd_runtime/
├── lead_quality_model.pkl      ← LightGBM model
├── model_metadata.json         ← AUC, KS, Brier, Lift metrics
└── signal_tables.json          ← per-partner/client/vertical approval lookups
```

**Key source files:**

| File | Purpose |
|------|---------|
| `src/lead_scoring/api/app.py` | FastAPI endpoints |
| `src/lead_scoring/platform/engine.py` | Core scoring logic |
| `src/lead_scoring/platform/training.py` | Model training pipeline |
| `src/lead_scoring/platform/contracts.py` | All Pydantic data models |
| `src/lead_scoring/platform/brief_parser.py` | Campaign brief + XLSX/CSV spec parser |
| `src/lead_scoring/portal/ingest.py` | CSV/Excel intake, header aliasing, domain derivation |
| `config/platform_config.yaml` | Thresholds, weights, keyword mappings |

---

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Service status + active model mode |
| POST | `/score` | Score a single lead |
| POST | `/score/batch` | Score a list of leads — account score computed once per domain |
| POST | `/portal/parse-spec` | Parse a campaign spec XLSX/CSV and return JSON — used by the portal to pre-fill the form |
| POST | `/portal/import-score` | Upload leads file + campaign context, score all leads, return report |
| POST | `/buying-group/preview` | Preview buying group signal without scoring |
| GET | `/reports/campaign/{id}` | Account-level campaign report with BDR triggers |
| POST | `/accounts/score` | Score an account from intent + firmographic signals |
| GET | `/accounts/{domain}/profile` | Return the most recently stored account score |
| POST | `/outcomes/label` | Attach client acceptance/rejection to a scored lead |
| POST | `/deals/outcome` | Record CRM deal outcome (closed_won, closed_lost, etc.) |
| POST | `/operations/retrain` | Trigger model retrain from a feature table |

### `/portal/import-score` — form fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `file` | File | Yes | Lead data — CSV or Excel (.xlsx/.xls) |
| `campaign_spec_file` | File | No | Campaign spec XLSX/CSV — takes precedence over `campaign_context` if both supplied |
| `campaign_context` | String (JSON) | No | Campaign context as JSON — used when no spec file is provided |

### `/portal/parse-spec` — form fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `campaign_spec_file` | File | Yes | Campaign spec XLSX or CSV to parse |

Returns a `CampaignContext` JSON object with all parsed fields.
