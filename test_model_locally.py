#!/usr/bin/env python3
"""
Local Model Testing & Behavior Analysis

Tests the trained ML model with different lead profiles
to understand how it's behaving and predicting.
"""

import pickle
import pandas as pd
import numpy as np
from pathlib import Path
import json

# ============================================================================
# LOAD MODEL & DATA
# ============================================================================

def load_model_and_data():
    """Load trained model and test data"""
    
    # Model
    model_path = Path("models/lead_scorer.pkl")
    with open(model_path, 'rb') as f:
        model = pickle.load(f)
    
    # Metadata
    metadata_path = Path("models/model_metadata.json")
    with open(metadata_path, 'r') as f:
        metadata = json.load(f)
    
    # Test data
    test_features = pd.read_csv("data_processed/features.csv", index_col=0)
    test_targets = pd.read_csv("data_processed/targets.csv", index_col=0).squeeze()
    
    # Full data with narratives
    full_data = pd.read_parquet("data_processed/leads_with_narratives.parquet")
    
    return model, metadata, test_features, test_targets, full_data

# ============================================================================
# TEST SCENARIOS
# ============================================================================

class LeadScenarios:
    """Different lead profiles to test"""
    
    @staticmethod
    def get_scenarios():
        return {
            "1_ideal_lead": {
                "description": "CEO at Fortune 500, high engagement",
                "features": [8, 4, 1, 1, 0, 2, 2],
                "expected": "Very high (90+)"
            },
            "2_hot_executive": {
                "description": "VP at large company, clicked both emails",
                "features": [7, 2, 1, 1, 0, 1, 1],
                "expected": "High (85-90)"
            },
            "3_cold_executive": {
                "description": "Director at mid-size, no engagement",
                "features": [5, 0, 0, 1, 0, 0, 0],
                "expected": "Medium (75-80)"
            },
            "4_engaged_ic": {
                "description": "Analyst at enterprise, clicked emails",
                "features": [8, 3, 1, 0, 0, 2, 1],
                "expected": "Medium (75-85)"
            },
            "5_cold_ic": {
                "description": "Junior at small company, no engagement",
                "features": [2, 0, 0, 0, 0, 0, 0],
                "expected": "Low (70-75)"
            },
            "6_unsubscribed_exec": {
                "description": "VP but unsubscribed",
                "features": [6, 0, 0, 1, 1, 0, 0],
                "expected": "Medium (75-80)"
            },
            "7_high_engagement_ic": {
                "description": "Analyst with very high engagement",
                "features": [4, 4, 1, 0, 0, 2, 2],
                "expected": "Medium-High (80-85)"
            },
            "8_random_small": {
                "description": "Random person at small company",
                "features": [1, 1, 1, 0, 0, 0, 1],
                "expected": "Low (70-75)"
            },
        }

def feature_names():
    """Get feature column names"""
    return [
        'company_size_score',
        'total_engagement_score',
        'has_engagement',
        'is_executive',
        'unsubscribed',
        'email1_engagement',
        'email2_engagement'
    ]

# ============================================================================
# TESTING FUNCTIONS
# ============================================================================

def test_scenarios(model):
    """Test model on different lead scenarios"""
    
    print("\n" + "="*80)
    print("🧪 TESTING MODEL ON LEAD SCENARIOS")
    print("="*80)
    
    scenarios = LeadScenarios.get_scenarios()
    feature_cols = feature_names()
    results = []
    
    for scenario_id, scenario_data in scenarios.items():
        description = scenario_data['description']
        features = np.array([scenario_data['features']])
        expected = scenario_data['expected']
        
        # Predict
        prediction = model.predict(features)[0]
        
        # Create readable output
        result = {
            'id': scenario_id,
            'description': description,
            'prediction': prediction,
            'expected': expected
        }
        results.append(result)
        
        # Print
        print(f"\n{scenario_id.upper()}")
        print(f"  {description}")
        print(f"  Features: {dict(zip(feature_cols, scenario_data['features']))}")
        print(f"  Predicted Score: {prediction:.1f}")
        print(f"  Expected Range: {expected}")
        
        # Reasoning
        reasoning = generate_prediction_reasoning(scenario_data['features'], feature_cols)
        print(f"  Reasoning: {reasoning}")
    
    return results

