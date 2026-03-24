"""API tests for persisted feedback routes and drift-status compatibility."""

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from lead_scoring.api.app import app
from lead_scoring.database import connection as db_connection


@pytest.fixture
def feedback_client(tmp_path, monkeypatch):
    """Run the API against a temporary SQLite database."""
    db_path = tmp_path / "feedback-test.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    db_connection._db_config = None

    with TestClient(app) as client:
        yield client

    db_connection._db_config = None


def _feedback_payload(lead_id: str = "FB-TEST-001") -> dict:
    now = datetime.now(UTC)
    return {
        "lead_id": lead_id,
        "scored_at": (now - timedelta(days=2)).isoformat(),
        "feedback_at": now.isoformat(),
        "outcome": "accepted",
        "reason": "matched_expectations",
        "notes": "Sales accepted this lead.",
        "original_score": 74,
        "original_grade": "B",
        "sal_decision_maker": "seller@example.com",
    }


def test_submit_feedback_and_get_history(feedback_client):
    submit = feedback_client.post("/feedback", json=_feedback_payload())
    assert submit.status_code == 201
    assert submit.json()["feedback_count_stored"] == 1

    history = feedback_client.get("/feedback/FB-TEST-001")
    assert history.status_code == 200
    body = history.json()
    assert body["lead_id"] == "FB-TEST-001"
    assert body["feedback_count"] == 1
    assert body["feedback_history"][0]["reason"] == "matched_expectations"


def test_feedback_status_and_drift_status(feedback_client):
    feedback_client.post("/feedback", json=_feedback_payload("FB-TEST-002"))

    status_response = feedback_client.get("/feedback/status")
    assert status_response.status_code == 200
    status_body = status_response.json()
    assert status_body["total_feedback_items"] == 1
    assert status_body["feedback_by_outcome"]["accepted"] == 1

    drift_response = feedback_client.get("/drift-status")
    assert drift_response.status_code == 200
    drift_body = drift_response.json()
    assert drift_body["feedback_count"] == 1
    assert "recommendation" in drift_body["metrics"]


def test_clear_feedback_removes_persisted_rows(feedback_client):
    feedback_client.post("/feedback", json=_feedback_payload("FB-TEST-003"))

    clear_response = feedback_client.post("/feedback/clear")
    assert clear_response.status_code == 200
    assert "Cleared 1 feedback items" in clear_response.json()["message"]

    history = feedback_client.get("/feedback/FB-TEST-003")
    assert history.status_code == 404
