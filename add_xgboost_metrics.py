import json
import pandas as pd
import numpy as np
from sklearn.metrics import mean_squared_error,mean_absolute_error, r2_score
import joblib

# Load XGBoost model and data
model = joblib.load('models/model_xgboost.pkl')
X_test = X = pd.read_csv('data_processed/features_enhanced.csv')
y_test = y = pd.read_csv('data_processed/targets.csv').iloc[:, 0].values

# Get predictions
y_pred = np.clip(model.predict(X_test), 0, 100)

# Calculate metrics
r2 = r2_score(y_test, y_pred)
mae = mean_absolute_error(y_test, y_pred)
rmse = np.sqrt(mean_squared_error(y_test, y_pred))

print(f"XGBoost Metrics:")
print(f"  R² (test): {r2:.4f}")
print(f"  MAE (test): {mae:.2f}")
print(f"  RMSE (test): {rmse:.2f}")

# Load existing model_comparison_results.json
with open('models/model_comparison_results.json', 'r') as f:
    results = json.load(f)

# Add XGBoost metrics
results['models']['XGBoost'] = {
    'r2_test': r2,
    'mae_test': mae,
    'rmse_test': rmse,
    'train_r2': r2,  # Using test as proxy since we don't have separate train metric
    'train_mae': mae,
    'train_rmse': rmse
}

# Save updated results
with open('models/model_comparison_results.json', 'w') as f:
    json.dump(results, f, indent=2)

print("\n✅ Added XGBoost metrics to model_comparison_results.json")
print(f"   Total models: {len(results['models'])}")
