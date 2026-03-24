#!/usr/bin/env python3
"""Compare ML algorithms for lead quality classification.

Trains RandomForest, GradientBoosting, XGBoost, LightGBM, and a Logistic
Regression baseline on the same OOF-encoded feature table and prints a ranked
comparison table. The best model (by AUC-ROC) is optionally promoted.

Usage:
    python3 scripts/compare_models.py
    python3 scripts/compare_models.py --promote          # promote best model
    python3 scripts/compare_models.py --dataset PATH     # custom feature table
"""

from __future__ import annotations

import argparse
import json
import pickle
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    roc_auc_score,
)
from sklearn.model_selection import StratifiedKFold, cross_val_score, train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.utils.class_weight import compute_sample_weight

try:
    import xgboost as xgb
    HAS_XGB = True
except ImportError:
    HAS_XGB = False

try:
    import lightgbm as lgb
    HAS_LGB = True
except ImportError:
    HAS_LGB = False

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATASET = ROOT / "data_processed" / "prd_feature_table_full.csv"
MODEL_DIR = ROOT / "models" / "prd_runtime"
MODEL_DIR.mkdir(parents=True, exist_ok=True)

STATUS_MAP = {
    "approved": 1, "accept": 1, "accepted": 1, "delivered": 1,
    "rejected": 0, "refund": 0, "refunded": 0,
}

FEATURE_COLUMNS = [
    "authority_score", "fit_score", "intent_score", "partner_signal_score",
    "client_history_score", "campaign_history_score", "data_quality_score",
    "icp_match_score", "buying_group_score", "unique_persona_count",
    "late_stage_signal", "email_engagement_score", "second_touch_signal",
    "recency_score",
]


def _top_decile_precision(proba: np.ndarray, truth: pd.Series) -> float:
    p = pd.Series(proba).reset_index(drop=True)
    t = pd.Series(truth).reset_index(drop=True)
    thresh = p.quantile(0.9)
    sel = t[p >= thresh]
    return float(sel.mean()) if len(sel) else 0.0


def _ks_statistic(proba: np.ndarray, truth: pd.Series) -> float:
    pa = np.sort(proba[np.asarray(truth) == 1])
    pr = np.sort(proba[np.asarray(truth) == 0])
    if not len(pa) or not len(pr):
        return 0.0
    thresholds = np.unique(proba)
    ks = 0.0
    for t in thresholds:
        ks = max(ks, abs(np.mean(pa >= t) - np.mean(pr >= t)))
    return ks


def _lift(proba: np.ndarray, truth: pd.Series, pct: int) -> float:
    p = pd.Series(proba).reset_index(drop=True)
    t = pd.Series(truth).reset_index(drop=True)
    base = float(t.mean())
    if base == 0:
        return 0.0
    thresh = p.quantile(1 - pct / 100)
    sel = t[p >= thresh]
    return round(float(sel.mean()) / base, 4) if len(sel) else 0.0


def _build_candidates() -> list[dict[str, Any]]:
    candidates = [
        {
            "name": "GradientBoosting",
            "estimator": GradientBoostingClassifier(
                n_estimators=200, learning_rate=0.05,
                max_depth=4, subsample=0.8, random_state=42,
            ),
            "supports_sample_weight": True,
        },
        {
            "name": "RandomForest",
            "estimator": RandomForestClassifier(
                n_estimators=300, max_depth=8, min_samples_leaf=20,
                class_weight="balanced", random_state=42, n_jobs=-1,
            ),
            "supports_sample_weight": False,  # handled via class_weight
        },
        {
            "name": "LogisticRegression (baseline)",
            "estimator": Pipeline([
                ("scaler", StandardScaler()),
                ("clf", LogisticRegression(
                    max_iter=500, class_weight="balanced",
                    C=1.0, random_state=42,
                )),
            ]),
            "supports_sample_weight": False,
        },
    ]
    if HAS_XGB:
        candidates.append({
            "name": "XGBoost",
            "estimator": xgb.XGBClassifier(
                n_estimators=300, learning_rate=0.05, max_depth=5,
                subsample=0.8, colsample_bytree=0.8,
                use_label_encoder=False, eval_metric="logloss",
                random_state=42, n_jobs=-1, verbosity=0,
            ),
            "supports_sample_weight": True,
        })
    else:
        print("  [skip] XGBoost not available")

    if HAS_LGB:
        candidates.append({
            "name": "LightGBM",
            "estimator": lgb.LGBMClassifier(
                n_estimators=300, learning_rate=0.05, num_leaves=63,
                min_child_samples=20, subsample=0.8, colsample_bytree=0.8,
                class_weight="balanced", random_state=42, n_jobs=-1,
                verbose=-1,
            ),
            "supports_sample_weight": False,
        })
    else:
        print("  [skip] LightGBM not available")

    return candidates


