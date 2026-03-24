"""
Layer 2: ML Scoring Engine with Weighted ACE Composite.

Combines Accuracy, Client Fit, and Engagement sub-scores into final composite [0-100].
Applies program-type-specific weights.
Applies time decay (freshness multiplier).
Applies ICP violation penalty.
"""

import math
from lead_scoring.models import ExtractedFeatures, ProgramType
from lead_scoring.config import ScoringConfig


class Layer2ScoringResult:
    """Result from Layer 2 scoring."""
    
    def __init__(self,
                 composite_score: int,
                 accuracy_subscore: int,
                 client_fit_subscore: int,
                 engagement_subscore: int,
                 weights: dict,
                 freshness_decay_applied: float,
                 icp_violation_penalty: float):
        self.composite_score = composite_score
        self.accuracy_subscore = accuracy_subscore
        self.client_fit_subscore = client_fit_subscore
        self.engagement_subscore = engagement_subscore
        self.weights = weights  # {accuracy, client_fit, engagement}
        self.freshness_decay_applied = freshness_decay_applied
        self.icp_violation_penalty = icp_violation_penalty


def get_ace_weights(program_type: str, config: ScoringConfig) -> dict:
    """Get ACE weights for program type, normalized to sum to 1.0."""
    weights = config.get_weights(program_type)
    
    # Ensure sums to 1.0 (handle floating point errors)
    total = sum(weights.values())
    normalized = {k: v / total for k, v in weights.items()}
    
    return normalized


def apply_icp_violation_penalty(icp_violations: int) -> float:
    """
    Apply penalty for ICP violations.
    
    >2 violations → recommended max score is 50 (hard constraint).
    Returns multiplier [0.0-1.0] or recommended ceiling as adjustment.
    """
    if icp_violations > 2:
        return 0.5  # Max 50 points retained
    elif icp_violations == 2:
        return 0.75  # Max 75 points retained
    else:
        return 1.0  # No penalty


def apply_freshness_decay(client_fit_subscore: int,
                         engagement_subscore: int,
                         engagement_recency_days: int) -> float:
    """
    Apply conditional freshness decay to composite score.
    
    IF (ClientFit >= 75 AND Engagement >= 70):
      multiplier = exp(-0.02 * days)  # Slow decay for high-quality leads
    ELSE:
      multiplier = exp(-0.05 * days)  # Fast decay for lower-quality leads
    
    Returns multiplier [0.0-1.0].

    Special case:
    - If no engagement is present, the engagement pillar already floors to a neutral
      score. We apply a fixed moderation factor instead of treating it like 999 stale days,
      which would otherwise collapse most leads to zero.
    """
    if engagement_recency_days >= 999:
        return 0.70 if client_fit_subscore >= 75 else 0.55

    if client_fit_subscore >= 75 and engagement_subscore >= 70:
        decay_rate = 0.02  # Slow decay
    else:
        decay_rate = 0.05  # Fast decay
    
    multiplier = math.exp(-decay_rate * engagement_recency_days)
    return multiplier


def compute_composite_score(features: ExtractedFeatures,
                           program_type: str,
                           config: ScoringConfig,
                           accuracy_ceiling: int = 100) -> Layer2ScoringResult:
    """
    Compute composite lead score using weighted ACE pillars.
    
    Steps:
    1. Get program-type-specific ACE weights
    2. Extract sub-scores (capped by accuracy ceiling)
    3. Apply ICP violation penalty
    4. Compute weighted sum
    5. Apply freshness decay
    6. Cap at 100
    
    Args:
        features: ExtractedFeatures from Layer 1
        program_type: "nurture", "outbound", "abm", or "event"
        config: ScoringConfig
        accuracy_ceiling: Hard cap on final score (from Layer 1 gates)
    
    Returns:
        Layer2ScoringResult with composite score and breakdown
    """
    
    # Extract sub-scores
    a_subscore = features.accuracy.accuracy_subscore
    c_subscore = features.client_fit.client_fit_subscore
    e_subscore = features.engagement.engagement_subscore
    
    # Apply accuracy ceiling
    a_subscore = min(a_subscore, accuracy_ceiling)
    
    # Get weights
    weights = get_ace_weights(program_type, config)
    
    # Weighted composite (before decay and penalties)
    weighted_sum = (
        weights['accuracy'] * a_subscore +
        weights['client_fit'] * c_subscore +
        weights['engagement'] * e_subscore
    )
    
    # Apply ICP violation penalty
    icp_penalty_multiplier = apply_ipc_violation_penalty(features.derived.icp_violation_count)
    weighted_sum = weighted_sum * icp_penalty_multiplier
    
    # Apply ACE balance penalty (penalize extreme imbalance)
    ace_balance = features.derived.ace_balance_score
    if ace_balance > 30:  # High imbalance
        balance_penalty = 0.95  # 5% penalty
        weighted_sum = weighted_sum * balance_penalty
    
    # Apply freshness decay
    freshness_decay_mult = apply_freshness_decay(
        c_subscore,
        e_subscore,
        features.engagement.engagement_recency_days
    )
    weighted_sum = weighted_sum * freshness_decay_mult
    
    # Cap at 100, floor at 0
    composite_score = max(0, min(100, int(round(weighted_sum))))
    
    return Layer2ScoringResult(
        composite_score=composite_score,
        accuracy_subscore=a_subscore,
        client_fit_subscore=c_subscore,
        engagement_subscore=e_subscore,
        weights=weights,
        freshness_decay_applied=freshness_decay_mult,
        icp_violation_penalty=icp_penalty_multiplier,
    )


def apply_ipc_violation_penalty(icp_violations: int) -> float:
    """Apply penalty for ICP violations (corrected function name)."""
    if icp_violations > 2:
        return 0.5
    elif icp_violations == 2:
        return 0.75
    else:
        return 1.0
