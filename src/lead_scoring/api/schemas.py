"""API request/response schemas for the PRD-aligned application."""

from __future__ import annotations

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
