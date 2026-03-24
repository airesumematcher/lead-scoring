#!/usr/bin/env python3
"""
Phase 3: Add Homegrown Model to API

This script:
1. Loads the trained model
2. Creates an API endpoint for scoring
3. Shows how to integrate with existing API
"""

import os
import sys
from pathlib import Path

# Add project to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pickle
import json
import numpy as np
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, List, Optional

# ============================================================================
# LOAD MODEL
# ============================================================================

MODEL_PATH = Path(__file__).parent.parent.parent.parent / "models" / "lead_scorer.pkl"
METADATA_PATH = Path(__file__).parent.parent.parent.parent / "models" / "model_metadata.json"

def load_model():
    """Load trained model from disk"""
    if not MODEL_PATH.exists():
        raise FileNotFoundError(f"Model not found: {MODEL_PATH}\nRun Phase 2 first: python scripts/02_train_ml_model.py")
    
    with open(MODEL_PATH, 'rb') as f:
        model = pickle.load(f)
    
    with open(METADATA_PATH, 'r') as f:
        metadata = json.load(f)
    
    return model, metadata

# Load model on startup
try:
    MODEL, MODEL_METADATA = load_model()
    print(f"✅ Model loaded: {MODEL_PATH}")
except Exception as e:
    print(f"⚠️  Model not loaded: {e}")
    MODEL = None
    MODEL_METADATA = None

# ============================================================================
# API MODELS
# ============================================================================

class LeadInput(BaseModel):
    """Input for lead scoring"""
    company_size_score: float
    total_engagement_score: float
    has_engagement: int
    is_executive: int
    unsubscribed: int
    email1_engagement: float
    email2_engagement: float

class LeadScore(BaseModel):
    """Predicted lead score"""
    score: float
    confidence: float
    reasoning: str
    timestamp: str

# ============================================================================
# API ROUTER
# ============================================================================

router = APIRouter(prefix="/score", tags=["scoring"])

@router.post("/predict", response_model=LeadScore)
async def predict_lead_score(lead: LeadInput):
    """
    Predict lead score using homegrown ML model
    
    Input features:
    - company_size_score: 1-8 (Micro to XXLarge)
    - total_engagement_score: 0-4 (email opens + clicks)
    - has_engagement: 0-1 (any interaction)
    - is_executive: 0-1 (C-level/VP)
    - unsubscribed: 0-1 (has unsubscribed)
    - email1_engagement: 0-2
    - email2_engagement: 0-2
    
    Returns:
    - score: 0-100 lead priority
    - confidence: 0-1 model confidence
    - reasoning: Explanation of score
    """
    
    if MODEL is None:
        raise HTTPException(
            status_code=503,
            detail="Model not loaded. Run Phase 2: python scripts/02_train_ml_model.py"
        )
    
    # Prepare features
    features = np.array([[
        lead.company_size_score,
        lead.total_engagement_score,
        lead.has_engagement,
        lead.is_executive,
        lead.unsubscribed,
        lead.email1_engagement,
        lead.email2_engagement,
    ]])
    
    # Predict
    score = MODEL.predict(features)[0]
    
    # Clamp to 0-100
    score = max(0, min(100, score))
    
    # Confidence (approximation based on residuals)
    # Higher engagement + seniority = higher confidence
    base_confidence = 0.7 + (lead.total_engagement_score * 0.05)
    confidence = min(0.95, max(0.5, base_confidence))
    
    # Generate reasoning
    reasoning = generate_reasoning(lead)
    
    return LeadScore(
        score=float(score),
        confidence=float(confidence),
        reasoning=reasoning,
        timestamp=__import__('datetime').datetime.now().isoformat()
    )

@router.post("/batch-predict")
async def batch_predict_scores(leads: List[LeadInput]):
    """
    Predict scores for multiple leads
    """
    
    if MODEL is None:
        raise HTTPException(
            status_code=503,
            detail="Model not loaded"
        )
    
    results = []
    for lead in leads:
        result = await predict_lead_score(lead)
        results.append(result)
    
    return {
        "predictions": results,
        "total_leads": len(leads),
        "timestamp": __import__('datetime').datetime.now().isoformat()
    }

@router.get("/model-info")
async def get_model_info():
    """
    Get information about the trained model
    """
    
    if MODEL_METADATA is None:
        raise HTTPException(status_code=503, detail="Model not loaded")
    
    return {
        "model_type": MODEL_METADATA['model_type'],
        "features": MODEL_METADATA['features'],
        "metrics": MODEL_METADATA['metrics'],
        "top_features": sorted(
            MODEL_METADATA['feature_importance'].items(),
            key=lambda x: x[1],
            reverse=True
        )[:5],
        "created_at": MODEL_METADATA['created_at'],
        "version": MODEL_METADATA['version']
    }

@router.get("/feature-importance")
async def get_feature_importance():
    """
    Get feature importance rankings
    """
    
    if MODEL_METADATA is None:
        raise HTTPException(status_code=503, detail="Model not loaded")
    
    importance = MODEL_METADATA['feature_importance']
    
    # Sort by importance
    sorted_importance = sorted(
        importance.items(),
        key=lambda x: x[1],
        reverse=True
    )
    
    return {
        "feature_importance": dict(sorted_importance),
        "top_3": sorted_importance[:3],
        "note": "Higher values = more important for predictions"
    }

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def generate_reasoning(lead: LeadInput) -> str:
    """Generate human-readable explanation for score"""
    
    reasons = []
    
    # Seniority
    if lead.is_executive == 1:
        reasons.append("Executive/Senior opportunity")
    
    # Company size
    if lead.company_size_score >= 7:
        reasons.append("Enterprise company")
    elif lead.company_size_score >= 4:
        reasons.append("Mid-market company")
    else:
        reasons.append("Smaller company")
    
    # Engagement
    if lead.total_engagement_score >= 3:
        reasons.append("Strong email engagement")
    elif lead.total_engagement_score >= 1:
        reasons.append("Some engagement signals")
    else:
        reasons.append("Limited engagement")
    
    # Risk
    if lead.unsubscribed == 1:
        reasons.append("⚠️ Unsubscribed (high risk)")
    
    # Has interaction
    if lead.has_engagement == 1:
        reasons.append("Recent interaction")
    
    return ", ".join(reasons)

# ============================================================================
# CLI TESTING
# ============================================================================

def test_model():
    """Test model with sample lead"""
    
    if MODEL is None:
        print("❌ Model not loaded. Run Phase 2 first.")
        return
    
    # Sample lead (executive at large company with engagement)
    sample_lead = LeadInput(
        company_size_score=7,          # XLarge
        total_engagement_score=2,       # 2 clicks
        has_engagement=1,               # Has interaction
        is_executive=1,                 # C-suite
        unsubscribed=0,                 # Not unsubscribed
        email1_engagement=1,            # 1 click in email 1
        email2_engagement=1,            # 1 click in email 2
    )
    
    import asyncio
    
    async def score():
        result = await predict_lead_score(sample_lead)
        return result
    
    result = asyncio.run(score())
    
    print("\n" + "="*80)
    print("🧪 MODEL TEST")
    print("="*80)
    print(f"\nSample Lead:")
    print(f"  Company Size: Seven (1-8)")
    print(f"  Engagement: 2 clicks")
    print(f"  Seniority: Executive")
    print(f"\nPrediction:")
    print(f"  Score: {result.score:.1f} / 100")
    print(f"  Confidence: {result.confidence:.1%}")
    print(f"  Reasoning: {result.reasoning}")

if __name__ == "__main__":
    test_model()
