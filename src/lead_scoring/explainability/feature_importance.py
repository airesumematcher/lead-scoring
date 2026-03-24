"""
Feature Importance Extraction: Which features drove this score?

Analyzes ACE sub-score contributions and feature impacts.
Not using SHAP in Phase 1; instead using rule-based importance calculation.
"""

from lead_scoring.models import ExtractedFeatures
from lead_scoring.scoring.layer2_scorer import Layer2ScoringResult


class FeatureImportanceCalculator:
    """Calculate feature-level importance contributions."""
    
    @staticmethod
    def get_ace_pillar_importance(scoring_result: Layer2ScoringResult) -> dict:
        """
        Get importance of each ACE pillar in the final composite score.
        
        Returns:
            {
                'accuracy': {'subscore': int, 'weight': float, 'contribution': float},
                'client_fit': {...},
                'engagement': {...}
            }
        """
        weights = scoring_result.weights
        a_score = scoring_result.accuracy_subscore
        c_score = scoring_result.client_fit_subscore
        e_score = scoring_result.engagement_subscore
        
        # Calculate weighted contributions
        a_contribution = a_score * weights['accuracy']
        c_contribution = c_score * weights['client_fit']
        e_contribution = e_score * weights['engagement']
        
        total_contribution = a_contribution + c_contribution + e_contribution
        
        return {
            'accuracy': {
                'subscore': a_score,
                'weight': weights['accuracy'],
                'contribution': a_contribution,
                'pct_of_composite': (a_contribution / max(total_contribution, 1)) * 100
            },
            'client_fit': {
                'subscore': c_score,
                'weight': weights['client_fit'],
                'contribution': c_contribution,
                'pct_of_composite': (c_contribution / max(total_contribution, 1)) * 100
            },
            'engagement': {
                'subscore': e_score,
                'weight': weights['engagement'],
                'contribution': e_contribution,
                'pct_of_composite': (e_contribution / max(total_contribution, 1)) * 100
            }
        }
    
    @staticmethod
    def get_top_accuracy_features(features: ExtractedFeatures, limit: int = 3) -> list:
        """Get top accuracy features contributing to the subscore."""
        feature_scores = []
        acc = features.accuracy
        
        if acc.email_valid:
            feature_scores.append(('Email valid', 20))
        if acc.phone_valid:
            feature_scores.append(('Phone valid', 15))
        if acc.job_title_present:
            feature_scores.append((f'Job title seniority ({acc.job_title_seniority_score}/5)', 15))
        if acc.company_name_valid:
            feature_scores.append(('Company data valid', 20))
        if acc.domain_credibility > 70:
            feature_scores.append((f'Domain credibility ({acc.domain_credibility}/100)', 12))
        if not acc.duplicate_risk:
            feature_scores.append(('No duplicates detected', 15))
        
        feature_scores.sort(key=lambda x: x[1], reverse=True)
        return [f[0] for f in feature_scores[:limit]]
    
    @staticmethod
    def get_top_clientfit_features(features: ExtractedFeatures, limit: int = 3) -> list:
        """Get top client fit features contributing to the subscore."""
        feature_scores = []
        cf = features.client_fit
        
        if cf.industry_match_pts > 0:
            feature_scores.append((f'Industry match ({cf.industry_match_pts}/25)', cf.industry_match_pts))
        if cf.company_size_match_pts > 0:
            feature_scores.append((f'Company size match ({cf.company_size_match_pts}/25)', cf.company_size_match_pts))
        if cf.tal_match:
            feature_scores.append(('TAL account match', 20))
        if cf.job_title_match_persona_pts > 0:
            feature_scores.append((f'Job title persona match ({cf.job_title_match_persona_pts}/25)', cf.job_title_match_persona_pts))
        if cf.geography_match_pts > 0:
            feature_scores.append((f'Geography match ({cf.geography_match_pts}/20)', cf.geography_match_pts))
        
        feature_scores.sort(key=lambda x: x[1], reverse=True)
        return [f[0] for f in feature_scores[:limit]]
    
    @staticmethod
    def get_top_engagement_features(features: ExtractedFeatures, limit: int = 3) -> list:
        """Get top engagement features contributing to the subscore."""
        feature_scores = []
        eng = features.engagement
        
        if eng.asset_download_event:
            feature_scores.append(('Asset download (clear intent)', 10))
        if eng.asset_click_count > 0:
            feature_scores.append((f'Asset clicks ({eng.asset_click_count})', eng.asset_click_count * 2))
        if eng.email_open_count > 0:
            feature_scores.append((f'Email opens ({eng.email_open_count})', eng.email_open_count))
        if eng.engagement_recency_days <= 7:
            feature_scores.append((f'Fresh engagement ({eng.engagement_recency_days} days ago)', 8))
        elif eng.engagement_recency_days <= 30:
            feature_scores.append((f'Recent engagement ({eng.engagement_recency_days} days ago)', 4))
        if eng.repeat_visitor_count > 0:
            feature_scores.append((f'Repeat website visits ({eng.repeat_visitor_count})', eng.repeat_visitor_count * 2))
        
        feature_scores.sort(key=lambda x: x[1], reverse=True)
        return [f[0] for f in feature_scores[:limit]]
    
    @staticmethod
    def get_adjustments_summary(features: ExtractedFeatures,
                               scoring_result: Layer2ScoringResult) -> list:
        """Get list of penalties/multipliers applied to score."""
        adjustments = []
        
        # Freshness decay
        if scoring_result.freshness_decay_applied < 1.0:
            decay_pct = (1.0 - scoring_result.freshness_decay_applied) * 100
            adjustments.append(f"Freshness decay applied: −{decay_pct:.1f}%")
        
        # ICP violation penalty
        if scoring_result.icp_violation_penalty < 1.0:
            penalty_pct = (1.0 - scoring_result.icp_violation_penalty) * 100
            adjustments.append(f"ICP violation penalty: −{penalty_pct:.1f}%")
        
        # ACE balance penalty
        if features.derived.ace_balance_score > 30:
            adjustments.append(f"ACE imbalance penalty: −5.0% (StdDev={features.derived.ace_balance_score:.1f})")
        
        return adjustments


def explain_score_components(features: ExtractedFeatures,
                             scoring_result: Layer2ScoringResult) -> dict:
    """
    Generate comprehensive score explanation breaking down all components.
    
    Returns:
        {
            'ace_importance': {...},
            'top_accuracy_features': [...],
            'top_clientfit_features': [...],
            'top_engagement_features': [...],
            'adjustments': [...],
        }
    """
    calc = FeatureImportanceCalculator()
    
    return {
        'ace_importance': calc.get_ace_pillar_importance(scoring_result),
        'top_accuracy_features': calc.get_top_accuracy_features(features),
        'top_clientfit_features': calc.get_top_clientfit_features(features),
        'top_engagement_features': calc.get_top_engagement_features(features),
        'adjustments': calc.get_adjustments_summary(features, scoring_result),
    }
