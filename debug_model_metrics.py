#!/usr/bin/env python3
"""Debug script to test model metrics loading."""

import json
import sys
from pathlib import Path

# Test 1: Check if JSON file exists and can be read
models_dir = Path(__file__).parent / "models"
results_path = models_dir / "model_comparison_results.json"

print(f"Testing model metrics loading...")
print(f"Models dir: {models_dir}")
print(f"Results path: {results_path}")
print(f"Exists: {results_path.exists()}")

if results_path.exists():
    with open(results_path, 'r') as f:
        results_data = json.load(f)
    
    print(f"\nJSON Structure:")
    print(f"  Top-level keys: {list(results_data.keys())}")
    
    models = results_data.get('models', {})
    print(f"  Number of models: {len(models)}")
    print(f"  Model names: {list(models.keys())}")
    
    # Test 2: Check structure of one model
    if models:
        first_model = list(models.items())[0]
        print(f"\nFirst model ({first_model[0]}):")
        print(f"  Fields: {list(first_model[1].keys())}")
        print(f"  r2_test: {first_model[1].get('r2_test')}")
        print(f"  mae_test: {first_model[1].get('mae_test')}")
        print(f"  rmse_test: {first_model[1].get('rmse_test')}")

# Test 3: Check if model pkl files exist  
print(f"\nChecking model pickle files:")
model_files = {
    'RandomForest': 'model_randomforest.pkl',
    'GradientBoosting': 'model_gradientboosting.pkl',
    'ExtraTrees': 'model_extratrees.pkl',
    'Bagging': 'model_bagging.pkl',
    'SVR': 'model_svr.pkl',
    'NeuralNetwork': 'model_neuralnetwork.pkl',
    'Ensemble': 'model_ensemble.pkl'
}

for model_name, filename in model_files.items():
    path = models_dir / filename
    exists = path.exists()
    print(f"  {model_name}: {exists}")

# Test 4: Try loading from the API's perspective
print(f"\nTesting from API handler perspective:")
sys.path.insert(0, str(Path(__file__).parent / "src"))

from lead_scoring.api.handlers import _load_model_metrics, _get_model_predictions
import numpy as np

model_metrics_data, scaler = _load_model_metrics()
print(f"  Loaded metrics: {model_metrics_data is not None}")
print(f"  Metrics data type: {type(model_metrics_data)}")

if model_metrics_data:
    print(f"  Metrics keys: {list(model_metrics_data.keys()) if isinstance(model_metrics_data, dict) else 'Not a dict'}")

lead_features_25d = np.zeros(25)
predictions = _get_model_predictions(None, lead_features_25d)
print(f"  Predictions: {predictions}")
