"""
Drift detection and analytics for feedback loop.
Monitors model performance degradation and triggers retraining.
"""

from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from collections import Counter

from lead_scoring.feedback.models import (
    LeadFeedback,
    FeedbackOutcome,
    DriftMetrics,
)


class DriftDetector:
    """Detects model performance drift from sales feedback."""
    
    BASELINE_ACCEPTANCE_RATE = 0.50  # 50% baseline
    DRIFT_THRESHOLD_PCT = 5.0  # 5% change triggers investigation
    CRITICAL_DRIFT_THRESHOLD_PCT = 10.0  # 10% triggers alert
    
    def __init__(self, baseline_acceptance_rate: float = 0.50):
        """
        Initialize drift detector.
        
        Args:
            baseline_acceptance_rate: Expected acceptance rate from training data
        """
        self.baseline_acceptance_rate = baseline_acceptance_rate
    
    def calculate_metrics(
        self,
        feedback_items: List[LeadFeedback],
        time_period_days: int = 7,
    ) -> DriftMetrics:
        """
        Calculate drift metrics from feedback.
        
        Args:
            feedback_items: List of feedback entries
            time_period_days: Period covered (for reporting)
        
        Returns:
            DriftMetrics with acceptance rates, score gaps, etc.
        """
        if not feedback_items:
            raise ValueError("Cannot calculate metrics from empty feedback list")
        
        # Separate by outcome
        accepted = [f for f in feedback_items if f.outcome == FeedbackOutcome.ACCEPTED]
        rejected = [f for f in feedback_items if f.outcome == FeedbackOutcome.REJECTED]
        total = len(feedback_items)
        
        # Acceptance rates
        acceptance_rate = len(accepted) / total
        acceptance_rate_change = (acceptance_rate - self.baseline_acceptance_rate) * 100
        rejection_rate = len(rejected) / total
        
        # Average scores
        avg_score_accepted = (
            sum(f.original_score for f in accepted) / len(accepted) if accepted else 0
        )
        avg_score_rejected = (
            sum(f.original_score for f in rejected) / len(rejected) if rejected else 0
        )
        score_gap = avg_score_accepted - avg_score_rejected
        
        # Grade distribution
        grade_dist = Counter(f.original_grade for f in feedback_items)
        grade_counts = {
            "A": grade_dist.get("A", 0),
            "B": grade_dist.get("B", 0),
            "C": grade_dist.get("C", 0),
            "D": grade_dist.get("D", 0),
        }
        
        # Top reasons
        top_accepted = (
            Counter(f.reason.value for f in accepted).most_common(1)[0][0]
            if accepted
            else None
        )
        top_rejected = (
            Counter(f.reason.value for f in rejected).most_common(1)[0][0]
            if rejected
            else None
        )
        
        return DriftMetrics(
            acceptance_rate=round(acceptance_rate, 3),
            acceptance_rate_change_pct=round(acceptance_rate_change, 1),
            rejection_rate=round(rejection_rate, 3),
            avg_score_accepted=round(avg_score_accepted, 1),
            avg_score_rejected=round(avg_score_rejected, 1),
            score_gap=round(score_gap, 1),
            grade_distribution=grade_counts,
            top_reason_accepted=top_accepted,
            top_reason_rejected=top_rejected,
            feedback_count=total,
            time_period_days=time_period_days,
        )
    
    def detect_drift(self, metrics: DriftMetrics) -> Tuple[str, str, float]:
        """
        Detect if drift has occurred.
        
        Args:
            metrics: DriftMetrics to analyze
        
        Returns:
            Tuple of (status, reason, severity_score)
            - status: "normal", "drift_detected", "critical_drift"
            - reason: Description of drift
            - severity_score: Numeric severity (0-1)
        """
        # Check acceptance rate change
        rate_change_abs = abs(metrics.acceptance_rate_change_pct)
        
        if rate_change_abs >= self.CRITICAL_DRIFT_THRESHOLD_PCT:
            return (
                "critical_drift",
                f"Acceptance rate changed by {metrics.acceptance_rate_change_pct:.1f}% "
                f"(from {self.baseline_acceptance_rate:.1%} to {metrics.acceptance_rate:.1%})",
                min(1.0, rate_change_abs / 20.0),  # Normalize to 0-1
            )
        elif rate_change_abs >= self.DRIFT_THRESHOLD_PCT:
            return (
                "drift_detected",
                f"Acceptance rate changed by {metrics.acceptance_rate_change_pct:.1f}% "
                f"(from {self.baseline_acceptance_rate:.1%} to {metrics.acceptance_rate:.1%})",
                rate_change_abs / 10.0,
            )
        
        # Check score gap (accepted vs rejected should be positive and >10)
        if metrics.score_gap < 5:
            return (
                "drift_detected",
                f"Poor discrimination: accepted score ({metrics.avg_score_accepted:.0f}) "
                f"is too close to rejected score ({metrics.avg_score_rejected:.0f})",
                0.5,
            )
        
        return ("normal", "Model performance within expected parameters", 0.0)
    
    def summarize_feedback(self, feedback_items: List[LeadFeedback]) -> Dict[str, any]:
        """
        Create a summary report of feedback.
        
        Args:
            feedback_items: List of feedback entries
        
        Returns:
            Summary dict with key insights
        """
        if not feedback_items:
            return {"total": 0, "summary": "No feedback to summarize"}
        
        metrics = self.calculate_metrics(feedback_items)
        drift_status, drift_reason, severity = self.detect_drift(metrics)
        
        return {
            "total_feedback": metrics.feedback_count,
            "period_days": metrics.time_period_days,
            "acceptance_rate": f"{metrics.acceptance_rate:.1%}",
            "rejection_rate": f"{metrics.rejection_rate:.1%}",
            "rate_change": f"{metrics.acceptance_rate_change_pct:+.1f}%",
            "avg_score_accepted": metrics.avg_score_accepted,
            "avg_score_rejected": metrics.avg_score_rejected,
            "score_gap": metrics.score_gap,
            "grade_distribution": metrics.grade_distribution,
            "drift_status": drift_status,
            "drift_reason": drift_reason,
            "drift_severity": severity,
            "top_reason_accepted": metrics.top_reason_accepted or "N/A",
            "top_reason_rejected": metrics.top_reason_rejected or "N/A",
        }


