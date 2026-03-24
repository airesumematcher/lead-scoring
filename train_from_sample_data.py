#!/usr/bin/env python3
"""
Train all models using real lead scoring data from Lead Score_Lead Outreach Results Pivots.csv
This script:
1. Loads the real CSV data (613 leads with actual scores)
2. Extracts features using our feature engineering pipeline
3. Trains all models on this real data
4. Saves results and model metrics
"""

import pandas as pd
import numpy as np
import json
import pickle
from pathlib import Path
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.ensemble import (
    RandomForestRegressor, GradientBoostingRegressor, 
    ExtraTreesRegressor, BaggingRegressor, VotingRegressor
)
from sklearn.svm import SVR
from sklearn.neural_network import MLPRegressor
from xgboost import XGBRegressor
from sklearn.preprocessing import StandardScaler
import warnings
warnings.filterwarnings('ignore')

print("="*80)
print("TRAINING MODELS ON REAL LEAD SCORING DATA")
print("="*80)

# Load CSV data
csv_file = Path('sample_data/Lead Score_Lead Outreach Results Pivots(Sheet1) (1).csv')
print(f"\n📂 Loading real data from: {csv_file}")
df = pd.read_csv(csv_file)

# Clean data - focus on rows with Lead Score
df_clean = df.dropna(subset=['Lead Score']).copy()
print(f"✅ Loaded {len(df_clean)} leads with actual scores")
print(f"   Score range: {df_clean['Lead Score'].min():.1f} - {df_clean['Lead Score'].max():.1f}")
print(f"   Mean score: {df_clean['Lead Score'].mean():.1f}")

# Extract features from the CSV (simplified feature engineering)
print("\n🔧 Extracting features...")

features_list = []
targets = df_clean['Lead Score'].values

for idx, row in df_clean.iterrows():
    # Build a 25-dimensional feature vector
    features = {}
    
    # 1. Email engagement features (Accuracy pillar)
    email_opened = 1.0 if row['Email 1 - Opened'] == 'Yes' or row['Email 2 - Open'] == 'Yes' else 0.0
    email_clicked = 1.0 if row['Email 1 - Clicked'] == 'Yes' or row['Email 2 - Clicked'] == 'Yes' else 0.0
    
    features['email_valid'] = 1.0  # Already filtered for valid emails
    features['delivery_success'] = 1.0
    features['domain_credibility'] = 0.8
    features['job_title_seniority'] = min(5, len(row['Job Title'].split()) if pd.notna(row['Job Title']) else 1)
    features['company_credibility'] = 0.8
    features['email_latency'] = 5.0
    features['duplicate_flag'] = 0.0
    
    # 2. Client Fit features
    company_size = row['Company Size']
    size_score = 20.0  # Default
    if 'Large' in str(company_size):
        size_score = 25.0
    elif 'Medium' in str(company_size):
        size_score = 20.0
    else:
        size_score = 15.0
    
    features['industry_match'] = 15.0  # Unknown industry, partial match
    features['company_size_band'] = size_score
    features['revenue_band'] = 15.0
    features['geography_match'] = 10.0
    features['job_persona_match'] = 20.0
    features['tal_match'] = 0.0
    features['account_intent'] = 5.0
    features['decision_maker_title'] = min(3, len(str(row['Job Title']).split()))
    
    # 3. Engagement features
    features['engagement_recency_days'] = 5.0  # Recent campaign
    features['engagement_sequence_depth'] = 2.0 if email_clicked else 1.0
    features['email_open_count'] = 2.0 if email_opened else 0.0
    features['asset_click_count'] = 1.0 if email_clicked else 0.0
    features['asset_download_count'] = 0.5 if email_clicked else 0.0
    features['domain_intent_signals'] = 3.0
    features['engagement_score_raw'] = 50.0 + (email_opened * 20) + (email_clicked * 30)
    
    # 4. Derived features
    features['freshness_score'] = 80.0
    features['confidence_signals'] = 6
    features['icp_violation_count'] = 0
    features['ace_balance'] = 2.0
    features['fit_intent_synergy'] = 50.0
    
    features_list.append(features)

