#!/usr/bin/env python3
"""
Phase 1: Train XGBoost model for lead scoring
"""

import pandas as pd
import numpy as np
import xgboost as xgb
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.preprocessing import StandardScaler
import joblib
import json
from pathlib import Path

print("=" * 70)
print("PHASE 1: Training XGBoost Model")
print("=" * 70)

# Load data
print("\n[1/4] Loading training data...")
X = pd.read_csv('data_processed/features_enhanced.csv')
y = pd.read_csv('data_processed/targets.csv', header=None).values.flatten()

print(f"  Features: {X.shape[0]} samples × {X.shape[1]} features")
print(f"  Target: {y.shape[0]} samples")
print(f"  Target range: {y.min():.1f} - {y.max():.1f}")

# Split data
print("\n[2/4] Splitting train/test (80/20)...")
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42
)
print(f"  Train: {X_train.shape[0]} samples")
print(f"  Test:  {X_test.shape[0]} samples")

# Train XGBoost
print("\n[3/4] Training XGBoost model...")
model = xgb.XGBRegressor(
    n_estimators=200,
    max_depth=5,
    learning_rate=0.1,
    subsample=0.9,
    colsample_bytree=0.9,
    reg_alpha=0.1,      # L1 regularization
    reg_lambda=1.0,     # L2 regularization
    random_state=42,
    objective='reg:squarederror',
    n_jobs=-1
)

model.fit(
    X_train, y_train,
    eval_set=[(X_test, y_test)],
    early_stopping_rounds=20,
    verbose=10
)

# Evaluate
print("\n[4/4] Evaluating...")
y_pred_train = model.predict(X_train)
y_pred_test = model.predict(X_test)

# Clip predictions to 0-100
y_pred_train = np.clip(y_pred_train, 0, 100)
y_pred_test = np.clip(y_pred_test, 0, 100)

# Calculate metrics
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score

train_r2 = r2_score(y_train, y_pred_train)
test_r2 = r2_score(y_test, y_pred_test)
train_mae = mean_absolute_error(y_train, y_pred_train)
test_mae = mean_absolute_error(y_test, y_pred_test)
train_rmse = np.sqrt(mean_squared_error(y_train, y_pred_train))
test_rmse = np.sqrt(mean_squared_error(y_test, y_pred_test))

print("\n" + "=" * 70)
print("RESULTS")
print("=" * 70)
print(f"""
XGBoost Performance:
  Train R²:  {train_r2:.4f}
  Test R²:   {test_r2:.4f}
  
  Train MAE: ±{train_mae:.2f}
  Test MAE:  ±{test_mae:.2f}
  
  Train RMSE: {train_rmse:.2f}
  Test RMSE:  {test_rmse:.2f}
""")

# Cross-validation
print("Cross-validation (5-fold)...")
cv_scores = cross_val_score(
    model, X, y, cv=5, 
    scoring='r2', n_jobs=-1
)
print(f"  CV R² scores: {cv_scores}")
print(f"  Mean CV R²: {cv_scores.mean():.4f} ± {cv_scores.std():.4f}")

# Save model
print("\nSaving model...")
Path('models').mkdir(exist_ok=True)
joblib.dump(model, 'models/model_xgboost.pkl')
print("  ✓ Saved to models/model_xgboost.pkl")

# Save metadata
metadata = {
    'model_type': 'XGBoost',
    'train_r2': float(train_r2),
    'test_r2': float(test_r2),
    'train_mae': float(train_mae),
    'test_mae': float(test_mae),
    'train_rmse': float(train_rmse),
    'test_rmse': float(test_rmse),
    'cv_r2_mean': float(cv_scores.mean()),
    'cv_r2_std': float(cv_scores.std()),
    'n_features': X.shape[1],
    'n_train_samples': X_train.shape[0],
    'n_test_samples': X_test.shape[0],
    'hyperparameters': {
        'n_estimators': 200,
        'max_depth': 5,
        'learning_rate': 0.1,
        'subsample': 0.9,
        'colsample_bytree': 0.9,
        'reg_alpha': 0.1,
        'reg_lambda': 1.0
    }
}

with open('models/metadata_xgboost.json', 'w') as f:
    json.dump(metadata, f, indent=2)
print("  ✓ Saved metadata to models/metadata_xgboost.json")

# Show feature importance
print("\nTop 10 Most Important Features:")
feature_importance = pd.DataFrame({
    'feature': X.columns,
    'importance': model.feature_importances_
}).sort_values('importance', ascending=False)

for idx, row in feature_importance.head(10).iterrows():
    bar = '█' * int(row['importance'] * 50)
    print(f"  {row['feature']:30s} {bar} {row['importance']:.4f}")

# Save feature importance
feature_importance.to_csv('models/xgboost_feature_importance.csv', index=False)
print("\n✓ Feature importance saved to models/xgboost_feature_importance.csv")

print("\n" + "=" * 70)
print("✅ PHASE 1 STEP 1: TRAINING COMPLETE")
print("=" * 70)
print("\nNext: Integrate model into API (Step 2)")
print("=" * 70)
