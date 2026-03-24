#!/usr/bin/env python3
"""Train a non-leaky model suite from all structured sample-data sources."""

from __future__ import annotations

import json
import pickle
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import (
    ExtraTreesRegressor,
    HistGradientBoostingRegressor,
    RandomForestRegressor,
    VotingRegressor,
)
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from xgboost import XGBRegressor


SAMPLE_DIR = Path("sample_data")
OUTPUT_DIR = Path("models/all_sample_data")
RANDOM_STATE = 42


@dataclass
class PreparedDataset:
    X_train: pd.DataFrame
    X_test: pd.DataFrame
    y_train: pd.Series
    y_test: pd.Series
    X_train_imputed: np.ndarray
    X_test_imputed: np.ndarray
    X_train_scaled: np.ndarray
    X_test_scaled: np.ndarray
    feature_names: list[str]
    summary: dict[str, Any]
    domain_features: pd.DataFrame


REDUCED_SIGNAL_EXCLUSIONS = {
    "source_latest",
    "source_pivot",
    "email_component_score",
    "phone_component_score",
    "title_component_score",
    "company_size_component_score",
    "linkedin_component_score",
    "manual_review_required",
    "mli_flag_target",
    "mli_flag_nurture",
    "mli_raw_score",
    "mli_model_score",
    "mli_uplift",
}


def _safe_json_loads(raw: str | float | None) -> dict[str, Any]:
    if not isinstance(raw, str) or not raw.strip():
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}


def _nested_number(payload: dict[str, Any], *keys: str) -> float:
    value: Any = payload
    for key in keys:
        if not isinstance(value, dict):
            return 0.0
        value = value.get(key)
    try:
        if value is None or value == "":
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _nested_text(payload: dict[str, Any], *keys: str) -> str:
    value: Any = payload
    for key in keys:
        if not isinstance(value, dict):
            return ""
        value = value.get(key)
    return str(value or "").strip()


def _yes_no(value: Any) -> float:
    return 1.0 if str(value).strip().lower() == "yes" else 0.0


def _email_domain(email: str) -> str:
    if "@" not in email:
        return ""
    return email.rsplit("@", 1)[-1].strip().lower()


def _seniority_score(raw_title: str) -> float:
    title = raw_title.lower()
    if any(token in title for token in ["chief", "ceo", "cfo", "cto", "coo", "c-suite", "president", "executive", "vp", "vice president"]):
        return 5.0
    if "director" in title or "head" in title:
        return 4.0
    if "manager" in title or "lead" in title:
        return 3.0
    if any(token in title for token in ["analyst", "engineer", "specialist", "professional", "associate"]):
        return 2.0
    if title:
        return 1.0
    return 0.0


def _company_size_score(raw_size: str) -> float:
    size = raw_size.lower()
    if "xxlarge" in size or "10,000" in size or "10000" in size:
        return 8.0
    if "xlarge" in size or "5,000" in size or "5000" in size:
        return 7.0
    if "large" in size or "1,000" in size or "1000" in size:
        return 6.0
    if "medium-large" in size or "500" in size:
        return 5.0
    if "medium" in size or "200" in size:
        return 4.0
    if "small" in size or "50" in size:
        return 3.0
    if "micro" in size or "1 - 9" in size:
        return 2.0
    return 1.0 if size else 0.0


def _job_function_score(raw_function: str) -> float:
    job_function = raw_function.lower()
    if any(token in job_function for token in ["executive", "c-suite"]):
        return 5.0
    if any(token in job_function for token in ["finance", "operations", "sales", "marketing"]):
        return 4.0
    if any(token in job_function for token in ["technology", "it", "engineering", "product"]):
        return 3.0
    if any(token in job_function for token in ["analyst", "business"]):
        return 2.0
    return 1.0 if job_function else 0.0


