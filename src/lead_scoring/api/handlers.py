"""Handlers for lead scoring API endpoints."""

from typing import List
from datetime import datetime
from pathlib import Path
from functools import lru_cache
import pickle
import json
import numpy as np
import pandas as pd
import logging
from lead_scoring.config import load_config
from lead_scoring.scoring import score_lead
from lead_scoring.models import LeadInput, Grade
from lead_scoring.features import extract_all_features
from .reduced_signal_model import predict_reduced_signal_score
from .schemas import (
    ACEPillarScores,
    BatchScoringResponse,
    FitmentRecommendation,
    LeadScoreComparisonResponse,
    ModelMetrics,
    ReducedSignalModelScore,
    ReducedSignalScoreResponse,
    ScoreComparison,
    ScoringResponse,
)

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _load_model_metrics():
    """Load model performance metrics and trained models."""
    try:
        # Path from handlers.py: src/lead_scoring/api/handlers.py
        # Need to go up 4 levels to reach project root: models are in PROJECT_ROOT/models
        models_dir = Path(__file__).parent.parent.parent.parent / "models"
        results_path = models_dir / "model_comparison_results.json"
        
        if not results_path.exists():
            return None, None
        
        with open(results_path, 'r') as f:
            results_data = json.load(f)
        
        model_metrics = results_data.get('models', {})
        
        # Load scaler for scaled models
        scaler = None
        scaler_path = models_dir / "scaler.pkl"
        if scaler_path.exists():
            try:
                with open(scaler_path, 'rb') as f:
                    scaler = pickle.load(f)
            except:
                pass
        
        return model_metrics, scaler
    except Exception as e:
        print(f"Error loading model metrics: {e}")
        return None, None


def _predict_with_model(model_name: str, model, features: np.ndarray, scaler=None):
    """Predict with a single model when the feature signature matches."""
    expected_features = getattr(model, "n_features_in_", None)

    if model_name in {"SVR", "NeuralNetwork"} and scaler is not None:
        scaler_features = getattr(scaler, "n_features_in_", None)
        if scaler_features is not None and scaler_features != features.size:
            logger.warning(
                "Skipping %s prediction: scaler expects %s features, got %s",
                model_name,
                scaler_features,
                features.size,
            )
            return None
        if hasattr(scaler, "feature_names_in_"):
            scaler_input = pd.DataFrame([features], columns=scaler.feature_names_in_)
            features_to_use = scaler.transform(scaler_input)[0]
        else:
            features_to_use = scaler.transform([features])[0]
    else:
        features_to_use = features

    if expected_features is not None and expected_features != len(features_to_use):
        logger.warning(
            "Skipping %s prediction: model expects %s features, got %s",
            model_name,
            expected_features,
            len(features_to_use),
        )
        return None

    if hasattr(model, "feature_names_in_"):
        model_input = pd.DataFrame([features_to_use], columns=model.feature_names_in_)
        prediction = float(model.predict(model_input)[0])
    else:
        prediction = float(model.predict([features_to_use])[0])
    return max(0.0, min(100.0, prediction))


