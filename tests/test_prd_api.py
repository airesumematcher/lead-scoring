"""Regression tests for the revised PRD-aligned API."""

from io import BytesIO
import json
from pathlib import Path
import sys

from fastapi.testclient import TestClient
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from data.prd_sample_payloads import build_priority_lead, build_supporting_it_lead
from lead_scoring.api.app import app
from lead_scoring.database import connection as db_connection


@pytest.fixture
def prd_client(tmp_path, monkeypatch):
    """Run the revised API against an isolated SQLite database."""
    db_path = tmp_path / "prd-api.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    db_connection._db_config = None

    with TestClient(app) as client:
        yield client

    db_connection._db_config = None


def test_score_endpoint_returns_prd_contract(prd_client):
    lead = build_priority_lead()

    response = prd_client.post("/score", json={"lead": lead.model_dump(mode="json")})

    assert response.status_code == 200
    body = response.json()
    assert body["delivery_decision"] == "deliver"
    assert body["predicted_outcome"] == "approved"
    assert body["quadrant"] == "Priority"
    assert body["buying_group"]["bdr_trigger"] is True
    assert len(body["top_reasons"]) == 3


def test_campaign_report_reflects_multi_persona_signal(prd_client):
    primary = build_priority_lead()
    secondary = build_supporting_it_lead()

    prd_client.post("/score", json={"lead": primary.model_dump(mode="json")})
    prd_client.post("/score", json={"lead": secondary.model_dump(mode="json")})

    response = prd_client.get(f"/reports/campaign/{primary.campaign.campaign_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["total_accounts"] == 1
    assert body["accounts_with_bdr_trigger"] == 1
    assert body["report_items"][0]["unique_persona_count"] >= 2


def test_portal_import_score_accepts_csv_with_flexible_headers(prd_client):
    lead = build_priority_lead()
    campaign_context = {
        "client_id": lead.campaign.client_id,
        "campaign_id": lead.campaign.campaign_id,
        "campaign_name": lead.campaign.campaign_name,
        "asset_name": lead.campaign.asset_name,
        "asset_type": lead.campaign.taxonomy.asset_type,
        "asset_stage_override": lead.campaign.taxonomy.asset_stage_override.value,
        "topic": lead.campaign.taxonomy.topic,
        "audience": lead.campaign.taxonomy.audience,
        "volume": lead.campaign.taxonomy.volume,
        "sequence": lead.campaign.taxonomy.sequence,
        "vertical_override": lead.campaign.taxonomy.vertical_override,
        "history_approval_rate": lead.campaign.history_approval_rate,
        "partner_id": lead.partner_signals.partner_id,
        "approval_rate_6m": lead.partner_signals.approval_rate_6m,
        "approval_rate_client_6m": lead.partner_signals.approval_rate_client_6m,
        "approval_rate_vertical_6m": lead.partner_signals.approval_rate_vertical_6m,
        "client_acceptance_rate_6m": lead.account_signals.client_acceptance_rate_6m,
        "brief_text": lead.campaign.brief_text,
    }
    csv_body = "\n".join(
        [
            "Email Address,First Name,Last Name,Title,Company,Website,Vertical,Country,Employees,Partner Approval Rate,Email 1 Opened,Email 1 Clicked,Email 2 Opened",
            "nina.carter@northstarhealth.com,Nina,Carter,VP Clinical Operations,Northstar Health,northstarhealth.com,healthcare,United States,1000+,0.81,1,1,1",
        ]
    )

    response = prd_client.post(
        "/portal/import-score",
        data={"campaign_context": json.dumps(campaign_context)},
        files={"file": ("leads.csv", csv_body, "text/csv")},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["detected_format"] == "csv"
    assert body["total_rows"] == 1
    result = body["batch_result"]["results"][0]
    assert result["delivery_decision"] in {"deliver", "review", "hold"}
    assert isinstance(result["approval_score"], int)
    assert result["model_version"] is not None
    assert body["interpreted_headers"]["email"] == "Email Address"
    assert body["interpreted_headers"]["company_name"] == "Company"
    assert body["interpreted_headers"]["domain"] == "Website"


def test_portal_import_score_accepts_excel(prd_client):
    lead = build_priority_lead()
    campaign_context = {
        "client_id": lead.campaign.client_id,
        "campaign_id": lead.campaign.campaign_id,
        "campaign_name": lead.campaign.campaign_name,
        "asset_name": lead.campaign.asset_name,
        "asset_type": lead.campaign.taxonomy.asset_type,
        "asset_stage_override": lead.campaign.taxonomy.asset_stage_override.value,
        "topic": lead.campaign.taxonomy.topic,
        "audience": lead.campaign.taxonomy.audience,
        "volume": lead.campaign.taxonomy.volume,
        "sequence": lead.campaign.taxonomy.sequence,
        "vertical_override": lead.campaign.taxonomy.vertical_override,
        "history_approval_rate": lead.campaign.history_approval_rate,
        "partner_id": lead.partner_signals.partner_id,
        "approval_rate_6m": lead.partner_signals.approval_rate_6m,
        "approval_rate_client_6m": lead.partner_signals.approval_rate_client_6m,
        "approval_rate_vertical_6m": lead.partner_signals.approval_rate_vertical_6m,
        "client_acceptance_rate_6m": lead.account_signals.client_acceptance_rate_6m,
        "brief_text": lead.campaign.brief_text,
    }
    frame = pd.DataFrame(
        [
            {
                "Email Address": "nina.carter@northstarhealth.com",
                "First Name": "Nina",
                "Last Name": "Carter",
                "Title": "VP Clinical Operations",
                "Company": "Northstar Health",
                "Website": "northstarhealth.com",
                "Vertical": "healthcare",
                "Country": "United States",
                "Employees": "1000+",
                "Email 1 Opened": 1,
                "Email 1 Clicked": 1,
                "Email 2 Opened": 1,
            }
        ]
    )
    buffer = BytesIO()
    frame.to_excel(buffer, index=False)
    buffer.seek(0)

    response = prd_client.post(
        "/portal/import-score",
        data={"campaign_context": json.dumps(campaign_context)},
        files={
            "file": (
                "leads.xlsx",
                buffer.getvalue(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["detected_format"] == "excel"
    assert body["total_rows"] == 1
    assert body["batch_result"]["results"][0]["approval_score"] > 0
