"""
Score Builder: Assemble complete LeadScore output.

Takes formatted features and scoring results, builds final LeadScore object
with all required output fields: score, grade, confidence, ACE breakdown,
freshness, narrative (placeholder), pipeline influence proxy, etc.
"""

from datetime import datetime, timezone
from lead_scoring.models import (
    LeadInput, ExtractedFeatures, LeadScore, Grade, ConfidenceBand, Freshness,
    ACEBreakdown, PipelineInfluence, FreshnessSignal, ScoreNarrative,
    RecommendedAction, AccountContext, DataQuality, AuditTrail,
)
from lead_scoring.scoring.layer1_gate import AccuracyGateResult
from lead_scoring.scoring.layer2_scorer import Layer2ScoringResult
from lead_scoring.config import ScoringConfig
from lead_scoring.explainability.narrative_generator import generate_narrative
from lead_scoring.utils import (
    compute_feature_hash, grade_from_score, confidence_from_signal_count,
    freshness_from_recency, get_timestamp_iso
)


def map_score_to_grade(composite_score: int, config: ScoringConfig) -> Grade:
    """Map composite score to grade letter."""
    boundaries = config.get_grade_boundaries()
    
    if composite_score >= boundaries['A']:
        return Grade.A
    elif composite_score >= boundaries['B']:
        return Grade.B
    elif composite_score >= boundaries['C']:
        return Grade.C
    else:
        return Grade.D


def map_score_to_confidence(signal_count: int, accuracy_subscore: int) -> ConfidenceBand:
    """Map signal count to confidence band."""
    if accuracy_subscore < 60:
        return ConfidenceBand.LOW
    elif signal_count >= 12:
        return ConfidenceBand.HIGH
    elif signal_count >= 8:
        return ConfidenceBand.MEDIUM
    else:
        return ConfidenceBand.LOW


def map_freshness(engagement_recency: int, delivery_age: int, thresholds: dict) -> Freshness:
    """Map recency to freshness signal."""
    fresh_threshold = thresholds['fresh']
    aging_threshold = thresholds['aging']
    
    # Fresh if recent engagement or fresh delivery
    if engagement_recency <= fresh_threshold or (delivery_age <= 14 and engagement_recency < 999):
        return Freshness.FRESH
    elif engagement_recency <= aging_threshold:
        return Freshness.AGING
    else:
        return Freshness.STALE


def map_recommended_action(grade: Grade, engagement_absent: bool) -> RecommendedAction:
    """Map grade to recommended action."""
    if grade == Grade.A:
        return RecommendedAction.FAST_TRACK
    elif grade == Grade.B:
        return RecommendedAction.NURTURE
    elif grade == Grade.C:
        # If no engagement, recommend enrichment; else nurture
        return RecommendedAction.ENRICH if engagement_absent else RecommendedAction.NURTURE
    else:
        return RecommendedAction.DEPRIORITIZE