def _build_feature_vector_25d(lead: LeadInput):
    """
    Extract features from lead and build 25-dimensional feature vector for ML models.
    
    Matches the order expected by trained ML models.
    """
    try:
        logger.debug(f"🔍 Extracting features for lead {lead.lead_id}...")
        
        # Extract all features using the feature engineering pipeline
        extracted_features = extract_all_features(lead)
        
        # Build 25-dimensional vector matching training data format
        # Order: accuracy (6), client_fit (6), engagement (8), derived (5)
        feature_vector = [
            # Accuracy (6 features)
            float(extracted_features.accuracy.email_valid),
            float(extracted_features.accuracy.phone_valid),
            float(extracted_features.accuracy.job_title_present),
            extracted_features.accuracy.job_title_seniority_score / 5.0,  # Normalize (0-1)
            extracted_features.accuracy.domain_credibility / 100.0,  # Normalize (0-1)
            extracted_features.accuracy.delivery_latency_days / 60.0,  # Normalize (0-1)
            
            # Client Fit (6 features)
            extracted_features.client_fit.industry_match_pts / 25.0,  # Normalize
            extracted_features.client_fit.company_size_match_pts / 25.0,  # Normalize
            extracted_features.client_fit.revenue_band_match_pts / 20.0,  # Normalize
            extracted_features.client_fit.geography_match_pts / 20.0,  # Normalize
            float(extracted_features.client_fit.tal_match),  # Boolean → 0/1
            extracted_features.client_fit.job_title_match_persona_pts / 25.0,  # Normalize
            
            # Engagement (8 features)
            extracted_features.engagement.engagement_recency_days / 90.0,  # Normalize
            extracted_features.engagement.engagement_sequence_depth / 5.0,  # Normalize
            extracted_features.engagement.email_open_count / 10.0,  # Normalize
            extracted_features.engagement.asset_click_count / 10.0,  # Normalize
            float(extracted_features.engagement.asset_download_event),  # Boolean
            extracted_features.engagement.time_decay_engagement_score / 100.0,  # Already 0-1
            extracted_features.engagement.asset_stage_alignment_pts / 20.0,  # Normalize
            float(extracted_features.engagement.engagement_absent_flag),  # Boolean
            
            # Derived (5 features)
            extracted_features.derived.ace_balance_score / 100.0,  # Normalize
            extracted_features.derived.fit_intent_synergy / 100.0,  # Normalize
            extracted_features.derived.freshness_decay_multiplier,  # Already 0-1
            extracted_features.derived.confidence_signal_count / 13.0,  # Normalize (max 13 signals)
            extracted_features.derived.icp_violation_count / 5.0,  # Normalize
        ]
        
        feature_vector = np.array(feature_vector, dtype=np.float32)
        
        logger.info(f"✅ Extracted 25-dimensional feature vector for {lead.lead_id}")
        logger.debug(f"   Features: {feature_vector}")
        
        return feature_vector
        
    except Exception as e:
        logger.error(f"❌ Error building feature vector: {e}", exc_info=True)
        # Return fallback vector of zeros if extraction fails
        return np.zeros(25, dtype=np.float32)


def _get_model_predictions(lead: LeadInput):
    """Get predictions from trained models using actual lead features."""
    try:
        logger.debug(f"🤖 Getting model predictions for {lead.lead_id}...")
        
        # Path from handlers.py: src/lead_scoring/api/handlers.py
        # Need to go up 4 levels to reach project root: models are in PROJECT_ROOT/models
        models_dir = Path(__file__).parent.parent.parent.parent / "models"
        model_metrics_data, scaler = _load_model_metrics()
        
        if model_metrics_data is None:
            logger.warning("No model metrics data found")
            return None
        
        # BUILD ACTUAL FEATURE VECTOR FROM LEAD
        lead_features_25d = _build_feature_vector_25d(lead)
        
        predictions = {}
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
            path = models_dir / filename
            if not path.exists():
                logger.warning(f"❌ Model file not found: {path}")
                continue
            
            try:
                with open(path, 'rb') as f:
                    model = pickle.load(f)

                pred = _predict_with_model(
                    model_name=model_name,
                    model=model,
                    features=lead_features_25d,
                    scaler=scaler,
                )
                if pred is None:
                    continue

                predictions[model_name] = pred
                logger.info(f"  ✅ {model_name}: {pred:.1f}/100")
            except Exception as e:
                logger.warning(f"⚠️  Could not score with {model_name}: {e}")
        
        if predictions:
            logger.info(f"✅ Got predictions from {len(predictions)} models")
        
        return predictions if predictions else None
    except Exception as e:
        logger.error(f"Error getting model predictions: {e}", exc_info=True)
        return None


def _build_ace_scores(lead_score) -> ACEPillarScores:
    """Map the live LeadScore ACE breakdown into API response fields."""
    return ACEPillarScores(
        accuracy=lead_score.ace_breakdown.accuracy,
        client_fit=lead_score.ace_breakdown.client_fit,
        engagement=lead_score.ace_breakdown.engagement,
    )


