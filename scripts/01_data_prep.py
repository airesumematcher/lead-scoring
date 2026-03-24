#!/usr/bin/env python3
"""
Phase 1: Data Preparation for LLM Lead Scoring

This script:
1. Loads lead data from sample_data/
2. Cleans engagement metrics
3. Engineers features
4. Creates lead narratives for LLM
5. Saves processed data
"""

import pandas as pd
import numpy as np
from pathlib import Path
import json
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

# ============================================================================
# CONFIG
# ============================================================================

DATA_PATH = "sample_data"
CSV_FILE = "Lead Score_Lead Outreach Results Pivots(Sheet1) (1).csv"
OUTPUT_DIR = Path("data_processed")
OUTPUT_DIR.mkdir(exist_ok=True)

# ============================================================================
# LOAD & CLEAN DATA
# ============================================================================

def load_data():
    """Load CSV file and perform initial validation"""
    print("\n" + "="*80)
    print("📥 LOADING DATA")
    print("="*80)
    
    csv_path = Path(DATA_PATH) / CSV_FILE
    print(f"\n📄 Loading: {csv_path}")
    
    df = pd.read_csv(csv_path)
    print(f"   ✅ Loaded {len(df)} rows × {len(df.columns)} columns")
    
    # Info
    print(f"\n   Data Quality:")
    print(f"   • Lead Score non-null: {df['Lead Score'].notna().sum()} / {len(df)}")
    print(f"   • Score range: {df['Lead Score'].min():.1f} - {df['Lead Score'].max():.1f}")
    print(f"   • Company sizes: {df['Company Size'].nunique()}")
    print(f"   • Unique job functions: {df['Job Function'].nunique()}")
    
    return df

def clean_engagement_metrics(df):
    """Convert Yes/No engagement to binary"""
    print("\n" + "="*80)
    print("🧹 CLEANING ENGAGEMENT METRICS")
    print("="*80)
    
    engagement_cols = [
        'Email 1 - Opened', 'Email 1 - Clicked', 'Email 1 - Unsubscribe',
        'Email 2 - Open', 'Email 2 - Clicked', 'Email 2 - Unsubscribe'
    ]
    
    for col in engagement_cols:
        if col in df.columns:
            df[col] = (df[col] == 'Yes').astype(int)
            print(f"   ✅ {col}: Converted to binary")
    
    return df

def engineer_features(df):
    """Create derived features for modeling"""
    print("\n" + "="*80)
    print("⚙️  ENGINEERING FEATURES")
    print("="*80)
    
    # 1. Company Size Score (ordinal)
    size_mapping = {
        'Micro (1 - 9 Employees)': 1,
        'Small (10 - 49 Employees)': 2,
        'Medium-Small (50 - 199 Employees)': 3,
        'Medium (200 - 499 Employees)': 4,
        'Medium-Large (500 - 999 Employees)': 5,
        'Large (1,000 - 4,999 Employees)': 6,
        'XLarge (5,000 - 10,000 Employees)': 7,
        'XXLarge (10,000+ Employees)': 8,
    }
    df['company_size_score'] = df['Company Size'].map(size_mapping)
    print(f"   ✅ company_size_score: Ordinal encoding (1-8)")
    
    # 2. Email Engagement Metrics
    df['email1_engagement'] = (
        df['Email 1 - Opened'].astype(int) + 
        df['Email 1 - Clicked'].astype(int)
    )
    df['email2_engagement'] = (
        df['Email 2 - Open'].astype(int) + 
        df['Email 2 - Clicked'].astype(int)
    )
    df['total_engagement_score'] = (
        df['email1_engagement'] + df['email2_engagement']
    )
    print(f"   ✅ email1_engagement: Total opens + clicks")
    print(f"   ✅ email2_engagement: Total opens + clicks")
    print(f"   ✅ total_engagement_score: Sum of all engagements")
    
    # 3. Engagement Flag
    df['has_engagement'] = (df['total_engagement_score'] > 0).astype(int)
    print(f"   ✅ has_engagement: Binary flag")
    
    # 4. Unsubscribe Risk
    df['unsubscribed'] = (
        (df['Email 1 - Unsubscribe'].astype(int) + 
         df['Email 2 - Unsubscribe'].astype(int)) > 0
    ).astype(int)
    print(f"   ✅ unsubscribed: Any unsubscribe = high risk")
    
    # 5. Seniority from Job Title
    executive_titles = ['ceo', 'cfo', 'coo', 'cto', 'chief', 'president', 'vp ', 'vice president']
    df['is_executive'] = df['Job Title'].str.lower().apply(
        lambda x: 1 if any(title in str(x).lower() for title in executive_titles) else 0
    )
    print(f"   ✅ is_executive: Detected C-suite/VP titles")
    
    # 6. Job Function Categories (one-hot?)
    print(f"   ✅ job_function: {df['Job Function'].nunique()} categories")
    
    # 7. Target variable
    df['target_score'] = df['Lead Score']  # Keep original for training
    df['target_normalized'] = df['Lead Score'] / 100.0  # Normalize 0-1
    print(f"   ✅ target_score: Lead Score (actual values for training)")
    
    return df

