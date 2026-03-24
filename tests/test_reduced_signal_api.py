"""Tests for ACE-vs-reduced-signal scoring routes and enriched responses."""

import pytest
from fastapi.testclient import TestClient

from lead_scoring.api.app import app
from lead_scoring.api.handlers import score_batch_leads, score_single_lead
from lead_scoring.database import connection as db_connection


@pytest.fixture
def scoring_client(tmp_path, monkeypatch):
    """Run the API against a temporary SQLite database."""
    db_path = tmp_path / "reduced-signal-test.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    db_connection._db_config = None

    with TestClient(app) as client:
        yield client

    db_connection._db_config = None


def test_single_lead_response_includes_ace_fitment_and_model(sample_lead_high_fit):
    response = score_single_lead(sample_lead_high_fit)

    assert response.success is True
    assert response.ace_scores is not None
    assert response.ace_scores.accuracy >= 0
    assert response.fitment is not None
    assert response.fitment.segment
    assert response.reduced_signal_model is not None
    assert 0 <= response.reduced_signal_model.score <= 100
    assert response.score_comparison is not None


def test_batch_response_summary_includes_ace_and_model_stats(
    sample_lead_high_fit,
    sample_lead_low_fit,
):
    response = score_batch_leads([sample_lead_high_fit, sample_lead_low_fit])

    assert response.success is True
    assert "average_ace_scores" in response.batch_summary
    assert "average_reduced_signal_score" in response.batch_summary
    assert "fitment_distribution" in response.batch_summary


def test_predict_reduced_signal_route(sample_lead_high_fit, scoring_client):
    payload = {"lead": sample_lead_high_fit.model_dump(mode="json"), "program_type": "abm"}
    response = scoring_client.post("/score/predict-reduced-signal", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["lead_id"] == sample_lead_high_fit.lead_id
    assert body["reduced_signal_model"]["model_name"] == "ReducedSignalXGBoost"
    assert body["ace_scores"]["client_fit"] >= 0
    assert body["fitment"]["segment"]


def test_compare_route(sample_lead_high_fit, scoring_client):
    payload = {"lead": sample_lead_high_fit.model_dump(mode="json"), "program_type": "abm"}
    response = scoring_client.post("/score/compare", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["ace_scoring"]["lead_id"] == sample_lead_high_fit.lead_id
    assert body["reduced_signal_model"]["score"] >= 0
    assert "summary" in body["score_comparison"]
