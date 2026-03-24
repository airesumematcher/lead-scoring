"""Feedback loop API endpoints backed by the local database."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from lead_scoring.database.connection import DatabaseManager, get_session
from lead_scoring.feedback.drift import DriftDetector, RetrainingScheduler
from lead_scoring.feedback.models import (
    AcceptanceGuardrail,
    BatchFeedback,
    DriftMetrics,
    FeedbackOutcome,
    FeedbackReason,
    LeadFeedback,
    RetariningTrigger,
)


router = APIRouter(prefix="/feedback", tags=["Feedback Loop"])

_drift_detector = DriftDetector(baseline_acceptance_rate=0.50)
_retrain_scheduler = RetrainingScheduler(min_feedback_count=100, max_days_since_retrain=30)
_guardrail = AcceptanceGuardrail()


class FeedbackSubmissionResponse(BaseModel):
    """Response when feedback is submitted."""

    success: bool
    message: str
    feedback_count_stored: int
    timestamp: datetime


class FeedbackAnalyticsResponse(BaseModel):
    """Response with drift metrics and analytics."""

    success: bool
    metrics: DriftMetrics
    summary: dict
    drift_status: str
    retraining_recommended: bool
    notes: str


class DriftStatusResponse(BaseModel):
    """Compatibility response for top-level drift checks."""

    status: str
    drift_detected: bool
    metrics: dict
    feedback_count: int
    timestamp: str


def _get_manager() -> DatabaseManager:
    """Create a short-lived database manager."""
    return DatabaseManager(get_session())


def _normalize_datetime(value: datetime | None, fallback: datetime) -> datetime:
    """Normalize datetimes to UTC-aware values."""
    if value is None:
        return fallback
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _feedback_payload(feedback: LeadFeedback) -> str:
    """Store extra feedback fields without requiring a DB migration."""
    payload = {
        "scored_at": _normalize_datetime(feedback.scored_at, feedback.feedback_at).isoformat(),
        "feedback_at": _normalize_datetime(feedback.feedback_at, feedback.feedback_at).isoformat(),
        "original_grade": feedback.original_grade,
        "user_notes": feedback.notes,
    }
    return json.dumps(payload)


def _decode_feedback_payload(raw_notes: str | None) -> dict:
    """Decode stored feedback metadata from the notes column."""
    if not raw_notes:
        return {}
    try:
        return json.loads(raw_notes)
    except json.JSONDecodeError:
        return {"user_notes": raw_notes}


def _coerce_outcome(value: str | None) -> FeedbackOutcome:
    """Convert stored values into the feedback outcome enum."""
    try:
        return FeedbackOutcome(value or FeedbackOutcome.NEUTRAL.value)
    except ValueError:
        return FeedbackOutcome.NEUTRAL


def _coerce_reason(value: str | None) -> FeedbackReason:
    """Convert stored values into the feedback reason enum."""
    try:
        return FeedbackReason(value or FeedbackReason.UNCLEAR.value)
    except ValueError:
        return FeedbackReason.UNCLEAR


def _ensure_feedback_lead(manager: DatabaseManager, feedback: LeadFeedback) -> None:
    """Create a lightweight lead record when feedback arrives before persistence."""
    existing = manager.get_lead(feedback.lead_id)
    if existing is not None:
        return

    manager.add_lead(
        lead_id=feedback.lead_id,
        email=f"{feedback.lead_id.lower()}@feedback.local",
        first_name="Feedback",
        last_name="Only",
        company_name="Unknown",
    )


def _store_feedback(manager: DatabaseManager, feedback: LeadFeedback) -> None:
    """Persist a feedback item and write an audit log."""
    _ensure_feedback_lead(manager, feedback)

    manager.add_feedback(
        lead_id=feedback.lead_id,
        outcome=feedback.outcome.value,
        reason=feedback.reason.value,
        provided_score=None,
        actual_score=float(feedback.original_score),
        submitted_by=feedback.sal_decision_maker,
        submitted_at=_normalize_datetime(feedback.feedback_at, feedback.feedback_at).replace(tzinfo=None),
        notes=_feedback_payload(feedback),
    )
    manager.add_audit_log(
        operation="feedback",
        lead_id=feedback.lead_id,
        status="success",
        details=f"Stored feedback outcome={feedback.outcome.value}",
    )


def _record_to_feedback(record) -> LeadFeedback:
    """Rehydrate a DB feedback row into the API model used for analytics."""
    payload = _decode_feedback_payload(record.notes)
    submitted_at = record.submitted_at or datetime.utcnow()
    feedback_at = _normalize_datetime(
        datetime.fromisoformat(payload["feedback_at"]) if payload.get("feedback_at") else None,
        submitted_at,
    )
    scored_at = _normalize_datetime(
        datetime.fromisoformat(payload["scored_at"]) if payload.get("scored_at") else None,
        submitted_at,
    )

    return LeadFeedback(
        lead_id=record.lead_id,
        scored_at=scored_at.replace(tzinfo=None),
        feedback_at=feedback_at.replace(tzinfo=None),
        outcome=_coerce_outcome(record.outcome),
        reason=_coerce_reason(record.reason),
        notes=payload.get("user_notes"),
        original_score=int(round(record.actual_score or 0)),
        original_grade=payload.get("original_grade", "C"),
        sal_decision_maker=record.submitted_by,
    )


def _load_feedback_items(lead_id: Optional[str] = None) -> List[LeadFeedback]:
    """Load persisted feedback items from the database."""
    manager = _get_manager()
    try:
        if lead_id:
            records = manager.get_feedback_for_lead(lead_id)
        else:
            records = manager.get_all_feedback()
        return [_record_to_feedback(record) for record in records]
    finally:
        manager.close()


def _filter_feedback_by_days(
    feedback_items: List[LeadFeedback],
    days: Optional[int],
) -> List[LeadFeedback]:
    """Filter feedback to the requested time window."""
    if not days or days <= 0:
        return feedback_items

    cutoff = datetime.utcnow() - timedelta(days=days)
    return [item for item in feedback_items if item.feedback_at >= cutoff]


def _build_trigger_payload(
    feedback_count: int,
    drift_status: str,
    reason: str,
) -> list[dict]:
    """Build a small list of active retraining triggers for status responses."""
    should_retrain, retrain_reason = _retrain_scheduler.should_retrain(
        feedback_count=feedback_count,
        drift_status=drift_status,
        last_retrain_date=None,
    )
    if not should_retrain:
        return []

    trigger = RetariningTrigger(
        trigger_type="drift" if drift_status != "normal" else "schedule",
        reason=retrain_reason or reason,
        recommended_action="retrain",
        severity="high" if drift_status == "critical_drift" else "medium",
    )
    return [
        {
            "trigger_type": trigger.trigger_type,
            "triggered_at": trigger.triggered_at.isoformat(),
            "severity": trigger.severity,
            "reason": trigger.reason,
        }
    ]


def get_drift_status_payload() -> dict:
    """Return a root-level drift status response."""
    feedback_items = _load_feedback_items()

    if not feedback_items:
        return DriftStatusResponse(
            status="ok",
            drift_detected=False,
            metrics={
                "acceptance_rate": 0.0,
                "acceptance_rate_change": 0.0,
                "score_gap": 0.0,
                "recommendation": "Collect feedback before evaluating drift.",
            },
            feedback_count=0,
            timestamp=datetime.utcnow().isoformat(),
        ).model_dump()

    metrics = _drift_detector.calculate_metrics(feedback_items, time_period_days=30)
    drift_status, drift_reason, _ = _drift_detector.detect_drift(metrics)
    status_map = {
        "normal": "ok",
        "drift_detected": "warning",
        "critical_drift": "critical",
    }
    return DriftStatusResponse(
        status=status_map[drift_status],
        drift_detected=drift_status != "normal",
        metrics={
            "acceptance_rate": metrics.acceptance_rate,
            "acceptance_rate_change": metrics.acceptance_rate_change_pct,
            "score_gap": metrics.score_gap,
            "recommendation": drift_reason,
        },
        feedback_count=len(feedback_items),
        timestamp=datetime.utcnow().isoformat(),
    ).model_dump()


async def _submit_feedback_impl(feedback: LeadFeedback) -> FeedbackSubmissionResponse:
    """Shared implementation for feedback submission endpoints."""
    if feedback.scored_at > feedback.feedback_at:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="feedback_at must be after scored_at",
        )

    manager = _get_manager()
    try:
        _store_feedback(manager, feedback)
        count = len(manager.get_all_feedback())
        return FeedbackSubmissionResponse(
            success=True,
            message=f"Feedback received for lead {feedback.lead_id}: {feedback.outcome.value}",
            feedback_count_stored=count,
            timestamp=datetime.utcnow(),
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing feedback: {exc}",
        ) from exc
    finally:
        manager.close()


@router.post(
    "",
    response_model=FeedbackSubmissionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit lead feedback",
)
async def submit_feedback_root(feedback: LeadFeedback):
    """Compatibility endpoint for POST /feedback."""
    return await _submit_feedback_impl(feedback)


@router.post(
    "/submit",
    response_model=FeedbackSubmissionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit lead feedback",
)
async def submit_feedback(feedback: LeadFeedback):
    """Submit feedback for a scored lead."""
    return await _submit_feedback_impl(feedback)


@router.post(
    "/submit-batch",
    response_model=dict,
    status_code=status.HTTP_201_CREATED,
    summary="Submit batch feedback",
)
async def submit_batch_feedback(batch: BatchFeedback):
    """Submit feedback for multiple leads."""
    existing_feedback = _load_feedback_items()
    guardrail_result = _guardrail.check_guardrails(existing_feedback + batch.feedback_items)
    if not guardrail_result["passed"]:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "message": "Guardrail violations detected",
                "errors": guardrail_result["errors"],
                "warnings": guardrail_result["warnings"],
            },
        )

    manager = _get_manager()
    try:
        for feedback in batch.feedback_items:
            if feedback.scored_at > feedback.feedback_at:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"feedback_at must be after scored_at for lead {feedback.lead_id}",
                )
            _store_feedback(manager, feedback)

        total_feedback = len(manager.get_all_feedback())
        return {
            "success": True,
            "message": f"Stored {len(batch.feedback_items)} feedback items",
            "total_feedback_count": total_feedback,
            "batch_id": batch.batch_id or "auto-generated",
            "guardrail_warnings": guardrail_result.get("warnings", []),
            "timestamp": datetime.utcnow().isoformat(),
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing batch: {exc}",
        ) from exc
    finally:
        manager.close()


@router.get(
    "/analytics",
    response_model=FeedbackAnalyticsResponse,
    summary="Get drift analytics and retraining status",
)
async def get_analytics(days: Optional[int] = 7, min_feedback: Optional[int] = 50):
    """Get drift metrics and analytics for feedback data."""
    try:
        feedback_items = _filter_feedback_by_days(_load_feedback_items(), days)
        if len(feedback_items) < min_feedback:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Insufficient feedback data: {len(feedback_items)} < {min_feedback} required",
            )

        metrics = _drift_detector.calculate_metrics(feedback_items, time_period_days=days or 7)
        drift_status, drift_reason, _ = _drift_detector.detect_drift(metrics)
        summary = _drift_detector.summarize_feedback(feedback_items)
        should_retrain, _ = _retrain_scheduler.should_retrain(
            feedback_count=len(feedback_items),
            drift_status=drift_status,
            last_retrain_date=None,
        )

        return FeedbackAnalyticsResponse(
            success=True,
            metrics=metrics,
            summary=summary,
            drift_status=drift_status,
            retraining_recommended=should_retrain,
            notes=drift_reason,
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error calculating analytics: {exc}",
        ) from exc


@router.get(
    "/status",
    response_model=dict,
    summary="Get feedback loop status",
)
async def get_feedback_status():
    """Get current feedback loop status."""
    try:
        feedback_items = _load_feedback_items()
        feedback_count = len(feedback_items)

        if feedback_items:
            metrics = _drift_detector.calculate_metrics(feedback_items, time_period_days=30)
            drift_status, drift_reason, _ = _drift_detector.detect_drift(metrics)
        else:
            metrics = None
            drift_status = "normal"
            drift_reason = "No feedback collected yet"

        next_opportunity = _retrain_scheduler.next_retrain_opportunity(
            feedback_count=feedback_count,
            drift_status=drift_status,
            last_retrain_date=None,
        )
        active_triggers = _build_trigger_payload(feedback_count, drift_status, drift_reason)

        accepted = sum(1 for item in feedback_items if item.outcome == FeedbackOutcome.ACCEPTED)
        rejected = sum(1 for item in feedback_items if item.outcome == FeedbackOutcome.REJECTED)
        neutral = sum(1 for item in feedback_items if item.outcome == FeedbackOutcome.NEUTRAL)

        return {
            "success": True,
            "total_feedback_items": feedback_count,
            "feedback_by_outcome": {
                "accepted": accepted,
                "rejected": rejected,
                "neutral": neutral,
            },
            "drift_status": drift_status,
            "drift_notes": drift_reason,
            "retraining_triggers": len(active_triggers),
            "next_retrain_opportunity": next_opportunity,
            "outstanding_triggers": active_triggers,
            "latest_metrics": metrics.model_dump() if metrics else None,
            "timestamp": datetime.utcnow().isoformat(),
        }
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting status: {exc}",
        ) from exc


@router.post(
    "/clear",
    response_model=dict,
    summary="Clear feedback (dev only)",
)
async def clear_feedback():
    """Clear all stored feedback. Development only."""
    manager = _get_manager()
    try:
        count = manager.delete_all_feedback()
        manager.add_audit_log(
            operation="feedback",
            status="success",
            details=f"Cleared {count} feedback items",
        )
        return {
            "success": True,
            "message": f"Cleared {count} feedback items",
            "timestamp": datetime.utcnow().isoformat(),
        }
    finally:
        manager.close()


@router.get(
    "/{lead_id}",
    response_model=dict,
    summary="Get feedback history for a lead",
)
async def get_feedback_history(lead_id: str):
    """Return stored feedback history for a specific lead."""
    feedback_items = _load_feedback_items(lead_id=lead_id)
    if not feedback_items:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No feedback found for lead {lead_id}",
        )

    return {
        "lead_id": lead_id,
        "feedback_count": len(feedback_items),
        "feedback_history": [
            {
                "outcome": item.outcome.value,
                "reason": item.reason.value,
                "original_score": item.original_score,
                "original_grade": item.original_grade,
                "scored_at": item.scored_at.isoformat(),
                "feedback_at": item.feedback_at.isoformat(),
                "notes": item.notes,
                "sal_decision_maker": item.sal_decision_maker,
            }
            for item in feedback_items
        ],
    }
