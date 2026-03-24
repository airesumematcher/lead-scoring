#!/usr/bin/env python3
"""
Phase 2 (Revised): Train Homegrown ML Lead Scoring Model

This script:
1. Loads engineered features from Phase 1
2. Trains a Gradient Boosting Regressor
3. Evaluates model performance
4. Creates feature importance analysis
5. Saves trained model for predictions
"""

import pandas as pd
import numpy as np
from pathlib import Path
import json
import pickle
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_squared_error, r2_score, mean_absolute_error
import warnings
warnings.filterwarnings('ignore')

# ============================================================================
# CONFIG
# ============================================================================

DATA_DIR = Path("data_processed")
MODEL_DIR = Path("models")
MODEL_DIR.mkdir(exist_ok=True)

RANDOM_STATE = 42
TEST_SIZE = 0.2

# ============================================================================
# LOAD DATA
# ============================================================================

def load_training_data():
    """Load features and targets from Phase 1"""
    print("\n" + "="*80)
    print("📥 LOADING TRAINING DATA")
    print("="*80)
    
    features_path = DATA_DIR / "features.csv"
    targets_path = DATA_DIR / "targets.csv"
    
    if not features_path.exists():
        print(f"\n❌ Missing data files. Run Phase 1 first:")
        print(f"   python scripts/01_data_prep.py")
        return None, None, None
    
    X = pd.read_csv(features_path, index_col=0)
    y = pd.read_csv(targets_path, index_col=0).squeeze()
    
    print(f"\n   ✅ Features: {X.shape[0]} leads × {X.shape[1]} features")
    print(f"   ✅ Targets: {len(y)} lead scores")
    print(f"\n   Feature columns: {list(X.columns)}")
    print(f"\n   Target statistics:")
    print(f"   • Mean: {y.mean():.2f}")
    print(f"   • Std: {y.std():.2f}")
    print(f"   • Min: {y.min():.2f}")
    print(f"   • Max: {y.max():.2f}")
    
    return X, y

def prepare_data(X, y):
    """Split data into train/test sets"""
    print("\n" + "="*80)
    print("🧪 PREPARING DATA SPLITS")
    print("="*80)
    
    # Split
    X_train, X_test, y_train, y_test = train_test_split(
        X, y,
        test_size=TEST_SIZE,
        random_state=RANDOM_STATE
    )
    
    print(f"\n   Training set: {len(X_train)} leads")
    print(f"   Test set: {len(X_test)} leads")
    print(f"   Train/Test split: {TEST_SIZE*100:.0f}% holdout")
    
    return X_train, X_test, y_train, y_test

def train_model(X_train, y_train):
    """Train Gradient Boosting model"""
    print("\n" + "="*80)
    print("🤖 TRAINING GRADIENT BOOSTING MODEL")
    print("="*80)
    
    # Initialize model
    model = GradientBoostingRegressor(
        n_estimators=100,      # Number of boosting stages
        learning_rate=0.1,     # Shrinkage
        max_depth=5,           # Tree depth
        min_samples_split=5,   # Prevents overfitting
        min_samples_leaf=2,
        random_state=RANDOM_STATE,
        verbose=0
    )
    
    # Train
    print(f"\n   Training with 100 boosting stages...")
    model.fit(X_train, y_train)
    
    print(f"   ✅ Model trained successfully")
    
    # Cross-validation
    cv_scores = cross_val_score(
        model, X_train, y_train,
        cv=5,
        scoring='r2'
    )
    
    print(f"\n   Cross-validation R² scores:")
    for i, score in enumerate(cv_scores, 1):
        print(f"   • Fold {i}: {score:.4f}")
    print(f"   • Mean: {cv_scores.mean():.4f} (+/- {cv_scores.std():.4f})")
    
    return model

def evaluate_model(model, X_train, X_test, y_train, y_test):
    """Evaluate model on train and test sets"""
    print("\n" + "="*80)
    print("📊 MODEL EVALUATION")
    print("="*80)
    
    # Predictions
    y_train_pred = model.predict(X_train)
    y_test_pred = model.predict(X_test)
    
    # Metrics
    train_r2 = r2_score(y_train, y_train_pred)
    test_r2 = r2_score(y_test, y_test_pred)
    
    train_rmse = np.sqrt(mean_squared_error(y_train, y_train_pred))
    test_rmse = np.sqrt(mean_squared_error(y_test, y_test_pred))
    
    train_mae = mean_absolute_error(y_train, y_train_pred)
    test_mae = mean_absolute_error(y_test, y_test_pred)
    
    print(f"\n   Coefficient of Determination (R²):")
    print(f"   • Train R²: {train_r2:.4f}")
    print(f"   • Test R²:  {test_r2:.4f}")
    
    print(f"\n   Root Mean Squared Error (RMSE):")
    print(f"   • Train: {train_rmse:.2f} points")
    print(f"   • Test:  {test_rmse:.2f} points")
    
    print(f"\n   Mean Absolute Error (MAE):")
    print(f"   • Train: {train_mae:.2f} points")
    print(f"   • Test:  {test_mae:.2f} points")
    
    # Interpretation
    print(f"\n   📈 Model Interpretation:")
    if test_r2 > 0.7:
        print(f"   ✅ Excellent: Model explains {test_r2*100:.1f}% of score variance")
    elif test_r2 > 0.5:
        print(f"   ✅ Good: Model explains {test_r2*100:.1f}% of score variance")
    elif test_r2 > 0.3:
        print(f"   ⚠️  Fair: Model explains {test_r2*100:.1f}% of score variance")
    else:
        print(f"   ❌ Poor: Model explains {test_r2*100:.1f}% of score variance")
    
    print(f"\n   Average prediction error: ±{test_mae:.1f} points (on 0-100 scale)")
    
    return {
        'train_r2': train_r2,
        'test_r2': test_r2,
        'train_rmse': train_rmse,
        'test_rmse': test_rmse,
        'train_mae': train_mae,
        'test_mae': test_mae,
    }

