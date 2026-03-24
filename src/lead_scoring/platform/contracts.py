"""Contracts for the revised buying intelligence platform."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, EmailStr, Field, field_validator


class FunnelStage(str, Enum):
    """Lifecycle stage of the engaged asset."""

    TOFU = "TOFU"
    MOFU = "MOFU"
    BOFU = "BOFU"


class DeliveryDecision(str, Enum):
    """Operational action for campaign ops."""

    DELIVER = "deliver"
    REVIEW = "review"
    HOLD = "hold"


class PredictedOutcome(str, Enum):
    """Predicted client response."""

    APPROVED = "approved"
    REJECTED = "rejected"


class LeadQuadrant(str, Enum):
    """Client-facing triage view."""

    PRIORITY = "Priority"
    NURTURE = "Nurture"
    CHAMPION = "Champion"
    MONITOR = "Monitor"


class CampaignTaxonomy(BaseModel):
    """Five-tag taxonomy used to infer campaign mode."""

    asset_type: str | None = None
    topic: str | None = None
    audience: str | None = None
    volume: str | None = None
    sequence: str | None = None
    asset_stage_override: FunnelStage | None = None
    vertical_override: str | None = None


class TargetProfile(BaseModel):
    """Target audience profile derived from briefs or campaign metadata."""

    industries: list[str] = Field(default_factory=list)
    geographies: list[str] = Field(default_factory=list)
    company_sizes: list[str] = Field(default_factory=list)
    job_functions: list[str] = Field(default_factory=list)
    seniorities: list[str] = Field(default_factory=list)
    required_personas: list[str] = Field(default_factory=list)


class CampaignContext(BaseModel):
    """Campaign-scoped context for every score."""

    campaign_id: str
    client_id: str
    campaign_name: str
    brief_text: str | None = None
    asset_name: str | None = None
    target_profile: TargetProfile = Field(default_factory=TargetProfile)
    taxonomy: CampaignTaxonomy = Field(default_factory=CampaignTaxonomy)
    history_approval_rate: float | None = Field(default=None, ge=0.0, le=1.0)


class PartnerSignals(BaseModel):
    """Partner-level historical quality features."""

    partner_id: str | None = None
    approval_rate_6m: float | None = Field(default=None, ge=0.0, le=1.0)
    approval_rate_client_6m: float | None = Field(default=None, ge=0.0, le=1.0)
    approval_rate_vertical_6m: float | None = Field(default=None, ge=0.0, le=1.0)


class PersonaSnapshot(BaseModel):
    """Known contact within the account buying group."""

    lead_id: str | None = None
    email: str | None = None
    full_name: str | None = None
    job_title: str | None = None
    job_function: str | None = None
    seniority: str | None = None
    status: str = "approved"
    asset_name: str | None = None
    asset_stage: FunnelStage | None = None
    occurred_at: datetime | None = None

    @field_validator("occurred_at")
    @classmethod
    def ensure_timezone(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return value
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)


class AccountSignals(BaseModel):
    """Account-level context used for Layer 2."""

    account_id: str | None = None
    client_acceptance_rate_6m: float | None = Field(default=None, ge=0.0, le=1.0)
    recent_personas: list[PersonaSnapshot] = Field(default_factory=list)


class ContactPayload(BaseModel):
    """Submitted lead contact record."""

    email: EmailStr
    first_name: str
    last_name: str
    job_title: str
    linkedin_url: str | None = None


class CompanyPayload(BaseModel):
    """Submitted company/account record."""

    company_name: str
    domain: str
    industry: str
    geography: str
    company_size: str | None = None


class EngagementEvent(BaseModel):
    """Individual engagement touchpoint."""

    event_type: str = Field(description="open, click, download, visit")
    occurred_at: datetime
    asset_name: str | None = None
    email_number: int = Field(default=1, ge=1, le=2)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("event_type")
    @classmethod
    def normalise_event_type(cls, value: str) -> str:
        return str(value).strip().lower()

    @field_validator("occurred_at")
    @classmethod
    def ensure_occured_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)


class LeadRecord(BaseModel):
    """Top-level scoring request contract."""

    lead_id: str
    submitted_at: datetime
    source_partner: str | None = None
    contact: ContactPayload
    company: CompanyPayload
    campaign: CampaignContext
    partner_signals: PartnerSignals = Field(default_factory=PartnerSignals)
    account_signals: AccountSignals = Field(default_factory=AccountSignals)
    engagement_events: list[EngagementEvent] = Field(default_factory=list)

    @field_validator("submitted_at")
    @classmethod
    def ensure_submitted_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)


class TopReason(BaseModel):
    """Human-readable reason behind the score."""

    feature: str
    impact: float
    message: str


class LeadQualityBreakdown(BaseModel):
    """Layer 1 decomposition of the approval score."""

    fit_score: int
    intent_score: int
    partner_signal_score: int
    client_history_score: int
    campaign_history_score: int
    data_quality_score: int
    icp_match_score: int


class BuyingGroupSummary(BaseModel):
    """Layer 2 account-level buying group signal."""

    account_domain: str
    unique_persona_count: int
    function_coverage: list[str]
    seniority_coverage: list[str]
    persona_completeness_score: int
    journey_stage_reached: FunnelStage
    missing_personas: list[str]
    bdr_trigger: bool
    buying_group_score: int


class LeadScoreResult(BaseModel):
    """End-to-end PRD-aligned scoring response."""

    lead_id: str
    campaign_id: str
    client_id: str
    model_version: str
    predicted_outcome: PredictedOutcome
    delivery_decision: DeliveryDecision
    approval_score: int
    campaign_mode: FunnelStage
    quadrant: LeadQuadrant
    breakdown: LeadQualityBreakdown
    top_reasons: list[TopReason]
    buying_group: BuyingGroupSummary
    score_audit_id: int | None = None
    scored_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class BatchScoreResult(BaseModel):
    """Response for multi-lead scoring."""

    total_leads: int
    scored_leads: int
    results: list[LeadScoreResult]


class CampaignReportItem(BaseModel):
    """Account-level campaign report row."""

    account_domain: str
    client_id: str
    campaign_id: str
    unique_persona_count: int
    persona_completeness_score: int
    function_coverage: list[str]
    journey_stage_reached: FunnelStage
    bdr_trigger: bool
    missing_personas: list[str]
    accounts_leads: list[str]


class CampaignReport(BaseModel):
    """Campaign-level deliverable for client success and sales."""

    campaign_id: str
    client_id: str | None = None
    total_accounts: int
    accounts_with_bdr_trigger: int
    report_items: list[CampaignReportItem]


class OutcomeLabel(BaseModel):
    """Post-delivery label used for retraining."""

    lead_id: str
    campaign_id: str
    outcome: PredictedOutcome
    notes: str | None = None


class RetrainRequest(BaseModel):
    """Manual trigger payload for the monthly retrain pipeline."""

    dataset_path: str
    force_promote: bool = False


class RetrainResult(BaseModel):
    """Outcome of a retrain job."""

    success: bool
    dataset_path: str
    model_promoted: bool
    evaluation: dict[str, Any]
    signal_tables_path: str | None = None
    model_path: str | None = None
    metadata_path: str | None = None
    message: str
