"""
ENHANCED DATA PREPARATION WITH CAMPAIGN CONTEXT
Incorporates campaign taxonomy: Asset Type, Topic, Audience, Volume, Engagement Sequence
Builds Fit Score (demographic) and Intent Score (behavioral) separately
Output: Train-ready dataset with 20+ features for campaign-aware scoring
"""

import pandas as pd
import numpy as np
import json
from pathlib import Path
from datetime import datetime

def load_data():
    """Load both CSV (campaign metadata) and Excel (lead enrichment) files"""
    print("📂 Loading data sources...")
    
    # Main lead data with campaign info
    csv_data = pd.read_csv(
        "sample_data/Lead Score_Lead Outreach Results Pivots(Sheet1) (1).csv"
    )
    
    # Clean Total Leads Delivered (handle "34 of 54" format -> take first number)
    def parse_leads_delivered(val):
        if pd.isna(val):
            return np.nan
        val_str = str(val).strip()
        if ' of ' in val_str:
            # Extract first number from "X of Y" format
            return float(val_str.split(' of ')[0])
        try:
            return float(val_str)
        except:
            return np.nan
    
    csv_data['Total Leads Delivered'] = csv_data['Total Leads Delivered'].apply(parse_leads_delivered)
    
    # Enriched lead attributes
    xl_data = pd.read_excel("sample_data/cleaned_data.xlsx", sheet_name='cleaned_data')
    
    print(f"✅ CSV records: {len(csv_data)}")
    print(f"✅ Excel enrichment records: {len(xl_data)}")
    
    return csv_data, xl_data


