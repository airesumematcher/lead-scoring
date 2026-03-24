"""ACE Buying Intelligence Platform package."""

__version__ = "2.0.0"
__author__ = "RevOps Data Science"

from lead_scoring.platform import (
    BuyingGroupSummary,
    BuyingIntelligenceService,
    CampaignReport,
    LeadRecord,
    LeadScoreResult,
    OutcomeLabel,
    RetrainRequest,
    RetrainResult,
    load_platform_config,
)

__all__ = [
    "BuyingGroupSummary",
    "BuyingIntelligenceService",
    "CampaignReport",
    "LeadRecord",
    "LeadScoreResult",
    "OutcomeLabel",
    "RetrainRequest",
    "RetrainResult",
    "load_platform_config",
]
