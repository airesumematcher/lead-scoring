"""
End-to-end scoring demo.
Shows complete pipeline: feature extraction → Layer 1 gates → Layer 2 scoring → LeadScore output.
"""

import sys
import json
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from lead_scoring.config import load_config
from lead_scoring.scoring import score_lead, score_leads_batch
from data.sample_leads import get_sample_leads


def print_lead_score(lead_score):
    """Pretty-print a LeadScore."""
    print(f"\n{'='*80}")
    print(f"LEAD: {lead_score.lead_id}")
    print(f"{'='*80}")
    
    print(f"\n🎯 SCORE & GRADE:")
    print(f"  Composite Score: {lead_score.score}/100")
    print(f"  Grade: {lead_score.grade.value}")
    print(f"  Confidence: {lead_score.confidence.value}")
    
    print(f"\n📊 ACE BREAKDOWN:")
    print(f"  Accuracy: {lead_score.ace_breakdown.accuracy}/100 ({lead_score.ace_breakdown.weights['accuracy']:.1%})")
    print(f"  Client Fit: {lead_score.ace_breakdown.client_fit}/100 ({lead_score.ace_breakdown.weights['client_fit']:.1%})")
    print(f"  Engagement: {lead_score.ace_breakdown.engagement}/100 ({lead_score.ace_breakdown.weights['engagement']:.1%})")
    
    print(f"\n🔮 PIPELINE INFLUENCE:")
    print(f"  Probability: {lead_score.pipeline_influence.pct:.1%}")
    print(f"  Confidence: {lead_score.pipeline_influence.confidence.value}")
    print(f"  Drivers: {', '.join(lead_score.pipeline_influence.drivers[:2])}")
    
    print(f"\n🕐 FRESHNESS:")
    print(f"  Status: {lead_score.freshness.status.value}")
    print(f"  Delivery Age: {lead_score.freshness.delivery_age_days} days")
    if lead_score.freshness.last_engagement_days_ago:
        print(f"  Last Engagement: {lead_score.freshness.last_engagement_days_ago} days ago")
    else:
        print(f"  Last Engagement: None recorded")
    print(f"  Decay Multiplier: {lead_score.freshness.decay_multiplier:.3f}")
    
    print(f"\n✅ RECOMMENDED ACTION:")
    print(f"  Action: {lead_score.narrative.recommended_action.value}")
    print(f"  Reason: {lead_score.narrative.action_reason}")
    
    print(f"\n📋 DATA QUALITY:")
    print(f"  Feature Completeness: {lead_score.data_quality.feature_completeness_pct}%")
    print(f"  Accuracy Ceiling Applied: {lead_score.data_quality.accuracy_ceiling_applied}")
    print(f"  Engagement Data Available: {lead_score.data_quality.engagement_data_available}")
    
    print(f"\n🔐 AUDIT TRAIL:")
    print(f"  Model Version: {lead_score.audit_trail.model_version}")
    print(f"  Feature Hash: {lead_score.audit_trail.feature_set_hash[:16]}...")
    print(f"  Training Data Date: {lead_score.audit_trail.training_data_date}")


def main():
    """Run end-to-end scoring demo."""
    print("=" * 80)
    print("LEAD SCORING: END-TO-END PIPELINE DEMO (Step 2: Scoring Architecture)")
    print("=" * 80)
    
    # Load config
    config = load_config()
    print(f"\n✅ Configuration loaded (model v{config.get_model_version()})")
    
    # Get sample leads
    sample_leads = get_sample_leads()
    print(f"✅ Loaded {len(sample_leads)} sample leads")
    
    # Score each lead
    print(f"\nScoring {len(sample_leads)} leads...")
    lead_scores = []
    
    for lead_id, lead in sample_leads.items():
        try:
            score = score_lead(lead, config)
            lead_scores.append(score)
            print(f"  ✅ {lead_id}: {score.grade.value}/{score.score} ({score.narrative.recommended_action.value})")
        except Exception as e:
            print(f"  ❌ {lead_id}: {str(e)}")
            import traceback
            traceback.print_exc()
    
    # Display detailed results
    for lead_score in lead_scores:
        print_lead_score(lead_score)
    
    # Summary table
    print(f"\n{'='*80}")
    print("SUMMARY TABLE")
    print(f"{'='*80}")
    print(f"{'Lead ID':<12} {'Grade':<8} {'Score':<8} {'Confidence':<12} {'Action':<15} {'Freshness':<10}")
    print("-" * 80)
    for score in lead_scores:
        print(f"{score.lead_id:<12} {score.grade.value:<8} {score.score:<8} {score.confidence.value:<12} {score.narrative.recommended_action.value:<15} {score.freshness.status.value:<10}")
    
    print(f"\n{'='*80}")
    print("✅ DEMO COMPLETE - Step 2 (Scoring Architecture) is operational!")
    print(f"{'='*80}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
