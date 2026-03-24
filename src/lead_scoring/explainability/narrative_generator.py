"""
Narrative Generation: Plain-English Lead Score Stories.

Converts technical scores + features into CSM/sales-friendly narratives.
No jargon (no "feature weight", "logit", "gradient"). 
Structure: Summary + 3 positive drivers + 2 limiting factors + reasoning.
"""

from lead_scoring.models import (
    ExtractedFeatures, LeadInput, Grade, ScoreNarrative, RecommendedAction
)
from lead_scoring.scoring.layer2_scorer import Layer2ScoringResult


class DriverExtractor:
    """Extract top positive drivers from features."""
    
    @staticmethod
    def get_top_3_drivers(lead: LeadInput,
                         features: ExtractedFeatures,
                         scoring_result: Layer2ScoringResult,
                         composite_score: int) -> list:
        """
        Extract top 3 positive drivers ranked by contribution.
        
        Returns list of plain-English driver narratives.
        """
        drivers = []
        
        # Accuracy pillar drivers
        if features.accuracy.email_valid and features.accuracy.phone_valid:
            drivers.append({
                'text': "Valid contact data with email and phone — lead is reachable",
                'strength': 20
            })
        elif features.accuracy.email_valid:
            drivers.append({
                'text': "Valid email address on file — lead is reachable",
                'strength': 15
            })
        
        if features.accuracy.job_title_seniority_score >= 4:
            seniority_text = {4: "Director", 5: "VP / C-Suite"}.get(
                features.accuracy.job_title_seniority_score, "Senior"
            )
            drivers.append({
                'text': f"{seniority_text}-level contact — likely decision-maker on purchase committee",
                'strength': 18
            })
        
        if features.accuracy.domain_credibility >= 80:
            drivers.append({
                'text': "Company domain has strong credibility — legitimate business",
                'strength': 12
            })
        
        # Client Fit drivers
        if features.client_fit.industry_match_pts >= 25:
            drivers.append({
                'text': "Industry is exact match to your target verticals",
                'strength': 22
            })
        elif features.client_fit.industry_match_pts >= 15:
            drivers.append({
                'text': "Industry is related to your target verticals",
                'strength': 14
            })
        
        if features.client_fit.company_size_match_pts >= 25:
            drivers.append({
                'text': "Company size is in your sweet spot — ideal deal size range",
                'strength': 20
            })
        
        if features.client_fit.tal_match:
            drivers.append({
                'text': "Account is on your Target Account List — priority account",
                'strength': 25
            })
        
        if features.client_fit.job_title_match_persona_pts >= 25:
            drivers.append({
                'text': "Job title exactly matches your target buyer persona",
                'strength': 23
            })
        elif features.client_fit.job_title_match_persona_pts >= 15:
            drivers.append({
                'text': "Job title is related to your target buyer persona",
                'strength': 16
            })
        
        # Engagement drivers
        if features.engagement.asset_download_event:
            drivers.append({
                'text': "Downloaded your content — clear buying intent signal",
                'strength': 24
            })
        
        if features.engagement.asset_click_count >= 2:
            drivers.append({
                'text': f"Clicked through your content {features.engagement.asset_click_count} times — active interest",
                'strength': 16
            })
        elif features.engagement.asset_click_count == 1:
            drivers.append({
                'text': "Clicked through your content — showing interest",
                'strength': 10
            })
        
        if features.engagement.engagement_recency_days <= 7:
            drivers.append({
                'text': f"Engaged with your content {features.engagement.engagement_recency_days} days ago — fresh, active lead",
                'strength': 21
            })
        
        if features.engagement.repeat_visitor_count > 0:
            drivers.append({
                'text': f"Returned to your website {features.engagement.repeat_visitor_count} times — sustained interest",
                'strength': 13
            })
        
        # Derived features
        if scoring_result.icp_violation_penalty >= 0.9:
            drivers.append({
                'text': "Strong alignment with your Ideal Customer Profile (ICP) on multiple dimensions",
                'strength': 17
            })
        
        # Sort by strength descending, take top 3
        drivers.sort(key=lambda x: x['strength'], reverse=True)
        top_3 = [d['text'] for d in drivers[:3]]
        
        # Pad to exactly 3
        while len(top_3) < 3:
            if composite_score >= 70:
                top_3.append("Strong overall lead profile")
            elif composite_score >= 50:
                top_3.append("Meets baseline scoring criteria")
            else:
                top_3.append("Some positive signals detected")
        
        return top_3[:3]


