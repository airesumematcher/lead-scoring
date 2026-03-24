"""
Test script demonstrating feature extraction end-to-end.
"""

import sys
import json
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from lead_scoring.features import extract_all_features
from data.sample_leads import get_sample_leads


def main():
    """Extract features from sample leads and print results."""
    
    print("=" * 80)
    print("LEAD SCORING: FEATURE EXTRACTION DEMO")
    print("=" * 80)
    
    sample_leads = get_sample_leads()
    
    for lead_id, lead in sample_leads.items():
        print(f"\n{'='*80}")
        print(f"LEAD: {lead_id} ({lead.contact.first_name} {lead.contact.last_name})")
        print(f"COMPANY: {lead.company.company_name}")
        print(f"ROLE: {lead.contact.job_title}")
        print(f"{'='*80}")
        
        try:
            # Extract features
            features = extract_all_features(lead)
            
            # Display Accuracy pillar
            print(f"\n📊 ACCURACY PILLAR:")
            print(f"  Sub-score: {features.accuracy.accuracy_subscore}/100")
            print(f"  Email valid: {features.accuracy.email_valid}")
            print(f"  Phone valid: {features.accuracy.phone_valid}")
            print(f"  Company valid: {features.accuracy.company_name_valid}")
            print(f"  Domain credibility: {features.accuracy.domain_credibility}/100")
            print(f"  Delivery latency: {features.accuracy.delivery_latency_days} days")
            print(f"  Job title seniority: {features.accuracy.job_title_seniority_score}/5")
            print(f"  Hard gate triggered: {features.accuracy.accuracy_subscore <= 40}")
            
            # Display Client Fit pillar
            print(f"\n🎯 CLIENT FIT PILLAR:")
            print(f"  Sub-score: {features.client_fit.client_fit_subscore}/100")
            print(f"  Industry match: {features.client_fit.industry_match_pts}/25")
            print(f"  Company size match: {features.client_fit.company_size_match_pts}/25")
            print(f"  Job title match: {features.client_fit.job_title_match_persona_pts}/25")
            print(f"  TAL match: {features.client_fit.tal_match}")
            print(f"  ICP violations: {features.derived.icp_violation_count}")
            
            # Display Engagement pillar
            print(f"\n💬 ENGAGEMENT PILLAR:")
            print(f"  Sub-score: {features.engagement.engagement_subscore}/100")
            print(f"  Recency: {features.engagement.engagement_recency_days} days ago")
            print(f"  Sequence depth: {features.engagement.engagement_sequence_depth}")
            print(f"  Email opens: {features.engagement.email_open_count}")
            print(f"  Asset clicks: {features.engagement.asset_click_count}")
            print(f"  Asset download: {features.engagement.asset_download_event}")
            print(f"  Time-decay score: {features.engagement.time_decay_engagement_score:.2f}")
            print(f"  No engagement data: {features.engagement.engagement_absent_flag}")
            
            # Display Derived features
            print(f"\n🔀 DERIVED FEATURES:")
            print(f"  ACE balance score: {features.derived.ace_balance_score:.2f}")
            print(f"  Fit-Intent synergy: {features.derived.fit_intent_synergy:.2f}")
            print(f"  Freshness decay multiplier: {features.derived.freshness_decay_multiplier:.3f}")
            print(f"  Confidence signal count: {features.derived.confidence_signal_count}")
            
            print(f"\n✅ Feature extraction successful!")
            
        except Exception as e:
            print(f"\n❌ ERROR during feature extraction:")
            print(f"  {type(e).__name__}: {str(e)}")
            import traceback
            traceback.print_exc()
    
    print("\n" + "=" * 80)
    print("DEMO COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    main()
