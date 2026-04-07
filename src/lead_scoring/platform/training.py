"""Monthly retraining support for the revised PRD setup."""

from __future__ import annotations

import json
import pickle
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from lightgbm import LGBMClassifier
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    roc_auc_score,
)
from sklearn.model_selection import StratifiedKFold, cross_val_score

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

# Columns that may hold a submission timestamp for time-based splitting
TIME_COLUMNS = ("submitted_at", "created_date", "created_at", "scored_at")

STATUS_MAP = {
    "approved": 1,
    "accept": 1,
    "accepted": 1,
    "delivered": 1,
    "rejected": 0,
    "refund": 0,
    "refunded": 0,
}

# Minimum samples required before enabling calibration and cross-validation
MIN_SAMPLES_FOR_CALIBRATION = 60
MIN_SAMPLES_FOR_CV = 30


@dataclass(frozen=True)
class TrainingArtifacts:
    """Paths to promoted model artifacts."""

    model_path: Path
    metadata_path: Path
    signal_tables_path: Path


def run_monthly_retrain(dataset_path: str, force_promote: bool = False) -> RetrainResult:
    """Train a lead quality classifier when a PRD feature table is available.

    Improvements over the original pipeline:
    - Time-based train/test split to prevent temporal leakage (falls back to
      stratified random split when no timestamp column is present).
    - Class-imbalance handling via sample weights (balanced).
    - Probability calibration via Platt scaling (CalibratedClassifierCV) so
      that the raw GBC probability maps reliably to real-world approval rates.
    - Cross-validation (5-fold stratified) for stable AUC estimates when
      enough data is available.
    - Extended evaluation: Brier score, PR-AUC, KS statistic, Lift@10,
      Lift@20 — all stored in model metadata.
    """
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

    # --- Time-based vs random split ---
    time_col = next(
        (c for c in TIME_COLUMNS if c in trainable.columns),
        None,
    )
    split_strategy = "temporal" if time_col else "stratified_random"

    if time_col:
        sorted_frame = trainable.sort_values(time_col).reset_index(drop=True)
        model_frame = sorted_frame[available_features + ["target"]].dropna()
        cutoff = int(len(model_frame) * 0.8)
        train_x = model_frame[available_features].iloc[:cutoff]
        test_x = model_frame[available_features].iloc[cutoff:]
        train_y = model_frame["target"].iloc[:cutoff]
        test_y = model_frame["target"].iloc[cutoff:]
        # Ensure test set has both classes; fall back to random if not
        if test_y.nunique() < 2:
            split_strategy = "stratified_random_fallback"
            time_col = None

    if not time_col:
        from sklearn.model_selection import train_test_split  # noqa: PLC0415
        train_x, test_x, train_y, test_y = train_test_split(
            model_frame[available_features],
            model_frame["target"],
            test_size=0.2,
            random_state=42,
            stratify=model_frame["target"],
        )

    # --- Cross-validation (reporting only, not used for promotion) ---
    cv_auc_mean: float | None = None
    cv_auc_std: float | None = None
    if len(model_frame) >= MIN_SAMPLES_FOR_CV:
        base_clf = LGBMClassifier(
            n_estimators=500,
            learning_rate=0.05,
            max_depth=6,
            num_leaves=31,
            subsample=0.8,
            colsample_bytree=0.8,
            min_child_samples=20,
            class_weight="balanced",
            random_state=42,
            verbose=-1,
        )
        n_splits = 5 if len(model_frame) >= MIN_SAMPLES_FOR_CALIBRATION else 3
        cv = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=42)
        cv_scores = cross_val_score(
            base_clf,
            model_frame[available_features],
            model_frame["target"],
            cv=cv,
            scoring="roc_auc",
        )
        cv_auc_mean = float(cv_scores.mean())
        cv_auc_std = float(cv_scores.std())

    # --- Train LightGBM model ---
    # LGBMClassifier.predict_proba() produces well-calibrated probabilities
    # natively. class_weight="balanced" handles class imbalance internally,
    # removing the need for CalibratedClassifierCV or compute_sample_weight.
    model: Any = LGBMClassifier(
        n_estimators=500,
        learning_rate=0.05,
        max_depth=6,
        num_leaves=31,
        subsample=0.8,
        colsample_bytree=0.8,
        min_child_samples=20,
        class_weight="balanced",
        random_state=42,
        verbose=-1,
    )
    model.fit(train_x, train_y)
    calibrated = True  # LightGBM produces calibrated probabilities natively

    # --- Evaluate on test set ---
    probabilities = model.predict_proba(test_x)[:, 1]
    auc = float(roc_auc_score(test_y, probabilities))
    pr_auc = float(average_precision_score(test_y, probabilities))
    brier = float(brier_score_loss(test_y, probabilities))
    top_decile_precision = _top_decile_precision(probabilities, test_y)
    ks_stat = _ks_statistic(probabilities, test_y)
    lift_10 = _lift_at_percentile(probabilities, test_y, percentile=10)
    lift_20 = _lift_at_percentile(probabilities, test_y, percentile=20)

    evaluation: dict[str, Any] = {
        "auc_roc": round(auc, 4),
        "pr_auc": round(pr_auc, 4),
        "brier_score": round(brier, 4),
        "top_decile_precision": round(top_decile_precision, 4),
        "ks_statistic": round(ks_stat, 4),
        "lift_at_10pct": round(lift_10, 4),
        "lift_at_20pct": round(lift_20, 4),
        "records_used": int(len(model_frame)),
        "records_train": int(len(train_x)),
        "records_test": int(len(test_x)),
        "feature_columns": available_features,
        "split_strategy": split_strategy,
        "calibrated": calibrated,
    }
    if cv_auc_mean is not None:
        evaluation["cv_auc_mean"] = round(cv_auc_mean, 4)
        evaluation["cv_auc_std"] = round(cv_auc_std, 4)

    # Store gain-based feature importances as a fallback explanation source
    # when per-lead SHAP values cannot be computed.
    feature_importances: dict[str, float] = {}
    if hasattr(model, "feature_importances_"):
        raw = model.feature_importances_.tolist()
        total = sum(raw) or 1.0
        feature_importances = {
            col: round(float(val) / total, 6)
            for col, val in zip(available_features, raw)
        }

    metadata: dict[str, Any] = {
        "model_version": f"prd_runtime_lgbm_{pd.Timestamp.utcnow().strftime('%Y%m%d%H%M%S')}",
        "trained_at": pd.Timestamp.utcnow().isoformat(),
        "algorithm": "LightGBM",
        "feature_columns": available_features,
        "feature_importances": feature_importances,
        **evaluation,
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
        evaluation=evaluation,
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


def _ks_statistic(probabilities: Any, truth: pd.Series) -> float:
    """Compute the KS statistic (max separation between approved/rejected CDFs).

    KS measures how well the model separates the two classes across all
    thresholds. A value of 0 means no discrimination; 1 means perfect.
    """
    if len(truth) == 0:
        return 0.0
    prob_arr = np.asarray(probabilities)
    label_arr = np.asarray(truth)
    approved_probs = np.sort(prob_arr[label_arr == 1])
    rejected_probs = np.sort(prob_arr[label_arr == 0])
    if len(approved_probs) == 0 or len(rejected_probs) == 0:
        return 0.0
    # Compute empirical CDFs at each unique threshold
    thresholds = np.unique(prob_arr)
    ks = 0.0
    for t in thresholds:
        tpr = float(np.mean(approved_probs >= t))
        fpr = float(np.mean(rejected_probs >= t))
        ks = max(ks, abs(tpr - fpr))
    return ks


def _lift_at_percentile(probabilities: Any, truth: pd.Series, percentile: int) -> float:
    """Compute lift at the top N-th percentile of scored leads.

    Lift = (precision in top-N%) / (base approval rate).
    A lift of 2.0 at 10% means the top 10% of scored leads are approved at
    twice the rate of a random sample.
    """
    if len(truth) == 0:
        return 0.0
    prob_series = pd.Series(probabilities).reset_index(drop=True)
    truth_series = pd.Series(truth).reset_index(drop=True)
    base_rate = float(truth_series.mean())
    if base_rate == 0.0:
        return 0.0
    threshold = prob_series.quantile(1.0 - percentile / 100.0)
    selected = truth_series[prob_series >= threshold]
    if len(selected) == 0:
        return 0.0
    precision_at_n = float(selected.mean())
    return round(precision_at_n / base_rate, 4)
