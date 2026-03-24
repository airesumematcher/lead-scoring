"""Utility functions for lead scoring."""

import hashlib
from datetime import datetime
from typing import Dict, Any


def compute_feature_hash(feature_dict: Dict[str, Any]) -> str:
    """Compute MD5 hash of features for audit trail."""
    feature_str = str(sorted(feature_dict.items()))
    return hashlib.md5(feature_str.encode()).hexdigest()


def grade_from_score(score: int) -> str:
    """Map composite score to grade (A/B/C/D)."""
    if score >= 85:
        return "A"
    elif score >= 70:
        return "B"
    elif score >= 50:
        return "C"
    else:
        return "D"


def confidence_from_signal_count(signal_count: int, accuracy_subscore: int) -> str:
    """Determine confidence band from signal count."""
    if accuracy_subscore < 60:
        return "Low"
    elif signal_count >= 12:
        return "High"
    elif signal_count >= 8:
        return "Medium"
    else:
        return "Low"


def freshness_from_recency(days_since_engagement: int, days_since_delivery: int = 0) -> str:
    """Determine freshness signal (Fresh/Aging/Stale)."""
    if days_since_engagement <= 7 or (days_since_delivery <= 14 and days_since_engagement < 999):
        return "Fresh"
    elif days_since_engagement <= 30:
        return "Aging"
    else:
        return "Stale"


def get_timestamp_iso() -> str:
    """Get current UTC timestamp in ISO format."""
    return datetime.utcnow().isoformat() + "Z"