def engineer_campaign_context_features(df_csv):
    """Extract and encode campaign taxonomy features"""
    print("\n🏷️  Engineering Campaign Context Features...")
    
    features = pd.DataFrame()
    
    # 1. CAMPAIGN ASSET TYPE ENCODING
    # Infer from Campaign Name patterns
    def get_asset_type(campaign_name):
        """Extract asset type from campaign name"""
        if pd.isna(campaign_name):
            return 'Unknown'
        campaign_lower = str(campaign_name).lower()
        if 'case study' in campaign_lower or 'csr' in campaign_lower:
            return 'CaseStudy'
        elif 'buyer guide' in campaign_lower or 'guide' in campaign_lower:
            return 'BuyerGuide'
        elif 'webinar' in campaign_lower or 'event' in campaign_lower:
            return 'Webinar'
        elif 'whitepaper' in campaign_lower or 'ebook' in campaign_lower:
            return 'Whitepaper'
        elif 'checklist' in campaign_lower:
            return 'Checklist'
        elif 'thought leadership' in campaign_lower or 'tl' in campaign_lower:
            return 'ThoughtLeadership'
        else:
            return 'Other'
    
    asset_types = df_csv['Campaign Name'].apply(get_asset_type)
    asset_type_mapping = {
        'ThoughtLeadership': 1.0, 'BuyerGuide': 0.9, 'CaseStudy': 0.95,
        'Webinar': 0.85, 'Whitepaper': 0.8, 'Checklist': 0.75, 'Other': 0.5, 'Unknown': 0.4
    }
    features['asset_type_score'] = asset_types.map(asset_type_mapping).fillna(0.5)
    features['asset_type'] = asset_types
    
    # 2. CAMPAIGN VOLUME TIER (High/Mid/Low engagement potential)
    def get_volume_tier(total_delivered):
        """Categorize campaign by reach"""
        if pd.isna(total_delivered):
            return 'Unknown'
        if total_delivered >= 300:
            return 'HighVolume'  # 300+
        elif total_delivered >= 100:
            return 'MidVolume'     # 100-299
        else:
            return 'LowVolume'     # <100
    
    volume_tiers = df_csv['Total Leads Delivered'].apply(get_volume_tier)
    volume_tier_score = {
        'HighVolume': 0.8, 'MidVolume': 0.9, 'LowVolume': 0.7, 'Unknown': 0.5
    }
    features['campaign_volume_tier'] = volume_tiers
    features['campaign_volume_score'] = volume_tiers.map(volume_tier_score).fillna(0.5)
    features['total_leads_delivered'] = df_csv['Total Leads Delivered'].fillna(0)
    
    # 3. ENGAGEMENT SEQUENCE (Multi-touch depth)
    # Single Touch (1 email) vs Multi-Touch (2+ emails) vs Teleguide (sequential)
    def get_engagement_sequence(row):
        """Determine engagement sequence type"""
        email1_engaged = (row.get('Email 1 - Opened') == 'Yes') or (row.get('Email 1 - Clicked') == 'Yes')
        email2_engaged = (row.get('Email 2 - Open') == 'Yes') or (row.get('Email 2 - Clicked') == 'Yes')
        
        if email1_engaged and email2_engaged:
            return 'MultiTouch'  # Engaged with multiple touches
        elif email1_engaged or email2_engaged:
            return 'SingleTouch'  # Only one email
        else:
            return 'NoTouch'      # No engagement recorded
    
    features['engagement_sequence'] = df_csv.apply(get_engagement_sequence, axis=1)
    sequence_score = {'MultiTouch': 1.0, 'SingleTouch': 0.6, 'NoTouch': 0.2}
    features['engagement_sequence_score'] = features['engagement_sequence'].map(sequence_score)
    
    # 4. JOB FUNCTION (Audience type mapping)
    def map_audience_type(job_function):
        """Map to audience intent level"""
        if pd.isna(job_function):
            return 'Unknown'
        jf_lower = str(job_function).lower()
        
        # Decision makers
        if any(x in jf_lower for x in ['finance', 'operations', 'it', 'executive', 'cto', 'cfo', 'ceo']):
            return 'DecisionMaker'
        # Buyers/procurers
        elif any(x in jf_lower for x in ['procurement', 'buyer', 'purchas']):
            return 'Buyer'
        # Domain experts
        elif any(x in jf_lower for x in ['engineer', 'architect', 'analyst', 'scientist', 'manager']):
            return 'Expert'
        # Other
        else:
            return 'Other'
    
    features['audience_type'] = df_csv['Job Function'].apply(map_audience_type)
    audience_score = {
        'DecisionMaker': 1.0, 'Buyer': 0.95, 'Expert': 0.7, 'Other': 0.5, 'Unknown': 0.3
    }
    features['audience_type_score'] = features['audience_type'].map(audience_score)
    
    # 5. COMPANY SIZE MAPPING (Fit signal)
    def map_company_size(size_str):
        """Convert company size to numeric score (1-8 scale)"""
        if pd.isna(size_str):
            return 4
        size_lower = str(size_str).lower()
        if 'xxlarge' in size_lower or '10,000+' in size_lower or '10000' in size_lower:
            return 8
        elif 'xlarge' in size_lower or '1,000' in size_lower or '5,000' in size_lower:
            return 7
        elif 'large' in size_lower or '500' in size_lower:
            return 6
        elif 'medium' in size_lower or '100' in size_lower:
            return 4
        elif 'small' in size_lower or '50' in size_lower or '10-' in size_lower:
            return 2
        else:
            return 4
    
    features['company_size_score'] = df_csv['Company Size'].apply(map_company_size)
    
    # 6. ENGAGEMENT METRICS (Intent score components)
    email1_opened = (df_csv['Email 1 - Opened'] == 'Yes').astype(int)
    email1_clicked = (df_csv['Email 1 - Clicked'] == 'Yes').astype(int)
    email2_opened = (df_csv['Email 2 - Open'] == 'Yes').astype(int)
    email2_clicked = (df_csv['Email 2 - Clicked'] == 'Yes').astype(int)
    
    features['email1_opened'] = email1_opened
    features['email1_clicked'] = email1_clicked
    features['email2_opened'] = email2_opened
    features['email2_clicked'] = email2_clicked
    
    # Total engagement count (0-4 scale: each action = +1)
    features['total_engagements'] = (
        email1_opened + email1_clicked + email2_opened + email2_clicked
    )
    
    # 7. DERIVED SCORES (Phase 2 framework)
    # FIT SCORE: Company fit + Audience fit (demographic/firmographic)
    features['fit_score'] = (
        (features['company_size_score'] / 8) * 0.6 +  # 60% company size
        features['audience_type_score'] * 0.4  # 40% audience type
    ) * 100
    
    # INTENT SCORE: Email engagement + Asset engagement (behavioral)
    features['intent_score'] = (
        (features['total_engagements'] / 4) * 0.5 +  # 50% email engagement
        features['engagement_sequence_score'] * 0.3 +  # 30% sequence depth
        features['asset_type_score'] * 0.2  # 20% asset relevance
    ) * 100
    
    # CAMPAIGN QUALITY SCORE: Volume tier + Asset quality
    features['campaign_quality_score'] = (
        features['campaign_volume_score'] * 0.5 +
        features['asset_type_score'] * 0.5
    ) * 100
    
    # COMBINED SCORE: Weighted composite (preliminary, to be tuned per campaign mode)
    # These weights are for default mode - will be overridden by campaign-specific weights
    features['combined_score'] = (
        features['fit_score'] * 0.6 +  # Fit is primary
        features['intent_score'] * 0.3 +  # Intent is secondary
        features['campaign_quality_score'] * 0.1  # Campaign context
    )
    
    print(f"✅ Engineered {len(features.columns)} campaign context features")
    
    return features