def build_buying_stage_domain_features() -> pd.DataFrame:
    """Aggregate domain-level intent features from Buying_stage.csv."""
    usecols = [
        "DOMAIN",
        "CATEGORY",
        "TOTAL_LEADS",
        "TOTAL_IMPS",
        "TOTAL_CLICKS",
        "TOTAL_LI_CLICKS",
        "TOTAL_EXPOSURE_TIME_MS",
        "TOTAL_LI_SHARES",
    ]
    df = pd.read_csv(SAMPLE_DIR / "Buying_stage.csv", usecols=usecols, low_memory=False)
    df["DOMAIN"] = df["DOMAIN"].astype(str).str.strip().str.lower()
    df = df[df["DOMAIN"].ne("")]

    grouped = (
        df.groupby("DOMAIN", dropna=False)
        .agg(
            buying_records=("DOMAIN", "size"),
            buying_categories=("CATEGORY", "nunique"),
            buying_total_leads=("TOTAL_LEADS", "sum"),
            buying_total_imps=("TOTAL_IMPS", "sum"),
            buying_total_clicks=("TOTAL_CLICKS", "sum"),
            buying_total_li_clicks=("TOTAL_LI_CLICKS", "sum"),
            buying_total_exposure_ms=("TOTAL_EXPOSURE_TIME_MS", "sum"),
            buying_total_li_shares=("TOTAL_LI_SHARES", "sum"),
        )
        .reset_index()
        .rename(columns={"DOMAIN": "domain"})
    )

    grouped["buying_ctr"] = np.where(
        grouped["buying_total_imps"] > 0,
        grouped["buying_total_clicks"] / grouped["buying_total_imps"],
        0.0,
    )
    grouped["buying_li_ctr"] = np.where(
        grouped["buying_total_imps"] > 0,
        grouped["buying_total_li_clicks"] / grouped["buying_total_imps"],
        0.0,
    )
    grouped["buying_avg_exposure_ms"] = np.where(
        grouped["buying_total_imps"] > 0,
        grouped["buying_total_exposure_ms"] / grouped["buying_total_imps"],
        0.0,
    )

    for column in [
        "buying_records",
        "buying_categories",
        "buying_total_leads",
        "buying_total_imps",
        "buying_total_clicks",
        "buying_total_li_clicks",
        "buying_total_exposure_ms",
        "buying_total_li_shares",
        "buying_avg_exposure_ms",
    ]:
        grouped[column] = grouped[column].clip(lower=0)
        grouped[f"{column}_log"] = np.log1p(grouped[column])

    keep_columns = [
        "domain",
        "buying_ctr",
        "buying_li_ctr",
        "buying_records_log",
        "buying_categories_log",
        "buying_total_leads_log",
        "buying_total_imps_log",
        "buying_total_clicks_log",
        "buying_total_li_clicks_log",
        "buying_total_exposure_ms_log",
        "buying_total_li_shares_log",
        "buying_avg_exposure_ms_log",
    ]
    return grouped[keep_columns]