def _build_fitment_recommendation(ace_scores: ACEPillarScores) -> FitmentRecommendation:
    """Translate ACE pillar scores into a routing-friendly fitment recommendation."""
    accuracy = ace_scores.accuracy
    client_fit = ace_scores.client_fit
    engagement = ace_scores.engagement

    if accuracy < 60:
        return FitmentRecommendation(
            segment="Data quality repair",
            sales_readiness="Blocked",
            best_motion="Enrich",
            recommendation="Fix contact accuracy and delivery confidence before spending sales time.",
        )
    if client_fit >= 80 and engagement >= 70:
        return FitmentRecommendation(
            segment="High fit / high engagement",
            sales_readiness="Sales-ready",
            best_motion="Fast-track",
            recommendation="Route immediately to sales. The account fits well and intent is active.",
        )
    if client_fit >= 80 and engagement < 70:
        return FitmentRecommendation(
            segment="High fit / low engagement",
            sales_readiness="Monitor",
            best_motion="ABM nurture",
            recommendation="Keep this lead in targeted nurture. Fit is strong, but engagement has not matured yet.",
        )
    if client_fit >= 60 and engagement >= 45:
        return FitmentRecommendation(
            segment="Mid fit / emerging engagement",
            sales_readiness="Developing",
            best_motion="Nurture",
            recommendation="Continue nurture and watch for stronger engagement before routing to sales.",
        )
    if client_fit < 60 and engagement >= 60:
        return FitmentRecommendation(
            segment="Low fit / curious account",
            sales_readiness="Needs qualification",
            best_motion="Selective outreach",
            recommendation="Interest exists, but validate ICP fit before investing SDR time.",
        )
    return FitmentRecommendation(
        segment="Low fit / low signal",
        sales_readiness="Low priority",
        best_motion="Deprioritize",
        recommendation="Hold this lead until data quality, fit, or engagement materially improves.",
    )


def _build_reduced_signal_model(
    lead_input: LeadInput,
    extracted_features,
) -> ReducedSignalModelScore | None:
    """Score the lead with the reduced-signal XGBoost model."""
    try:
        prediction = predict_reduced_signal_score(
            lead_input,
            extracted_features=extracted_features,
        )
        metrics = prediction.metrics or {}
        confidence = max(0.0, min(1.0, float(metrics.get("r2_test", 0.0))))
        return ReducedSignalModelScore(
            model_name=prediction.model_name,
            model_version=prediction.model_version,
            score=prediction.score,
            confidence=round(confidence, 3),
            r2_score=round(float(metrics.get("r2_test", 0.0)), 4),
            mae=round(float(metrics.get("mae_test", 0.0)), 2),
            rmse=round(float(metrics.get("rmse_test", 0.0)), 2),
            feature_count=prediction.feature_count,
        )
    except Exception as e:
        logger.warning("Could not score reduced-signal model for %s: %s", lead_input.lead_id, e)
        return None


def _build_score_comparison(
    ace_score: int,
    reduced_signal_model: ReducedSignalModelScore | None,
) -> ScoreComparison | None:
    """Summarize how the reduced-signal model compares to the live ACE scorer."""
    if reduced_signal_model is None:
        return None

    gap = round(reduced_signal_model.score - ace_score, 1)
    if abs(gap) < 5:
        summary = "ACE and the reduced-signal model broadly agree on this lead."
        higher = "Tie"
    elif gap > 0:
        summary = (
            "The reduced-signal model is more optimistic than ACE, which usually means "
            "the live ACE policy is discounting engagement recency or balance more heavily."
        )
        higher = "Reduced-signal model"
    else:
        summary = (
            "ACE is more optimistic than the reduced-signal model, which suggests the "
            "historical sample-data patterns are seeing weaker conversion potential."
        )
        higher = "ACE"

    return ScoreComparison(
        ace_score=ace_score,
        reduced_signal_score=reduced_signal_model.score,
        score_gap=gap,
        higher_score_source=higher,
        summary=summary,
    )