def engineer_base_features(df_csv):
    """Keep original base engagement features for backward compatibility"""
    print("\n🔧 Engineering Base Features...")
    
    features = pd.DataFrame()
    
    # Original engagement metrics
    is_executive = (df_csv['Job Title'].str.contains(
        'Vice President|VP|President|CEO|CTO|CIO|CFO|Chief|Director|SVP|EVP',
        case=False, na=False
    )).astype(int)
    features['is_executive'] = is_executive
    
    # Company size (1-8 scale, original)
    def map_size(size_str):
        if pd.isna(size_str):
            return 4
        size_lower = str(size_str).lower()
        if 'xxlarge' in size_lower:
            return 8
        elif 'xlarge' in size_lower:
            return 7
        elif 'large' in size_lower:
            return 6
        elif 'medium' in size_lower:
            return 4
        elif 'small' in size_lower:
            return 2
        return 4
    
    features['company_size_score'] = df_csv['Company Size'].apply(map_size)
    
    # Email engagement
    e1_open = (df_csv['Email 1 - Opened'] == 'Yes').astype(int)
    e1_click = (df_csv['Email 1 - Clicked'] == 'Yes').astype(int)
    e2_open = (df_csv['Email 2 - Open'] == 'Yes').astype(int)
    e2_click = (df_csv['Email 2 - Clicked'] == 'Yes').astype(int)
    
    features['has_engagement'] = ((e1_open | e1_click | e2_open | e2_click)).astype(int)
    features['email1_engagement'] = (e1_open + e1_click).clip(0, 2)
    features['email2_engagement'] = (e2_open + e2_click).clip(0, 2)
    features['total_engagement_score'] = (e1_open + e1_click + e2_open + e2_click)
    
    # Unsubscribed flag
    features['unsubscribed'] = (
        (df_csv['Email 1 - Unsubscribe'] == 'Yes') |
        (df_csv['Email 2 - Unsubscribe'] == 'Yes')
    ).astype(int)
    
    print(f"✅ Engineered {len(features.columns)} base features")
    
    return features


def combine_features(campaign_features, base_features):
    """Combine campaign context and base features"""
    combined = pd.concat([campaign_features, base_features], axis=1)
    
    # Remove duplicates (keep campaign versions which are more detailed)
    if 'company_size_score' in combined.columns and combined['company_size_score'].duplicated().any():
        # Keep the campaign version
        combined = combined.loc[:, ~combined.columns.duplicated(keep='first')]
    
    return combined


def generate_narratives(df_base, features):
    """Generate lead narratives incorporating campaign context"""
    print("\n📝 Generating Lead Narratives with Campaign Context...")
    
    narratives = []
    
    for idx, row in df_base.iterrows():
        feat = features.iloc[idx]
        
        # Role seniority
        role = "C-level/Executive" if feat['is_executive'] else "Individual Contributor"
        
        # Company size
        size_map = {8: "Fortune 500", 7: "Enterprise", 6: "Large", 5: "Mid-Market", 4: "Mid-Market", 3: "SMB", 2: "Small", 1: "Startup"}
        company_size = size_map.get(feat['company_size_score'], "Unknown")
        
        # Campaign asset type
        asset_type = feat.get('asset_type', 'Unknown').replace('_', ' ')
        
        # Audience type
        audience = feat.get('audience_type', 'Unknown')
        
        # Engagement depth
        if feat['total_engagements'] >= 3:
            engagement_desc = "Very High Engagement"
        elif feat['total_engagements'] == 2:
            engagement_desc = "Good Engagement"
        elif feat['total_engagements'] == 1:
            engagement_desc = "Some Engagement"
        else:
            engagement_desc = "No Engagement"
        
        # Campaign volume context
        volume = feat.get('campaign_volume_tier', 'Unknown')
        
        narrative = (
            f"{role} at {company_size} company. "
            f"Function: {audience}. "
            f"Engaged with {asset_type} campaign. "
            f"{engagement_desc}. "
            f"Campaign reach: {volume}. "
        )
        
        if feat['unsubscribed']:
            narrative += "⚠️ Unsubscribed from communications. "
        
        narratives.append(narrative)
    
    return pd.Series(narratives)