def compute_pipeline_influence_proxy(features: ExtractedFeatures, config: ScoringConfig) -> PipelineInfluence:
    """
    Compute pipeline influence proxy (0-100 %).
    
    Uses Phase 1 proxy components:
    - Acceptance rate baseline for this grade band (TBD post-launch)
    - Job title seniority
    - TAL match
    - Engagement recency
    - Freshness
    
    Returns tuple: (pct: 0-100, confidence: High/Medium/Low, drivers: list)
    """
    pipeline_cfg = config.config.get("pipeline_influence", {})
    components = pipeline_cfg.get("proxy_components", {})
    
    # Placeholder: Phase 1 is using acceptance rates as proxy
    # Will upgrade to true L2O conversion once CRM data available
    
    a_score = features.accuracy.accuracy_subscore
    c_score = features.client_fit.client_fit_subscore
    e_score = features.engagement.engagement_subscore
    seniority = features.accuracy.job_title_seniority_score
    tal_match = features.client_fit.tal_match
    engagement_recency = features.engagement.engagement_recency_days
    
    # Compute influence percentage (0-100)
    influence_pct = 50  # Baseline
    
    # Seniority boost (20% weight)
    seniority_boost = (seniority / 5.0) * 20
    influence_pct += seniority_boost
    
    # TAL match boost (15% weight)
    tal_boost = 15 if tal_match else -5
    influence_pct += tal_boost
    
    # Engagement recency boost (15% weight)
    if engagement_recency <= 7:
        engagement_boost = 15
    elif engagement_recency <= 30:
        engagement_boost = 8
    else:
        engagement_boost = 0
    influence_pct += engagement_boost
    
    # Cap at 100
    influence_pct = min(100, max(0, influence_pct))
    
    # Drivers (top 3 contributors)
    drivers = []
    if seniority >= 4:
        drivers.append(f"Senior stakeholder (seniority {seniority}/5)")
    if tal_match:
        drivers.append("TAL account match")
    if engagement_recency <= 7:
        drivers.append(f"Recent engagement ({engagement_recency} days ago)")
    
    # Pad to 3
    while len(drivers) < 3:
        if a_score >= 80:
            drivers.append("Valid contact data")
        elif c_score >= 75:
            drivers.append("Strong ICP fit")
        else:
            drivers.append("Baseline opportunity score")
    drivers = drivers[:3]
    
    # Confidence in pipeline influence prediction
    if a_score >= 80 and c_score >= 75 and e_score >= 70:
        confidence = ConfidenceBand.HIGH
    elif a_score >= 60 and (c_score >= 60 or e_score >= 60):
        confidence = ConfidenceBand.MEDIUM
    else:
        confidence = ConfidenceBand.LOW
    
    return PipelineInfluence(
        pct=influence_pct / 100.0,  # Convert to 0.0-1.0
        confidence=confidence,
        drivers=drivers,
    )


def assemble_lead_score(lead: LeadInput,
                       features: ExtractedFeatures,
                       gate_result: AccuracyGateResult,
                       scoring_result: Layer2ScoringResult,
                       config: ScoringConfig) -> LeadScore:
    """
    Assemble complete LeadScore output.
    
    Args:
        lead: Original lead input
        features: Extracted features from Layer 1
        gate_result: Result from accuracy gates
        scoring_result: Result from Layer 2 scoring
        config: Configuration
    
    Returns:
        LeadScore: Complete scoring output
    """
    
    if not gate_result.passed:
        return _build_failed_score(lead, gate_result, config)

    composite_score = min(
        scoring_result.composite_score,
        gate_result.recommended_accuracy_ceiling,
    )
    
    # Map to grade
    grade = map_score_to_grade(composite_score, config)
    
    # Map to confidence
    confidence = map_score_to_confidence(
        features.derived.confidence_signal_count,
        features.accuracy.accuracy_subscore
    )
    
    # Compute freshness
    freshness_thresholds = config.get_freshness_thresholds()
    # Handle timezone-naive submission_timestamp
    submission_ts = lead.submission_timestamp
    if submission_ts.tzinfo is None:
        # If naive, treat as UTC
        submission_ts = submission_ts.replace(tzinfo=timezone.utc)
    
    delivery_age = (datetime.utcnow().replace(tzinfo=timezone.utc) - submission_ts).days
    freshness = map_freshness(
        features.engagement.engagement_recency_days,
        delivery_age,
        freshness_thresholds
    )
    
    # Build ACE breakdown
    ace_breakdown = ACEBreakdown(
        accuracy=scoring_result.accuracy_subscore,
        client_fit=scoring_result.client_fit_subscore,
        engagement=scoring_result.engagement_subscore,
        weights=scoring_result.weights,
        program_type=lead.campaign.program_type.value,
    )
    
    # Pipeline influence proxy
    pipeline_influence = compute_pipeline_influence_proxy(features, config)
    
    # Freshness signal details
    freshness_signal = FreshnessSignal(
        status=freshness,
        delivery_age_days=delivery_age,
        last_engagement_days_ago=features.engagement.engagement_recency_days if features.engagement.engagement_recency_days < 999 else None,
        decay_multiplier=scoring_result.freshness_decay_applied,
    )
    
    # Recommended action
    recommended_action = map_recommended_action(grade, features.engagement.engagement_absent_flag)
    
    # Generate narrative with drivers and limiters
    narrative = generate_narrative(
        lead,
        features,
        composite_score,
        grade,
        recommended_action,
        scoring_result,
    )
    
    # Account context (if available)
    account_context = AccountContext(
        account_id=None,  # Would come from enrichment
        in_market=False,  # Would be set by account-level logic
        buying_committee_coverage_pct=None,
    )
    
    # Data quality
    data_quality = DataQuality(
        feature_completeness_pct=int((features.derived.confidence_signal_count / 13.0) * 100),
        accuracy_ceiling_applied=(gate_result.recommended_accuracy_ceiling < 100),
        engagement_data_available=(not features.engagement.engagement_absent_flag),
    )
    
    # Audit trail
    feature_dict = {
        'accuracy': features.accuracy.accuracy_subscore,
        'client_fit': features.client_fit.client_fit_subscore,
        'engagement': features.engagement.engagement_subscore,
        'program_type': lead.campaign.program_type.value,
    }
    feature_hash = compute_feature_hash(feature_dict)
    
    audit_trail = AuditTrail(
        model_version=config.get_model_version(),
        feature_set_hash=feature_hash,
        training_data_date=config.get_training_data_date(),
        retraining_recommended=False,  # Would be set by feedback loop
    )
    
    # Build final LeadScore
    lead_score = LeadScore(
        lead_id=lead.lead_id,
        scored_at=datetime.utcnow(),
        
        score=composite_score,
        grade=grade,
        confidence=confidence,
        
        ace_breakdown=ace_breakdown,
        pipeline_influence=pipeline_influence,
        freshness=freshness_signal,
        narrative=narrative,
        account_context=account_context,
        
        data_quality=data_quality,
        audit_trail=audit_trail,
    )
    
    return lead_score


