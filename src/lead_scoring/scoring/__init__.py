"""Scoring modules: Layer 1 gates, Layer 2 composite scoring, and output assembly."""

from lead_scoring.scoring.scorer import score_lead, score_leads_batch
from lead_scoring.scoring.layer1_gate import apply_accuracy_gates, AccuracyGateResult
from lead_scoring.scoring.layer2_scorer import compute_composite_score, Layer2ScoringResult
from lead_scoring.scoring.score_builder import assemble_lead_score

__all__ = [
    'score_lead',
    'score_leads_batch',
    'apply_accuracy_gates',
    'AccuracyGateResult',
    'compute_composite_score',
    'Layer2ScoringResult',
    'assemble_lead_score',
]