class RetrainingScheduler:
    """Determines when to retrain the model."""
    
    def __init__(
        self,
        min_feedback_count: int = 100,
        max_days_since_retrain: int = 30,
    ):
        """
        Initialize retraining scheduler.
        
        Args:
            min_feedback_count: Minimum feedback items needed before retraining
            max_days_since_retrain: Max days before forcing retraining
        """
        self.min_feedback_count = min_feedback_count
        self.max_days_since_retrain = max_days_since_retrain
    
    def should_retrain(
        self,
        feedback_count: int,
        drift_status: str,
        last_retrain_date: Optional[datetime] = None,
    ) -> Tuple[bool, str]:
        """
        Determine if retraining is needed.
        
        Args:
            feedback_count: Number of feedback items since last train
            drift_status: Drift status ("normal", "drift_detected", "critical_drift")
            last_retrain_date: When model was last retrained
        
        Returns:
            Tuple of (should_retrain: bool, reason: str)
        """
        reasons = []
        
        # Critical drift always triggers retraining
        if drift_status == "critical_drift":
            return True, "Critical drift detected in model performance"
        
        # Drift with enough data triggers retraining
        if drift_status == "drift_detected" and feedback_count >= self.min_feedback_count:
            return True, f"Drift detected with {feedback_count} feedback items"
        
        # Schedule-based retraining
        if last_retrain_date:
            days_since = (datetime.utcnow() - last_retrain_date).days
            if days_since >= self.max_days_since_retrain:
                return True, f"Scheduled retraining ({days_since} days since last train)"
        
        # Sufficient feedback accumulated
        if feedback_count >= self.min_feedback_count and last_retrain_date is None:
            # First retraining with enough data
            return True, f"Initial retraining with {feedback_count} feedback items"
        
        return False, f"Not enough data or drift ({feedback_count} items, status: {drift_status})"
    
    def next_retrain_opportunity(
        self,
        feedback_count: int,
        drift_status: str,
        last_retrain_date: Optional[datetime] = None,
    ) -> Dict[str, any]:
        """
        Calculate when next retraining opportunity is.
        
        Returns:
            Dict with timing information
        """
        should_retrain, reason = self.should_retrain(
            feedback_count, drift_status, last_retrain_date
        )
        
        items_needed = max(0, self.min_feedback_count - feedback_count)
        
        if last_retrain_date:
            days_since = (datetime.utcnow() - last_retrain_date).days
            days_remaining = max(0, self.max_days_since_retrain - days_since)
        else:
            days_remaining = "N/A"
        
        return {
            "should_retrain_now": should_retrain,
            "reason": reason,
            "current_feedback_count": feedback_count,
            "items_needed_for_retrain": items_needed,
            "days_since_last_retrain": days_since if last_retrain_date else "N/A",
            "days_until_scheduled_retrain": days_remaining,
        }