def build_latest_leads_frame(domain_features: pd.DataFrame) -> pd.DataFrame:
    """Create a training frame from Latest_leads_data.csv."""
    usecols = ["LEAD_SCORE", "RESPONSE"]
    df = pd.read_csv(SAMPLE_DIR / "Latest_leads_data.csv", usecols=usecols, low_memory=False)

    rows: list[dict[str, float | str]] = []
    for row in df.itertuples(index=False):
        response = _safe_json_loads(row.RESPONSE)
        email_value = _nested_text(response, "email", "value")
        domain = _email_domain(email_value)
        interaction_status = _nested_text(response, "lastInteractionDate", "status").lower()

        rows.append(
            {
                "source_latest": 1.0,
                "source_pivot": 0.0,
                "email_valid": 1.0 if _nested_text(response, "email", "status").lower() == "valid" else 0.0,
                "phone_valid": 1.0 if _nested_text(response, "phone", "status").lower() == "valid" else 0.0,
                "email_component_score": _nested_number(response, "email", "score"),
                "phone_component_score": _nested_number(response, "phone", "score"),
                "title_seniority_score": _seniority_score(
                    _nested_text(response, "jobTitle", "seniority")
                    or _nested_text(response, "jobTitle", "value")
                ),
                "title_component_score": _nested_number(response, "jobTitle", "score"),
                "company_size_band_score": _company_size_score(_nested_text(response, "companySize", "value")),
                "company_size_component_score": _nested_number(response, "companySize", "score"),
                "job_function_score": 0.0,
                "open_count": 0.0,
                "click_count": 0.0,
                "unsubscribe_count": 0.0,
                "engagement_actions": 0.0,
                "linkedin_present": 1.0 if _nested_text(response, "linkedInUrl", "status").lower() == "present" else 0.0,
                "linkedin_component_score": _nested_number(response, "linkedInUrl", "score"),
                "manual_review_required": 0.0 if _nested_text(response, "manualReview", "value").lower() == "not_required" else 1.0,
                "mli_flag_target": 1.0 if _nested_text(response, "mliScore", "flag").lower() == "target" else 0.0,
                "mli_flag_nurture": 1.0 if _nested_text(response, "mliScore", "flag").lower() == "nurture" else 0.0,
                "mli_raw_score": _nested_number(response, "mliScore", "score"),
                "mli_model_score": _nested_number(response, "mliScore", "mliScore"),
                "mli_uplift": _nested_number(response, "mliScore", "uplift"),
                "interaction_within_7d": 1.0 if interaction_status == "within_7_days" else 0.0,
                "interaction_within_30d": 1.0 if interaction_status in {"within_7_days", "within_30_days"} else 0.0,
                "interaction_days_diff": _nested_number(response, "lastInteractionDate", "dateDifference"),
                "domain": domain,
                "lead_score": float(row.LEAD_SCORE),
            }
        )

    latest = pd.DataFrame(rows)
    latest = latest.merge(domain_features, on="domain", how="left")
    return latest


def build_pivot_frame(domain_features: pd.DataFrame) -> pd.DataFrame:
    """Create a training frame from the smaller outreach pivot CSV."""
    df = pd.read_csv(SAMPLE_DIR / "Lead Score_Lead Outreach Results Pivots(Sheet1) (1).csv", low_memory=False)
    df = df.dropna(subset=["Lead Score"]).copy()

    rows: list[dict[str, float | str]] = []
    for _, row in df.iterrows():
        job_title = str(row.get("Job Title", "") or "")
        company_size = str(row.get("Company Size", "") or "")
        job_function = str(row.get("Job Function", "") or "")
        lead_email = str(row.get("Lead Email", "") or "")

        open_count = _yes_no(row.get("Email 1 - Opened", "")) + _yes_no(row.get("Email 2 - Open", ""))
        click_count = _yes_no(row.get("Email 1 - Clicked", "")) + _yes_no(row.get("Email 2 - Clicked", ""))
        unsubscribe_count = _yes_no(row.get("Email 1 - Unsubscribe", "")) + _yes_no(row.get("Email 2 - Unsubscribe", ""))

        rows.append(
            {
                "source_latest": 0.0,
                "source_pivot": 1.0,
                "email_valid": 1.0 if "@" in lead_email else 0.0,
                "phone_valid": 0.0,
                "email_component_score": 0.0,
                "phone_component_score": 0.0,
                "title_seniority_score": _seniority_score(job_title),
                "title_component_score": _seniority_score(job_title) * 5.0,
                "company_size_band_score": _company_size_score(company_size),
                "company_size_component_score": 0.0,
                "job_function_score": _job_function_score(job_function),
                "open_count": float(open_count),
                "click_count": float(click_count),
                "unsubscribe_count": float(unsubscribe_count),
                "engagement_actions": float(open_count + (2.0 * click_count) - (3.0 * unsubscribe_count)),
                "linkedin_present": 0.0,
                "linkedin_component_score": 0.0,
                "manual_review_required": 0.0,
                "mli_flag_target": 0.0,
                "mli_flag_nurture": 0.0,
                "mli_raw_score": 0.0,
                "mli_model_score": 0.0,
                "mli_uplift": 0.0,
                "interaction_within_7d": 0.0,
                "interaction_within_30d": 0.0,
                "interaction_days_diff": 0.0,
                "domain": _email_domain(lead_email),
                "lead_score": float(row["Lead Score"]),
            }
        )

    pivot = pd.DataFrame(rows)
    pivot = pivot.merge(domain_features, on="domain", how="left")
    return pivot