def analyze_feature_importance(model, X_train):
    """Analyze which features matter most"""
    print("\n" + "="*80)
    print("🔍 FEATURE IMPORTANCE ANALYSIS")
    print("="*80)
    
    # Get importances
    importances = model.feature_importances_
    feature_names = X_train.columns
    
    # Sort
    indices = np.argsort(importances)[::-1]
    
    print(f"\n   Top features driving predictions:\n")
    for rank, idx in enumerate(indices, 1):
        importance = importances[idx]
        feature = feature_names[idx]
        bar = "█" * int(importance * 50)
        print(f"   {rank}. {feature:30s} {bar} {importance:.4f}")
    
    # Save
    importance_dict = {
        str(feature_names[i]): float(importances[i])
        for i in range(len(feature_names))
    }
    
    importance_path = MODEL_DIR / "feature_importance.json"
    with open(importance_path, 'w') as f:
        json.dump(importance_dict, f, indent=2)
    
    print(f"\n   ✅ Saved: {importance_path}")
    
    return importance_dict

def save_model(model, metrics, feature_importance, X_train):
    """Save trained model and metadata"""
    print("\n" + "="*80)
    print("💾 SAVING MODEL")
    print("="*80)
    
    # Save model
    model_path = MODEL_DIR / "lead_scorer.pkl"
    with open(model_path, 'wb') as f:
        pickle.dump(model, f)
    print(f"   ✅ Model: {model_path}")
    
    # Save metadata
    metadata = {
        'model_type': 'GradientBoostingRegressor',
        'features': list(X_train.columns),
        'n_estimators': 100,
        'metrics': metrics,
        'feature_importance': feature_importance,
        'created_at': pd.Timestamp.now().isoformat(),
        'version': '1.0.0'
    }
    
    metadata_path = MODEL_DIR / "model_metadata.json"
    with open(metadata_path, 'w') as f:
        json.dump(metadata, f, indent=2)
    print(f"   ✅ Metadata: {metadata_path}")
    
    print(f"\n   📁 Models directory: {MODEL_DIR.absolute()}")
    print(f"   Files saved:")
    print(f"   • lead_scorer.pkl (model)")
    print(f"   • model_metadata.json (info)")
    print(f"   • feature_importance.json (weights)")

def create_prediction_example(model, X_test, y_test):
    """Show example predictions"""
    print("\n" + "="*80)
    print("📋 PREDICTION EXAMPLES")
    print("="*80)
    
    # Pick some examples
    sample_indices = np.random.choice(len(X_test), size=min(5, len(X_test)), replace=False)
    
    print(f"\n   Sample predictions on test set:\n")
    for idx in sample_indices:
        X_sample = X_test.iloc[idx:idx+1]
        y_actual = y_test.iloc[idx]
        y_pred = model.predict(X_sample)[0]
        error = abs(y_actual - y_pred)
        
        print(f"   Lead: {idx}")
        print(f"   • Actual score:     {y_actual:.1f}")
        print(f"   • Predicted score:  {y_pred:.1f}")
        print(f"   • Error:            ±{error:.1f} points ({error/y_actual*100:.1f}%)\n")

# ============================================================================
# MAIN
# ============================================================================

def main():
    """Run complete Phase 2 pipeline"""
    
    print("\n")
    print("╔" + "="*78 + "╗")
    print("║" + " "*78 + "║")
    print("║" + "PHASE 2: TRAIN HOMEGROWN ML LEAD SCORING MODEL".center(78) + "║")
    print("║" + " "*78 + "║")
    print("╚" + "="*78 + "╝")
    
    try:
        # 1. Load data
        X, y = load_training_data()
        if X is None:
            return False
        
        # 2. Prepare splits
        X_train, X_test, y_train, y_test = prepare_data(X, y)
        
        # 3. Train model
        model = train_model(X_train, y_train)
        
        # 4. Evaluate
        metrics = evaluate_model(model, X_train, X_test, y_train, y_test)
        
        # 5. Feature importance
        importance = analyze_feature_importance(model, X_train)
        
        # 6. Save
        save_model(model, metrics, importance, X_train)
        
        # 7. Examples
        create_prediction_example(model, X_test, y_test)
        
        # Summary
        print("\n" + "="*80)
        print("✅ PHASE 2 COMPLETE - MODEL TRAINED")
        print("="*80)
        print(f"""
Your homegrown ML model is ready!

Model Performance:
  📊 Test R²: {metrics['test_r2']:.4f} ({metrics['test_r2']*100:.1f}% variance explained)
  📊 Test RMSE: {metrics['test_rmse']:.2f} points
  📊 Test MAE: {metrics['test_mae']:.2f} points (avg error)

What This Means:
  ✓ Model can predict lead scores within ±{metrics['test_mae']:.1f} points
  ✓ Understands {metrics['test_r2']*100:.1f}% of what drives score variation
  ✓ No external APIs - everything runs locally

Next Steps:
  1. Review feature importance: models/feature_importance.json
  2. Add model to API: Phase 3
  3. Deploy scoring endpoint

Files Created:
  • models/lead_scorer.pkl          → Trained model
  • models/model_metadata.json      → Model info
  • models/feature_importance.json  → Feature weights

To use the model in your code:
  import pickle
  with open('models/lead_scorer.pkl', 'rb') as f:
      model = pickle.load(f)
  
  score = model.predict([[features]])[0]
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
