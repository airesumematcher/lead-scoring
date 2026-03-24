"""
ENHANCED API: CAMPAIGN-AWARE LEAD SCORING ENDPOINTS
Supports Fit Score, Intent Score, and mode-specific scoring
POST /score/predict-campaign-aware - Single lead with campaign context
POST /score/batch-predict-campaign-aware - Batch scoring
GET /score/campaign-modes - Available scoring modes
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional, Literal
import pickle
import json
from pathlib import Path
import numpy as np
import pandas as pd

router = APIRouter(prefix="/score", tags=["scoring"])

# Load models
MODEL_BASE_PATH = Path(__file__).parent.parent.parent.parent / "models"
MODEL_PATH = MODEL_BASE_PATH / "lead_scorer_campaign_aware.pkl"
METADATA_PATH = MODEL_BASE_PATH / "model_metadata_campaign_aware.json"

try:
    with open(MODEL_PATH, 'rb') as f:
        MODEL = pickle.load(f)
    with open(METADATA_PATH, 'r') as f:
        MODEL_METADATA = json.load(f)
except Exception as e:
    MODEL = None
    MODEL_METADATA = None
    print(f"⚠️  Warning: Could not load campaign-aware model: {e}")


# Request/Response Models
class CampaignContext(BaseModel):
    """Campaign-specific attributes"""
    asset_type_score: float = Field(0.5, description="0-1, e.g., 0.95 for case study")
    campaign_volume_score: float = Field(0.7, description="0-1, volume tier")
    engagement_sequence_score: float = Field(0.6, description="0-1, multi-touch depth")
    audience_type_score: float = Field(0.7, description="0-1, audience intent level")
    fit_score: float = Field(60, description="0-100, demographic/company fit")
    intent_score: float = Field(50, description="0-100, behavioral intent")
    campaign_quality_score: float = Field(70, description="0-100, campaign quality")


class LeadInputEnhanced(BaseModel):
    """Enhanced lead input with campaign context"""
    # Base signals
    is_executive: int = Field(0, description="1 if C-level/VP, 0 otherwise")
    company_size_score: int = Field(4, description="1-8 scale")
    has_engagement: int = Field(0, description="1 if any email engagement, 0 otherwise")
    email1_engagement: int = Field(0, description="0-2: none, opened, or clicked")
    email2_engagement: int = Field(0, description="0-2: none, opened, or clicked")
    total_engagement_score: int = Field(0, description="0-4: count of actions")
    unsubscribed: int = Field(0, description="1 if unsubscribed, 0 otherwise")
    
    # Campaign context (optional - will be derived if not provided)
    campaign_context: Optional[CampaignContext] = None
    campaign_mode: Literal['default', 'prospecting', 'engagement', 'nurture'] = 'default'


class LeadScoreEnhanced(BaseModel):
    """Enhanced lead score response"""
    score: float = Field(..., description="0-100 lead score")
    confidence: float = Field(..., description="0-100 confidence level")
    fit_score: float = Field(..., description="0-100 demographic fit")
    intent_score: float = Field(..., description="0-100 behavioral intent")
    campaign_quality_score: float = Field(..., description="0-100 campaign quality")
    combined_score: float = Field(..., description="0-100 combined score")
    campaign_mode: str = Field(..., description="Scoring mode used")
    reasoning: str = Field(..., description="Explanation of score")


def _derive_campaign_context(lead: LeadInputEnhanced) -> dict:
    """Calculate campaign context scores if not provided"""
    if lead.campaign_context:
        return lead.campaign_context.model_dump()
    
    # Derive from base signals
    fit_score = (
        (lead.company_size_score / 8) * 60 +
        (lead.is_executive * 40)
    )
    
    intent_score = (
        (lead.total_engagement_score / 4) * 50 +
        ((lead.email1_engagement + lead.email2_engagement) / 4) * 50
    )
    
    campaign_quality_score = 70  # Default
    
    return {
        'asset_type_score': 0.5,
        'campaign_volume_score': 0.7,
        'engagement_sequence_score': 0.6 if lead.total_engagement_score > 0 else 0.2,
        'audience_type_score': 0.8 if lead.is_executive else 0.6,
        'fit_score': min(100, fit_score),
        'intent_score': min(100, intent_score),
        'campaign_quality_score': campaign_quality_score
    }


def _apply_campaign_mode_weights(
    fit_score: float, 
    intent_score: float, 
    campaign_quality_score: float,
    mode: str
) -> float:
    """Apply campaign-mode specific weights to scores"""
    
    modes = {
        'default': {'fit': 0.60, 'intent': 0.30, 'campaign': 0.10},
        'prospecting': {'fit': 0.70, 'intent': 0.20, 'campaign': 0.10},
        'engagement': {'fit': 0.40, 'intent': 0.50, 'campaign': 0.10},
        'nurture': {'fit': 0.30, 'intent': 0.30, 'campaign': 0.40}
    }
    
    weights = modes.get(mode, modes['default'])
    
    weighted_score = (
        (fit_score / 100) * weights['fit'] * 100 +
        (intent_score / 100) * weights['intent'] * 100 +
        (campaign_quality_score / 100) * weights['campaign'] * 100
    )
    
    return min(100, weighted_score)


@router.post("/predict-campaign-aware", response_model=LeadScoreEnhanced)
async def predict_lead_score_campaign_aware(lead: LeadInputEnhanced):
    """
    Score a single lead with campaign context awareness
    
    Returns:
    - score: Final 0-100 lead score
    - fit_score: Demographic/company fit (0-100)
    - intent_score: Behavioral engagement (0-100)
    - campaign_quality_score: Campaign asset quality
    - reasoning: Explanation of the score
    """
    
    if MODEL is None:
        raise HTTPException(status_code=503, detail="Model not loaded")
    
    # Get campaign context
    campaign_context = _derive_campaign_context(lead)
    
    # Build feature vector matching model's expected columns
    feature_names = MODEL_METADATA.get('features', [])
    feature_vector = []
    
    lead_dict = lead.model_dump()
    campaign_context_copy = campaign_context.copy()
    
    # Combine dicts
    all_features = {**lead_dict, **campaign_context_copy}
    all_features.pop('campaign_context', None)
    all_features.pop('campaign_mode', None)
    
    # Build vector in correct order
    for feature_name in feature_names:
        value = all_features.get(feature_name, 0)
        feature_vector.append(value)
    
    # Get base prediction from model
    model_input = pd.DataFrame([feature_vector], columns=feature_names)
    base_score = MODEL.predict(model_input)[0]
    
    # Apply campaign mode weighting as an adjustment relative to the default mode.
    default_mode_score = _apply_campaign_mode_weights(
        campaign_context['fit_score'],
        campaign_context['intent_score'],
        campaign_context['campaign_quality_score'],
        'default'
    )
    mode_score = _apply_campaign_mode_weights(
        campaign_context['fit_score'],
        campaign_context['intent_score'],
        campaign_context['campaign_quality_score'],
        lead.campaign_mode
    )
    final_score = max(0, min(100, float(base_score) + (mode_score - default_mode_score)))
    
    # Generate reasoning
    if lead.is_executive:
        exec_text = "Executive (high priority)"
    else:
        exec_text = "Individual contributor"
    
    company_size_text = f"Company size: {lead.company_size_score}/8"
    
    engagement_text = f"Engagement: {lead.total_engagement_score}/4 touches"
    
    mode_text = f"Scoring mode: {lead.campaign_mode}"
    
    reasoning = (
        f"{exec_text} | {company_size_text} | {engagement_text} | {mode_text}"
    )
    
    # Calculate confidence based on data completeness and model fit
    confidence = min(
        95,
        70 +  # Base confidence
        (lead.total_engagement_score * 5) +  # +5% per engagement
        (lead.is_executive * 10)  # +10% for executive
    )
    
    return LeadScoreEnhanced(
        score=final_score,
        confidence=confidence,
        fit_score=campaign_context['fit_score'],
        intent_score=campaign_context['intent_score'],
        campaign_quality_score=campaign_context['campaign_quality_score'],
        combined_score=final_score,
        campaign_mode=lead.campaign_mode,
        reasoning=reasoning
    )


@router.post("/batch-predict-campaign-aware")
async def batch_predict_campaign_aware(leads: List[LeadInputEnhanced]):
    """Score multiple leads with campaign context awareness"""
    
    if MODEL is None:
        raise HTTPException(status_code=503, detail="Model not loaded")
    
    results = []
    for lead in leads:
        result = await predict_lead_score_campaign_aware(lead)
        results.append(result)
    
    return {
        'count': len(results),
        'scores': results,
        'average_score': sum(r.score for r in results) / len(results) if results else 0
    }


@router.get("/campaign-modes")
async def get_campaign_modes():
    """Get available campaign scoring modes and their weights"""
    
    if MODEL_METADATA is None:
        raise HTTPException(status_code=503, detail="Model metadata not loaded")
    
    return {
        'available_modes': ['default', 'prospecting', 'engagement', 'nurture'],
        'modes': MODEL_METADATA.get('campaign_scoring_modes', {}),
        'description': 'Different campaign modes weight Fit/Intent/Campaign Quality differently'
    }


@router.get("/model-info-campaign-aware")
async def get_model_info_campaign_aware():
    """Get campaign-aware model metadata"""
    
    if MODEL_METADATA is None:
        raise HTTPException(status_code=503, detail="Model metadata not loaded")
    
    return {
        'model_type': MODEL_METADATA.get('model_type'),
        'version': MODEL_METADATA.get('version'),
        'performance': MODEL_METADATA.get('performance'),
        'feature_count': MODEL_METADATA.get('feature_count'),
        'campaign_features': [
            'fit_score', 'intent_score', 'campaign_quality_score',
            'asset_type_score', 'audience_type_score'
        ]
    }


@router.get("/campaign-feature-importance")
async def get_campaign_feature_importance():
    """Get feature importance rankings with campaign context highlighted"""
    
    if MODEL_METADATA is None:
        raise HTTPException(status_code=503, detail="Model metadata not loaded")
    
    importance = MODEL_METADATA.get('feature_importance', {})
    
    # Categorize
    campaign_features = [
        'fit_score', 'intent_score', 'campaign_quality_score',
        'asset_type_score', 'audience_type_score', 'engagement_sequence_score'
    ]
    
    categorized = {
        'campaign_context': {k: v for k, v in importance.items() if k in campaign_features},
        'base_signals': {k: v for k, v in importance.items() if k not in campaign_features},
        'top_5': dict(sorted(importance.items(), key=lambda x: x[1], reverse=True)[:5])
    }
    
    return categorized
