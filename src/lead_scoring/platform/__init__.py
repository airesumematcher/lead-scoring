"""PRD-aligned buying intelligence platform."""

from .config import load_platform_config
from .contracts import (
    BuyingGroupSummary,
    CampaignReport,
    LeadRecord,
    LeadScoreResult,
    OutcomeLabel,
    RetrainRequest,
    RetrainResult,
)
from .engine import BuyingIntelligenceService

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
