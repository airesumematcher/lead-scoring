"""
Layer 1: Rules-Based Accuracy Gatekeeping.

Hard gates that determine if a lead can be scored at all.
If any gate fails, score is blocked and lead is flagged for manual review/enrichment.
"""

from lead_scoring.models import ExtractedFeatures, Grade
from lead_scoring.config import ScoringConfig


class AccuracyGateResult:
    """Result of Layer 1 gatekeeping."""
    
    def __init__(self, passed: bool, reason: str = "", recommended_accuracy_ceiling: int = 100):
        self.passed = passed
        self.reason = reason
        self.recommended_accuracy_ceiling = recommended_accuracy_ceiling


def apply_accuracy_gates(features: ExtractedFeatures, config: ScoringConfig) -> AccuracyGateResult:
    """
    Apply hard gates to Accuracy pillar.
    
    Rules:
    1. If email_valid = False → BLOCK (cannot reach lead)
    2. If delivery_success = False → BLOCK (delivery failed)
    3. If delivery_latency > 60 days → cap score at 60 (stale window)
    4. If duplicate_risk = True → cap score at 85 (contact fatigue, don't prioritize)
    
    Returns:
        AccuracyGateResult with passed flag and recommended ceiling
    """
    
    accuracy = features.accuracy
    gates_config = config.get_accuracy_gates()
    
    # Gate 1: Email validity (hard fail)
    if not accuracy.email_valid:
        return AccuracyGateResult(
            passed=False,
            reason="Email validation failed - cannot reach lead; requires enrichment",
            recommended_accuracy_ceiling=0
        )
    
    # Gate 2: Delivery success (hard fail)
    if not accuracy.lead_delivery_success:
        return AccuracyGateResult(
            passed=False,
            reason="Lead delivery failed after multiple attempts; verify delivery partner quality",
            recommended_accuracy_ceiling=0
        )
    
    # Gate 3: Delivery latency (soft gate - caps score)
    max_latency = gates_config.get("max_delivery_latency_days", 60)
    if accuracy.delivery_latency_days > max_latency:
        return AccuracyGateResult(
            passed=True,  # Soft gate: can score but capped
            reason=f"Delivery latency {accuracy.delivery_latency_days} days exceeds threshold ({max_latency} days); score capped at 60",
            recommended_accuracy_ceiling=60
        )
    
    # Gate 4: Duplicate risk (soft gate - caps score)
    if accuracy.duplicate_risk:
        return AccuracyGateResult(
            passed=True,  # Soft gate: can score but capped
            reason="Duplicate contact within 30 days; avoid contact fatigue; score capped at 85",
            recommended_accuracy_ceiling=85
        )
    
    # All gates passed
    return AccuracyGateResult(
        passed=True,
        reason="All accuracy gates passed",
        recommended_accuracy_ceiling=100
    )
