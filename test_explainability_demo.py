"""
End-to-end demo with explainability: Feature extraction → Scoring → Narratives.
Shows complete lead score with plain-English explanations, drivers, and limiters.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from lead_scoring.config import load_config
from lead_scoring.scoring import score_lead
from lead_scoring.explainability import explain_score_components
from data.sample_leads import get_sample_leads


def print_full_lead_explanation(lead_score, explanation):
    """Print complete lead score with narrative and explanation."""
    print(f"\n{'='*80}")
    print(f"LEAD SCORE & NARRATIVE: {lead_score.lead_id}")
    print(f"{'='*80}")
    
    # Score Header
    print(f"\n🎯 SCORE & GRADE:")
    print(f"  Score: {lead_score.score}/100")
    print(f"  Grade: {lead_score.grade.value}")
    print(f"  Confidence: {lead_score.confidence.value}")
    
    # Narrative (Main Story)
    print(f"\n📖 SCORE NARRATIVE:")
    print(f"  {lead_score.narrative.summary}")
    
    print(f"\n  ✅ Top Positive Drivers:")
    for i, driver in enumerate(lead_score.narrative.positive_drivers, 1):
        print(f"     {i}. {driver}")
    
    print(f"\n  ⚠️  Limiting Factors:")
    for i, limiter in enumerate(lead_score.narrative.limiting_factors, 1):
        print(f"     {i}. {limiter}")
    
    print(f"\n  📌 Recommended Action:")
    print(f"     {lead_score.narrative.recommended_action.value}")
    print(f"     Reason: {lead_score.narrative.action_reason}")
    
    # ACE Breakdown with Importance
    print(f"\n📊 ACE PILLAR BREAKDOWN:")
    ace_importance = explanation['ace_importance']
    
    acc = ace_importance['accuracy']
    print(f"  Accuracy:")
    print(f"    Sub-score: {acc['subscore']}/100 (weight: {acc['weight']:.0%})")
    print(f"    Contribution: {acc['contribution']:.1f} pts ({acc['pct_of_composite']:.1f}% of composite)")
    print(f"    Top features: {', '.join(explanation['top_accuracy_features'][:2])}")
    
    cf = ace_importance['client_fit']
    print(f"  Client Fit:")
    print(f"    Sub-score: {cf['subscore']}/100 (weight: {cf['weight']:.0%})")
    print(f"    Contribution: {cf['contribution']:.1f} pts ({cf['pct_of_composite']:.1f}% of composite)")
    print(f"    Top features: {', '.join(explanation['top_clientfit_features'][:2])}")
    
    eng = ace_importance['engagement']
    print(f"  Engagement:")
    print(f"    Sub-score: {eng['subscore']}/100 (weight: {eng['weight']:.0%})")
    print(f"    Contribution: {eng['contribution']:.1f} pts ({eng['pct_of_composite']:.1f}% of composite)")
    print(f"    Top features: {', '.join(explanation['top_engagement_features'][:2])}")
    
    # Score Adjustments
    if explanation['adjustments']:
        print(f"\n⚙️  SCORE ADJUSTMENTS:")
        for adjustment in explanation['adjustments']:
            print(f"  • {adjustment}")
    
    # Freshness & Pipeline
    print(f"\n🕐 FRESHNESS & PIPELINE:")
    print(f"  Freshness: {lead_score.freshness.status.value}")
    print(f"  Delivery Age: {lead_score.freshness.delivery_age_days} days")
    if lead_score.freshness.last_engagement_days_ago:
        print(f"  Last Engagement: {lead_score.freshness.last_engagement_days_ago} days ago")
    print(f"  Pipeline Influence: {lead_score.pipeline_influence.pct:.0%}")
    print(f"  Confidence: {lead_score.pipeline_influence.confidence.value}")


def main():
    """Run explainability demo."""
    print("=" * 80)
    print("LEAD SCORING WITH EXPLAINABILITY (Step 3: Narrative Generation)")
    print("=" * 80)
    
    # Load config
    config = load_config()
    print(f"\n✅ Configuration loaded (model v{config.get_model_version()})")
    
    # Get sample leads
    sample_leads = get_sample_leads()
    print(f"✅ Loaded {len(sample_leads)} sample leads")
    
    # Score each lead with full explanation
    print(f"\nScoring {len(sample_leads)} leads with narrative generation...")
    
    results = []
    for lead_id, lead in sample_leads.items():
        try:
            # Score the lead
            lead_score = score_lead(lead, config)
            
            # Extract features for explanation
            from lead_scoring.features import extract_all_features
            from lead_scoring.scoring.layer1_gate import apply_accuracy_gates
            from lead_scoring.scoring.layer2_scorer import compute_composite_score
            
            features = extract_all_features(lead)
            gate_result = apply_accuracy_gates(features, config)
            accuracy_ceiling = gate_result.recommended_accuracy_ceiling if not gate_result.passed else 100
            scoring_result = compute_composite_score(
                features,
                program_type=lead.campaign.program_type.value,
                config=config,
                accuracy_ceiling=accuracy_ceiling,
            )
            
            # Generate explanation
            explanation = explain_score_components(features, scoring_result)
            
            results.append((lead_score, explanation))
            print(f"  ✅ {lead_id}: {lead_score.grade.value}/{lead_score.score} — {lead_score.narrative.recommended_action.value}")
            
        except Exception as e:
            print(f"  ❌ {lead_id}: {str(e)}")
            import traceback
            traceback.print_exc()
    
    # Display detailed explanations
    for lead_score, explanation in results:
        print_full_lead_explanation(lead_score, explanation)
    
    # Summary
    print(f"\n{'='*80}")
    print("SUMMARY TABLE")
    print(f"{'='*80}")
    print(f"{'Lead ID':<12} {'Grade':<8} {'Score':<8} {'Freshness':<10} {'Action':<15} {'Confidence':<12}")
    print("-" * 80)
    for lead_score, _ in results:
        print(f"{lead_score.lead_id:<12} {lead_score.grade.value:<8} {lead_score.score:<8} {lead_score.freshness.status.value:<10} {lead_score.narrative.recommended_action.value:<15} {lead_score.confidence.value:<12}")
    
    print(f"\n{'='*80}")
    print("✅ Step 3 (Explainability Layer) COMPLETE — Narratives are now fully functional!")
    print(f"{'='*80}\n")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