class LimiterExtractor:
    """Extract top limiting factors from features."""
    
    @staticmethod
    def get_top_2_limiters(features: ExtractedFeatures, composite_score: int) -> list:
        """
        Extract top 2 limiting factors ranked by severity.
        
        Returns list of plain-English limiter narratives.
        """
        limiters = []
        
        # Accuracy limiters
        if not features.accuracy.phone_valid:
            limiters.append({
                'text': "Phone number missing or invalid — cannot reach lead by phone",
                'severity': 18
            })
        
        if features.accuracy.delivery_latency_days > 60:
            limiters.append({
                'text': f"Lead delivered {features.accuracy.delivery_latency_days} days after submission — may have lost interest",
                'severity': 16
            })
        
        if features.accuracy.duplicate_risk:
            limiters.append({
                'text': "Potential duplicate contact within 30 days — avoid contact fatigue",
                'severity': 12
            })
        
        # Client Fit limiters
        if features.client_fit.industry_match_pts == 0:
            limiters.append({
                'text': "Industry is not in your target verticals — lower ICP fit",
                'severity': 20
            })
        
        if features.client_fit.company_size_match_pts == 0:
            limiters.append({
                'text': "Company size outside your typical deal size range",
                'severity': 15
            })
        
        if features.client_fit.job_title_match_persona_pts == 0:
            limiters.append({
                'text': "Job title does not match your target buyer persona — may not be decision-maker",
                'severity': 19
            })
        
        if not features.client_fit.tal_match:
            limiters.append({
                'text': "Account is not on Target Account List — lower strategic priority",
                'severity': 11
            })
        
        # Engagement limiters
        if features.engagement.engagement_absent_flag:
            limiters.append({
                'text': "No engagement detected to date — interest unclear; cold outreach",
                'severity': 22
            })
        
        if features.engagement.engagement_recency_days > 30:
            limiters.append({
                'text': f"Last engagement was {features.engagement.engagement_recency_days} days ago — intent may have cooled",
                'severity': 17
            })
        
        if features.engagement.asset_click_count == 0 and features.engagement.email_open_count == 0:
            limiters.append({
                'text': "No clicks or opens on sent content — minimal engagement signal",
                'severity': 13
            })
        
        # Derived limiters
        if features.derived.icp_violation_count > 2:
            limiters.append({
                'text': f"{features.derived.icp_violation_count} significant ICP mismatches — profile alignment weak",
                'severity': 21
            })
        
        if features.derived.ace_balance_score > 30:
            limiters.append({
                'text': "Extreme imbalance across ACE pillars — incomplete data picture",
                'severity': 10
            })
        
        # Sort by severity descending, take top 2
        limiters.sort(key=lambda x: x['severity'], reverse=True)
        top_2 = [l['text'] for l in limiters[:2]]
        
        # Pad to exactly 2
        while len(top_2) < 2:
            if composite_score < 50:
                top_2.append("Lead requires data enrichment or additional research")
            else:
                top_2.append("Continue monitoring for engagement signals")
        
        return top_2[:2]


def generate_narrative(lead: LeadInput,
                      features: ExtractedFeatures,
                      composite_score: int,
                      grade: Grade,
                      action: RecommendedAction,
                      scoring_result: Layer2ScoringResult) -> ScoreNarrative:
    """
    Generate complete lead score narrative.
    
    Args:
        lead: Original lead input
        features: Extracted features
        composite_score: Final composite score (0-100)
        grade: Grade mapping (A/B/C/D)
        action: Recommended action
        scoring_result: Layer 2 scoring result
    
    Returns:
        ScoreNarrative with summary, drivers, limiters, action, reason
    """
    
    # Extract drivers and limiters
    drivers = DriverExtractor.get_top_3_drivers(lead, features, scoring_result, composite_score)
    limiters = LimiterExtractor.get_top_2_limiters(features, composite_score)
    
    # Build summary
    grade_text = {
        Grade.A: "top-tier",
        Grade.B: "strong",
        Grade.C: "viable",
        Grade.D: "below-threshold",
    }.get(grade, "ungraded")
    
    summary = f"This lead scored {composite_score}/100 ({grade.value} grade) — a {grade_text} prospect."
    
    if action == RecommendedAction.FAST_TRACK:
        summary += " Immediate sales outreach recommended."
    elif action == RecommendedAction.NURTURE:
        summary += " Include in nurture cadence to build engagement."
    elif action == RecommendedAction.ENRICH:
        summary += " Requires data enrichment before sales outreach."
    else:  # DEPRIORITIZE
        summary += " De-prioritize unless account status changes."
    
    # Build action reason
    reason_map = {
        RecommendedAction.FAST_TRACK: "TAL account with high-confidence signals; immediate sales capacity justified",
        RecommendedAction.NURTURE: "Strong fit profile; lacks engagement; nurture to activate buying motion",
        RecommendedAction.ENRICH: "Viable profile but missing critical data; research before outreach",
        RecommendedAction.DEPRIORITIZE: "Quality or fit concerns; de-prioritize unless account re-engages",
    }
    reason = reason_map.get(action, "See driver and limiter analysis")
    
    return ScoreNarrative(
        summary=summary,
        positive_drivers=drivers,
        limiting_factors=limiters,
        recommended_action=action,
        action_reason=reason,
    )
