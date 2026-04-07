"""API request/response schemas for the PRD-aligned application."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from lead_scoring.platform.contracts import (
    BatchScoreResult,
    BuyingGroupSummary,
    CampaignReport,
    LeadRecord,
    LeadScoreResult,
    OutcomeLabel,
    RetrainRequest,
    RetrainResult,
)


class ScoreLeadRequest(BaseModel):
    """Request for the Layer 1 + Layer 2 score endpoint."""

    lead: LeadRecord


class BatchScoreRequest(BaseModel):
    """Request for batch scoring."""

    leads: list[LeadRecord] = Field(min_length=1)


class BuyingGroupPreviewRequest(BaseModel):
    """Preview a buying-group summary without persisting a new score."""

    lead: LeadRecord


class OperationStatus(BaseModel):
    """Simple mutation response."""

    success: bool
    message: str


class HealthCheckResponse(BaseModel):
    """Health response for operational monitoring."""

    status: str
    version: str
    architecture: str
    runtime_model: str


class PortalLeadSummary(BaseModel):
    """Minimal original lead context returned to the portal."""

    lead_id: str
    company_name: str
    domain: str


class PortalImportResponse(BaseModel):
    """Combined import, score, and report response for the upload portal."""

    filename: str
    detected_format: str
    total_rows: int
    interpreted_headers: dict[str, str]
    warnings: list[str] = Field(default_factory=list)
    imported_leads: list[PortalLeadSummary]
    batch_result: BatchScoreResult
    campaign_report: CampaignReport


class FeedbackSubmitRequest(BaseModel):
    """Payload for submitting outcome feedback on a scored lead."""

    lead_id: str
    scored_at: datetime | None = None
    feedback_at: datetime | None = None
    outcome: str
    reason: str | None = None
    notes: str | None = None
    original_score: float | None = None
    original_grade: str | None = None
    sal_decision_maker: str | None = None


class FeedbackItem(BaseModel):
    """Single feedback entry returned in history."""

    outcome: str
    reason: str | None = None
    notes: str | None = None
    submitted_at: datetime | None = None


class FeedbackHistoryResponse(BaseModel):
    """All feedback for a specific lead."""

    lead_id: str
    feedback_count: int
    feedback_history: list[FeedbackItem]


class FeedbackSubmitResponse(BaseModel):
    """Confirmation of feedback submission."""

    feedback_count_stored: int


class FeedbackStatusResponse(BaseModel):
    """Aggregate feedback stats across all leads."""

    total_feedback_items: int
    feedback_by_outcome: dict[str, int]


class FeedbackClearResponse(BaseModel):
    """Confirmation of feedback bulk-delete."""

    message: str


class DriftStatusResponse(BaseModel):
    """High-level model drift assessment based on accumulated feedback."""

    feedback_count: int
    metrics: dict[str, Any]


__all__ = [
    "BatchScoreRequest",
    "BatchScoreResult",
    "BuyingGroupPreviewRequest",
    "BuyingGroupSummary",
    "CampaignReport",
    "HealthCheckResponse",
    "LeadScoreResult",
    "OperationStatus",
    "OutcomeLabel",
    "PortalImportResponse",
    "PortalLeadSummary",
    "RetrainRequest",
    "RetrainResult",
    "ScoreLeadRequest",
]
