"""
Derived Features (Cross-Pillar).

Features computed from combinations of ACE pillars.
"""

from statistics import stdev, mean
from lead_scoring.models import (
    AccuracyFeatures, ClientFitFeatures, EngagementFeatures, DerivedFeatures
)


def compute_ace_balance_score(accuracy: int, client_fit: int, engagement: int) -> float:
    """
    Compute standard deviation of ACE sub-scores.
    High imbalance (e.g., high E, low C) is penalized.
    """
    if not all([accuracy, client_fit, engagement]):
        return 0.0
    
    scores = [accuracy, client_fit, engagement]
    if len(set(scores)) <= 1:  # All same score
        return 0.0
    
    try:
        std_dev = stdev(scores)
    except:
        std_dev = 0.0
    
    return std_dev


def compute_fit_intent_synergy(client_fit: int, engagement: int) -> float:
    """
    Multiplicative synergy: Client_Fit × Engagement.
    Boost if both high; loss if one is very low.
    Formula: (CF * E) / 100 (to normalize back to 0-100 range)
    """
    synergy = (client_fit * engagement) / 100.0
    return synergy


def compute_freshness_decay_multiplier(
    client_fit: int,
    engagement: int,
    engagement_recency_days: int
) -> float:
    """
    Conditional freshness decay based on fit + intent.
    
    IF (CF >= 75 AND E >= 70):
      decay = exp(-0.02 * days)  # Slow decay, high-quality leads
    ELSE:
      decay = exp(-0.05 * days)  # Fast decay, lower-quality
    
    Returns multiplier [0.0-1.0] to apply to composite score.
    """
    import math
    
    if client_fit >= 75 and engagement >= 70:
        decay_rate = 0.02
    else:
        decay_rate = 0.05
    
    multiplier = math.exp(-decay_rate * engagement_recency_days)
    return multiplier


def compute_confidence_signal_count(accuracy_feat: AccuracyFeatures,
                                   client_fit_feat: ClientFitFeatures,
                                   engagement_feat: EngagementFeatures) -> int:
    """
    Count non-null/significant features across ACE.
    Higher count = higher confidence in score.
    """
    count = 0
    
    # Accuracy signals
    if accuracy_feat.email_valid:
        count += 1
    if accuracy_feat.phone_valid:
        count += 1
    if accuracy_feat.job_title_present:
        count += 1
    if accuracy_feat.company_name_valid:
        count += 1
    if accuracy_feat.domain_credibility > 60:
        count += 1
    
    # Client Fit signals
    if client_fit_feat.industry_match_pts > 0:
        count += 1
    if client_fit_feat.company_size_match_pts > 0:
        count += 1
    if client_fit_feat.job_title_match_persona_pts > 0:
        count += 1
    if client_fit_feat.tal_match:
        count += 1
    
    # Engagement signals
    if engagement_feat.engagement_sequence_depth > 0:
        count += 1
    if engagement_feat.asset_download_event:
        count += 1
    if engagement_feat.engagement_recency_days < 30:
        count += 1
    if engagement_feat.repeat_visitor_count > 0:
        count += 1
    
    return count


def compute_icp_violation_count(client_fit_feat: ClientFitFeatures) -> int:
    """
    Count mismatches in ICP alignment.
    >2 violations → max score 50.
    """
    violations = 0
    
    if client_fit_feat.industry_match_pts == 0:
        violations += 1
    if client_fit_feat.company_size_match_pts == 0:
        violations += 1
    if client_fit_feat.job_title_match_persona_pts == 0:
        violations += 1
    if not client_fit_feat.tal_match:
        violations += 1
    
    return violations


def extract_derived_features(
    accuracy_feat: AccuracyFeatures,
    client_fit_feat: ClientFitFeatures,
    engagement_feat: EngagementFeatures
) -> DerivedFeatures:
    """Compute all derived cross-pillar features."""
    
    # ACE scores
    a_score = accuracy_feat.accuracy_subscore
    c_score = client_fit_feat.client_fit_subscore
    e_score = engagement_feat.engagement_subscore
    
    # Compute derived features
    ace_balance = compute_ace_balance_score(a_score, c_score, e_score)
    fit_intent_synergy = compute_fit_intent_synergy(c_score, e_score)
    freshness_decay_mult = compute_freshness_decay_multiplier(
        c_score, e_score, engagement_feat.engagement_recency_days
    )
    confidence_count = compute_confidence_signal_count(
        accuracy_feat, client_fit_feat, engagement_feat
    )
    icp_violations = compute_icp_violation_count(client_fit_feat)
    
    return DerivedFeatures(
        ace_balance_score=ace_balance,
        fit_intent_synergy=fit_intent_synergy,
        freshness_decay_multiplier=freshness_decay_mult,
        confidence_signal_count=confidence_count,
        icp_violation_count=icp_violations,
    )
