"""Multi-model scoring API backed by the trained local model artifacts."""

import pickle
import json
from pathlib import Path
from typing import List, Dict, Optional
import numpy as np
import pandas as pd
from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel, Field
from datetime import datetime

router = APIRouter(prefix="/models", tags=["multi-model"])

# Model loading paths
MODELS_DIR = Path(__file__).parent.parent.parent.parent / "models"

class ModelPrediction(BaseModel):
    """Single model prediction"""
    model_name: str = Field(..., description="Name of the model")
    score: float = Field(..., description="Predicted score (0-100)", ge=0, le=100)
    confidence: float = Field(..., description="Model confidence (0-1)")
    
class MultiModelResponse(BaseModel):
    """Response with predictions from multiple models"""
    lead_id: str = Field(..., description="Lead identifier")
    predictions: List[ModelPrediction] = Field(..., description="Predictions from each model")
    ensemble_score: float = Field(..., description="Weighted ensemble score")
    ensemble_confidence: float = Field(..., description="Ensemble confidence")
    recommended_model: str = Field(..., description="Recommended best-performing model")
    recommendation_reason: str = Field(..., description="Why this model is recommended")
    timestamp: str = Field(..., description="Scoring timestamp")
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "lead_id": "LEAD-001",
                "predictions": [
                    {"model_name": "XGBoost", "score": 75, "confidence": 0.92},
                    {"model_name": "RandomForest", "score": 72, "confidence": 0.88},
                    {"model_name": "LightGBM", "score": 78, "confidence": 0.90}
                ],
                "ensemble_score": 75,
                "ensemble_confidence": 0.90,
                "recommended_model": "XGBoost",
                "recommendation_reason": "Best R² score on test set (0.5847)"
            }
        }
    }

