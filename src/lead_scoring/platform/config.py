"""Configuration loader for the revised PRD runtime."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml


CONFIG_PATH = Path(__file__).resolve().parents[3] / "config" / "platform_config.yaml"


@lru_cache(maxsize=1)
def load_platform_config() -> dict[str, Any]:
    """Load the platform configuration from disk once per process."""
    with open(CONFIG_PATH, "r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}
