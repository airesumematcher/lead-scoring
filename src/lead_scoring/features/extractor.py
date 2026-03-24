"""
Feature Extraction Orchestrator.

Combines all feature engineering modules (accuracy, client_fit, engagement, derived)
into a single feature extraction pipeline.
"""

from lead_scoring.models import LeadInput, ExtractedFeatures
from lead_scoring.features.accuracy import extract_accuracy_features
from lead_scoring.features.client_fit import extract_client_fit_features
from lead_scoring.features.engagement import extract_engagement_features
from lead_scoring.features.derived import extract_derived_features


def extract_all_features(lead: LeadInput) -> ExtractedFeatures:
    """
    Main feature extraction function.
    
    Flow:
    1. Extract Accuracy features (hard gate)
    2. Extract Client Fit features
    3. Extract Engagement features (with missing data handling)
    4. Compute derived cross-pillar features
    5. Return complete feature set
    """
    
    # Layer 1: Accuracy
    accuracy_features = extract_accuracy_features(lead)
    
    # Layer 2: Client Fit
    client_fit_features = extract_client_fit_features(lead)
    
    # Layer 3: Engagement
    engagement_features = extract_engagement_features(lead)
    
    # Layer 4: Derived (cross-pillar)
    derived_features = extract_derived_features(
        accuracy_features,
        client_fit_features,
        engagement_features
    )
    
    # Assemble complete feature set
    extracted_features = ExtractedFeatures(
        lead_id=lead.lead_id,
        accuracy=accuracy_features,
        client_fit=client_fit_features,
        engagement=engagement_features,
        derived=derived_features,
    )
    
    return extracted_features
