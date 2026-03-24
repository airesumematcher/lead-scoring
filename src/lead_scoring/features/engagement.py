"""
Engagement Pillar Feature Engineering.

Engagement answers: Is there evidence of buying motion or intent?
Time decay applied: recent > older, clicks > opens.
Missing engagement handled gracefully (floor score, no penalty).
"""

import math
from datetime import datetime, timedelta
from lead_scoring.models import LeadInput, EngagementFeatures, EngagementType


def compute_engagement_recency_days(lead: LeadInput) -> int:
    """
    Find days since most recent engagement event.
    Default: 999 if no engagement.
    """
    if not lead.engagement_events or len(lead.engagement_events) == 0:
        return 999
    
    # Find max (most recent) timestamp
    max_timestamp = max((e.timestamp for e in lead.engagement_events), default=None)
    if not max_timestamp:
        return 999
    
    now = datetime.utcnow()
    delta = now - max_timestamp
    return max(0, delta.days)


def compute_engagement_sequence_depth(lead: LeadInput) -> int:
    """
    Count distinct engagement types.
    E.g., download + click + open = depth 3.
    """
    if not lead.engagement_events:
        return 0
    
    engagement_types = set(e.event_type for e in lead.engagement_events)
    return len(engagement_types)


def compute_email_open_count(lead: LeadInput) -> int:
    """Count email opens (capped at 3 for diminishing returns)."""
    opens = sum(1 for e in lead.engagement_events or [] if e.event_type == EngagementType.OPEN)
    return min(3, opens)


def compute_asset_click_count(lead: LeadInput) -> int:
    """Count asset clicks."""
    clicks = sum(1 for e in lead.engagement_events or [] if e.event_type == EngagementType.CLICK)
    return min(5, clicks)  # Cap at 5


def compute_asset_download_event(lead: LeadInput) -> bool:
    """Flag: has lead downloaded content?"""
    return any(e.event_type == EngagementType.DOWNLOAD for e in lead.engagement_events or [])


def apply_time_decay(raw_engagement_score: float, days_since_engagement: int) -> float:
    """
    Apply exponential time decay to engagement score.
    Formula: score * exp(-0.1 * days)
    
    Examples:
      3 days ago:  score * 0.74
      10 days ago: score * 0.37
      30 days ago: score * 0.05
    """
    if days_since_engagement >= 999:  # No engagement
        return 0.0
    
    decay_rate = 0.1
    multiplier = math.exp(-decay_rate * days_since_engagement)
    return raw_engagement_score * multiplier


def compute_asset_stage_alignment(lead: LeadInput) -> int:
    """
    Score asset stage alignment with campaign stage [0-20].
    Perfect alignment = 20; Misalignment = 0.
    
    Simplified: if asset_stage_tag matches campaign intent, +20.
    """
    asset_stage = (lead.campaign.asset_stage_tag or "").lower()
    
    # Assume campaign is targeting based on asset stage
    # Perfect match = asset stage aligns with expected recipient stage
    
    if not asset_stage:
        return 0
    
    # Simplified logic: if awareness asset but contact is director+ , good fit
    # If decision stage asset and senior contact, good fit
    alignment_score = 0
    if asset_stage in ('awareness', 'consideration', 'decision'):
        # Assume good alignment (simplified; in production, use explicit mapping)
        alignment_score = 15
    
    return alignment_score


def compute_domain_intent_topics_match(lead: LeadInput) -> int:
    """
    Match domain-level intent topics (IP-based ABM Pulse) to campaign.
    Score [0-15].
    """
    if not lead.account_context or not lead.account_context.abm_pulse_intent_score:
        return 0
    
    intent_score = lead.account_context.abm_pulse_intent_score  # 0.0-1.0
    
    # Convert to 0-15 scale
    return int(intent_score * 15)


def compute_repeat_visitor_count(lead: LeadInput) -> int:
    """Count repeat website visits (simplified; actual would use CDN/analytics data)."""
    visits = sum(1 for e in lead.engagement_events or [] if e.event_type == EngagementType.VISIT)
    return visits


def extract_engagement_features(lead: LeadInput) -> EngagementFeatures:
    """Extract all Engagement pillar features."""
    
    # Recency
    engagement_recency_days = compute_engagement_recency_days(lead)
    
    # Sequence depth
    engagement_sequence_depth = compute_engagement_sequence_depth(lead)
    
    # Individual engagement counts
    email_open_count = compute_email_open_count(lead)
    asset_click_count = compute_asset_click_count(lead)
    asset_download_event = compute_asset_download_event(lead)
    
    # Time decay applied to raw engagement score
    # Raw score: opens (1pt each, max 3) + clicks (2pts each, max 10) + download (10pts)
    raw_engagement_score = (email_open_count * 1) + (asset_click_count * 2) + (10 if asset_download_event else 0)
    time_decay_engagement_score = apply_time_decay(float(raw_engagement_score), engagement_recency_days)
    
    # Asset stage alignment bonus
    asset_stage_alignment_pts = compute_asset_stage_alignment(lead)
    
    # Domain intent topics
    domain_intent_topics_match = compute_domain_intent_topics_match(lead)
    
    # Repeat visitor count
    repeat_visitor_count = compute_repeat_visitor_count(lead)
    
    # Engagement absent flag (for missing data handling)
    engagement_absent_flag = engagement_recency_days >= 999
    
    # === Compute Engagement Sub-score ===
    # Base: time_decay_score + asset stage alignment (up to ~60 pts)
    engagement_base = min(60, 
        int(time_decay_engagement_score) + asset_stage_alignment_pts + domain_intent_topics_match
    )
    
    # Missing data handling:
    # If no engagement data, floor at 40 (neutral, no penalty)
    engagement_subscore = engagement_base
    if engagement_absent_flag:
        engagement_subscore = max(40, engagement_base)
    else:
        engagement_subscore = max(0, engagement_subscore)
    
    # Cap at 100
    engagement_subscore = min(100, engagement_subscore)
    
    return EngagementFeatures(
        engagement_recency_days=engagement_recency_days,
        engagement_sequence_depth=engagement_sequence_depth,
        email_open_count=email_open_count,
        asset_click_count=asset_click_count,
        asset_download_event=asset_download_event,
        time_decay_engagement_score=time_decay_engagement_score,
        asset_stage_alignment_pts=asset_stage_alignment_pts,
        domain_intent_topics_match=domain_intent_topics_match,
        repeat_visitor_count=repeat_visitor_count,
        engagement_absent_flag=engagement_absent_flag,
        engagement_subscore=engagement_subscore,
    )
