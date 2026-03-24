# Quick Start

This repo now runs the revised March 2026 PRD version of ACE: a two-layer buying-intelligence platform.

Canonical project memory: [PROJECT_CONTEXT.md](PROJECT_CONTEXT.md)

## 1. Install

```bash
cd /Users/schadha/Desktop/lead-scoring
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
```

## 2. Verify

```bash
python verify_setup.py
```

What this checks:
- PRD runtime imports
- Two-layer scoring logic
- API endpoints
- Buying-group reporting
- Retraining workflow

## 3. Start the API

```bash
uvicorn lead_scoring.api.app:app --host 0.0.0.0 --port 8000
```

Open:
- `http://127.0.0.1:8000`
- `http://127.0.0.1:8000/docs`

At `http://127.0.0.1:8000` you now get a lightweight portal UI for:
- CSV / Excel upload
- campaign-context CSV upload
- campaign context setup
- auto-scoring on import
- scored output export
- campaign buying-group report review

Template buttons in the portal:
- `Lead CSV Template`: downloads a populated example row so the file is easier to edit and re-upload
- `Campaign CSV Template`: downloads a one-row campaign-context file that can be imported directly into the form

## 4. Score a Lead

```bash
curl -X POST http://127.0.0.1:8000/score \
  -H "Content-Type: application/json" \
  -d '{
    "lead": {
      "lead_id": "ACE-LOCAL-001",
      "submitted_at": "2026-03-22T10:00:00Z",
      "source_partner": "partner-alpha",
      "contact": {
        "email": "nina.carter@northstarhealth.com",
        "first_name": "Nina",
        "last_name": "Carter",
        "job_title": "VP Clinical Operations"
      },
      "company": {
        "company_name": "Northstar Health",
        "domain": "northstarhealth.com",
        "industry": "healthcare",
        "geography": "United States",
        "company_size": "1000+"
      },
      "campaign": {
        "campaign_id": "HC-BOFU-2026-01",
        "client_id": "client-health-01",
        "campaign_name": "Clinical ROI Acceleration",
        "brief_text": "Target healthcare provider executives across clinical, finance, and IT teams in the United States.",
        "asset_name": "Clinical ROI Case Study",
        "target_profile": {
          "industries": ["healthcare"],
          "geographies": ["united states"],
          "company_sizes": ["enterprise", "1000+"],
          "job_functions": ["clinical", "finance", "it"],
          "seniorities": ["executive", "vp", "director"],
          "required_personas": ["clinical", "finance", "it"]
        },
        "taxonomy": {
          "asset_type": "case study",
          "topic": "decision",
          "audience": "late stage shortlist",
          "volume": "highly targeted",
          "sequence": "decision",
          "asset_stage_override": "BOFU",
          "vertical_override": "healthcare"
        },
        "history_approval_rate": 0.77
      },
      "partner_signals": {
        "partner_id": "partner-alpha",
        "approval_rate_6m": 0.81,
        "approval_rate_client_6m": 0.79,
        "approval_rate_vertical_6m": 0.76
      },
      "account_signals": {
        "account_id": "acct-northstar-health",
        "client_acceptance_rate_6m": 0.74,
        "recent_personas": [
          {
            "lead_id": "ACE-HIST-100",
            "email": "marta.fin@northstarhealth.com",
            "full_name": "Marta Fin",
            "job_title": "Director Finance",
            "job_function": "finance",
            "seniority": "director",
            "status": "approved",
            "asset_name": "ROI Checklist",
            "asset_stage": "BOFU",
            "occurred_at": "2026-03-10T10:00:00Z"
          }
        ]
      },
      "engagement_events": [
        {
          "event_type": "open",
          "occurred_at": "2026-03-16T10:00:00Z",
          "asset_name": "Clinical ROI Case Study",
          "email_number": 1
        },
        {
          "event_type": "download",
          "occurred_at": "2026-03-21T10:00:00Z",
          "asset_name": "Clinical ROI Case Study",
          "email_number": 2
        }
      ]
    }
  }'
```

## 5. Preview the Buying Group Signal

```bash
curl -X POST http://127.0.0.1:8000/buying-group/preview \
  -H "Content-Type: application/json" \
  -d @payload.json
```

## 6. Pull a Campaign Report

Score leads for a campaign first, then:

```bash
curl http://127.0.0.1:8000/reports/campaign/HC-BOFU-2026-01
```

## 7. Store the Actual Client Outcome

```bash
curl -X POST http://127.0.0.1:8000/outcomes/label \
  -H "Content-Type: application/json" \
  -d '{
    "lead_id": "ACE-LOCAL-001",
    "campaign_id": "HC-BOFU-2026-01",
    "outcome": "approved",
    "notes": "Client accepted the lead"
  }'
```

## 8. Run Monthly Retraining

The retrain job expects a Phase 1/Phase 2 PRD feature table. At minimum it should contain:
- `status`
- the runtime feature columns such as `fit_score`, `intent_score`, `partner_signal_score`, `icp_match_score`

Run it from the CLI:

```bash
python scripts/run_monthly_retrain.py /absolute/path/to/prd_feature_table.csv
```

Or via API:

```bash
curl -X POST http://127.0.0.1:8000/operations/retrain \
  -H "Content-Type: application/json" \
  -d '{
    "dataset_path": "/absolute/path/to/prd_feature_table.csv",
    "force_promote": false
  }'
```

## 9. Restart After Promotion

If retraining promotes a model, restart the API so the new bundle is loaded:

```bash
pkill -f "uvicorn lead_scoring.api.app:app"
uvicorn lead_scoring.api.app:app --host 0.0.0.0 --port 8000
```