def score_single_lead(
    lead_input: LeadInput, program_type: str = "nurture"
) -> ScoringResponse:
    """
    Score a single lead and return formatted response.

    Args:
        lead_input: Lead data to score
        program_type: Program type (nurture, outbound, abm, event) - used to update lead if needed

    Returns:
        ScoringResponse with full scoring results
    """
    try:
        logger.info(f"📌 START: Scoring lead {lead_input.lead_id}")
        logger.debug(f"   Contact: {lead_input.contact.email}")
        logger.debug(f"   Company: {lead_input.company.company_name}")
        logger.debug(f"   Program type: {lead_input.campaign.program_type.value}")
        
        # If program_type is provided and different from lead's, we use the lead's existing value
        # since the scoring engine pulls program_type from lead.campaign.program_type
        config = load_config()
        extracted_features = extract_all_features(lead_input)

        # Score the lead
        logger.debug(f"🔄 Running scoring pipeline...")
        lead_score = score_lead(lead_input, config)
        
        logger.info(f"✅ Scoring complete - Score: {lead_score.score}, Grade: {lead_score.grade.value}")
        logger.debug(f"   ACE: A={lead_score.ace_breakdown.accuracy}, C={lead_score.ace_breakdown.client_fit}, E={lead_score.ace_breakdown.engagement}")
        logger.debug(f"   Confidence: {lead_score.confidence}, Freshness: {lead_score.freshness.status}")

        # Extract components for response
        drivers = (
            lead_score.narrative.positive_drivers if lead_score.narrative else ["N/A"]
        )
        limiters = (
            lead_score.narrative.limiting_factors if lead_score.narrative else ["N/A"]
        )
        summary = lead_score.narrative.summary if lead_score.narrative else "Unable to generate narrative."

        logger.debug(f"   Drivers: {drivers}")
        logger.debug(f"   Limiters: {limiters}")

        ace_scores = _build_ace_scores(lead_score)
        fitment = _build_fitment_recommendation(ace_scores)
        reduced_signal_model = _build_reduced_signal_model(
            lead_input,
            extracted_features=extracted_features,
        )
        score_comparison = _build_score_comparison(
            lead_score.score,
            reduced_signal_model,
        )

        # Collect adjustments applied
        adjustments = []
        # Note: In Phase 1, adjustments are tracked within the explainability module
        # For now, we provide empty list; can integrate feature_importance later
        # if lead_score.audit_trail and hasattr(lead_score.audit_trail, 'score_adjustments'):
        #     for adj_name, adj_value in lead_score.audit_trail.score_adjustments.items():
        #         adjustments.append(f"{adj_name}: {adj_value:.1f}%")

        # Get model metrics and predictions (optional)
        model_metrics_list = None
        ensemble_confidence = None
        try:
            logger.debug(f"🔍 Loading model metrics for {lead_input.lead_id}...")
            model_metrics_data, scaler = _load_model_metrics()
            
            # Get predictions using ACTUAL engineered features (not zeros!)
            model_predictions = _get_model_predictions(lead_input)
            
            if model_predictions and model_metrics_data:
                logger.debug(f"📊 Building model metrics for {len(model_predictions)} models...")
                model_metrics_list = []
                total_r2 = sum(m.get('r2_test', 0) for m in model_metrics_data.values())
                
                for model_name, prediction in model_predictions.items():
                    metrics = model_metrics_data.get(model_name, {})
                    if metrics:
                        confidence = max(0.5, metrics.get('r2_test', 0.5))
                        model_metrics_list.append(
                            ModelMetrics(
                                model_name=model_name,
                                r2_score=round(metrics.get('r2_test', 0), 4),
                                mae=round(metrics.get('mae_test', 0), 2),
                                rmse=round(metrics.get('rmse_test', 0), 2),
                                prediction=round(prediction, 1),
                                confidence=round(confidence, 3)
                            )
                        )
                        logger.debug(f"  {model_name}: pred={prediction:.1f}, r2={confidence:.3f}")
                
                # Calculate ensemble confidence as weighted average
                if total_r2 > 0 and model_metrics_list:
                    ensemble_confidence = round(
                        sum(m.r2_score for m in model_metrics_list) / len(model_metrics_list),
                        3
                    )
                    logger.info(f"✅ Ensemble confidence: {ensemble_confidence:.3f}")
        except Exception as e:
            logger.warning(f"⚠️  Could not load model metrics: {e}", exc_info=True)

        # Build ScoringResponse
        logger.info(f"📤 Returning ScoringResponse: score={lead_score.score}, grade={lead_score.grade.value}, model_metrics={len(model_metrics_list) if model_metrics_list else 0}")
        return ScoringResponse(
            success=True,
            lead_id=lead_input.lead_id,
            score=lead_score.score,
            grade=lead_score.grade,
            confidence=lead_score.confidence,
            freshness=lead_score.freshness.status,  # Extract status from FreshnessSignal
            recommended_action=lead_score.narrative.recommended_action
            if lead_score.narrative
            else "Deprioritize",
            summary=summary,
            drivers=drivers,
            limiters=limiters,
            pipeline_influence_score=int(
                (lead_score.pipeline_influence.pct * 100)
                if lead_score.pipeline_influence else 0
            ),
            adjustments_applied=adjustments,
            ace_scores=ace_scores,
            fitment=fitment,
            reduced_signal_model=reduced_signal_model,
            score_comparison=score_comparison,
            model_metrics=model_metrics_list,
            ensemble_confidence=ensemble_confidence,
            error=None,
        )

    except Exception as e:
        logger.error(f"❌ Error scoring lead {lead_input.lead_id}: {e}", exc_info=True)
        # Return error response
        return ScoringResponse(
            success=False,
            lead_id=lead_input.lead_id,
            score=0,
            grade=Grade.D,
            confidence="Low",
            freshness="Stale",
            recommended_action="Deprioritize",
            summary="Scoring failed due to data validation error.",
            drivers=[],
            limiters=["System error during scoring"],
            pipeline_influence_score=0,
            adjustments_applied=[],
            ace_scores=None,
            fitment=None,
            reduced_signal_model=None,
            score_comparison=None,
            model_metrics=None,
            ensemble_confidence=None,
            error=str(e),
        )


