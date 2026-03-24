#!/usr/bin/env python3
"""
Phase 2 Step 3: Retrain All Models with Conversion Data
Compares performance before/after adding historical conversions
"""

import pandas as pd
import numpy as np
import joblib
import json
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor, ExtraTreesRegressor, BaggingRegressor
from sklearn.svm import SVR
from sklearn.neural_network import MLPRegressor
import xgboost as xgb
import warnings
warnings.filterwarnings('ignore')

print("=" * 80)
print("PHASE 2 STEP 3: Retraining All Models with Conversion Data")
print("=" * 80)

# Load new combined training data
print("\n[1/4] Loading datasets...")
X_new = pd.read_csv('data_processed/features_with_conversions.csv')
y_new = pd.read_csv('data_processed/targets_with_conversions.csv', header=None).values.flatten()

# Load original data for comparison
X_old = pd.read_csv('data_processed/features_enhanced.csv')
y_old = pd.read_csv('data_processed/targets.csv').iloc[:, 0].values

print(f"  Old dataset: {X_old.shape[0]} samples")
print(f"  New dataset: {X_new.shape[0]} samples")
print(f"  Increase: +{len(X_new) - len(X_old)} samples (+{(len(X_new)/len(X_old) - 1):.1%})")

# Split data
X_train_new, X_test_new, y_train_new, y_test_new = train_test_split(
    X_new, y_new, test_size=0.2, random_state=42
)
X_train_old, X_test_old, y_train_old, y_test_old = train_test_split(
    X_old, y_old, test_size=0.2, random_state=42
)

print(f"\n  New - Train: {X_train_new.shape[0]}, Test: {X_test_new.shape[0]}")
print(f"  Old - Train: {X_train_old.shape[0]}, Test: {X_test_old.shape[0]}")

# Define models
print("\n[2/4] Initializing models...")
models = {
    'RandomForest': RandomForestRegressor(n_estimators=100, max_depth=10, random_state=42, n_jobs=-1),
    'GradientBoosting': GradientBoostingRegressor(n_estimators=100, learning_rate=0.1, max_depth=5, random_state=42),
    'ExtraTrees': ExtraTreesRegressor(n_estimators=100, max_depth=10, random_state=42, n_jobs=-1),
    'Bagging': BaggingRegressor(n_estimators=50, random_state=42, n_jobs=-1),
    'SVR': SVR(kernel='rbf', C=100, epsilon=0.1),
    'NeuralNetwork': MLPRegressor(hidden_layer_sizes=(128, 64), max_iter=500, random_state=42),
    'XGBoost': xgb.XGBRegressor(n_estimators=200, max_depth=5, learning_rate=0.1, random_state=42, n_jobs=-1),
}

print(f"  Initialized {len(models)} models")

# Train and evaluate models
print("\n[3/4] Training models...")
results = {}

for model_name, model in models.items():
    print(f"\n  Training {model_name}...")
    
    # Train on new dataset
    model.fit(X_train_new, y_train_new)
    
    # Predictions
    y_pred_new = np.clip(model.predict(X_test_new), 0, 100)
    
    # Metrics
    r2_new = r2_score(y_test_new, y_pred_new)
    mae_new = mean_absolute_error(y_test_new, y_pred_new)
    rmse_new = np.sqrt(mean_squared_error(y_test_new, y_pred_new))
    
    # CV score
    cv_scores = cross_val_score(model, X_new, y_new, cv=3, scoring='r2', n_jobs=-1)
    cv_mean = cv_scores.mean()
    
    results[model_name] = {
        'r2_test_new': r2_new,
        'mae_test_new': mae_new,
        'rmse_test_new': rmse_new,
        'cv_r2_mean': cv_mean,
    }
    
    print(f"    ✅ R² = {r2_new:.4f} | MAE = ±{mae_new:.2f} | CV R² = {cv_mean:.4f}")

# Calculate improvements
print("\n[4/4] Calculating improvements...")
print("\n" + "=" * 80)
print("MODEL PERFORMANCE WITH CONVERSION DATA")
print("=" * 80)

# Load old metrics for comparison
with open('models/model_comparison_results.json', 'r') as f:
    old_results = json.load(f)

improvements = {}
for model_name, metrics in results.items():
    old_r2 = old_results['models'].get(model_name, {}).get('r2_test', 0)
    new_r2 = metrics['r2_test_new']
    improvement = new_r2 - old_r2
    improvement_pct = (improvement / old_r2 * 100) if old_r2 > 0 else 0
    
    improvements[model_name] = {
        'old_r2': old_r2,
        'new_r2': new_r2,
        'improvement': improvement,
        'improvement_pct': improvement_pct,
    }
    
    symbol = "📈" if improvement > 0 else "📉"
    print(f"\n{model_name:20s}")
    print(f"  Old R²: {old_r2:.4f} → New R²: {new_r2:.4f}")
    print(f"  Improvement: {symbol} {improvement:+.4f} ({improvement_pct:+.1f}%)")
    print(f"  CV R² (5-fold): {metrics['cv_r2_mean']:.4f}")

# Show top performers
print("\n" + "=" * 80)
print("TOP PERFORMERS (After Conversion Data Integration)")
print("=" * 80)

sorted_models = sorted(results.items(), key=lambda x: x[1]['r2_test_new'], reverse=True)
for rank, (model_name, metrics) in enumerate(sorted_models[:3], 1):
    print(f"{rank}. {model_name:20s} R² = {metrics['r2_test_new']:.4f}")

# Save updated model metadata
print("\n" + "=" * 80)
print("Saving Results...")
print("=" * 80)

# Update comparison results
update_results = {
    'models': {}
}

for model_name, metrics in results.items():
    update_results['models'][model_name] = {
        'r2_test': round(metrics['r2_test_new'], 4),
        'mae_test': round(metrics['mae_test_new'], 2),
        'rmse_test': round(metrics['rmse_test_new'], 2),
        'cv_r2_mean': round(metrics['cv_r2_mean'], 4),
        'improvement_note': f"Retrained with {len(X_new)} samples including {(y_new == 1).sum()} conversions"
    }

with open('models/model_comparison_results_phase2.json', 'w') as f:
    json.dump(update_results, f, indent=2)

print(f"✅ Saved Phase 2 results to models/model_comparison_results_phase2.json")

# Save improvements summary
improvements_summary = {
    'total_samples_old': len(X_old),
    'total_samples_new': len(X_new),
    'samples_added': len(X_new) - len(X_old),
    'conversions_in_new_data': int((y_new == 1).sum()),
    'conversion_rate': float(np.mean(y_new == 1)),
    'improvements_by_model': {}
}

for model_name, imp in improvements.items():
    improvements_summary['improvements_by_model'][model_name] = {
        'old_r2': round(imp['old_r2'], 4),
        'new_r2': round(imp['new_r2'], 4),
        'improvement': round(imp['improvement'], 4),
        'improvement_pct': round(imp['improvement_pct'], 2),
    }

with open('data_processed/phase2_improvements.json', 'w') as f:
    json.dump(improvements_summary, f, indent=2)

print(f"✅ Saved improvements summary to data_processed/phase2_improvements.json")

print("\n" + "=" * 80)
print("✅ PHASE 2 STEP 3: COMPLETE")
print("=" * 80)
print(f"\nNext: Update API with new models (Step 4)")
print("=" * 80)
