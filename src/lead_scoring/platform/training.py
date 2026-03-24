"""Monthly retraining support for the revised PRD setup."""

from __future__ import annotations

import json
import pickle
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import train_test_split

from .contracts import RetrainResult


MODEL_DIR = Path(__file__).resolve().parents[3] / "models" / "prd_runtime"
MODEL_DIR.mkdir(parents=True, exist_ok=True)

FEATURE_COLUMNS = [
    "authority_score",
    "fit_score",
    "intent_score",
    "partner_signal_score",
    "client_history_score",
    "campaign_history_score",
    "data_quality_score",
    "icp_match_score",
    "buying_group_score",
    "unique_persona_count",
    "late_stage_signal",
    "email_engagement_score",
    "second_touch_signal",
    "recency_score",
]

STATUS_MAP = {
    "approved": 1,
    "accept": 1,
    "accepted": 1,
    "delivered": 1,
    "rejected": 0,
    "refund": 0,
    "refunded": 0,
}


@dataclass(frozen=True)
class TrainingArtifacts:
    """Paths to promoted model artifacts."""

    model_path: Path
    metadata_path: Path
    signal_tables_path: Path


def run_monthly_retrain(dataset_path: str, force_promote: bool = False) -> RetrainResult:
    """Train a lead quality classifier when a PRD feature table is available."""
    dataset = Path(dataset_path).expanduser().resolve()
    if not dataset.exists():
        return RetrainResult(
            success=False,
            dataset_path=str(dataset),
            model_promoted=False,
            evaluation={},
            message=f"Dataset not found: {dataset}",
        )

    frame = pd.read_csv(dataset)
    signal_tables_path = MODEL_DIR / "signal_tables.json"
    signal_tables = _build_signal_tables(frame)
    with open(signal_tables_path, "w", encoding="utf-8") as handle:
        json.dump(signal_tables, handle, indent=2)

    if "status" not in frame.columns:
        return RetrainResult(
            success=True,
            dataset_path=str(dataset),
            model_promoted=False,
            evaluation={"signal_tables_only": True},
            signal_tables_path=str(signal_tables_path),
            message=(
                "Signal tables refreshed. Model training skipped because the dataset "
                "does not include a 'status' column."
            ),
        )

    labels = frame["status"].astype(str).str.lower().map(STATUS_MAP)
    trainable = frame.copy()
    trainable["target"] = labels
    trainable = trainable.dropna(subset=["target"])
    available_features = [column for column in FEATURE_COLUMNS if column in trainable.columns]

    if len(available_features) < 5:
        return RetrainResult(
            success=True,
            dataset_path=str(dataset),
            model_promoted=False,
            evaluation={
                "signal_tables_only": True,
                "available_features": available_features,
            },
            signal_tables_path=str(signal_tables_path),
            message=(
                "Signal tables refreshed. Model training skipped because the PRD "
                "feature table columns were not present."
            ),
        )

    model_frame = trainable[available_features + ["target"]].dropna()
    if model_frame["target"].nunique() < 2:
        return RetrainResult(
            success=True,
            dataset_path=str(dataset),
            model_promoted=False,
            evaluation={"class_balance_error": True},
            signal_tables_path=str(signal_tables_path),
            message="Signal tables refreshed. Model training skipped because labels contain only one class.",
        )

    train_x, test_x, train_y, test_y = train_test_split(
        model_frame[available_features],
        model_frame["target"],
        test_size=0.2,
        random_state=42,
        stratify=model_frame["target"],
    )

    model = GradientBoostingClassifier(random_state=42)
    model.fit(train_x, train_y)
    probabilities = model.predict_proba(test_x)[:, 1]
    auc = float(roc_auc_score(test_y, probabilities))
    top_decile_precision = _top_decile_precision(probabilities, test_y)

    metadata = {
        "model_version": f"prd_runtime_gbc_{pd.Timestamp.utcnow().strftime('%Y%m%d%H%M%S')}",
        "trained_at": pd.Timestamp.utcnow().isoformat(),
        "feature_columns": available_features,
        "auc_roc": auc,
        "top_decile_precision": top_decile_precision,
        "records_used": int(len(model_frame)),
    }
    promoted = force_promote or _should_promote(metadata)

    model_path = MODEL_DIR / "lead_quality_model.pkl"
    metadata_path = MODEL_DIR / "model_metadata.json"
    if promoted:
        with open(model_path, "wb") as handle:
            pickle.dump(model, handle)
        with open(metadata_path, "w", encoding="utf-8") as handle:
            json.dump(metadata, handle, indent=2)

    return RetrainResult(
        success=True,
        dataset_path=str(dataset),
        model_promoted=promoted,
        evaluation={
            "auc_roc": round(auc, 4),
            "top_decile_precision": round(top_decile_precision, 4),
            "records_used": len(model_frame),
            "feature_columns": available_features,
        },
        signal_tables_path=str(signal_tables_path),
        model_path=str(model_path) if promoted else None,
        metadata_path=str(metadata_path) if promoted else None,
        message=(
            "Retraining completed and model promoted."
            if promoted
            else "Retraining completed, but the model was not promoted because the baseline remains stronger."
        ),
    )


def _build_signal_tables(frame: pd.DataFrame) -> dict[str, Any]:
    """Create partner/client/vertical approval lookups from a labelled dataset."""
    if "status" not in frame.columns:
        return {"message": "status column missing; no approval tables built"}

    working = frame.copy()
    working["target"] = working["status"].astype(str).str.lower().map(STATUS_MAP)
    working = working.dropna(subset=["target"])
    output: dict[str, Any] = {}
    for column in ("partner_id", "client_id", "vertical", "campaign_id"):
        if column in working.columns:
            grouped = (
                working.groupby(column)["target"]
                .mean()
                .sort_values(ascending=False)
                .round(4)
                .to_dict()
            )
            output[column] = grouped
    return output


def _should_promote(candidate_metadata: dict[str, Any]) -> bool:
    """Promote when there is no baseline or the AUC improves."""
    metadata_path = MODEL_DIR / "model_metadata.json"
    if not metadata_path.exists():
        return True
    with open(metadata_path, "r", encoding="utf-8") as handle:
        current = json.load(handle)
    return float(candidate_metadata.get("auc_roc", 0.0)) >= float(current.get("auc_roc", 0.0))


def _top_decile_precision(probabilities: Any, truth: pd.Series) -> float:
    """Compute precision in the top 10% scored rows."""
    if len(truth) == 0:
        return 0.0
    probability_series = pd.Series(probabilities).reset_index(drop=True)
    truth_series = pd.Series(truth).reset_index(drop=True)
    threshold = probability_series.quantile(0.9)
    selected = truth_series[probability_series >= threshold]
    if len(selected) == 0:
        return 0.0
    return float(selected.mean())
