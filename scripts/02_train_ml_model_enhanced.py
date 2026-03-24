"""
PHASE 2 ENHANCED: CAMPAIGN-AWARE MODEL TRAINING
Trains GradientBoosting model using campaign context features
Separately tracks Fit Score importance and Intent Score importance
Provides campaign-mode specific scoring recommendations
"""

import pandas as pd
import numpy as np
import pickle
import json
from pathlib import Path
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import r2_score, mean_absolute_error, mean_squared_error
import warnings
warnings.filterwarnings('ignore')


def load_enhanced_data():
    """Load campaign-aware features and targets"""
    print("📂 Loading enhanced dataset...")
    
    X = pd.read_csv("data_processed/features_enhanced.csv")
    y = pd.read_csv("data_processed/targets.csv")['lead_score']
    
    print(f"✅ Features shape: {X.shape}")
    print(f"✅ Target shape: {y.shape}")
    
    return X, y


def train_campaign_aware_model(X, y):
    """Train model with campaign context awareness"""
    print("\n🎓 Training Campaign-Aware Gradient Boosting Model...")
    
    # Split data
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )
    
    # Train model with optimized hyperparameters for campaign context
    # More trees + better depth to capture campaign interactions
    model = GradientBoostingRegressor(
        n_estimators=150,  # More trees (was 100)
        max_depth=6,       # Slightly deeper (was 5) for interaction capture
        learning_rate=0.1,
        min_samples_split=5,
        min_samples_leaf=2,
        random_state=42,
        subsample=0.8,
        loss='huber'  # More robust to outliers
    )
    
    model.fit(X_train, y_train)
    
    # Evaluate
    y_pred_train = model.predict(X_train)
    y_pred_test = model.predict(X_test)
    
    r2_train = r2_score(y_train, y_pred_train)
    r2_test = r2_score(y_test, y_pred_test)
    mae_test = mean_absolute_error(y_test, y_pred_test)
    rmse_test = np.sqrt(mean_squared_error(y_test, y_pred_test))
    
    # Cross-validation
    cv_scores = cross_val_score(model, X, y, cv=5, scoring='r2')
    
    print(f"\n📊 Model Performance:")
    print(f"  Train R²: {r2_train:.4f}")
    print(f"  Test R²:  {r2_test:.4f} {'✅ GOOD' if r2_test > 0.5 else '⚠️  CHECK'}")
    print(f"  CV R²:    {cv_scores.mean():.4f} (±{cv_scores.std():.4f})")
    print(f"  MAE:      ±{mae_test:.2f} points")
    print(f"  RMSE:     {rmse_test:.2f} points")
    
    return model, X_train, X_test, y_train, y_test, {
        'r2_train': r2_train,
        'r2_test': r2_test,
        'mae_test': mae_test,
        'rmse_test': rmse_test,
        'cv_mean': cv_scores.mean(),
        'cv_std': cv_scores.std()
    }


