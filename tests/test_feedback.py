"""Tests for the current feedback and drift detection contracts."""

from datetime import datetime, timedelta

import pytest

from lead_scoring.feedback.drift import DriftDetector, RetrainingScheduler
from lead_scoring.feedback.models import (
    AcceptanceGuardrail,
    FeedbackOutcome,
    FeedbackReason,
    LeadFeedback,
)


def make_feedback(
    lead_id: str,
    outcome: FeedbackOutcome,
    reason: FeedbackReason,
    original_score: int,
    original_grade: str,
    scored_at: datetime | None = None,
    feedback_at: datetime | None = None,
    sal_decision_maker: str | None = "seller@example.com",
):
    now = datetime.utcnow()
    scored_at = scored_at or (now - timedelta(days=2))
    feedback_at = feedback_at or now
    return LeadFeedback(
        lead_id=lead_id,
        scored_at=scored_at,
        feedback_at=feedback_at,
        outcome=outcome,
        reason=reason,
        original_score=original_score,
        original_grade=original_grade,
        sal_decision_maker=sal_decision_maker,
    )


class TestDriftDetector:
    def test_detector_initialization(self):
        detector = DriftDetector()
        assert detector.baseline_acceptance_rate == 0.50

    def test_calculate_metrics(self):
        detector = DriftDetector()
        feedback_items = [
            make_feedback("L-1", FeedbackOutcome.ACCEPTED, FeedbackReason.EXCELLENT_FIT, 85, "A"),
            make_feedback("L-2", FeedbackOutcome.REJECTED, FeedbackReason.POOR_FIT, 25, "D"),
            make_feedback("L-3", FeedbackOutcome.ACCEPTED, FeedbackReason.STRONG_ENGAGEMENT, 75, "B"),
            make_feedback("L-4", FeedbackOutcome.REJECTED, FeedbackReason.WRONG_PERSONA, 35, "D"),
        ]

        metrics = detector.calculate_metrics(feedback_items, time_period_days=14)
        assert metrics.acceptance_rate == 0.5
        assert metrics.feedback_count == 4
        assert metrics.score_gap > 0

    def test_calculate_metrics_empty_feedback_raises(self):
        detector = DriftDetector()
        with pytest.raises(ValueError):
            detector.calculate_metrics([])

    def test_detect_drift(self):
        detector = DriftDetector()
        feedback_items = [
            make_feedback(f"L-{idx}", FeedbackOutcome.ACCEPTED, FeedbackReason.MATCHED_EXPECTATIONS, 75, "B")
            for idx in range(11)
        ] + [
            make_feedback(f"R-{idx}", FeedbackOutcome.REJECTED, FeedbackReason.POOR_FIT, 30, "D")
            for idx in range(9)
        ]
        metrics = detector.calculate_metrics(feedback_items)
        status, _, _ = detector.detect_drift(metrics)
        assert status == "drift_detected"


class TestRetrainingScheduler:
    def test_scheduler_initialization(self):
        scheduler = RetrainingScheduler()
        assert scheduler.min_feedback_count == 100

    def test_should_not_retrain_without_data(self):
        scheduler = RetrainingScheduler()
        should_retrain, reason = scheduler.should_retrain(20, "normal")
        assert should_retrain is False
        assert "Not enough data" in reason

    def test_should_retrain_on_critical_drift(self):
        scheduler = RetrainingScheduler()
        should_retrain, reason = scheduler.should_retrain(10, "critical_drift")
        assert should_retrain is True
        assert "Critical drift" in reason

    def test_next_retrain_opportunity(self):
        scheduler = RetrainingScheduler(min_feedback_count=10, max_days_since_retrain=30)
        opportunity = scheduler.next_retrain_opportunity(4, "normal")
        assert opportunity["items_needed_for_retrain"] == 6


class TestGuardrails:
    def test_guardrail_warnings_and_errors(self):
        guardrail = AcceptanceGuardrail(
            max_single_client_influence_pct=30.0,
            min_sample_size_per_class=2,
        )
        feedback_items = [
            make_feedback("L-1", FeedbackOutcome.ACCEPTED, FeedbackReason.EXCELLENT_FIT, 80, "B", sal_decision_maker="a@example.com"),
            make_feedback("L-2", FeedbackOutcome.ACCEPTED, FeedbackReason.EXCELLENT_FIT, 82, "B", sal_decision_maker="a@example.com"),
            make_feedback("L-3", FeedbackOutcome.ACCEPTED, FeedbackReason.EXCELLENT_FIT, 85, "A", sal_decision_maker="a@example.com"),
            make_feedback("L-4", FeedbackOutcome.REJECTED, FeedbackReason.POOR_FIT, 20, "D", sal_decision_maker="b@example.com"),
        ]

        result = guardrail.check_guardrails(feedback_items)
        assert result["passed"] is False
        assert result["errors"]
