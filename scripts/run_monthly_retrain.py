#!/usr/bin/env python3
"""CLI wrapper for the revised monthly retraining workflow."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from lead_scoring.platform import BuyingIntelligenceService


DEFAULT_DATASET = ROOT / "data_processed" / "verify_prd_training.csv"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the ACE monthly retraining workflow.")
    parser.add_argument(
        "dataset_path",
        nargs="?",
        default=str(DEFAULT_DATASET),
        help=(
            "Path to the PRD feature table CSV (must include a 'status' column). "
            f"Defaults to {DEFAULT_DATASET}"
        ),
    )
    parser.add_argument(
        "--force-promote",
        action="store_true",
        help="Promote the trained model even if the baseline AUC is higher.",
    )
    args = parser.parse_args()

    service = BuyingIntelligenceService()
    result = service.run_retrain(args.dataset_path, force_promote=args.force_promote)
    print(json.dumps(result.model_dump(), indent=2))
    return 0 if result.success else 1


if __name__ == "__main__":
    raise SystemExit(main())
