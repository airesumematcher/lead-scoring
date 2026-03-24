"""Tests for the live API schemas and handler contracts."""

import json

import pytest
from pydantic import ValidationError

from lead_scoring.api.handlers import score_batch_leads, score_single_lead
from lead_scoring.api.schemas import (
    BatchScoringRequest,
    BatchScoringResponse,
    ScoringRequest,
    ScoringResponse,
)
from lead_scoring.models import ConfidenceBand, Freshness, Grade, RecommendedAction


class TestRequestSchemas:
    def test_score_request_valid(self, sample_lead_high_fit):
        request = ScoringRequest(lead=sample_lead_high_fit)
        assert request.lead.lead_id == sample_lead_high_fit.lead_id

    def test_score_request_serializable(self, sample_lead_high_fit):
        request = ScoringRequest(lead=sample_lead_high_fit)
        request_dict = request.model_dump(mode="json")
        assert "lead" in request_dict

    def test_batch_request_valid(self, sample_lead_high_fit, sample_lead_low_fit):
        request = BatchScoringRequest(leads=[sample_lead_high_fit, sample_lead_low_fit])
        assert len(request.leads) == 2

    def test_batch_request_empty_rejected(self):
        with pytest.raises(ValidationError):
            BatchScoringRequest(leads=[])


class TestResponseSchemas:
    def test_score_response_valid(self):
        response = ScoringResponse(
            success=True,
            lead_id="TEST-001",
            score=75,
            grade=Grade.B,
            confidence=ConfidenceBand.MEDIUM,
            freshness=Freshness.FRESH,
            recommended_action=RecommendedAction.NURTURE,
            summary="Viable prospect for nurture cadence.",
            drivers=["Strong fit", "Good data quality", "Recent activity"],
            limiters=["Needs more engagement", "Moderate firmographic confidence"],
            pipeline_influence_score=65,
            adjustments_applied=[],
        )

        assert response.success is True
        assert response.score == 75

    def test_score_response_serializable(self):
        response = ScoringResponse(
            success=True,
            lead_id="TEST-001",
            score=75,
            grade=Grade.B,
            confidence=ConfidenceBand.MEDIUM,
            freshness=Freshness.FRESH,
            recommended_action=RecommendedAction.NURTURE,
            summary="Viable prospect for nurture cadence.",
            drivers=["Strong fit", "Good data quality", "Recent activity"],
            limiters=["Needs more engagement", "Moderate firmographic confidence"],
            pipeline_influence_score=65,
            adjustments_applied=[],
        )
        response_dict = response.model_dump(mode="json")
        assert response_dict["score"] == 75

    def test_batch_response_valid(self):
        response = BatchScoringResponse(
            success=True,
            total_leads=0,
            scored_leads=0,
            failed_leads=0,
            results=[],
            batch_summary={"average_score": 0.0},
        )
        assert response.total_leads == 0


class TestHandlers:
    def test_handle_single_score_success(self, sample_lead_high_fit):
        response = score_single_lead(sample_lead_high_fit)
        assert response.success is True
        assert response.lead_id == sample_lead_high_fit.lead_id
        assert response.score is not None

    def test_handle_single_score_low_fit(self, sample_lead_low_fit):
        response = score_single_lead(sample_lead_low_fit)
        assert response.lead_id == sample_lead_low_fit.lead_id

    def test_handle_batch_score_success(self, sample_lead_high_fit, sample_lead_low_fit):
        response = score_batch_leads([sample_lead_high_fit, sample_lead_low_fit])
        assert response.success is True
        assert response.total_leads == 2
        assert response.scored_leads == 2

    def test_handle_batch_score_empty(self):
        response = score_batch_leads([])
        assert response.total_leads == 0
        assert response.scored_leads == 0


class TestResponseFormatting:
    def test_score_response_format(self, sample_lead_high_fit):
        response = score_single_lead(sample_lead_high_fit)
        response_dict = response.model_dump(mode="json")
        assert "success" in response_dict
        assert "lead_id" in response_dict
        assert "score" in response_dict
        assert "grade" in response_dict

    def test_batch_response_format(self, sample_lead_high_fit):
        response = score_batch_leads([sample_lead_high_fit])
        response_dict = response.model_dump(mode="json")
        assert "success" in response_dict
        assert "total_leads" in response_dict
        assert "scored_leads" in response_dict

    def test_response_json_serialization(self, sample_lead_high_fit):
        response = score_single_lead(sample_lead_high_fit)
        json_str = json.dumps(response.model_dump(mode="json"))
        assert isinstance(json_str, str)