def create_training_dataset(features_df, df_csv):
    """Create final training dataset with targets"""
    print("\n🎯 Creating Training Dataset...")
    
    # Target: Lead Score from original data
    targets = df_csv['Lead Score'].copy()
    
    # Remove rows with missing targets or invalid scores
    valid_idx = targets.notna() & (targets >= 0)
    
    X = features_df[valid_idx].copy()
    y = targets[valid_idx].copy()
    
    # Ensure numeric types
    for col in X.columns:
        X[col] = pd.to_numeric(X[col], errors='coerce')
    X = X.fillna(0)
    
    print(f"✅ Training samples: {len(X)}")
    print(f"✅ Score range: {y.min():.1f} - {y.max():.1f}")
    print(f"✅ Average score: {y.mean():.1f}")
    
    return X, y


def save_dataset(X, y, features_df, feature_names, narratives):
    """Save processed data to disk"""
    print("\n💾 Saving processed data...")
    
    Path("data_processed").mkdir(exist_ok=True)
    
    # Save feature matrix
    X.to_csv("data_processed/features_enhanced.csv", index=False)
    print("  ✓ features_enhanced.csv")
    
    # Save targets
    y.to_csv("data_processed/targets.csv", index=False, header=['lead_score'])
    print("  ✓ targets.csv")
    
    # Save feature metadata
    feature_meta = {
        'features': feature_names,
        'campaign_features': [
            'asset_type_score', 'campaign_volume_score', 'engagement_sequence_score',
            'audience_type_score', 'fit_score', 'intent_score', 'campaign_quality_score',
            'combined_score'
        ],
        'base_features': [
            'is_executive', 'company_size_score', 'email1_engagement', 'email2_engagement',
            'total_engagement_score', 'has_engagement', 'unsubscribed'
        ],
        'engagement_features': [
            'email1_opened', 'email1_clicked', 'email2_opened', 'email2_clicked',
            'total_engagements'
        ],
        'count': len(X),
        'timestamp': datetime.now().isoformat()
    }
    
    with open("data_processed/feature_metadata_enhanced.json", "w") as f:
        json.dump(feature_meta, f, indent=2)
    print("  ✓ feature_metadata_enhanced.json")
    
    # Save sample narratives
    sample_narratives = narratives.iloc[::max(1, len(narratives)//10)].tolist()[:10]
    with open("data_processed/sample_narratives_enhanced.json", "w") as f:
        json.dump(sample_narratives, f, indent=2)
    print("  ✓ sample_narratives_enhanced.json")
    
    print("\n✅ All data saved to data_processed/")


def main():
    print("\n" + "="*80)
    print("PHASE 1 ENHANCED: DATA PREPARATION WITH CAMPAIGN CONTEXT")
    print("="*80)
    
    # Load data
    df_csv, df_excel = load_data()
    
    # Engineer features
    campaign_features = engineer_campaign_context_features(df_csv)
    base_features = engineer_base_features(df_csv)
    
    # Combine
    all_features = combine_features(campaign_features, base_features)
    
    # Generate narratives
    narratives = generate_narratives(df_csv, all_features)
    
    # Create training dataset
    X, y = create_training_dataset(all_features, df_csv)
    
    # Save
    save_dataset(X, y, all_features, all_features.columns.tolist(), narratives)
    
    print("\n" + "="*80)
    print("✅ PHASE 1 COMPLETE: Campaign-aware dataset ready for model training")
    print("="*80)
    print(f"\nFeature Summary:")
    print(f"  Campaign Context: Asset Type, Volume Tier, Engagement Sequence")
    print(f"  Demographic: Company Size, Audience Type, Job Function")
    print(f"  Behavioral: Email Engagement (4 signals), Total Engagements")
    print(f"  Derived Scores: Fit Score, Intent Score, Campaign Quality Score")
    print(f"\nNext: Run scripts/02_train_ml_model.py to train with campaign-aware features")


if __name__ == "__main__":
    main()
