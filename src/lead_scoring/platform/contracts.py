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


class BuyingGroupRole(str, Enum):
    """The commercial role a persona plays within the buying committee."""

    DECISION_MAKER = "Decision-Maker"
    INFLUENCER = "Influencer"
    CHAMPION = "Champion"
    USER = "User"
    GATEKEEPER = "Gatekeeper"


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


class BuyingGroupPersonaSlot(BaseModel):
    """A single required persona within a buying group definition."""

    job_function: str
    job_level: str
    role: BuyingGroupRole


class BuyingGroupDefinition(BaseModel):
    """A product-level buying group (Recommended or Manually Created)."""

    product_category: str
    group_type: str = "recommended"  # "recommended" | "manual"
    is_verified: bool = False
    personas: list[BuyingGroupPersonaSlot] = Field(default_factory=list)


class PersonaCoverageItem(BaseModel):
    """Coverage status of one persona slot in the buying group definition."""

    job_function: str
    job_level: str
    role: BuyingGroupRole
    covered: bool
    covered_by: str | None = None  # lead_id or email of the covering lead


class SellingStory(BaseModel):
    """Synthesized selling narrative for BDR / CS handoff."""

    motion: str  # "accelerate" | "nurture" | "hold"
    confidence: str  # "High" | "Medium" | "Low"
    lead_narrative: str
    account_narrative: str
    buying_group_narrative: str
    recommended_action: str


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
    buying_group_definition: BuyingGroupDefinition | None = None


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


class FirmographicTrajectory(BaseModel):
    """Directional firmographic signals — trajectory matters more than snapshot."""

    headcount_6m_delta: int | None = None  # positive = growing, negative = shrinking
    latest_funding_date: datetime | None = None
    latest_funding_amount_usd: int | None = None
    funding_stage: str | None = None  # seed, series_a, series_b, series_c, pe, public
    tech_stack: list[str] = Field(default_factory=list)  # installed technologies (from BuiltWith/HG)
    executive_change_90d: bool = False  # new CIO/CFO/CMO in last 90 days


class ThirdPartyIntentSignal(BaseModel):
    """Account-level intent surge from a third-party data provider."""

    topic: str  # "healthcare analytics", "cloud migration", etc.
    surge_score: float = Field(ge=0.0, le=100.0)
    source: str = "bombora"  # bombora, g2, techtarget
    week_ending: datetime


class AccountSignals(BaseModel):
    """Account-level context used for Layer 2."""

    account_id: str | None = None
    client_acceptance_rate_6m: float | None = Field(default=None, ge=0.0, le=1.0)
    recent_personas: list[PersonaSnapshot] = Field(default_factory=list)
    # New: external enrichment signals
    firmographic: FirmographicTrajectory | None = None
    intent_signals: list[ThirdPartyIntentSignal] = Field(default_factory=list)
    cross_campaign_persona_count: int | None = None  # platform-wide persona count (pre-fetched)
    account_visit_count: int | None = None  # site visits attributed to this account (from MAP/analytics)


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


class SignalDetail(BaseModel):
    """Per-signal explanation with sub-component drivers and penalty flags."""

    score: int
    drivers: list[str] = Field(default_factory=list)
    flags: list[str] = Field(default_factory=list)


class LeadAnalysis(BaseModel):
    """Full per-signal breakdown explaining what drove each score."""

    fit: SignalDetail
    intent: SignalDetail
    icp_match: SignalDetail
    data_quality: SignalDetail
    partner_signal: SignalDetail


class LeadQualityBreakdown(BaseModel):
    """Layer 1 decomposition of the approval score."""

    fit_score: int
    intent_score: int
    partner_signal_score: int
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
    # Structured buying group fields (populated when a BuyingGroupDefinition is present)
    product_category: str | None = None
    group_type: str = "inferred"
    is_verified: bool = False
    decision_maker_coverage_pct: int = 0
    role_coverage: dict[str, int] = Field(default_factory=dict)
    persona_coverage: list[PersonaCoverageItem] = Field(default_factory=list)


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
    analysis: LeadAnalysis
    buying_group: BuyingGroupSummary
    account_score: AccountScoreResult | None = None
    selling_story: SellingStory | None = None
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
    product_category: str | None = None
    decision_maker_coverage_pct: int = 0
    role_coverage: dict[str, int] = Field(default_factory=dict)


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


class MLEngagementSignals(BaseModel):
    """Madison Logic platform engagement signals for an account — used for Moody's-style account scoring."""

    cs_lead_count: int = 0                    # content syndication leads delivered this account
    display_impressions: int = 0              # display ad impressions served
    display_clicks: int = 0                   # display ad clicks
    display_ctr: float = 0.0                  # click-through rate as a percentage (e.g. 0.25 = 0.25%)
    site_visits: int = 0                      # site visits attributed to this account
    trending_mli_topic_count: int = 0         # # of MLI intent topics trending over last 7 weeks
    top_mli_topic: str | None = None          # highest-scoring MLI topic label
    top_mli_topic_stage: FunnelStage | None = None  # TOFU / MOFU / BOFU for the top topic


class AccountScoreRequest(BaseModel):
    """Request to score an account's readiness to buy."""

    domain: str
    client_id: str | None = None
    # Optional: caller can pre-supply external enrichment; if absent, platform uses what it has stored
    firmographic: FirmographicTrajectory | None = None
    intent_signals: list[ThirdPartyIntentSignal] = Field(default_factory=list)
    ml_engagement: MLEngagementSignals = Field(default_factory=MLEngagementSignals)


class AccountScoreResult(BaseModel):
    """Account-level readiness score and buying group status."""

    domain: str
    account_score: int  # 0-100 composite
    intent_score: int  # 0-100 from third-party intent signals
    firmographic_score: int  # 0-100 from trajectory signals
    moodys_engagement_score: int = 0  # 0-100 scaled from Moody's CS+CTR+SiteVisit+MLI+TopicStage signals
    intent_tier: str = "Low"  # "High" | "Med" | "Low" per Moody's thresholds (≥41 High, 20-40 Med, <20 Low)
    buying_group_maturity: str  # "early" | "developing" | "mature"
    persona_count_platform_wide: int  # unique personas across all clients/campaigns
    persona_count_client: int  # unique personas for this client
    function_coverage: list[str]
    in_market_signals: list[str]  # human-readable list of active buying signals
    missing_personas: list[str]  # persona functions not yet engaged
    recommended_action: str  # "hold" | "engage" | "accelerate"
    scored_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class DealOutcomeLabel(BaseModel):
    """CRM deal outcome linked to a previously scored lead — closes the learning loop."""

    lead_id: str
    account_domain: str
    campaign_id: str
    opportunity_id: str | None = None
    deal_stage: str  # qualified, proposal, closed_won, closed_lost
    closed_at: datetime | None = None
    revenue_usd: float | None = None
    crm_source: str = "manual"  # salesforce, hubspot, manual