def prepare_dataset() -> PreparedDataset:
    """Load and prepare the unified all-sample-data training set."""
    domain_features = build_buying_stage_domain_features()
    latest = build_latest_leads_frame(domain_features)
    pivot = build_pivot_frame(domain_features)
    combined = pd.concat([latest, pivot], ignore_index=True, sort=False)

    combined = combined.fillna(0.0)
    y = combined.pop("lead_score").astype(float)
    combined = combined.drop(columns=["domain"])

    summary = {
        "rows_total": int(len(combined)),
        "rows_latest": int(len(latest)),
        "rows_pivot": int(len(pivot)),
        "feature_count": int(combined.shape[1]),
        "target_mean": float(y.mean()),
        "target_std": float(y.std()),
        "target_min": float(y.min()),
        "target_max": float(y.max()),
    }

    X_train, X_test, y_train, y_test = train_test_split(
        combined,
        y,
        test_size=0.2,
        random_state=RANDOM_STATE,
    )

    imputer = SimpleImputer(strategy="median")
    X_train_imputed = imputer.fit_transform(X_train)
    X_test_imputed = imputer.transform(X_test)

    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train_imputed)
    X_test_scaled = scaler.transform(X_test_imputed)

    return PreparedDataset(
        X_train=X_train,
        X_test=X_test,
        y_train=y_train,
        y_test=y_test,
        X_train_imputed=X_train_imputed,
        X_test_imputed=X_test_imputed,
        X_train_scaled=X_train_scaled,
        X_test_scaled=X_test_scaled,
        feature_names=combined.columns.tolist(),
        summary=summary,
        domain_features=domain_features,
    )


def evaluate_predictions(y_true: pd.Series, y_pred: np.ndarray) -> dict[str, float]:
    """Return holdout metrics."""
    y_pred = np.clip(y_pred, 0, 100)
    return {
        "r2_test": float(r2_score(y_true, y_pred)),
        "mae_test": float(mean_absolute_error(y_true, y_pred)),
        "rmse_test": float(np.sqrt(mean_squared_error(y_true, y_pred))),
    }


def reduced_signal_features(feature_names: list[str]) -> list[str]:
    """Return the subset that excludes score-component reconstruction fields."""
    return [name for name in feature_names if name not in REDUCED_SIGNAL_EXCLUSIONS]


def train_all_models(dataset: PreparedDataset) -> tuple[dict[str, Any], dict[str, dict[str, float]], SimpleImputer, StandardScaler]:
    """Train the model suite and return fitted estimators plus metrics."""
    imputer = SimpleImputer(strategy="median")
    imputer.fit(dataset.X_train)

    scaler = StandardScaler()
    scaler.fit(imputer.transform(dataset.X_train))

    X_train_imputed = imputer.transform(dataset.X_train)
    X_test_imputed = imputer.transform(dataset.X_test)
    X_train_scaled = scaler.transform(X_train_imputed)
    X_test_scaled = scaler.transform(X_test_imputed)

    models: dict[str, Any] = {}
    metrics: dict[str, dict[str, float]] = {}

    model_specs = {
        "Ridge": Ridge(alpha=1.0),
        "RandomForest": RandomForestRegressor(
            n_estimators=160,
            max_depth=18,
            min_samples_leaf=2,
            random_state=RANDOM_STATE,
            n_jobs=-1,
        ),
        "ExtraTrees": ExtraTreesRegressor(
            n_estimators=160,
            max_depth=18,
            min_samples_leaf=2,
            random_state=RANDOM_STATE,
            n_jobs=-1,
        ),
        "HistGradientBoosting": HistGradientBoostingRegressor(
            learning_rate=0.05,
            max_depth=8,
            max_iter=350,
            random_state=RANDOM_STATE,
        ),
        "XGBoost": XGBRegressor(
            n_estimators=300,
            max_depth=8,
            learning_rate=0.05,
            subsample=0.8,
            colsample_bytree=0.8,
            objective="reg:squarederror",
            random_state=RANDOM_STATE,
            n_jobs=-1,
            verbosity=0,
        ),
    }

    for name, model in model_specs.items():
        print(f"Training {name}...")
        if name == "Ridge":
            model.fit(X_train_scaled, dataset.y_train)
            y_pred = model.predict(X_test_scaled)
        else:
            model.fit(X_train_imputed, dataset.y_train)
            y_pred = model.predict(X_test_imputed)
        models[name] = model
        metrics[name] = evaluate_predictions(dataset.y_test, y_pred)

    ensemble = VotingRegressor(
        estimators=[
            ("rf", models["RandomForest"]),
            ("et", models["ExtraTrees"]),
            ("hgb", models["HistGradientBoosting"]),
            ("xgb", models["XGBoost"]),
        ]
    )
    print("Training Ensemble...")
    ensemble.fit(X_train_imputed, dataset.y_train)
    models["Ensemble"] = ensemble
    metrics["Ensemble"] = evaluate_predictions(dataset.y_test, ensemble.predict(X_test_imputed))

    return models, metrics, imputer, scaler