def analyze_feature_importance(model, feature_names):
    """Analyze campaign vs engagement feature importance"""
    print("\n🔍 Feature Importance Analysis...")
    
    importances = model.feature_importances_
    feature_importance_dict = dict(zip(feature_names, importances))
    
    # Sort by importance
    sorted_features = sorted(feature_importance_dict.items(), key=lambda x: x[1], reverse=True)
    
    # Categorize features
    campaign_features = [
        'asset_type_score', 'campaign_volume_score', 'engagement_sequence_score',
        'audience_type_score', 'fit_score', 'intent_score', 'campaign_quality_score'
    ]
    
    base_features = [
        'is_executive', 'company_size_score', 'email1_engagement', 'email2_engagement',
        'total_engagement_score', 'has_engagement', 'unsubscribed'
    ]
    
    engagement_features = [
        'email1_opened', 'email1_clicked', 'email2_opened',
        'email2_clicked', 'total_engagements'
    ]
    
    print(f"\n📈 Top 15 Features by Importance:")
    print(f"{'Rank':<5} {'Feature':<30} {'Importance':<12} {'Type':<20}")
    print("─" * 70)
    
    for rank, (feature, importance) in enumerate(sorted_features[:15], 1):
        # Categorize
        if feature in campaign_features:
            ftype = "Campaign Context"
        elif feature in base_features:
            ftype = "Base Signal"
        elif feature in engagement_features:
            ftype = "Email Engagement"
        else:
            ftype = "Other"
        
        print(f"{rank:<5} {feature:<30} {importance*100:>6.2f}%  {ftype:<20}")
    
    # Summary by category
    print(f"\n📊 Importance by Category:")
    
    campaign_total = sum(feature_importance_dict.get(f, 0) for f in campaign_features)
    base_total = sum(feature_importance_dict.get(f, 0) for f in base_features)
    engagement_total = sum(feature_importance_dict.get(f, 0) for f in engagement_features)
    
    print(f"  Campaign Context Features: {campaign_total*100:.1f}%")
    print(f"    - Fit Score:            {feature_importance_dict.get('fit_score', 0)*100:>6.2f}%")
    print(f"    - Intent Score:         {feature_importance_dict.get('intent_score', 0)*100:>6.2f}%")
    print(f"    - Campaign Quality:     {feature_importance_dict.get('campaign_quality_score', 0)*100:>6.2f}%")
    print(f"    - Asset Type:           {feature_importance_dict.get('asset_type_score', 0)*100:>6.2f}%")
    
    print(f"  Base Signals:              {base_total*100:.1f}%")
    print(f"    - Is Executive:         {feature_importance_dict.get('is_executive', 0)*100:>6.2f}%")
    print(f"    - Company Size:         {feature_importance_dict.get('company_size_score', 0)*100:>6.2f}%")
    
    print(f"  Email Engagement:          {engagement_total*100:.1f}%")
    print(f"    - Total Engagements:    {feature_importance_dict.get('total_engagements', 0)*100:>6.2f}%")
    
    return dict(sorted_features)


def generate_campaign_scoring_weights(feature_importance_dict):
    """Recommend campaign-mode specific scoring weights"""
    print("\n⚙️  Campaign Mode Scoring Weights (Recommendations)...")
    
    # Extract key scores
    fit_score_importance = feature_importance_dict.get('fit_score', 0)
    intent_score_importance = feature_importance_dict.get('intent_score', 0)
    campaign_quality_importance = feature_importance_dict.get('campaign_quality_score', 0)
    
    total_strategic = fit_score_importance + intent_score_importance + campaign_quality_importance
    
    # Recommend weights for different campaign modes
    modes = {
        'default': {
            'description': 'Balanced (60% Fit + 30% Intent + 10% Campaign)',
            'fit_weight': 0.60,
            'intent_weight': 0.30,
            'campaign_quality_weight': 0.10
        },
        'prospecting': {
            'description': 'Fit-focused (70% Fit + 20% Intent + 10% Campaign)',
            'fit_weight': 0.70,
            'intent_weight': 0.20,
            'campaign_quality_weight': 0.10
        },
        'engagement': {
            'description': 'Intent-focused (40% Fit + 50% Intent + 10% Campaign)',
            'fit_weight': 0.40,
            'intent_weight': 0.50,
            'campaign_quality_weight': 0.10
        },
        'nurture': {
            'description': 'Campaign-driven (30% Fit + 30% Intent + 40% Campaign)',
            'fit_weight': 0.30,
            'intent_weight': 0.30,
            'campaign_quality_weight': 0.40
        }
    }
    
    print("\nRecommended Weights by Campaign Mode:\n")
    for mode, config in modes.items():
        print(f"  Mode: {mode.upper()}")
        print(f"    {config['description']}")
        print(f"    fit_weight: {config['fit_weight']}")
        print(f"    intent_weight: {config['intent_weight']}")
        print(f"    campaign_quality_weight: {config['campaign_quality_weight']}")
        print()
    
    return modes


