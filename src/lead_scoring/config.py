"""
Configuration management for lead scoring.
Loads YAML configuration with defaults.
"""

import os
import yaml
from pathlib import Path
from typing import Dict, Any, Optional


class ScoringConfig:
    """Lead scoring configuration holder."""
    
    def __init__(self, config_dict: Dict[str, Any]):
        self.config = config_dict
    
    # ACE Weights by program type
    def get_weights(self, program_type: str = "nurture") -> Dict[str, float]:
        """Get ACE weights for program type."""
        weights = self.config.get("ace_weights", {}).get(program_type.lower())
        if not weights:
            return {"accuracy": 0.30, "client_fit": 0.40, "engagement": 0.30}
        return weights
    
    # Score to Grade boundaries
    def get_grade_boundaries(self) -> Dict[str, int]:
        """Get score-to-grade mapping."""
        return self.config.get("grade_boundaries", {
            "A": 85,
            "B": 70,
            "C": 50,
        })
    
    # Time decay parameters
    def get_engagement_decay_rate(self) -> float:
        """Get engagement time decay rate."""
        return self.config.get("time_decay", {}).get("engagement_rate", 0.1)
    
    def get_freshness_decay_rates(self) -> Dict[str, float]:
        """Get freshness decay rates (slow vs fast)."""
        decay_cfg = self.config.get("time_decay", {}).get("freshness", {})
        return {
            "slow": decay_cfg.get("high_quality_rate", 0.02),
            "fast": decay_cfg.get("low_quality_rate", 0.05),
        }
    
    # Freshness thresholds
    def get_freshness_thresholds(self) -> Dict[str, int]:
        """Get freshness signal thresholds (in days)."""
        return self.config.get("freshness_thresholds", {
            "fresh": 7,
            "aging": 30,
            "stale": 999,
        })
    
    # Confidence thresholds
    def get_confidence_thresholds(self) -> Dict[str, int]:
        """Get confidence band thresholds (signal count)."""
        return self.config.get("confidence_thresholds", {
            "high": 12,
            "medium": 8,
        })
    
    # Accuracy gate thresholds
    def get_accuracy_gates(self) -> Dict[str, Any]:
        """Get accuracy hard gate rules."""
        return self.config.get("accuracy_gates", {
            "max_delivery_latency_days": 60,
            "max_duplicate_age_days": 30,
        })
    
    # Model metadata
    def get_model_version(self) -> str:
        """Get model version."""
        return self.config.get("model", {}).get("version", "0.1.0")
    
    def get_training_data_date(self) -> str:
        """Get training data date."""
        return self.config.get("model", {}).get("training_date", "2026-03-01")


def load_config(config_path: Optional[str] = None) -> ScoringConfig:
    """
    Load configuration from YAML file.
    
    Args:
        config_path: Path to config YAML. If None, looks for default locations.
    
    Returns:
        ScoringConfig instance
    """
    if config_path is None:
        # Look for config in default locations
        default_paths = [
            "config/scoring_config.yaml",
            "./config/scoring_config.yaml",
            os.path.expanduser("~/.lead-scoring/config.yaml"),
        ]
        for path in default_paths:
            if os.path.exists(path):
                config_path = path
                break
    
    if not config_path or not os.path.exists(config_path):
        # Return default config
        return ScoringConfig(_default_config())
    
    # Load YAML
    with open(config_path, 'r') as f:
        config_dict = yaml.safe_load(f) or {}
    
    return ScoringConfig(config_dict)


def _default_config() -> Dict[str, Any]:
    """Return default configuration."""
    return {
        "model": {
            "version": "0.1.0",
            "training_date": "2026-03-01",
        },
        "ace_weights": {
            "nurture": {"accuracy": 0.30, "client_fit": 0.40, "engagement": 0.30},
            "outbound": {"accuracy": 0.35, "client_fit": 0.30, "engagement": 0.35},
            "abm": {"accuracy": 0.25, "client_fit": 0.40, "engagement": 0.35},
            "event": {"accuracy": 0.30, "client_fit": 0.35, "engagement": 0.35},
        },
        "grade_boundaries": {
            "A": 85,
            "B": 70,
            "C": 50,
        },
        "time_decay": {
            "engagement_rate": 0.1,
            "freshness": {
                "high_quality_rate": 0.02,
                "low_quality_rate": 0.05,
            },
        },
        "freshness_thresholds": {
            "fresh": 7,
            "aging": 30,
            "stale": 999,
        },
        "confidence_thresholds": {
            "high": 12,
            "medium": 8,
        },
        "accuracy_gates": {
            "max_delivery_latency_days": 60,
            "max_duplicate_age_days": 30,
        },
    }
