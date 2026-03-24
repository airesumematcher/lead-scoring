"""
Data models and schemas for lead scoring.
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, EmailStr
from enum import Enum
from datetime import datetime


class ProgramType(str, Enum):
    """Lead generation program type."""
    NURTURE = "nurture"
    OUTBOUND = "outbound"
    ABM = "abm"
    EVENT = "event"


class LeadStatus(str, Enum):
    """Lead status."""
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    PENDING = "pending"
    ENRICHED = "enriched"


class EngagementType(str, Enum):
    """Engagement event types."""
    OPEN = "open"
    CLICK = "click"
    DOWNLOAD = "download"
    VISIT = "visit"


class Grade(str, Enum):
    """Lead score grade."""
    A = "A"
    B = "B"
    C = "C"
    D = "D"


class ConfidenceBand(str, Enum):
    """Confidence level in score."""
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"


class Freshness(str, Enum):
    """Lead freshness signal."""
    FRESH = "Fresh"
    AGING = "Aging"
    STALE = "Stale"


class RecommendedAction(str, Enum):
    """Recommended action for lead."""
    FAST_TRACK = "Fast-track"
    NURTURE = "Nurture"
    ENRICH = "Enrich"
    DEPRIORITIZE = "Deprioritize"


# ============== Input Data Models ==============

class ContactFields(BaseModel):
    """Contact-level information."""
    email: EmailStr
    phone: Optional[str] = None
    first_name: str
    last_name: str
    job_title: str
    linkedin_url: Optional[str] = None


class CompanyFields(BaseModel):
    """Company-level information."""
    company_name: str
    domain: str
    industry: str
    company_size: Optional[str] = None  # e.g., "100-1000"
    revenue_band: Optional[str] = None  # e.g., "$10M-$50M"
    geography: str
    hq_location: Optional[str] = None


class CampaignFields(BaseModel):
    """Campaign metadata."""
    campaign_id: str
    campaign_name: str
    brief_objective: Optional[str] = None
    target_persona: Optional[str] = None
    industry_focus: Optional[str] = None
    asset_used: Optional[str] = None  # "whitepaper", "webinar", "report", "demo"
    asset_stage_tag: Optional[str] = None  # "awareness", "consideration", "decision"
    program_type: ProgramType


class EngagementEvent(BaseModel):
    """Individual engagement event."""
    timestamp: datetime
    event_type: EngagementType
    url_clicked: Optional[str] = None
    asset_name: Optional[str] = None


class AccountLevelFields(BaseModel):
    """Account-level context (when available)."""
    tal_match: Optional[bool] = None
    historical_account_acceptance_rate: Optional[float] = None  # 0.0-1.0
    historical_account_l2o_rate: Optional[float] = None
    account_industry: Optional[str] = None
    account_employee_count: Optional[int] = None
    account_revenue_band: Optional[str] = None
    abm_pulse_intent_score: Optional[float] = None  # 0.0-1.0


class FeedbackSignals(BaseModel):
    """Post-delivery feedback."""
    sales_accepted: Optional[bool] = None
    rejection_reason: Optional[str] = None
    crf_stage_change: Optional[str] = None
    timestamp: Optional[datetime] = None


class LeadInput(BaseModel):
    """Complete input for lead scoring."""
    lead_id: str
    submission_timestamp: datetime
    source_partner: Optional[str] = None
    
    contact: ContactFields
    company: CompanyFields
    campaign: CampaignFields
    
    delivery_date: Optional[datetime] = None
    delivery_attempt_count: Optional[int] = 0
    
    engagement_events: Optional[List[EngagementEvent]] = []
    ip_address: Optional[str] = None
    
    account_context: Optional[AccountLevelFields] = None
    feedback: Optional[FeedbackSignals] = None


# ============== Feature Output Models ==============

class AccuracyFeatures(BaseModel):
    """Accuracy pillar features."""
    email_valid: bool
    phone_valid: bool
    job_title_present: bool
    job_title_seniority_score: int  # 1-5
    company_name_valid: bool
    domain_credibility: int  # 0-100
    company_size_confidence: float  # 0.0-1.0
    geo_match_with_campaign: float  # 0.0-1.0
    lead_delivery_success: bool
    delivery_latency_days: int
    engagement_data_available: bool
    duplicate_risk: bool
    accuracy_subscore: int  # 0-100 calculated score


class ClientFitFeatures(BaseModel):
    """Client Fit pillar features."""
    industry_match_pts: int  # 0-25
    company_size_match_pts: int  # 0-25
    revenue_band_match_pts: int  # 0-20
    geography_match_pts: int  # 0-20
    tal_match: bool
    job_title_match_persona_pts: int  # 0-25
    historical_account_conversion: int  # 0-15
    firmographic_confidence: int  # -5 to 5
    client_fit_subscore: int  # 0-100


class EngagementFeatures(BaseModel):
    """Engagement pillar features."""
    engagement_recency_days: int
    engagement_sequence_depth: int
    email_open_count: int
    asset_click_count: int
    asset_download_event: bool
    time_decay_engagement_score: float
    asset_stage_alignment_pts: int  # 0-20
    domain_intent_topics_match: int  # 0-15
    repeat_visitor_count: int
    engagement_absent_flag: bool
    engagement_subscore: int  # 0-100


class DerivedFeatures(BaseModel):
    """Derived cross-pillar features."""
    ace_balance_score: float
    fit_intent_synergy: float
    freshness_decay_multiplier: float
    confidence_signal_count: int
    icp_violation_count: int


class ExtractedFeatures(BaseModel):
    """All extracted features for a lead."""
    lead_id: str
    accuracy: AccuracyFeatures
    client_fit: ClientFitFeatures
    engagement: EngagementFeatures
    derived: DerivedFeatures


# ============== Scoring Output Models ==============

class ACEBreakdown(BaseModel):
    """ACE sub-score breakdown."""
    accuracy: int
    client_fit: int
    engagement: int
    weights: Dict[str, float]
    program_type: str


class PipelineInfluence(BaseModel):
    """Pipeline influence proxy."""
    pct: float  # 0.0-1.0
    confidence: ConfidenceBand
    drivers: List[str]


class FreshnessSignal(BaseModel):
    """Freshness metadata."""
    status: Freshness
    delivery_age_days: int
    last_engagement_days_ago: Optional[int]
    decay_multiplier: float


class ScoreNarrative(BaseModel):
    """Plain-English narrative for the score."""
    summary: str
    positive_drivers: List[str]  # Exactly 3
    limiting_factors: List[str]  # Exactly 2
    recommended_action: RecommendedAction
    action_reason: str


class AccountContext(BaseModel):
    """Account-level scoring context."""
    account_id: Optional[str] = None
    in_market: bool
    buying_committee_coverage_pct: Optional[int] = None
    missing_roles: Optional[List[str]] = None


class DataQuality(BaseModel):
    """Data quality indicators."""
    feature_completeness_pct: int
    accuracy_ceiling_applied: bool
    engagement_data_available: bool


class AuditTrail(BaseModel):
    """Audit metadata for reproducibility."""
    model_version: str
    feature_set_hash: str
    training_data_date: str
    retraining_recommended: bool


class LeadScore(BaseModel):
    """Complete scoring output."""
    lead_id: str
    scored_at: datetime
    
    score: int  # 0-100
    grade: Grade
    confidence: ConfidenceBand
    
    ace_breakdown: ACEBreakdown
    pipeline_influence: PipelineInfluence
    freshness: FreshnessSignal
    narrative: ScoreNarrative
    account_context: AccountContext
    
    data_quality: DataQuality
    audit_trail: AuditTrail

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
        }