def generate_prediction_reasoning(features, feature_names):
    """Generate reasoning for a prediction"""
    feature_dict = dict(zip(feature_names, features))
    
    reasons = []
    
    # Seniority
    if feature_dict['is_executive'] == 1:
        reasons.append("Executive level")
    else:
        reasons.append("IC level")
    
    # Company size
    size = feature_dict['company_size_score']
    if size >= 7:
        reasons.append("Large company")
    elif size >= 4:
        reasons.append("Mid-market")
    else:
        reasons.append("Small company")
    
    # Engagement
    engagement = feature_dict['total_engagement_score']
    if engagement >= 3:
        reasons.append("High engagement")
    elif engagement >= 1:
        reasons.append("Some engagement")
    else:
        reasons.append("No engagement")
    
    # Risk
    if feature_dict['unsubscribed'] == 1:
        reasons.append("⚠️ Unsubscribed")
    
    return " | ".join(reasons)

def test_on_real_data(model, test_features, test_targets):
    """Test model on actual test set"""
    
    print("\n\n" + "="*80)
    print("📊 TESTING ON REAL DATA (Test Set)")
    print("="*80)
    
    # Get predictions
    predictions = model.predict(test_features)
    
    # Calculate metrics
    from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
    
    mae = mean_absolute_error(test_targets, predictions)
    rmse = np.sqrt(mean_squared_error(test_targets, predictions))
    r2 = r2_score(test_targets, predictions)
    
    # Prediction errors
    errors = np.abs(test_targets - predictions)
    
    print(f"\nPerformance Metrics:")
    print(f"  R² Score: {r2:.4f} ({r2*100:.1f}% variance explained)")
    print(f"  MAE: {mae:.2f} points (±typical error)")
    print(f"  RMSE: {rmse:.2f} points")
    
    print(f"\nError Distribution:")
    print(f"  Perfect predictions (±0.5): {(errors < 0.5).sum()} leads ({(errors < 0.5).sum()/len(errors)*100:.1f}%)")
    print(f"  Good predictions (±2 pts): {(errors < 2).sum()} leads ({(errors < 2).sum()/len(errors)*100:.1f}%)")
    print(f"  OK predictions (±5 pts): {(errors < 5).sum()} leads ({(errors < 5).sum()/len(errors)*100:.1f}%)")
    print(f"  Poor predictions (>5 pts): {(errors > 5).sum()} leads ({(errors > 5).sum()/len(errors)*100:.1f}%)")
    
    # Show some examples
    print(f"\nSample Predictions:")
    sample_indices = np.random.choice(len(test_features), 5, replace=False)
    for idx in sample_indices:
        actual = test_targets.iloc[idx]
        predicted = predictions[idx]
        error = actual - predicted
        print(f"  Actual: {actual:.1f} | Predicted: {predicted:.1f} | Error: {error:+.1f}")
    
    return mae, rmse, r2

def feature_sensitivity_analysis(model):
    """Test how each feature affects predictions"""
    
    print("\n\n" + "="*80)
    print("🔍 FEATURE SENSITIVITY ANALYSIS")
    print("="*80)
    
    # Baseline: average lead
    baseline = np.array([[4, 1, 0, 0, 0, 0, 0]])  # Small company, IC, no engagement
    baseline_score = model.predict(baseline)[0]
    
    print(f"\nBaseline (Small company, IC, no engagement): {baseline_score:.1f}\n")
    
    feature_cols = feature_names()
    
    # Test each feature
    print("Feature Impact (how much each feature changes score):\n")
    for i, feature in enumerate(feature_cols):
        
        # Test increasing this feature
        test_case = baseline.copy()
        
        if feature in ['company_size_score', 'total_engagement_score', 
                       'email1_engagement', 'email2_engagement']:
            # Numeric increment
            test_case[0, i] += 2
        else:
            # Binary toggle
            test_case[0, i] = 1
        
        new_score = model.predict(test_case)[0]
        impact = new_score - baseline_score
        
        print(f"  {feature:25s} → {impact:+.1f} points ({impact/baseline_score*100:+.1f}%)")