def save_enhanced_model(model, feature_importance_dict, modes, metrics, feature_names):
    """Save model with campaign-aware metadata"""
    print("\n💾 Saving Enhanced Model...")
    
    Path("models").mkdir(exist_ok=True)
    
    # Save model
    with open("models/lead_scorer_campaign_aware.pkl", "wb") as f:
        pickle.dump(model, f)
    print("  ✓ lead_scorer_campaign_aware.pkl")
    
    # Save comprehensive metadata
    metadata = {
        'model_type': 'GradientBoostingRegressor (Campaign-Aware)',
        'parameters': {
            'n_estimators': 150,
            'max_depth': 6,
            'learning_rate': 0.1,
            'min_samples_split': 5,
            'min_samples_leaf': 2,
            'subsample': 0.8,
            'loss': 'huber'
        },
        'performance': metrics,
        'features': feature_names,
        'feature_count': len(feature_names),
        'feature_importance': feature_importance_dict,
        'campaign_scoring_modes': modes,
        'created_at': pd.Timestamp.now().isoformat(),
        'version': '2.0_campaign_aware'
    }
    
    with open("models/model_metadata_campaign_aware.json", "w") as f:
        json.dump(metadata, f, indent=2)
    print("  ✓ model_metadata_campaign_aware.json")
    
    # Save feature importance separately
    importance_compact = {
        k: float(v) for k, v in sorted(
            feature_importance_dict.items(),
            key=lambda x: x[1],
            reverse=True
        )
    }
    
    with open("models/feature_importance_enhanced.json", "w") as f:
        json.dump(importance_compact, f, indent=2)
    print("  ✓ feature_importance_enhanced.json")


def test_campaign_scenarios(model, X_test):
    """Test model on different campaign scenarios"""
    print("\n🧪 Testing Campaign Scenarios...")
    
    # Get column indices
    feature_names = X_test.columns.tolist()
    
    # Test scenarios
    scenarios = {
        'High-Fit, High-Intent (Ideal)': {
            'fit_score': 85,
            'intent_score': 75,
            'campaign_quality_score': 80,
            'is_executive': 1,
            'company_size_score': 8,
            'total_engagements': 4
        },
        'High-Fit, Low-Intent (Prospecting)': {
            'fit_score': 85,
            'intent_score': 30,
            'campaign_quality_score': 70,
            'is_executive': 1,
            'company_size_score': 7,
            'total_engagements': 0
        },
        'Low-Fit, High-Intent (Wild Card)': {
            'fit_score': 40,
            'intent_score': 80,
            'campaign_quality_score': 75,
            'is_executive': 0,
            'company_size_score': 2,
            'total_engagements': 4
        }
    }
    
    print("\nScenario Predictions:")
    for scenario_name, attrs in scenarios.items():
        # Create feature vector
        test_vector = X_test.iloc[0].copy()
        for attr, value in attrs.items():
            if attr in feature_names:
                test_vector[attr] = value
        
        pred = model.predict(test_vector.values.reshape(1, -1))[0]
        print(f"  {scenario_name:<45} → Score: {pred:.1f}")


def main():
    print("\n" + "="*80)
    print("PHASE 2 ENHANCED: CAMPAIGN-AWARE MODEL TRAINING")
    print("="*80)
    
    # Load enhanced data
    X, y = load_enhanced_data()
    
    # Train model
    model, X_train, X_test, y_train, y_test, metrics = train_campaign_aware_model(X, y)
    
    # Analyze importance
    feature_importance_dict = analyze_feature_importance(model, X.columns.tolist())
    
    # Generate campaign mode weights
    modes = generate_campaign_scoring_weights(feature_importance_dict)
    
    # Test scenarios
    test_campaign_scenarios(model, X_test)
    
    # Save everything
    save_enhanced_model(model, feature_importance_dict, modes, metrics, X.columns.tolist())
    
    print("\n" + "="*80)
    print("✅ PHASE 2 COMPLETE: Campaign-aware model trained and saved")
    print("="*80)
    print(f"\nModel ready for:")
    print(f"  1. API integration with /score/predict endpoint")
    print(f"  2. Campaign-mode specific scoring (prospecting, engagement, nurture)")
    print(f"  3. A/B testing different weights per campaign type")
    print(f"\nFiles saved:")
    print(f"  - models/lead_scorer_campaign_aware.pkl")
    print(f"  - models/model_metadata_campaign_aware.json")
    print(f"  - models/feature_importance_enhanced.json")


if __name__ == "__main__":
    main()