class MultiModelLoader:
    """Manages loading and caching of all trained models"""
    
    def __init__(self):
        self.models = {}
        self.scaler = None
        self.model_performance = {}
        self.feature_count = None
        self.load_all_models()
    
    def load_all_models(self):
        """Load all trained models from disk"""
        print("📂 Loading trained models...")
        
        # Load individual models
        model_files = {
            'RandomForest': 'model_randomforest.pkl',
            'GradientBoosting': 'model_gradientboosting.pkl',
            'ExtraTrees': 'model_extratrees.pkl',
            'Bagging': 'model_bagging.pkl',
            'SVR': 'model_svr.pkl',
            'NeuralNetwork': 'model_neuralnetwork.pkl',
            'XGBoost': 'model_xgboost.pkl',
            'Ensemble': 'model_ensemble.pkl'
        }
        
        for model_name, filename in model_files.items():
            path = MODELS_DIR / filename
            if path.exists():
                try:
                    with open(path, 'rb') as f:
                        self.models[model_name] = pickle.load(f)
                    print(f"  ✅ {model_name} loaded")
                except Exception as e:
                    print(f"  ⚠️  {model_name} failed to load: {e}")
        
        # Load scaler
        scaler_path = MODELS_DIR / "scaler.pkl"
        if scaler_path.exists():
            try:
                with open(scaler_path, 'rb') as f:
                    self.scaler = pickle.load(f)
                print(f"  ✅ Scaler loaded")
            except Exception as e:
                print(f"  ⚠️  Scaler failed to load: {e}")
        
        # Load performance metrics
        results_path = MODELS_DIR / "model_comparison_results.json"
        if results_path.exists():
            try:
                with open(results_path, 'r') as f:
                    results_data = json.load(f)
                self.model_performance = results_data.get('models', {})
                feature_names = results_data.get('feature_names', [])
                if feature_names:
                    self.feature_count = len(feature_names)
                print(f"  ✅ Model performance metrics loaded")
            except Exception as e:
                print(f"  ⚠️  Performance metrics failed to load: {e}")

        if self.feature_count is None:
            if self.scaler is not None:
                self.feature_count = getattr(self.scaler, "n_features_in_", None)
            elif self.models:
                first_model = next(iter(self.models.values()))
                self.feature_count = getattr(first_model, "n_features_in_", None)

    @staticmethod
    def _predict_model(model, features: np.ndarray) -> float:
        """Predict with a fitted estimator and clamp to score range."""
        if hasattr(model, "feature_names_in_"):
            model_input = pd.DataFrame([features], columns=model.feature_names_in_)
            score = model.predict(model_input)[0]
        else:
            score = model.predict(features.reshape(1, -1))[0]
        return max(0, min(100, float(score)))
    
    def predict_all_models(self, features: np.ndarray) -> Dict[str, float]:
        """Get predictions from all available models"""
        predictions = {}

        if self.feature_count is not None and len(features) != self.feature_count:
            raise ValueError(
                f"Expected {self.feature_count} features, got {len(features)}"
            )

        # Non-scaled models
        non_scaled_models = [
            'XGBoost',
            'RandomForest',
            'GradientBoosting',
            'ExtraTrees',
            'Bagging',
            'Ensemble',
        ]
        for model_name in non_scaled_models:
            if model_name in self.models:
                try:
                    score = self._predict_model(self.models[model_name], features)
                    predictions[model_name] = score
                except Exception as e:
                    print(f"⚠️  Prediction failed for {model_name}: {e}")
        
        # Scaled models (NN, SVR)
        if self.scaler and features is not None:
            if hasattr(self.scaler, "feature_names_in_"):
                scaler_input = pd.DataFrame([features], columns=self.scaler.feature_names_in_)
                features_scaled = self.scaler.transform(scaler_input)
            else:
                features_scaled = self.scaler.transform(features.reshape(1, -1))
            
            for model_name in ['NeuralNetwork', 'SVR']:
                if model_name in self.models:
                    try:
                        score = max(0, min(100, float(self.models[model_name].predict(features_scaled)[0])))
                        predictions[model_name] = score
                    except Exception as e:
                        print(f"⚠️  Prediction failed for {model_name}: {e}")
        
        return predictions
    
    def get_ensemble_score(self, predictions: Dict[str, float]) -> float:
        """Calculate weighted ensemble score using model performance"""
        if not predictions:
            return 0.0

        if 'Ensemble' in predictions:
            return predictions['Ensemble']
        
        if self.model_performance:
            # Weight by R² scores
            total_weight = 0
            weighted_sum = 0
            
            for model_name, score in predictions.items():
                if model_name in self.model_performance:
                    weight = max(0, self.model_performance[model_name].get('r2_test', 0.5))
                    weighted_sum += score * weight
                    total_weight += weight
            
            if total_weight > 0:
                return weighted_sum / total_weight
        
        # Fallback: Simple average
        return np.mean(list(predictions.values()))
    
    def get_best_model(self) -> tuple:
        """Return name and reason for best performing model"""
        if not self.model_performance:
            return "Ensemble", "No training history available"
        
        best_model = max(
            self.model_performance.items(),
            key=lambda x: x[1].get('r2_test', 0)
        )
        
        model_name = best_model[0]
        r2_score = best_model[1].get('r2_test', 0)
        mae = best_model[1].get('mae_test', 0)
        
        reason = f"Best R² score on test set ({r2_score:.4f}) with MAE ±{mae:.2f}"
        
        return model_name, reason

# Initialize model loader
try:
    model_loader = MultiModelLoader()
    MODELS_AVAILABLE = len(model_loader.models) > 0
except Exception as e:
    print(f"⚠️  Failed to initialize model loader: {e}")
    MODELS_AVAILABLE = False


def _load_all_sample_report() -> dict:
    """Load the all-sample-data training report when available."""
    report_path = MODELS_DIR / "all_sample_data" / "training_report.json"
    if not report_path.exists():
        return {}
    try:
        with open(report_path, "r") as f:
            return json.load(f)
    except Exception:
        return {}