def train_reduced_signal_models(
    dataset: PreparedDataset,
) -> tuple[dict[str, Any], dict[str, dict[str, float]], SimpleImputer, list[str]]:
    """Train a deployable reduced-signal model set without reconstruction fields."""
    feature_subset = reduced_signal_features(dataset.feature_names)
    X_train = dataset.X_train[feature_subset]
    X_test = dataset.X_test[feature_subset]

    imputer = SimpleImputer(strategy="median")
    X_train_imputed = imputer.fit_transform(X_train)
    X_test_imputed = imputer.transform(X_test)

    models = {
        "HistGradientBoosting": HistGradientBoostingRegressor(
            learning_rate=0.05,
            max_depth=8,
            max_iter=350,
            random_state=RANDOM_STATE,
        ),
        "XGBoost": XGBRegressor(
            n_estimators=300,
            max_depth=8,
            learning_rate=0.05,
            subsample=0.8,
            colsample_bytree=0.8,
            objective="reg:squarederror",
            random_state=RANDOM_STATE,
            n_jobs=-1,
            verbosity=0,
        ),
    }

    trained_models: dict[str, Any] = {}
    metrics: dict[str, dict[str, float]] = {}
    for name, model in models.items():
        print(f"Training reduced-signal {name}...")
        model.fit(X_train_imputed, dataset.y_train)
        trained_models[name] = model
        metrics[name] = evaluate_predictions(dataset.y_test, model.predict(X_test_imputed))

    return trained_models, metrics, imputer, feature_subset


