"""
Main Scoring Pipeline Orchestrator.

Complete end-to-end scoring: Extract features → Apply gates → Score → Build output.
"""

from lead_scoring.models import LeadInput, LeadScore
from lead_scoring.features import extract_all_features
from lead_scoring.config import ScoringConfig
from lead_scoring.scoring.layer1_gate import apply_accuracy_gates
from lead_scoring.scoring.layer2_scorer import compute_composite_score
from lead_scoring.scoring.score_builder import assemble_lead_score


def score_lead(lead: LeadInput, config: ScoringConfig) -> LeadScore:
    """
    Complete lead scoring pipeline.
    
    Steps:
    1. Extract all features (Accuracy, Client Fit, Engagement, Derived)
    2. Apply Layer 1 accuracy gates (hard pass/fail checks)
    3. Compute Layer 2 score (weighted ACE composite)
    4. Assemble final LeadScore output
    
    Args:
        lead: LeadInput with contact, company, campaign, engagement data
        config: ScoringConfig with weights, thresholds, decay rates
    
    Returns:
        LeadScore: Complete scoring output with all fields
    """
    
    # Step 1: Feature Extraction
    features = extract_all_features(lead)
    
    # Step 2: Layer 1 - Accuracy Gates
    gate_result = apply_accuracy_gates(features, config)
    
    # Step 3: Layer 2 - Composite Score
    accuracy_ceiling = gate_result.recommended_accuracy_ceiling
    
    scoring_result = compute_composite_score(
        features,
        program_type=lead.campaign.program_type.value,
        config=config,
        accuracy_ceiling=accuracy_ceiling,
    )
    
    # Step 4: Assemble LeadScore
    lead_score = assemble_lead_score(
        lead,
        features,
        gate_result,
        scoring_result,
        config,
    )
    
    return lead_score


def score_leads_batch(leads: list, config: ScoringConfig) -> list:
    """
    Score multiple leads in batch.
    
    Args:
        leads: List of LeadInput objects
        config: ScoringConfig
    
    Returns:
        List of LeadScore objects
    """
    return [score_lead(lead, config) for lead in leads]
