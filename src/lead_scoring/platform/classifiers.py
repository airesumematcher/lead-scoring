"""Rule-based classifiers and fallback text normalisers for the PRD runtime."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

from .contracts import FunnelStage


def _normalise_text(value: str | None) -> str:
    return " ".join(str(value or "").strip().lower().split())


@dataclass(frozen=True)
class NormalisedTitle:
    """Normalized interpretation of a job title."""

    seniority: str
    job_function: str
    authority_score: int


@dataclass(frozen=True)
class AssetProfile:
    """Classification of an engaged asset."""

    stage: FunnelStage
    content_type: str
    vertical: str
    stage_weight: float


class TitleNormalizer:
    """Job title normaliser using rules with TF-IDF fallback."""

    def __init__(self, config: dict):
        self._seniority_keywords = config.get("seniority_keywords", {})
        self._seniority_scores = config.get("seniority_scores", {})
        self._function_keywords = config.get("job_function_keywords", {})
        self._function_prototypes = config.get("job_function_prototypes", {})
        labels: list[str] = []
        phrases: list[str] = []
        for label, prototype_list in self._function_prototypes.items():
            for prototype in prototype_list:
                labels.append(label)
                phrases.append(prototype)
        self._prototype_labels = labels
        self._vectorizer = TfidfVectorizer(ngram_range=(1, 2))
        self._prototype_matrix = (
            self._vectorizer.fit_transform(phrases) if phrases else None
        )

    def normalise(self, job_title: str | None) -> NormalisedTitle:
        """Return normalized seniority and job function."""
        title = _normalise_text(job_title)
        seniority = self._match_keyword(title, self._seniority_keywords) or "unknown"
        job_function = self._match_keyword(title, self._function_keywords)
        if job_function is None:
            job_function = self._fallback_job_function(title)
        authority_score = int(self._seniority_scores.get(seniority, 35))
        return NormalisedTitle(
            seniority=seniority,
            job_function=job_function or "unknown",
            authority_score=authority_score,
        )

    @staticmethod
    def _match_keyword(value: str, mapping: dict[str, Iterable[str]]) -> str | None:
        for label, keywords in mapping.items():
            for keyword in keywords:
                if keyword in value:
                    return label
        return None

    def _fallback_job_function(self, title: str) -> str | None:
        if not title or self._prototype_matrix is None:
            return None
        vector = self._vectorizer.transform([title])
        scores = (vector @ self._prototype_matrix.T).toarray().ravel()
        if scores.size == 0:
            return None
        best_idx = int(np.argmax(scores))
        if float(scores[best_idx]) < 0.1:
            return None
        return self._prototype_labels[best_idx]


class AssetClassifier:
    """Classify asset into funnel stage, content type, and vertical."""

    def __init__(self, config: dict):
        self._content_keywords = config.get("content_type_keywords", {})
        self._stage_keywords = config.get("stage_keywords", {})
        self._vertical_keywords = config.get("vertical_keywords", {})
        self._stage_weights = config.get("stage_weights", {})

    def classify(
        self,
        asset_name: str | None,
        taxonomy: dict[str, str | None] | None = None,
    ) -> AssetProfile:
        """Classify an asset from the name and campaign taxonomy."""
        tax = taxonomy or {}
        if tax.get("asset_stage_override"):
            override = tax["asset_stage_override"]
            stage = override if isinstance(override, FunnelStage) else FunnelStage(str(override))
        else:
            stage = self._match_stage(asset_name or tax.get("asset_type") or "")
        content_type = self._match_label(asset_name or tax.get("asset_type") or "", self._content_keywords, "asset")
        vertical = self._match_label(
            " ".join(filter(None, [asset_name, tax.get("topic"), tax.get("vertical_override")])),
            self._vertical_keywords,
            "general",
        )
        return AssetProfile(
            stage=stage,
            content_type=content_type,
            vertical=vertical,
            stage_weight=float(self._stage_weights.get(stage.value, 1.0)),
        )

    def _match_stage(self, text: str) -> FunnelStage:
        lowered = _normalise_text(text)
        for stage_name in ("BOFU", "MOFU", "TOFU"):
            if self._contains_any(lowered, self._stage_keywords.get(stage_name, [])):
                return FunnelStage(stage_name)
        return FunnelStage.MOFU

    def _match_label(
        self,
        text: str | None,
        mapping: dict[str, Iterable[str]],
        default: str,
    ) -> str:
        lowered = _normalise_text(text)
        for label, keywords in mapping.items():
            if self._contains_any(lowered, keywords):
                return label
        return default

    @staticmethod
    def _contains_any(text: str, keywords: Iterable[str]) -> bool:
        return any(keyword in text for keyword in keywords)


class CampaignModeInferrer:
    """Infer TOFU/MOFU/BOFU from the PRD five-tag taxonomy."""

    def __init__(self, config: dict):
        self._mode_keywords = config.get("campaign_mode_keywords", {})

    def infer(self, taxonomy: dict[str, str | None], asset_stage: FunnelStage) -> FunnelStage:
        """Score each mode based on the five tags and asset stage."""
        scores = {FunnelStage.TOFU: 0.0, FunnelStage.MOFU: 0.0, FunnelStage.BOFU: 0.0}
        tag_map = {
            "asset_type": taxonomy.get("asset_type"),
            "topic": taxonomy.get("topic"),
            "audience": taxonomy.get("audience"),
            "volume": taxonomy.get("volume"),
            "sequence": taxonomy.get("sequence"),
        }
        for stage in FunnelStage:
            stage_rules = self._mode_keywords.get(stage.value, {})
            for field_name, raw_value in tag_map.items():
                value = _normalise_text(raw_value)
                keywords = stage_rules.get(field_name, [])
                if value and any(keyword in value for keyword in keywords):
                    scores[stage] += 1.0
        scores[asset_stage] += 1.5
        return max(scores.items(), key=lambda item: item[1])[0]
