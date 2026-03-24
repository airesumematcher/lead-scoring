"""Runtime loader and inference helpers for the reduced-signal sample-data model."""

from __future__ import annotations

import json
import pickle
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import pandas as pd

from lead_scoring.features import extract_all_features
from lead_scoring.models import EngagementType, ExtractedFeatures, LeadInput


PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
MODEL_DIR = PROJECT_ROOT / "models" / "all_sample_data"


@dataclass(frozen=True)
class ReducedSignalArtifacts:
    """Loaded model artifacts and metadata."""

    model: object
    imputer: object
    feature_names: list[str]
    metrics: dict[str, float]
    model_name: str
    model_version: str


@dataclass(frozen=True)
class ReducedSignalPredictionResult:
    """Prediction result for a single lead."""

    score: float
    metrics: dict[str, float]
    feature_count: int
    model_name: str
    model_version: str


def _normalize_domain(value: str | None) -> str:
    return str(value or "").strip().lower()


def _company_size_score(raw_size: str | None) -> float:
    size = str(raw_size or "").lower()
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


def _job_function_score(raw_text: str | None) -> float:
    job_function = str(raw_text or "").lower()
    if any(token in job_function for token in ["executive", "chief", "c-suite", "vp", "vice president"]):
        return 5.0
    if any(token in job_function for token in ["finance", "operations", "sales", "marketing"]):
        return 4.0
    if any(token in job_function for token in ["technology", "it", "engineering", "product"]):
        return 3.0
    if any(token in job_function for token in ["analyst", "business"]):
        return 2.0
    return 1.0 if job_function else 0.0


def _clamp_score(value: float) -> float:
    return max(0.0, min(100.0, float(value)))


@lru_cache(maxsize=1)
def _load_domain_lookup() -> pd.DataFrame:
    """Load persisted domain-level intent features."""
    lookup_path = MODEL_DIR / "domain_intent_features.csv"
    if not lookup_path.exists():
        return pd.DataFrame()

    frame = pd.read_csv(lookup_path)
    if "domain" not in frame.columns:
        return pd.DataFrame()
    return frame.fillna(0.0).set_index("domain")


@lru_cache(maxsize=1)
def load_reduced_signal_artifacts() -> ReducedSignalArtifacts:
    """Load the reduced-signal production candidate and its metadata."""
    report_path = MODEL_DIR / "training_report.json"
    feature_names_path = MODEL_DIR / "reduced_signal_feature_names.json"
    imputer_path = MODEL_DIR / "reduced_signal_imputer.pkl"
    model_path = MODEL_DIR / "reduced_signal_model_xgboost.pkl"

    missing = [
        str(path.name)
        for path in [report_path, feature_names_path, imputer_path, model_path]
        if not path.exists()
    ]
    if missing:
        missing_str = ", ".join(missing)
        raise FileNotFoundError(
            f"Reduced-signal artifacts are missing: {missing_str}. "
            "Run scripts/04_train_all_sample_data.py to regenerate them."
        )

    with open(report_path, "r") as handle:
        report = json.load(handle)
    with open(feature_names_path, "r") as handle:
        feature_names = json.load(handle)
    with open(imputer_path, "rb") as handle:
        imputer = pickle.load(handle)
    with open(model_path, "rb") as handle:
        model = pickle.load(handle)

    production_candidate = report.get("production_candidate", {})
    metrics = (
        production_candidate.get("metrics")
        or report.get("reduced_signal_benchmark", {}).get("models", {}).get("XGBoost", {})
    )

    return ReducedSignalArtifacts(
        model=model,
        imputer=imputer,
        feature_names=list(feature_names),
        metrics=metrics,
        model_name=production_candidate.get("name", "ReducedSignalXGBoost"),
        model_version="all_sample_data_reduced_signal_v1",
    )


def build_reduced_signal_feature_frame(
    lead: LeadInput,
    extracted_features: ExtractedFeatures | None = None,
) -> pd.DataFrame:
    """Map a live lead into the reduced-signal training feature space."""
    artifacts = load_reduced_signal_artifacts()
    features = extracted_features or extract_all_features(lead)

    events = lead.engagement_events or []
    open_count = sum(1 for event in events if event.event_type == EngagementType.OPEN)
    click_count = sum(1 for event in events if event.event_type == EngagementType.CLICK)
    download_count = sum(1 for event in events if event.event_type == EngagementType.DOWNLOAD)
    visit_count = sum(1 for event in events if event.event_type == EngagementType.VISIT)

    recency_days = (
        float(features.engagement.engagement_recency_days)
        if not features.engagement.engagement_absent_flag
        else 999.0
    )

    domain_lookup = _load_domain_lookup()
    domain = _normalize_domain(lead.company.domain)
    domain_features: dict[str, float] = {}
    if not domain_lookup.empty and domain in domain_lookup.index:
        row = domain_lookup.loc[domain]
        if hasattr(row, "to_dict"):
            domain_features = {key: float(value) for key, value in row.to_dict().items()}

    raw_features = {
        "email_valid": float(features.accuracy.email_valid),
        "phone_valid": float(features.accuracy.phone_valid),
        "title_seniority_score": float(features.accuracy.job_title_seniority_score),
        "company_size_band_score": _company_size_score(lead.company.company_size),
        "job_function_score": _job_function_score(lead.contact.job_title),
        "open_count": float(open_count),
        "click_count": float(click_count),
        "unsubscribe_count": 0.0,
        "engagement_actions": float(open_count + (2 * click_count) + (2 * download_count) + visit_count),
        "linkedin_present": float(bool(lead.contact.linkedin_url)),
        "interaction_within_7d": float(recency_days <= 7),
        "interaction_within_30d": float(recency_days <= 30),
        "interaction_days_diff": float(recency_days),
    }
    raw_features.update(domain_features)

    row = {name: float(raw_features.get(name, 0.0)) for name in artifacts.feature_names}
    return pd.DataFrame([row], columns=artifacts.feature_names)


def predict_reduced_signal_score(
    lead: LeadInput,
    extracted_features: ExtractedFeatures | None = None,
) -> ReducedSignalPredictionResult:
    """Score a lead with the reduced-signal XGBoost production candidate."""
    artifacts = load_reduced_signal_artifacts()
    feature_frame = build_reduced_signal_feature_frame(lead, extracted_features=extracted_features)
    imputed_features = artifacts.imputer.transform(feature_frame)
    prediction = _clamp_score(float(artifacts.model.predict(imputed_features)[0]))

    return ReducedSignalPredictionResult(
        score=round(prediction, 1),
        metrics=artifacts.metrics,
        feature_count=len(artifacts.feature_names),
        model_name=artifacts.model_name,
        model_version=artifacts.model_version,
    )