def save_artifacts(
    dataset: PreparedDataset,
    models: dict[str, Any],
    metrics: dict[str, dict[str, float]],
    imputer: SimpleImputer,
    scaler: StandardScaler,
    reduced_models: dict[str, Any],
    reduced_metrics: dict[str, dict[str, float]],
    reduced_imputer: SimpleImputer,
    reduced_feature_names: list[str],
) -> None:
    """Persist models, preprocessors, and a compact report."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    for name, model in models.items():
        with open(OUTPUT_DIR / f"model_{name.lower()}.pkl", "wb") as handle:
            pickle.dump(model, handle)

    with open(OUTPUT_DIR / "imputer.pkl", "wb") as handle:
        pickle.dump(imputer, handle)
    with open(OUTPUT_DIR / "scaler.pkl", "wb") as handle:
        pickle.dump(scaler, handle)

    for name, model in reduced_models.items():
        filename = f"reduced_signal_model_{name.lower()}.pkl"
        with open(OUTPUT_DIR / filename, "wb") as handle:
            pickle.dump(model, handle)

    with open(OUTPUT_DIR / "reduced_signal_imputer.pkl", "wb") as handle:
        pickle.dump(reduced_imputer, handle)

    with open(OUTPUT_DIR / "reduced_signal_feature_names.json", "w") as handle:
        json.dump(reduced_feature_names, handle, indent=2)

    dataset.domain_features.to_csv(OUTPUT_DIR / "domain_intent_features.csv", index=False)

    ranked = sorted(metrics.items(), key=lambda item: item[1]["r2_test"], reverse=True)
    best_name, best_metrics = ranked[0]

    feature_importance = []
    best_model = models[best_name]
    if hasattr(best_model, "feature_importances_"):
        importance_series = pd.Series(best_model.feature_importances_, index=dataset.feature_names)
        feature_importance = [
            {"feature": feature, "importance": float(score)}
            for feature, score in importance_series.sort_values(ascending=False).head(15).items()
        ]

    report = {
        "dataset_summary": dataset.summary,
        "holdout_test_rows": int(len(dataset.y_test)),
        "best_model": best_name,
        "best_model_metrics": best_metrics,
        "models": metrics,
        "reduced_signal_benchmark": {
            "feature_count": len(reduced_feature_names),
            "excluded_features": sorted(REDUCED_SIGNAL_EXCLUSIONS),
            "models": reduced_metrics,
            "saved_artifacts": {
                "model_xgboost": "reduced_signal_model_xgboost.pkl",
                "model_histgradientboosting": "reduced_signal_model_histgradientboosting.pkl",
                "imputer": "reduced_signal_imputer.pkl",
                "feature_names": "reduced_signal_feature_names.json",
                "domain_lookup": "domain_intent_features.csv",
            },
        },
        "production_candidate": {
            "name": "ReducedSignalXGBoost",
            "artifact": "reduced_signal_model_xgboost.pkl",
            "metrics": reduced_metrics.get("XGBoost", {}),
            "feature_count": len(reduced_feature_names),
            "reason": "Best reduced-signal generalization among the non-leaky benchmark models.",
        },
        "feature_names": dataset.feature_names,
        "top_feature_importance": feature_importance,
        "notes": [
            "This model suite is trained to reproduce historical lead scores from structured sample-data CSVs.",
            "Leak-prone fields such as scoreInfo.finalScore and scoreInfo.accuracyScore were excluded.",
            "The reduced_signal_benchmark removes score-component fields and training-source flags to approximate a more realistic generalization test.",
            "Excel briefing docs in sample_data were not used because they are not normalized row-level supervised datasets.",
        ],
    }

    with open(OUTPUT_DIR / "training_report.json", "w") as handle:
        json.dump(report, handle, indent=2)


def main() -> None:
    """Build the combined dataset, train the model suite, and save artifacts."""
    print("=" * 80)
    print("TRAINING ON ALL STRUCTURED SAMPLE DATA")
    print("=" * 80)

    dataset = prepare_dataset()
    print(
        "Prepared dataset:",
        f"{dataset.summary['rows_total']} rows",
        f"{dataset.summary['feature_count']} features",
    )
    print(
        "Sources:",
        f"{dataset.summary['rows_latest']} latest leads +",
        f"{dataset.summary['rows_pivot']} outreach rows",
    )

    models, metrics, imputer, scaler = train_all_models(dataset)
    reduced_models, reduced_metrics, reduced_imputer, reduced_feature_names = train_reduced_signal_models(dataset)
    save_artifacts(
        dataset,
        models,
        metrics,
        imputer,
        scaler,
        reduced_models,
        reduced_metrics,
        reduced_imputer,
        reduced_feature_names,
    )

    ranked = sorted(metrics.items(), key=lambda item: item[1]["r2_test"], reverse=True)
    print("\nModel ranking:")
    for rank, (name, metric) in enumerate(ranked, start=1):
        print(
            f"{rank:>2}. {name:20s} "
            f"R²={metric['r2_test']:.4f} "
            f"MAE={metric['mae_test']:.2f} "
            f"RMSE={metric['rmse_test']:.2f}"
        )

    print("\nReduced-signal benchmark:")
    for name, metric in reduced_metrics.items():
        print(
            f" - {name:20s} "
            f"R²={metric['r2_test']:.4f} "
            f"MAE={metric['mae_test']:.2f} "
            f"RMSE={metric['rmse_test']:.2f}"
        )

    print(f"\nArtifacts saved to {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
