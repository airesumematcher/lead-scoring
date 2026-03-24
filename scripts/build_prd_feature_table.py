#!/usr/bin/env python3
"""Build a PRD-aligned feature table from cleaned_data.xlsx for model training.

Uses out-of-fold (OOF) target encoding for all acceptance-rate-derived features
to prevent data leakage: each row's feature is computed from folds that do NOT
include that row, so the model never sees its own label during feature engineering.

Outputs data_processed/prd_feature_table_full.csv, ready for:

    python3 scripts/run_monthly_retrain.py data_processed/prd_feature_table_full.csv
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.model_selection import KFold

ROOT = Path(__file__).resolve().parents[1]
INPUT_FILE = ROOT / "sample_data" / "cleaned_data.xlsx"
OUTPUT_FILE = ROOT / "data_processed" / "prd_feature_table_full.csv"

TEST_PUBLISHERS = {
    "Prod_Test_1", "Prod_Test_2", "Prod_Test_1_Partner",
    "Prod_Test_Cube_Pt", "Test_Prod_Partner_New", "EvolveBPM",
}

ASSET_STAGE_MAP: dict[str, float] = {
    "preawareness": 20.0,
    "awareness": 35.0,
    "consideration": 60.0,
    "decision": 90.0,
}

ACCOUNT_STAGE_MAP: dict[str, float] = {
    "no_predicted_stage": 25.0,
    "no_asset_information": 25.0,
    "preawareness": 30.0,
    "awareness": 45.0,
    "consideration": 65.0,
    "decision": 90.0,
}

COMPANY_SIZE_SCORE: dict[str, float] = {
    "micro (1 - 9 employees)": 30.0,
    "small (10 - 49 employees)": 42.0,
    "medium-small (50 - 199 employees)": 55.0,
    "medium (200 - 499 employees)": 65.0,
    "medium-large (500 - 999 employees)": 72.0,
    "large (1,000 - 4,999 employees)": 80.0,
    "xlarge (5,000 - 10,000 employees)": 88.0,
    "xxlarge (10,000+ employees)": 95.0,
}

GEOGRAPHY_SCORE: dict[str, float] = {
    "americas": 80.0,
    "united states": 82.0,
    "emea": 70.0,
    "europe": 70.0,
    "apac": 65.0,
    "asia pacific": 65.0,
}

N_SPLITS = 5  # folds for out-of-fold target encoding


def _oof_target_encode(
    series: pd.Series,
    is_approved: pd.Series,
    n_splits: int = N_SPLITS,
    min_score: float = 20.0,
    max_score: float = 95.0,
) -> pd.Series:
    """Out-of-fold target encoding scaled to [min_score, max_score].

    For each fold, the per-group acceptance rate is computed ONLY from the
    remaining folds (no leakage). Unknown groups in a fold fall back to the
    global mean computed from those same training folds.

    The resulting rates are min-max scaled to [min_score, max_score] so
    the output is in the same 0–100 unit space as other PRD features.
    """
    encoded = pd.Series(np.nan, index=series.index, dtype=float)
    kf = KFold(n_splits=n_splits, shuffle=True, random_state=42)
    global_rate = float(is_approved.mean())

    for train_idx, val_idx in kf.split(series):
        train_series = series.iloc[train_idx]
        train_target = is_approved.iloc[train_idx]
        val_series = series.iloc[val_idx]

        # Per-group rate from training folds only
        group_rates = train_target.groupby(train_series).mean()
        fold_global = float(train_target.mean())
        fold_encoded = val_series.map(group_rates).fillna(fold_global)
        encoded.iloc[val_idx] = fold_encoded

    # Globally min-max scale to [min_score, max_score]
    lo, hi = encoded.min(), encoded.max()
    if hi > lo:
        encoded = min_score + (encoded - lo) / (hi - lo) * (max_score - min_score)
    else:
        encoded = pd.Series(60.0, index=series.index)

    return encoded.round(2)


def build(input_path: Path = INPUT_FILE, output_path: Path = OUTPUT_FILE) -> pd.DataFrame:
    print(f"Reading {input_path} …")
    raw = pd.read_excel(input_path)
    print(f"  Loaded {len(raw):,} rows × {raw.shape[1]} columns")

    # --- Label ---
    raw["status"] = raw["LEAD_STATUS"].str.strip().map(
        {"Accepted": "approved", "Rejected": "rejected"}
    )
    df = raw.dropna(subset=["status"]).reset_index(drop=True).copy()
    is_approved = (df["status"] == "approved")
    print(f"  After label filter: {len(df):,} rows  "
          f"({is_approved.mean()*100:.1f}% approved)")

    print("  Computing out-of-fold target-encoded features (no data leakage)…")

    # --- partner_signal_score (OOF, test publishers excluded → neutral 50) ---
    pub_series = df["PUBLISHER_NAME"].copy()
    pub_series_masked = pub_series.where(~pub_series.isin(TEST_PUBLISHERS), other="__test__")
    partner_encoded = _oof_target_encode(pub_series_masked, is_approved)
    # Override test publishers with neutral 50
    df["partner_signal_score"] = partner_encoded.where(
        ~pub_series.isin(TEST_PUBLISHERS), other=50.0
    )

    # --- authority_score (OOF on JOB_FUNCTION) ---
    df["authority_score"] = _oof_target_encode(df["JOB_FUNCTION"], is_approved)

    # --- icp_match_score components (OOF each) ---
    industry_encoded = _oof_target_encode(df["INDUSTRY"], is_approved)
    size_encoded = _oof_target_encode(df["COMPANY_SIZE"], is_approved)
    function_encoded = _oof_target_encode(df["JOB_FUNCTION"], is_approved)
    df["icp_match_score"] = ((industry_encoded + size_encoded + function_encoded) / 3.0).clip(0, 100).round(2)

    # --- fit_score (OOF industry + static size/geography/function scores) ---
    # Company size and geography use fixed business-rule scores (not label-derived)
    # so they don't need OOF encoding.
    company_size_score = df["COMPANY_SIZE"].str.lower().map(COMPANY_SIZE_SCORE).fillna(60.0)
    geo_col = df["REGION"].fillna(df["COUNTRY"]).astype(str).str.strip().str.lower()
    geography_score = geo_col.map(GEOGRAPHY_SCORE).fillna(60.0)
    df["fit_score"] = (
        (company_size_score + geography_score + function_encoded + industry_encoded) / 4.0
    ).clip(0, 100).round(2)

    # --- data_quality_score (rule-based, no label dependency) ---
    email_clean = df["EMAIL_VALIDATION_STATUS"].astype(str).str.strip().str.lower()
    dq = pd.Series(100.0, index=df.index)
    dq -= 25.0 * email_clean.isin(["invalid", "risky"]).astype(float)
    dq -= 15.0 * (df["LINKEDIN_URL"] == 0).astype(float)
    dq -= 20.0 * (df["IS_REQUIRE_REVIEW"] == 1).astype(float)
    df["data_quality_score"] = dq.clip(0, 100)

    # --- email_engagement_score (log-scaled, no label dependency) ---
    df["email_engagement_score"] = (
        np.log1p(df["TOTAL_CLICKS"].astype(float)) * 20.0
        + np.log1p(df["TOTAL_IMPRESSION"].astype(float)) * 5.0
    ).clip(0, 100).round(2)

    # --- late_stage_signal (rule-based) ---
    stage_clean = df["ASSET_PREDICTED_BUYER_STAGE"].astype(str).str.strip().str.lower()
    df["late_stage_signal"] = stage_clean.map(ASSET_STAGE_MAP).fillna(50.0)

    # --- buying_group_score (rule-based: account stage + trending percentile) ---
    acct_stage_clean = df["ACCOUNT_PREDICTED_STAGE"].astype(str).str.strip().str.lower()
    acct_stage_score = acct_stage_clean.map(ACCOUNT_STAGE_MAP).fillna(25.0)
    trending_pct = df["ACCOUNT_TOTAL_TRENDING_TOPIC"].astype(float).rank(pct=True) * 100
    df["buying_group_score"] = (acct_stage_score * 0.6 + trending_pct * 0.4).clip(0, 100).round(2)

    # --- intent_score (derived, no direct label dependency) ---
    df["intent_score"] = (
        df["late_stage_signal"] * 0.4
        + df["email_engagement_score"] * 0.4
        + df["buying_group_score"] * 0.2
    ).clip(0, 100).round(2)

    # --- Constant defaults for signals not in this dataset ---
    df["client_history_score"] = 50.0
    df["campaign_history_score"] = 50.0
    df["unique_persona_count"] = 1
    df["second_touch_signal"] = 0.0
    df["recency_score"] = 80.0

    # --- Assemble output ---
    feature_columns = [
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
    output = df[["status"] + feature_columns].copy()

    null_count = output.isnull().sum().sum()
    if null_count > 0:
        print(f"  WARNING: {null_count} null values — filling with column medians")
        for col in feature_columns:
            if output[col].isnull().any():
                output[col] = output[col].fillna(output[col].median())

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output.to_csv(output_path, index=False)

    print(f"\nOutput written to {output_path}")
    print(f"  Shape: {output.shape}  |  Nulls: {output.isnull().sum().sum()}")
    print(f"  Label distribution:\n{output['status'].value_counts().to_string()}")
    print(f"\nFeature ranges (min / mean / max):")
    for col in feature_columns:
        s = output[col]
        print(f"  {col:<28} {s.min():>6.1f} / {s.mean():>6.1f} / {s.max():>6.1f}  std={s.std():.2f}")
    return output


if __name__ == "__main__":
    build()
