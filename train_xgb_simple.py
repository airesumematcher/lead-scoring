import pandas as pd
import numpy as np
import xgboost as xgb
from sklearn.model_selection import train_test_split
from sklearn.metrics import r2_score, mean_absolute_error, mean_squared_error
import joblib

print("Training XGBoost...")
X = pd.read_csv('data_processed/features_enhanced.csv')
y = pd.read_csv('data_processed/targets.csv').iloc[:, 0].values

# Ensure same number of samples
if len(X) != len(y):
    min_len = min(len(X), len(y))
    X = X.iloc[:min_len]
    y = y[:min_len]
    print(f"Aligned data to {min_len} samples")

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

model = xgb.XGBRegressor(
    n_estimators=200,
    max_depth=5,
    learning_rate=0.1,
    random_state=42,
    n_jobs=-1
)
model.fit(X_train, y_train, eval_set=[(X_test, y_test)], verbose=False)

y_pred = np.clip(model.predict(X_test), 0, 100)
r2 = r2_score(y_test, y_pred)
mae = mean_absolute_error(y_test, y_pred)
rmse = np.sqrt(mean_squared_error(y_test, y_pred))

print(f"Test R²:   {r2:.4f}")
print(f"Test MAE:  ±{mae:.2f}")
print(f"Test RMSE: {rmse:.2f}")

joblib.dump(model, 'models/model_xgboost.pkl')
print("✓ Model saved")