def create_lead_narratives(df):
    """Create natural language descriptions for LLM analysis"""
    print("\n" + "="*80)
    print("📝 CREATING LEAD NARRATIVES")
    print("="*80)
    
    def narrative(row):
        """Generate narrative for a single lead"""
        
        # Role & Seniority
        title = str(row['Job Title']).title()
        is_exec = "✓ Executive/Senior" if row['is_executive'] else "• Individual Contributor"
        
        # Company
        company_size = str(row['Company Size'])
        
        # Function
        function = str(row['Job Function'])
        
        # Engagement
        email1_status = "Opened E1" if row['Email 1 - Opened'] else "Skipped E1"
        email2_status = "Opened E2" if row['Email 2 - Open'] else "Skipped E2"
        clicks = row['total_engagement_score']
        
        # Construct narrative
        narrative_text = f"""
LEAD PROFILE:
Job Title: {title} ({is_exec})
Company Size: {company_size}
Department: {function}
Experience Level: {'Senior Leadership' if row['is_executive'] else 'Professional'}

ENGAGEMENT ACTIVITY:
Email 1: {email1_status}
Email 2: {email2_status}
Total Clicks: {clicks}
Status: {'Unsubscribed' if row['unsubscribed'] else 'Active'}

SIGNAL STRENGTH:
Seniority: {row['company_size_score']}/8
Engagement: {row['total_engagement_score']}/4
Overall Interest: {'High' if row['total_engagement_score'] >= 2 else 'Medium' if row['total_engagement_score'] == 1 else 'Low'}
        """.strip()
        
        return narrative_text
    
    df['narrative'] = df.apply(narrative, axis=1)
    print(f"   ✅ Created narratives for {len(df)} leads")
    print(f"\n   📌 Sample narrative:\n")
    print(df['narrative'].iloc[0])
    
    return df

def prepare_feature_set(df):
    """Prepare clean feature set for modeling"""
    print("\n" + "="*80)
    print("📊 PREPARING FEATURE SET")
    print("="*80)
    
    # Select features for modeling
    feature_cols = [
        'company_size_score',
        'total_engagement_score',
        'has_engagement',
        'is_executive',
        'unsubscribed',
        'email1_engagement',
        'email2_engagement',
    ]
    
    # Create feature matrix (drop rows with missing target)
    df_features = df.dropna(subset=['target_score']).copy()
    
    X = df_features[feature_cols].fillna(0)
    y = df_features['target_score']
    
    print(f"\n   Training set:")
    print(f"   • Samples: {len(X)}")
    print(f"   • Features: {len(feature_cols)}")
    print(f"   • Target range: {y.min():.1f} - {y.max():.1f}")
    print(f"   • Mean target: {y.mean():.2f}")
    
    return X, y, feature_cols, df_features

def save_processed_data(df, X, y, feature_cols):
    """Save all processed data for next phases"""
    print("\n" + "="*80)
    print("💾 SAVING PROCESSED DATA")
    print("="*80)
    
    # 1. Full dataframe with narratives
    parquet_path = OUTPUT_DIR / "leads_with_narratives.parquet"
    df.to_parquet(parquet_path)
    print(f"   ✅ {parquet_path}")
    
    # 2. Features for modeling
    feature_path = OUTPUT_DIR / "features.csv"
    X.to_csv(feature_path)
    print(f"   ✅ {feature_path}")
    
    # 3. Target values
    target_path = OUTPUT_DIR / "targets.csv"
    y.to_csv(target_path)
    print(f"   ✅ {target_path}")
    
    # 4. Feature colnames for model
    feature_names_path = OUTPUT_DIR / "feature_names.json"
    with open(feature_names_path, 'w') as f:
        json.dump(feature_cols, f, indent=2)
    print(f"   ✅ {feature_names_path}")
    
    # 5. Sample narratives for LLM testing
    sample_narratives_path = OUTPUT_DIR / "sample_narratives.json"
    samples = []
    for idx in df.sample(min(10, len(df))).index:
        samples.append({
            'email': df.loc[idx, 'Lead Email'],
            'narrative': df.loc[idx, 'narrative'],
            'actual_score': float(df.loc[idx, 'target_score']) if pd.notna(df.loc[idx, 'target_score']) else None
        })
    with open(sample_narratives_path, 'w') as f:
        json.dump(samples, f, indent=2)
    print(f"   ✅ {sample_narratives_path}")
    
    print(f"\n   📁 All files saved to: {OUTPUT_DIR.absolute()}")
    
    return {
        'narratives': parquet_path,
        'features': feature_path,
        'targets': target_path,
        'feature_names': feature_names_path,
        'samples': sample_narratives_path
    }

# ============================================================================
# MAIN
# ============================================================================

def main():
    """Run complete Phase 1 pipeline"""
    
    print("\n")
    print("╔" + "="*78 + "╗")
    print("║" + " "*78 + "║")
    print("║" + "PHASE 1: DATA PREPARATION FOR LLM LEAD SCORING".center(78) + "║")
    print("║" + " "*78 + "║")
    print("╚" + "="*78 + "╝")
    
    try:
        # Step 1: Load
        df = load_data()
        
        # Step 2: Clean
        df = clean_engagement_metrics(df)
        
        # Step 3: Engineer
        df = engineer_features(df)
        
        # Step 4: Create narratives
        df = create_lead_narratives(df)
        
        # Step 5: Prepare features
        X, y, feature_cols, df_features = prepare_feature_set(df)
        
        # Step 6: Save
        output_files = save_processed_data(df, X, y, feature_cols)
        
        # Summary
        print("\n" + "="*80)
        print("✅ PHASE 1 COMPLETE")
        print("="*80)
        print(f"""
Phase 1 successfully completed!

Outputs:
  📊 Training data: {len(df_features)} leads with scores
  📝 Narratives: {len(df)} leads with LLM narratives
  📂 Saved to: {OUTPUT_DIR.absolute()}

Next Steps:
  1. Review sample narratives: {output_files['samples']}
  2. Run Phase 2: LLM feature extraction
     python scripts/02_llm_feature_extraction.py

Questions to validate:
  ✓ Do narratives capture lead quality signals?
  ✓ Are engagement metrics correctly encoded?
  ✓ Does executive flag match your expectations?
        """)
        
        return True
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
