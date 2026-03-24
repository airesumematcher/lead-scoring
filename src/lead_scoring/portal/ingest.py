"""Lead-file ingestion for the lightweight upload portal."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from io import BytesIO
import json
import re
from typing import Any

import pandas as pd

from lead_scoring.platform.contracts import LeadRecord


REQUIRED_FIELDS = [
    "email",
    "first_name",
    "last_name",
    "job_title",
    "company_name",
    "domain",
    "industry",
    "geography",
]


HEADER_ALIASES: dict[str, list[str]] = {
    "lead_id": ["leadid", "lead_identifier", "record_id"],
    "submitted_at": ["submission_date", "submitted_date", "created_at", "created_date", "timestamp", "date"],
    "source_partner": ["partner", "partner_name", "lead_source", "source"],
    "email": ["email_address", "e_mail", "work_email", "business_email", "contact_email"],
    "first_name": ["firstname", "first", "fname", "given_name"],
    "last_name": ["lastname", "last", "lname", "surname", "family_name"],
    "job_title": ["title", "designation", "role", "contact_title"],
    "linkedin_url": ["linkedin", "linkedin_profile", "linkedin_link"],
    "company_name": ["company", "account_name", "organization", "organisation", "business_name"],
    "domain": ["company_domain", "website", "company_website", "web_domain", "domain_name"],
    "industry": ["vertical", "company_industry", "industry_name"],
    "geography": ["geo", "location", "region", "country", "market", "territory"],
    "company_size": ["employee_band", "employee_size", "employees", "size", "company_headcount"],
    "partner_id": ["partner_identifier"],
    "approval_rate_6m": ["partner_approval_rate_6m", "partner_approval_rate", "approval_rate"],
    "approval_rate_client_6m": ["client_partner_approval_rate_6m", "partner_client_approval_rate_6m"],
    "approval_rate_vertical_6m": ["vertical_partner_approval_rate_6m", "partner_vertical_approval_rate_6m"],
    "client_acceptance_rate_6m": ["client_approval_rate_6m", "client_acceptance_rate", "account_acceptance_rate_6m"],
    "account_id": ["company_id", "account_identifier"],
    "email1_opened": ["email_1_opened", "email1_open", "opened_email_1"],
    "email1_clicked": ["email_1_clicked", "email1_click", "clicked_email_1"],
    "email2_opened": ["email_2_opened", "email2_open", "opened_email_2"],
    "email2_clicked": ["email_2_clicked", "email2_click", "clicked_email_2"],
    "download_count": ["downloads", "downloaded", "asset_downloads"],
    "visit_count": ["visits", "page_visits", "web_visits"],
}


@dataclass(frozen=True)
class PortalImportArtifacts:
    """Result of interpreting an uploaded portal file."""

    leads: list[LeadRecord]
    detected_format: str
    total_rows: int
    interpreted_headers: dict[str, str]
    warnings: list[str]
    lead_summaries: list[dict[str, str]]


def import_leads_file(
    *,
    filename: str,
    content: bytes,
    campaign_context: dict[str, Any],
) -> PortalImportArtifacts:
    """Parse CSV/XLSX input and build PRD lead payloads."""
    dataframe, detected_format = _load_dataframe(filename, content)
    original_headers = [str(column) for column in dataframe.columns]
    normalized_headers = {_normalize_header(column): str(column) for column in original_headers}
    interpreted_headers = _resolve_header_mapping(normalized_headers)
    missing_required = [field for field in REQUIRED_FIELDS if field not in interpreted_headers]
    if missing_required:
        raise ValueError(
            "Missing required lead fields after header interpretation: "
            + ", ".join(missing_required)
        )

    warnings = []
    unused_headers = [
        original
        for normalized, original in normalized_headers.items()
        if original not in interpreted_headers.values()
    ]
    if unused_headers:
        warnings.append(
            "Unused columns ignored: " + ", ".join(unused_headers[:12]) + ("..." if len(unused_headers) > 12 else "")
        )

    rows = dataframe.fillna("").to_dict(orient="records")
    leads: list[LeadRecord] = []
    lead_summaries: list[dict[str, str]] = []
    for index, row in enumerate(rows):
        canonical_row = _to_canonical_row(row, interpreted_headers)
        lead = _build_lead_record(canonical_row, index=index, campaign_context=campaign_context)
        leads.append(lead)
        lead_summaries.append(
            {
                "lead_id": lead.lead_id,
                "company_name": lead.company.company_name,
                "domain": lead.company.domain,
            }
        )

    return PortalImportArtifacts(
        leads=leads,
        detected_format=detected_format,
        total_rows=len(leads),
        interpreted_headers=interpreted_headers,
        warnings=warnings,
        lead_summaries=lead_summaries,
    )


def _load_dataframe(filename: str, content: bytes) -> tuple[pd.DataFrame, str]:
    suffix = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    if suffix in {"xlsx", "xlsm", "xltx"}:
        frame = pd.read_excel(BytesIO(content), dtype=str, engine="openpyxl")
        return frame, "excel"
    if suffix == "xls":
        frame = pd.read_excel(BytesIO(content), dtype=str, engine="xlrd")
        return frame, "excel"
    if suffix == "csv":
        frame = _read_csv_bytes(content)
        return frame, "csv"
    raise ValueError("Unsupported file type. Upload CSV or Excel (.xlsx/.xls).")


def _read_csv_bytes(content: bytes) -> pd.DataFrame:
    last_error: Exception | None = None
    for encoding in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            return pd.read_csv(BytesIO(content), dtype=str, encoding=encoding)
        except Exception as exc:  # pragma: no cover - diagnostic fallback
            last_error = exc
    raise ValueError(f"Unable to read CSV file: {last_error}") from last_error


def _resolve_header_mapping(normalized_to_original: dict[str, str]) -> dict[str, str]:
    normalized_headers = list(normalized_to_original.keys())
    available = {_collapse_header(header): header for header in normalized_headers}
    mapping: dict[str, str] = {}
    used_normalized: set[str] = set()
    for canonical, aliases in HEADER_ALIASES.items():
        candidates = [canonical, *aliases]
        match = _match_header(candidates, available, used_normalized)
        if match:
            mapping[canonical] = match
            used_normalized.add(match)
    for field in REQUIRED_FIELDS:
        if field not in mapping and field in normalized_headers:
            mapping[field] = field
    return {canonical: normalized_to_original.get(header, header) for canonical, header in mapping.items()}


def _match_header(
    candidates: list[str],
    available: dict[str, str],
    used_normalized: set[str],
) -> str | None:
    candidate_collapsed = [_collapse_header(candidate) for candidate in candidates]
    for collapsed in candidate_collapsed:
        if collapsed in available and available[collapsed] not in used_normalized:
            return available[collapsed]
    for collapsed, normalized in available.items():
        if normalized in used_normalized:
            continue
        for candidate in candidate_collapsed:
            if candidate and (candidate in collapsed or collapsed in candidate):
                return normalized
    return None


def _to_canonical_row(row: dict[str, Any], interpreted_headers: dict[str, str]) -> dict[str, str]:
    normalized_lookup = {_normalize_header(key): str(value).strip() for key, value in row.items()}
    canonical: dict[str, str] = {}
    for field, source_header in interpreted_headers.items():
        canonical[field] = normalized_lookup.get(_normalize_header(source_header), "").strip()
    return canonical


def _build_lead_record(
    canonical_row: dict[str, str],
    *,
    index: int,
    campaign_context: dict[str, Any],
) -> LeadRecord:
    submitted_at = canonical_row.get("submitted_at") or datetime.now(UTC).isoformat()
    lead_id = canonical_row.get("lead_id") or f"{campaign_context.get('campaign_id', 'ACE')}-{index + 1:04d}"
    asset_name = campaign_context.get("asset_name") or canonical_row.get("asset_name") or None
    return LeadRecord.model_validate(
        {
            "lead_id": lead_id,
            "submitted_at": submitted_at,
            "source_partner": canonical_row.get("source_partner") or campaign_context.get("partner_id"),
            "contact": {
                "email": canonical_row.get("email"),
                "first_name": canonical_row.get("first_name"),
                "last_name": canonical_row.get("last_name"),
                "job_title": canonical_row.get("job_title"),
                "linkedin_url": canonical_row.get("linkedin_url") or None,
            },
            "company": {
                "company_name": canonical_row.get("company_name"),
                "domain": canonical_row.get("domain"),
                "industry": canonical_row.get("industry"),
                "geography": canonical_row.get("geography"),
                "company_size": canonical_row.get("company_size") or None,
            },
            "campaign": {
                "campaign_id": campaign_context.get("campaign_id"),
                "client_id": campaign_context.get("client_id"),
                "campaign_name": campaign_context.get("campaign_name"),
                "brief_text": campaign_context.get("brief_text") or None,
                "asset_name": asset_name,
                "target_profile": {
                    "industries": [campaign_context.get("vertical_override")] if campaign_context.get("vertical_override") else [],
                    "geographies": [str(canonical_row.get("geography", "")).lower()] if canonical_row.get("geography") else [],
                    "company_sizes": [str(canonical_row.get("company_size", "")).lower()] if canonical_row.get("company_size") else [],
                    "job_functions": [],
                    "seniorities": [],
                    "required_personas": [],
                },
                "taxonomy": {
                    "asset_type": campaign_context.get("asset_type") or None,
                    "topic": campaign_context.get("topic") or None,
                    "audience": campaign_context.get("audience") or None,
                    "volume": campaign_context.get("volume") or None,
                    "sequence": campaign_context.get("sequence") or None,
                    "asset_stage_override": campaign_context.get("asset_stage_override") or None,
                    "vertical_override": campaign_context.get("vertical_override") or None,
                },
                "history_approval_rate": _parse_float(campaign_context.get("history_approval_rate")),
            },
            "partner_signals": {
                "partner_id": canonical_row.get("partner_id") or campaign_context.get("partner_id") or None,
                "approval_rate_6m": _parse_float(canonical_row.get("approval_rate_6m") or campaign_context.get("approval_rate_6m")),
                "approval_rate_client_6m": _parse_float(
                    canonical_row.get("approval_rate_client_6m") or campaign_context.get("approval_rate_client_6m")
                ),
                "approval_rate_vertical_6m": _parse_float(
                    canonical_row.get("approval_rate_vertical_6m") or campaign_context.get("approval_rate_vertical_6m")
                ),
            },
            "account_signals": {
                "account_id": canonical_row.get("account_id") or None,
                "client_acceptance_rate_6m": _parse_float(
                    canonical_row.get("client_acceptance_rate_6m") or campaign_context.get("client_acceptance_rate_6m")
                ),
                "recent_personas": [],
            },
            "engagement_events": _build_engagement_events(canonical_row, submitted_at, asset_name),
        }
    )


def _build_engagement_events(canonical_row: dict[str, str], submitted_at: str, asset_name: str | None) -> list[dict[str, Any]]:
    base_date = _parse_datetime(submitted_at)
    definitions = [
        ("email1_opened", "open", 1, 6),
        ("email1_clicked", "click", 1, 5),
        ("email2_opened", "open", 2, 2),
        ("email2_clicked", "click", 2, 1),
        ("download_count", "download", 2, 1),
        ("visit_count", "visit", 1, 3),
    ]
    events: list[dict[str, Any]] = []
    for column, event_type, email_number, offset_days in definitions:
        count = _parse_int(canonical_row.get(column))
        for item_index in range(count):
            occurred_at = base_date - timedelta(days=offset_days + item_index)
            events.append(
                {
                    "event_type": event_type,
                    "occurred_at": occurred_at.isoformat(),
                    "asset_name": asset_name,
                    "email_number": email_number,
                    "metadata": {},
                }
            )
    return events


def _parse_datetime(value: str | None) -> datetime:
    if not value:
        return datetime.now(UTC)
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC)
    except ValueError:
        return datetime.now(UTC)


def _parse_float(value: Any) -> float | None:
    if value in ("", None):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed


def _parse_int(value: Any) -> int:
    if value in ("", None):
        return 0
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def _normalize_header(value: Any) -> str:
    cleaned = str(value or "").replace("\ufeff", "").strip().lower()
    cleaned = re.sub(r"(?<!^)(?=[A-Z])", "_", cleaned)
    cleaned = re.sub(r"[^a-z0-9]+", "_", cleaned)
    return cleaned.strip("_")


def _collapse_header(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", _normalize_header(value))