def evaluate_all(
    dataset_path: Path = DEFAULT_DATASET,
    promote_best: bool = False,
) -> list[dict[str, Any]]:
    print(f"\nLoading dataset: {dataset_path}")
    frame = pd.read_csv(dataset_path)
    labels = frame["status"].astype(str).str.lower().map(STATUS_MAP)
    frame["target"] = labels
    frame = frame.dropna(subset=["target"])
    available = [c for c in FEATURE_COLUMNS if c in frame.columns]

    model_frame = frame[available + ["target"]].dropna()
    print(f"  {len(model_frame):,} rows  |  {model_frame['target'].mean()*100:.1f}% approved  |  {len(available)} features\n")

    train_x, test_x, train_y, test_y = train_test_split(
        model_frame[available], model_frame["target"],
        test_size=0.2, random_state=42, stratify=model_frame["target"],
    )
    sample_weights = compute_sample_weight("balanced", train_y)

    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    candidates = _build_candidates()
    results = []

    for cand in candidates:
        name = cand["name"]
        est = cand["estimator"]
        print(f"  Training {name}...", end=" ", flush=True)
        t0 = time.time()

        # Cross-validation AUC (not calibrated, for comparison only)
        cv_aucs = cross_val_score(est, model_frame[available], model_frame["target"],
                                  cv=cv, scoring="roc_auc")

        # Train with calibration on train split
        if cand["supports_sample_weight"]:
            est.fit(train_x, train_y, sample_weight=sample_weights)
        else:
            est.fit(train_x, train_y)

        calibrated = CalibratedClassifierCV(est, cv="prefit" if False else 3, method="sigmoid")
        # Use cv=3 inside calibrated training with the full train set
        cal = CalibratedClassifierCV(
            _build_candidates()[candidates.index(cand)]["estimator"].__class__(
                **_get_params(est)
            ) if False else est,
            method="sigmoid", cv=3,
        )
        # Simpler: use the already-fitted estimator, calibrate on test held-out
        # (split test into cal/eval halves)
        half = len(test_x) // 2
        cal_x, eval_x = test_x.iloc[:half], test_x.iloc[half:]
        cal_y, eval_y = test_y.iloc[:half], test_y.iloc[half:]

        cal_model = CalibratedClassifierCV(est, cv="prefit" if hasattr(est, "predict_proba") else 3,
                                           method="sigmoid")
        try:
            # cv='prefit' removed in sklearn 1.8; fall back to direct prob
            proba_raw = est.predict_proba(eval_x)[:, 1]
            auc      = float(roc_auc_score(eval_y, proba_raw))
            pr_auc   = float(average_precision_score(eval_y, proba_raw))
            brier    = float(brier_score_loss(eval_y, proba_raw))
            tdp      = _top_decile_precision(proba_raw, eval_y)
            ks       = _ks_statistic(proba_raw, eval_y)
            lift10   = _lift(proba_raw, eval_y, 10)
            lift20   = _lift(proba_raw, eval_y, 20)
        except Exception as exc:
            print(f"[ERROR: {exc}]")
            continue

        elapsed = time.time() - t0
        print(f"done ({elapsed:.1f}s)  AUC={auc:.4f}  CV={cv_aucs.mean():.4f}±{cv_aucs.std():.4f}")

        results.append({
            "name": name,
            "auc_roc": round(auc, 4),
            "cv_auc_mean": round(float(cv_aucs.mean()), 4),
            "cv_auc_std": round(float(cv_aucs.std()), 4),
            "pr_auc": round(pr_auc, 4),
            "brier_score": round(brier, 4),
            "top_decile_precision": round(tdp, 4),
            "ks_statistic": round(ks, 4),
            "lift_at_10pct": round(lift10, 4),
            "lift_at_20pct": round(lift20, 4),
            "train_seconds": round(elapsed, 1),
            "estimator": est,
            "feature_columns": available,
        })

    # Sort by AUC-ROC descending
    results.sort(key=lambda r: r["auc_roc"], reverse=True)

    # Print comparison table
    print("\n" + "="*95)
    print(f"{'Model':<30} {'AUC':>6} {'CV AUC':>10} {'PR-AUC':>7} {'Brier':>7} {'KS':>6} {'Lift@10':>8} {'Top-10%':>8}")
    print("-"*95)
    for i, r in enumerate(results):
        marker = " ← BEST" if i == 0 else ""
        cv_str = f"{r['cv_auc_mean']:.4f}±{r['cv_auc_std']:.4f}"
        print(f"{r['name']:<30} {r['auc_roc']:>6.4f} {cv_str:>10} {r['pr_auc']:>7.4f} "
              f"{r['brier_score']:>7.4f} {r['ks_statistic']:>6.4f} {r['lift_at_10pct']:>8.4f} "
              f"{r['top_decile_precision']:>8.4f}{marker}")
    print("="*95)

    if promote_best and results:
        best = results[0]
        _promote(best, dataset_path)

    return results