def score_reduced_signal_lead(
    lead_input: LeadInput,
    program_type: str = "nurture",
) -> ReducedSignalScoreResponse:
    """Return the reduced-signal score alongside ACE pillar context."""
    ace_response = score_single_lead(lead_input, program_type)
    if not ace_response.success or not ace_response.ace_scores or not ace_response.fitment:
        return ReducedSignalScoreResponse(
            success=False,
            lead_id=lead_input.lead_id,
            ace_scores=ACEPillarScores(accuracy=0, client_fit=0, engagement=0),
            fitment=FitmentRecommendation(
                segment="Unavailable",
                sales_readiness="Unavailable",
                best_motion="Unavailable",
                recommendation="Reduced-signal scoring could not be produced.",
            ),
            reduced_signal_model=ReducedSignalModelScore(
                model_name="ReducedSignalXGBoost",
                model_version="all_sample_data_reduced_signal_v1",
                score=0.0,
                confidence=0.0,
                r2_score=0.0,
                mae=0.0,
                rmse=0.0,
                feature_count=0,
            ),
            summary="Reduced-signal scoring failed.",
            error=ace_response.error or "Unable to score lead",
        )

    if not ace_response.reduced_signal_model:
        return ReducedSignalScoreResponse(
            success=False,
            lead_id=ace_response.lead_id,
            ace_scores=ace_response.ace_scores,
            fitment=ace_response.fitment,
            reduced_signal_model=ReducedSignalModelScore(
                model_name="ReducedSignalXGBoost",
                model_version="all_sample_data_reduced_signal_v1",
                score=0.0,
                confidence=0.0,
                r2_score=0.0,
                mae=0.0,
                rmse=0.0,
                feature_count=0,
            ),
            summary="Reduced-signal model artifacts are unavailable.",
            error="Reduced-signal model unavailable",
        )

    summary = (
        ace_response.score_comparison.summary
        if ace_response.score_comparison
        else "Reduced-signal score generated successfully."
    )
    return ReducedSignalScoreResponse(
        success=True,
        lead_id=ace_response.lead_id,
        ace_scores=ace_response.ace_scores,
        fitment=ace_response.fitment,
        reduced_signal_model=ace_response.reduced_signal_model,
        summary=summary,
        error=None,
    )


