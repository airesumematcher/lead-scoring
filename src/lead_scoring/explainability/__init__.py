"""Explainability modules: narrative generation and feature importance."""

from lead_scoring.explainability.narrative_generator import (
    generate_narrative, DriverExtractor, LimiterExtractor
)
from lead_scoring.explainability.feature_importance import (
    explain_score_components, FeatureImportanceCalculator
)

__all__ = [
    'generate_narrative',
    'DriverExtractor',
    'LimiterExtractor',
    'explain_score_components',
    'FeatureImportanceCalculator',
]