@router.post("/predict-multi", response_model=MultiModelResponse, tags=["multi-model"])
async def predict_with_multiple_models(
    lead_id: str = Body(...),
    features: List[float] = Body(..., description="Feature vector matching the trained model signature"),
) -> MultiModelResponse:
    """
    Score a lead using multiple ML models and return ensemble recommendation
    
    Loads predictions from:
    - Random Forest
    - Gradient Boosting
    - Extra Trees
    - Bagging
    - Neural Network
    - Support Vector Regression
    """
    if not MODELS_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="Model infrastructure not available"
        )
    
    try:
        features_array = np.array(features)
        predictions = model_loader.predict_all_models(features_array)
        if not predictions:
            raise HTTPException(
                status_code=400,
                detail="No compatible models could score the supplied feature vector",
            )
        ensemble_score = model_loader.get_ensemble_score(predictions)
        best_model, reason = model_loader.get_best_model()
        confidence_values = [
            model_loader.model_performance.get(name, {}).get('r2_test', 0.65)
            for name in predictions
        ]
        
        pred_list = [
            ModelPrediction(
                model_name=name,
                score=score,
                confidence=model_loader.model_performance.get(name, {}).get('r2_test', 0.65)
            )
            for name, score in predictions.items()
        ]
        
        return MultiModelResponse(
            lead_id=lead_id,
            predictions=pred_list,
            ensemble_score=ensemble_score,
            ensemble_confidence=round(sum(confidence_values) / len(confidence_values), 3),
            recommended_model=best_model,
            recommendation_reason=reason,
            timestamp=datetime.now().isoformat()
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error scoring lead: {str(e)}")


@router.get("/comparison-summary", tags=["multi-model"])
async def get_model_comparison_summary():
    """
    Get summary of all trained models and their performance
    """
    
    if not model_loader.model_performance:
        raise HTTPException(
            status_code=404,
            detail="No model performance data available"
        )
    
    # Sort by R² score
    sorted_models = sorted(
        model_loader.model_performance.items(),
        key=lambda x: x[1].get('r2_test', 0),
        reverse=True
    )
    
    summary = {
        "total_models": len(sorted_models),
        "models": [
            {
                "rank": i + 1,
                "name": name,
                "r2_score": metrics.get('r2_test', 0),
                "mae": metrics.get('mae_test', 0),
                "rmse": metrics.get('rmse_test', 0),
                "cv_mean": metrics.get('cv_mean', 0),
                "status": "🥇 Best" if i == 0 else "✓ Good"
            }
            for i, (name, metrics) in enumerate(sorted_models)
        ]
    }
    
    return summary

@router.get("/recommended-model", tags=["multi-model"])
async def get_recommended_model():
    """
    Get the recommended model based on training performance
    """
    
    best_model_name, best_reason = model_loader.get_best_model()
    
    best_metrics = model_loader.model_performance.get(best_model_name, {})
    
    response = {
        "recommended_model": best_model_name,
        "reason": best_reason,
        "r2_score": best_metrics.get('r2_test', 0),
        "mae": best_metrics.get('mae_test', 0),
        "rmse": best_metrics.get('rmse_test', 0),
        "cv_mean": best_metrics.get('cv_mean', 0),
        "timestamp": datetime.now().isoformat()
    }
    all_sample_report = _load_all_sample_report()
    production_candidate = all_sample_report.get("production_candidate")
    if production_candidate:
        response["production_candidate"] = {
            "name": production_candidate.get("name"),
            "artifact": production_candidate.get("artifact"),
            "reason": production_candidate.get("reason"),
            "r2_score": production_candidate.get("metrics", {}).get("r2_test", 0),
            "mae": production_candidate.get("metrics", {}).get("mae_test", 0),
            "rmse": production_candidate.get("metrics", {}).get("rmse_test", 0),
            "feature_count": production_candidate.get("feature_count", 0),
        }
    return response
