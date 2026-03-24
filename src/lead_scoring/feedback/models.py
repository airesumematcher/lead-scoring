"""
Feedback data models for post-launch model improvement.
Tracks sales decisions and enables drift detection + retraining.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field


class FeedbackOutcome(str, Enum):
    """Sales outcome for a lead."""
    ACCEPTED = "accepted"  # Sales team engaged with lead
    REJECTED = "rejected"  # Sales team passed on lead
    NEUTRAL = "neutral"    # Insufficient action/data


class FeedbackReason(str, Enum):
    """Reason for sales decision."""
    # Accepted reasons
    MATCHED_EXPECTATIONS = "matched_expectations"
    EXCELLENT_FIT = "excellent_fit"
    STRONG_ENGAGEMENT = "strong_engagement"
    TAL_PRIORITY = "tal_priority"
    
    # Rejected reasons
    POOR_FIT = "poor_fit"
    DEAD_LEAD = "dead_lead"
    WRONG_PERSONA = "wrong_persona"
    LOW_QUALITY_DATA = "low_quality_data"
    TIMING_ISSUE = "timing_issue"
    DUPLICATE = "duplicate"
    
    # Neutral
    UNCLEAR = "unclear"
    INSUFFICIENT_DATA = "insufficient_data"


class LeadFeedback(BaseModel):
    """Individual lead feedback from sales team."""
    lead_id: str = Field(..., description="Original lead ID")
    scored_at: datetime = Field(..., description="When lead was scored")
    feedback_at: datetime = Field(..., description="When feedback was provided")
    
    outcome: FeedbackOutcome = Field(..., description="Sales decision")
    reason: FeedbackReason = Field(..., description="Reason for decision")
    notes: Optional[str] = Field(None, description="Sales notes/comments")
    
    # Context for drift analysis
    original_score: int = Field(..., ge=0, le=100, description="Original lead score (0-100)")
    original_grade: str = Field(..., description="Original lead grade (A/B/C/D)")
    sal_decision_maker: Optional[str] = Field(None, description="SAL/sales person who provided feedback")
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "lead_id": "L-10001",
                "scored_at": "2026-03-10T14:30:00",
                "feedback_at": "2026-03-12T16:45:00",
                "outcome": "accepted",
                "reason": "matched_expectations",
                "notes": "Great fit for Q2 pipeline, high intent signals.",
                "original_score": 62,
                "original_grade": "C",
                "sal_decision_maker": "alice@sales.com",
            }
        }
    }


class BatchFeedback(BaseModel):
    """Batch feedback submission."""
    feedback_items: List[LeadFeedback] = Field(..., min_items=1, description="Feedback entries")
    batch_id: Optional[str] = Field(None, description="Batch identifier")
    submitter: Optional[str] = Field(None, description="Person/system submitting feedback")
    submitted_at: datetime = Field(default_factory=datetime.utcnow)


class DriftMetrics(BaseModel):
    """Drift detection metrics."""
    acceptance_rate: float = Field(..., ge=0, le=1, description="Fraction of leads accepted (0-1)")
    acceptance_rate_change_pct: float = Field(..., description="Change from baseline (%)")
    rejection_rate: float = Field(..., ge=0, le=1, description="Fraction of leads rejected (0-1)")
    
    avg_score_accepted: float = Field(..., ge=0, le=100, description="Average score for accepted leads")
    avg_score_rejected: float = Field(..., ge=0, le=100, description="Average score for rejected leads")
    score_gap: float = Field(..., description="Difference (accepted - rejected)")
    
    grade_distribution: Dict[str, int] = Field(..., description="Count by grade (A/B/C/D)")
    
    top_reason_accepted: Optional[str] = Field(None, description="Most common acceptance reason")
    top_reason_rejected: Optional[str] = Field(None, description="Most common rejection reason")
    
    feedback_count: int = Field(..., ge=0, description="Number of feedback items analyzed")
    time_period_days: int = Field(..., ge=1, description="Period covered (days)")


class RetariningTrigger(BaseModel):
    """Retraining trigger event."""
    trigger_type: str = Field(..., description="Type of trigger (drift, schedule, manual)")
    triggered_at: datetime = Field(default_factory=datetime.utcnow)
    
    reason: str = Field(..., description="Reason for retraining")
    metrics: Optional[DriftMetrics] = Field(None, description="Associated drift metrics")
    
    recommended_action: str = Field(..., description="Recommended action (retrain, monitor, investigate)")
    severity: str = Field(..., enum=["low", "medium", "high"], description="Severity level")
    
    notes: Optional[str] = Field(None, description="Additional context")


class RetrainingJob(BaseModel):
    """Retraining job execution record."""
    job_id: str = Field(..., description="Unique job ID")
    triggered_by: RetariningTrigger = Field(..., description="Trigger that initiated retraining")
    
    status: str = Field(..., enum=["pending", "running", "completed", "failed"], description="Job status")
    started_at: Optional[datetime] = Field(None, description="Job start timestamp")
    completed_at: Optional[datetime] = Field(None, description="Job completion timestamp")
    
    training_data_size: Optional[int] = Field(None, description="Number of feedback items used for training")
    model_version_prev: str = Field(..., description="Previous model version")
    model_version_new: Optional[str] = Field(None, description="New model version after retraining")
    
    performance_metrics: Optional[Dict[str, float]] = Field(None, description="Performance on test set")
    error_message: Optional[str] = Field(None, description="Error if job failed")


class AcceptanceGuardrail(BaseModel):
    """Guardrails to prevent model bias and overfit."""
    max_single_client_influence_pct: float = Field(
        default=30.0,
        ge=0,
        le=100,
        description="Max % of training data from single client (30%)"
    )
    min_sample_size_per_class: int = Field(
        default=100,
        ge=1,
        description="Min samples needed per outcome class before retraining"
    )
    max_score_skew_pct: float = Field(
        default=15.0,
        ge=0,
        le=100,
        description="Max acceptable % skew in score distribution"
    )
    
    def check_guardrails(self, feedback: List[LeadFeedback]) -> Dict[str, Any]:
        """
        Check if feedback data violates guardrails.
        
        Returns:
            Dict with pass/warnings/errors
        """
        result = {
            "passed": True,
            "warnings": [],
            "errors": [],
        }
        
        # Check sample size
        accepted_count = sum(1 for f in feedback if f.outcome == FeedbackOutcome.ACCEPTED)
        rejected_count = sum(1 for f in feedback if f.outcome == FeedbackOutcome.REJECTED)
        
        if accepted_count < self.min_sample_size_per_class:
            result["warnings"].append(
                f"Low accepted sample size: {accepted_count} < {self.min_sample_size_per_class}"
            )
        if rejected_count < self.min_sample_size_per_class:
            result["warnings"].append(
                f"Low rejected sample size: {rejected_count} < {self.min_sample_size_per_class}"
            )
        
        # Check for extreme acceptance rate
        total = len(feedback)
        acceptance_rate = accepted_count / total if total > 0 else 0
        
        if acceptance_rate > (1.0 - self.max_score_skew_pct / 100) or acceptance_rate < (self.max_score_skew_pct / 100):
            result["warnings"].append(
                f"Extreme acceptance rate: {acceptance_rate:.1%} (expected 30-70%)"
            )
        
        # Check single client influence
        if feedback:
            sal_counts = {}
            for f in feedback:
                if f.sal_decision_maker:
                    sal_counts[f.sal_decision_maker] = sal_counts.get(f.sal_decision_maker, 0) + 1
            
            for sal, count in sal_counts.items():
                influence = (count / total) * 100
                if influence > self.max_single_client_influence_pct:
                    result["errors"].append(
                        f"Single SAL influence too high: {sal} has {influence:.1f}% "
                        f"(max {self.max_single_client_influence_pct}%)"
                    )
        
        result["passed"] = len(result["errors"]) == 0
        return result
