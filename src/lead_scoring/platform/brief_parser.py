"""Campaign brief parser with rule-based extraction."""

from __future__ import annotations

import re

from .contracts import TargetProfile


class CampaignBriefParser:
    """Parse campaign brief text into an ICP-like target profile."""

    def __init__(self, config: dict):
        self._vertical_keywords = config.get("vertical_keywords", {})
        self._geography_keywords = config.get("geography_keywords", {})
        self._size_keywords = config.get("size_keywords", {})
        self._function_keywords = config.get("job_function_keywords", {})
        self._seniority_keywords = config.get("seniority_keywords", {})

    def parse(self, brief_text: str | None) -> TargetProfile:
        """Extract lightweight targeting hints from a campaign brief."""
        if not brief_text:
            return TargetProfile()

        lowered = " ".join(str(brief_text).lower().split())
        industries = self._collect_matches(lowered, self._vertical_keywords)
        geographies = self._collect_matches(lowered, self._geography_keywords)
        company_sizes = self._collect_matches(lowered, self._size_keywords)
        job_functions = self._collect_matches(lowered, self._function_keywords)
        seniorities = self._collect_matches(lowered, self._seniority_keywords)

        # Capture explicit numeric size ranges when present.
        explicit_size_matches = re.findall(r"\b\d{2,5}\s*[-+]\s*\d{0,5}\b", lowered)
        company_sizes.extend(match.replace(" ", "") for match in explicit_size_matches)

        return TargetProfile(
            industries=self._unique(industries),
            geographies=self._unique(geographies),
            company_sizes=self._unique(company_sizes),
            job_functions=self._unique(job_functions),
            seniorities=self._unique(seniorities),
        )

    @staticmethod
    def _unique(values: list[str]) -> list[str]:
        seen: set[str] = set()
        ordered: list[str] = []
        for value in values:
            if value not in seen:
                ordered.append(value)
                seen.add(value)
        return ordered

    @staticmethod
    def _collect_matches(text: str, mapping: dict[str, list[str]]) -> list[str]:
        matches: list[str] = []
        for label, keywords in mapping.items():
            if any(str(keyword).lower() in text for keyword in keywords):
                matches.append(label)
        return matches