def _promote(result: dict[str, Any], dataset_path: Path) -> None:
    """Save best model to models/prd_runtime/ and update metadata."""
    model_path = MODEL_DIR / "lead_quality_model.pkl"
    meta_path = MODEL_DIR / "model_metadata.json"

    with open(model_path, "wb") as f:
        pickle.dump(result["estimator"], f)

    metadata = {
        "model_version": f"prd_runtime_{result['name'].lower().replace(' ', '_')}_{pd.Timestamp.utcnow().strftime('%Y%m%d%H%M%S')}",
        "trained_at": pd.Timestamp.utcnow().isoformat(),
        "algorithm": result["name"],
        "feature_columns": result["feature_columns"],
        "auc_roc": result["auc_roc"],
        "cv_auc_mean": result["cv_auc_mean"],
        "cv_auc_std": result["cv_auc_std"],
        "pr_auc": result["pr_auc"],
        "brier_score": result["brier_score"],
        "ks_statistic": result["ks_statistic"],
        "lift_at_10pct": result["lift_at_10pct"],
        "top_decile_precision": result["top_decile_precision"],
        "calibrated": False,
        "split_strategy": "stratified_random",
        "dataset_path": str(dataset_path),
    }
    with open(meta_path, "w") as f:
        json.dump(metadata, f, indent=2)

    print(f"\nPromoted: {result['name']}  →  {model_path}")
    print(f"Metadata: {meta_path}")


def _get_params(estimator: Any) -> dict:
    try:
        return estimator.get_params()
    except Exception:
        return {}


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare ML algorithms for lead scoring")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET,
                        help=f"PRD feature table CSV (default: {DEFAULT_DATASET})")
    parser.add_argument("--promote", action="store_true",
                        help="Promote the best-performing model to prd_runtime/")
    args = parser.parse_args()
    results = evaluate_all(dataset_path=args.dataset, promote_best=args.promote)
    return 0 if results else 1


if __name__ == "__main__":
    sys.exit(main())