def _build_failed_score(lead: LeadInput, 
                       gate_result: AccuracyGateResult,
                       config: ScoringConfig) -> LeadScore:
    """Build minimal LeadScore when accuracy gate fails."""
    
    return LeadScore(
        lead_id=lead.lead_id,
        scored_at=datetime.utcnow(),
        
        score=0,
        grade=Grade.D,
        confidence=ConfidenceBand.LOW,
        
        ace_breakdown=ACEBreakdown(
            accuracy=0,
            client_fit=0,
            engagement=0,
            weights={'accuracy': 1.0, 'client_fit': 0.0, 'engagement': 0.0},
            program_type=lead.campaign.program_type.value,
        ),
        
        pipeline_influence=PipelineInfluence(
            pct=0.0,
            confidence=ConfidenceBand.LOW,
            drivers=[gate_result.reason],
        ),
        
        freshness=FreshnessSignal(
            status=Freshness.STALE,
            delivery_age_days=(datetime.utcnow().replace(tzinfo=timezone.utc) - (lead.submission_timestamp.replace(tzinfo=timezone.utc) if lead.submission_timestamp.tzinfo is None else lead.submission_timestamp)).days,
            last_engagement_days_ago=None,
            decay_multiplier=0.0,
        ),
        
        narrative=ScoreNarrative(
            summary="Lead blocked by accuracy gate. Cannot proceed with scoring until data quality issues are resolved.",
            positive_drivers=[],
            limiting_factors=[gate_result.reason, "Insufficient data quality for reliable scoring"],
            recommended_action=RecommendedAction.ENRICH,
            action_reason="Data quality must be resolved first; route to enrichment or manual review.",
        ),
        
        account_context=AccountContext(
            account_id=None,
            in_market=False,
        ),
        
        data_quality=DataQuality(
            feature_completeness_pct=0,
            accuracy_ceiling_applied=True,
            engagement_data_available=False,
        ),
        
        audit_trail=AuditTrail(
            model_version=config.get_model_version(),
            feature_set_hash="",
            training_data_date=config.get_training_data_date(),
            retraining_recommended=False,
        ),
    )