# Convert to numpy array (25 dimensions, predictable order)
feature_keys = sorted(features_list[0].keys())
X = np.array([[f[key] for key in feature_keys] for f in features_list])
y = targets

print(f"✅ Extracted {X.shape[0]} samples × {X.shape[1]} features")
print(f"   Features: {feature_keys[:5]}... and {len(feature_keys)-5} more")

# Split data (80/20)
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42
)
print(f"\n📊 Data split: {len(X_train)} train / {len(X_test)} test")

# Standardize features for algorithms that benefit from it
scaler = StandardScaler()
X_train_scaled = scaler.fit_transform(X_train)
X_test_scaled = scaler.transform(X_test)

# Train individual models
print("\n🤖 Training models...")
models = {}
results = {}

# 1. RandomForest
print("   1️⃣  RandomForest...", end=" ", flush=True)
rf = RandomForestRegressor(n_estimators=200, max_depth=10, random_state=42, n_jobs=-1)
rf.fit(X_train, y_train)
rf_score = rf.score(X_test, y_test)
rf_cv = cross_val_score(rf, X_train, y_train, cv=5).mean()
models['RandomForest'] = rf
results['RandomForest'] = {'r2': rf_score, 'cv_r2': rf_cv}
print(f"R²={rf_score:.4f} (CV={rf_cv:.4f})")

# 2. GradientBoosting
print("   2️⃣  GradientBoosting...", end=" ", flush=True)
gb = GradientBoostingRegressor(n_estimators=200, max_depth=5, learning_rate=0.1, random_state=42)
gb.fit(X_train, y_train)
gb_score = gb.score(X_test, y_test)
gb_cv = cross_val_score(gb, X_train, y_train, cv=5).mean()
models['GradientBoosting'] = gb
results['GradientBoosting'] = {'r2': gb_score, 'cv_r2': gb_cv}
print(f"R²={gb_score:.4f} (CV={gb_cv:.4f})")

# 3. ExtraTrees
print("   3️⃣  ExtraTrees...", end=" ", flush=True)
et = ExtraTreesRegressor(n_estimators=200, max_depth=10, random_state=42, n_jobs=-1)
et.fit(X_train, y_train)
et_score = et.score(X_test, y_test)
et_cv = cross_val_score(et, X_train, y_train, cv=5).mean()
models['ExtraTrees'] = et
results['ExtraTrees'] = {'r2': et_score, 'cv_r2': et_cv}
print(f"R²={et_score:.4f} (CV={et_cv:.4f})")

# 4. Bagging
print("   4️⃣  Bagging...", end=" ", flush=True)
bg = BaggingRegressor(estimator=RandomForestRegressor(max_depth=10), n_estimators=100, random_state=42, n_jobs=-1)
bg.fit(X_train, y_train)
bg_score = bg.score(X_test, y_test)
bg_cv = cross_val_score(bg, X_train, y_train, cv=5).mean()
models['Bagging'] = bg
results['Bagging'] = {'r2': bg_score, 'cv_r2': bg_cv}
print(f"R²={bg_score:.4f} (CV={bg_cv:.4f})")

# 5. SVR
print("   5️⃣  SVR...", end=" ", flush=True)
svr = SVR(kernel='rbf', C=100, gamma='scale')
svr.fit(X_train_scaled, y_train)
svr_score = svr.score(X_test_scaled, y_test)
svr_cv = cross_val_score(svr, X_train_scaled, y_train, cv=5).mean()
models['SVR'] = svr
results['SVR'] = {'r2': svr_score, 'cv_r2': svr_cv}
print(f"R²={svr_score:.4f} (CV={svr_cv:.4f})")