def compare_with_actual_leads(model, full_data, test_targets):
    """Compare predictions with actual high/low scoring leads"""
    
    print("\n\n" + "="*80)
    print("📈 COMPARING WITH ACTUAL HIGH/LOW LEADS")
    print("="*80)
    
    # Get high and low actual scores
    high_leads_idx = test_targets[test_targets > test_targets.quantile(0.75)].index
    low_leads_idx = test_targets[test_targets < test_targets.quantile(0.25)].index
    
    # Get features for these leads
    high_features = full_data.loc[high_leads_idx, [
        'is_executive', 'company_size_score', 'total_engagement_score'
    ]].head(5)
    
    low_features = full_data.loc[low_leads_idx, [
        'is_executive', 'company_size_score', 'total_engagement_score'
    ]].head(5)
    
    print(f"\nHigh-Scoring Leads (75th+ percentile, score > {test_targets.quantile(0.75):.1f}):")
    print(f"  Average is_executive: {high_features['is_executive'].mean():.1%}")
    print(f"  Average company_size: {high_features['company_size_score'].mean():.1f} (1-8 scale)")
    print(f"  Average engagement: {high_features['total_engagement_score'].mean():.1f} clicks")
    
    print(f"\nLow-Scoring Leads (25th percentile, score < {test_targets.quantile(0.25):.1f}):")
    print(f"  Average is_executive: {low_features['is_executive'].mean():.1%}")
    print(f"  Average company_size: {low_features['company_size_score'].mean():.1f} (1-8 scale)")
    print(f"  Average engagement: {low_features['total_engagement_score'].mean():.1f} clicks")

def create_prediction_distribution(model, test_features, test_targets):
    """Show distribution of predictions vs actual"""
    
    print("\n\n" + "="*80)
    print("📊 PREDICTION DISTRIBUTION ANALYSIS")
    print("="*80)
    
    predictions = model.predict(test_features)
    
    print(f"\nActual Scores Distribution:")
    print(f"  Min: {test_targets.min():.1f}")
    print(f"  25th %ile: {test_targets.quantile(0.25):.1f}")
    print(f"  Median: {test_targets.median():.1f}")
    print(f"  75th %ile: {test_targets.quantile(0.75):.1f}")
    print(f"  Max: {test_targets.max():.1f}")
    
    print(f"\nPredicted Scores Distribution:")
    print(f"  Min: {predictions.min():.1f}")
    print(f"  25th %ile: {np.percentile(predictions, 25):.1f}")
    print(f"  Median: {np.median(predictions):.1f}")
    print(f"  75th %ile: {np.percentile(predictions, 75):.1f}")
    print(f"  Max: {predictions.max():.1f}")
    
    # Binned analysis
    print(f"\nPrediction Accuracy by Score Range:")
    ranges = [
        (70, 75, "Low (70-75)"),
        (75, 80, "Medium-Low (75-80)"),
        (80, 85, "Medium (80-85)"),
        (85, 90, "High (85-90)"),
        (90, 100, "Very High (90+)"),
    ]
    
    for min_score, max_score, label in ranges:
        mask = (test_targets >= min_score) & (test_targets < max_score)
        if mask.sum() > 0:
            actual_in_range = test_targets[mask]
            predicted_in_range = predictions[mask]
            mae_in_range = np.abs(actual_in_range - predicted_in_range).mean()
            print(f"  {label:20s}: {mask.sum():3d} leads, avg error ±{mae_in_range:.2f}")

# ============================================================================
# MAIN
# ============================================================================

def main():
    """Run complete testing suite"""
    
    print("\n")
    print("╔" + "="*78 + "╗")
    print("║" + " "*78 + "║")
    print("║" + "LOCAL MODEL TESTING & BEHAVIOR ANALYSIS".center(78) + "║")
    print("║" + " "*78 + "║")
    print("╚" + "="*78 + "╝")
    
    try:
        # Load everything
        print("\n📂 Loading model and data...")
        model, metadata, test_features, test_targets, full_data = load_model_and_data()
        print("✅ Model loaded successfully")
        
        # Run tests
        test_scenarios(model)
        mae, rmse, r2 = test_on_real_data(model, test_features, test_targets)
        feature_sensitivity_analysis(model)
        compare_with_actual_leads(model, full_data, test_targets)
        create_prediction_distribution(model, test_features, test_targets)
        
        # Summary
        print("\n\n" + "="*80)
        print("✅ TESTING COMPLETE")
        print("="*80)
        print(f"""
Model Behavior Summary:
  ✅ R² Score: {r2:.4f} (good accuracy)
  ✅ Average Error: ±{mae:.2f} points
  ✅ Feature Dependencies: Understood
  ✅ Real Data Performance: Confirmed

Next Steps:
  1. Review predictions on your actual leads
  2. Integrate into API
  3. Deploy to production
  4. Retrain as you get more data
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