def compare_ace_and_reduced_signal(
    lead_input: LeadInput,
    program_type: str = "nurture",
) -> LeadScoreComparisonResponse:
    """Return the live ACE score and reduced-signal model score together."""
    ace_response = score_single_lead(lead_input, program_type)
    if (
        not ace_response.success
        or not ace_response.reduced_signal_model
        or not ace_response.score_comparison
        or not ace_response.fitment
    ):
        fallback_reduced = ace_response.reduced_signal_model or ReducedSignalModelScore(
            model_name="ReducedSignalXGBoost",
            model_version="all_sample_data_reduced_signal_v1",
            score=0.0,
            confidence=0.0,
            r2_score=0.0,
            mae=0.0,
            rmse=0.0,
            feature_count=0,
        )
        fallback_fitment = ace_response.fitment or FitmentRecommendation(
            segment="Unavailable",
            sales_readiness="Unavailable",
            best_motion="Unavailable",
            recommendation="Comparison unavailable.",
        )
        fallback_comparison = ace_response.score_comparison or ScoreComparison(
            ace_score=ace_response.score,
            reduced_signal_score=fallback_reduced.score,
            score_gap=round(fallback_reduced.score - ace_response.score, 1),
            higher_score_source="Unavailable",
            summary="ACE and reduced-signal comparison is unavailable.",
        )
        return LeadScoreComparisonResponse(
            success=False,
            lead_id=ace_response.lead_id,
            ace_scoring=ace_response,
            reduced_signal_model=fallback_reduced,
            score_comparison=fallback_comparison,
            fitment=fallback_fitment,
            error=ace_response.error or "Unable to compare scoring methods",
        )

    return LeadScoreComparisonResponse(
        success=True,
        lead_id=ace_response.lead_id,
        ace_scoring=ace_response,
        reduced_signal_model=ace_response.reduced_signal_model,
        score_comparison=ace_response.score_comparison,
        fitment=ace_response.fitment,
        error=None,
    )


def score_batch_leads(
    leads: List[LeadInput], program_type: str = "nurture"
) -> BatchScoringResponse:
    """
    Score multiple leads and return batch results.

    Args:
        leads: List of leads to score
        program_type: Program type (nurture, outbound, abm, event)

    Returns:
        BatchScoringResponse with all individual results and batch stats
    """
    results = []
    successful = 0
    failed = 0

    # Score each lead
    for lead_input in leads:
        response = score_single_lead(lead_input, program_type)
        results.append(response)
        if response.success:
            successful += 1
        else:
            failed += 1

    # Calculate batch summary statistics
    successful_results = [r for r in results if r.success]
    avg_score = (
        sum(r.score for r in successful_results) / len(successful_results)
        if successful_results
        else 0
    )

    grade_counts = {
        "A": sum(1 for r in successful_results if r.grade == Grade.A),
        "B": sum(1 for r in successful_results if r.grade == Grade.B),
        "C": sum(1 for r in successful_results if r.grade == Grade.C),
        "D": sum(1 for r in successful_results if r.grade == Grade.D),
    }

    batch_summary = {
        "average_score": round(avg_score, 1),
        "grade_distribution": grade_counts,
        "successful_leads": successful,
        "failed_leads": failed,
        "average_ace_scores": {
            "accuracy": round(
                sum(r.ace_scores.accuracy for r in successful_results if r.ace_scores)
                / len(successful_results),
                1,
            )
            if successful_results
            else 0.0,
            "client_fit": round(
                sum(r.ace_scores.client_fit for r in successful_results if r.ace_scores)
                / len(successful_results),
                1,
            )
            if successful_results
            else 0.0,
            "engagement": round(
                sum(r.ace_scores.engagement for r in successful_results if r.ace_scores)
                / len(successful_results),
                1,
            )
            if successful_results
            else 0.0,
        },
        "average_reduced_signal_score": round(
            sum(
                r.reduced_signal_model.score
                for r in successful_results
                if r.reduced_signal_model
            )
            / len([r for r in successful_results if r.reduced_signal_model]),
            1,
        )
        if any(r.reduced_signal_model for r in successful_results)
        else 0.0,
        "fitment_distribution": {
            segment: sum(
                1
                for r in successful_results
                if r.fitment and r.fitment.segment == segment
            )
            for segment in sorted(
                {
                    r.fitment.segment
                    for r in successful_results
                    if r.fitment
                }
            )
        },
        "comparison_summary": {
            source: sum(
                1
                for r in successful_results
                if r.score_comparison and r.score_comparison.higher_score_source == source
            )
            for source in sorted(
                {
                    r.score_comparison.higher_score_source
                    for r in successful_results
                    if r.score_comparison
                }
            )
        },
        "batch_timestamp": datetime.now().isoformat(),
    }

    return BatchScoringResponse(
        success=failed == 0,
        total_leads=len(leads),
        scored_leads=successful,
        failed_leads=failed,
        results=results,
        batch_summary=batch_summary,
    )