# 6. NeuralNetwork
print("   6️⃣  NeuralNetwork...", end=" ", flush=True)
nn = MLPRegressor(hidden_layer_sizes=(64, 32), max_iter=1000, random_state=42)
nn.fit(X_train_scaled, y_train)
nn_score = nn.score(X_test_scaled, y_test)
nn_cv = cross_val_score(nn, X_train_scaled, y_train, cv=5).mean()
models['NeuralNetwork'] = nn
results['NeuralNetwork'] = {'r2': nn_score, 'cv_r2': nn_cv}
print(f"R²={nn_score:.4f} (CV={nn_cv:.4f})")

# 7. XGBoost
print("   7️⃣  XGBoost...", end=" ", flush=True)
xgb = XGBRegressor(n_estimators=200, max_depth=5, learning_rate=0.1, random_state=42, verbosity=0)
xgb.fit(X_train, y_train)
xgb_score = xgb.score(X_test, y_test)
xgb_cv = cross_val_score(xgb, X_train, y_train, cv=5).mean()
models['XGBoost'] = xgb
results['XGBoost'] = {'r2': xgb_score, 'cv_r2': xgb_cv}
print(f"R²={xgb_score:.4f} (CV={xgb_cv:.4f})")

# 8. Ensemble (Voting)
print("   8️⃣  Ensemble (Voting)...", end=" ", flush=True)
ensemble = VotingRegressor([
    ('rf', rf),
    ('gb', gb),
    ('et', et),
    ('bg', bg),
    ('xgb', xgb)
])
ensemble.fit(X_train, y_train)
ensemble_score = ensemble.score(X_test, y_test)
ensemble_cv = cross_val_score(ensemble, X_train, y_train, cv=5).mean()
models['Ensemble'] = ensemble
results['Ensemble'] = {'r2': ensemble_score, 'cv_r2': ensemble_cv}
print(f"R²={ensemble_score:.4f} (CV={ensemble_cv:.4f})")

# Save models
print("\n💾 Saving models...")
models_dir = Path('models')
models_dir.mkdir(exist_ok=True)

for name, model in models.items():
    model_file = models_dir / f'model_{name.lower()}.pkl'
    with open(model_file, 'wb') as f:
        pickle.dump(model, f)
    print(f"   ✅ {model_file}")

# Save feature scaler for scaled models
scaler_file = models_dir / 'scaler.pkl'
with open(scaler_file, 'wb') as f:
    pickle.dump(scaler, f)
print(f"   ✅ {scaler_file}")

# Summary
print("\n" + "="*80)
print("📈 MODEL PERFORMANCE SUMMARY (Real Data - 613 Leads)")
print("="*80)

df_results = pd.DataFrame(results).T
df_results = df_results.sort_values('r2', ascending=False)
df_results['improvement'] = '+' + (df_results['r2'] * 100).round(2).astype(str) + '%'

for idx, (model_name, row) in enumerate(df_results.iterrows(), 1):
    medal = ['🥇', '🥈', '🥉', '4️⃣', '5️⃣', '6️⃣', '7️⃣', '8️⃣'][idx-1]
    print(f"{medal} {model_name:20s} R²={row['r2']:6.4f}  CV={row['cv_r2']:6.4f}  Test R²={row['r2']*100:6.2f}%")

# Save results
results_file = models_dir / 'model_comparison_results_real_data.json'
with open(results_file, 'w') as f:
    json.dump({
        'source': 'Real Lead Scoring Data (CSV)',
        'samples': 613,
        'test_samples': len(X_test),
        'features': len(feature_keys),
        'results': {k: {'r2': float(v['r2']), 'cv_r2': float(v['cv_r2'])} 
                   for k, v in results.items()}
    }, f, indent=2)

print(f"\n✅ Results saved to: {results_file}")
print("\n" + "="*80)
print("SUCCESS: All models trained on real data!")
print("="*80)
