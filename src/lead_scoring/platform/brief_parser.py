"""Campaign brief parser and XLSX campaign spec parser."""

from __future__ import annotations

import io
import re
from typing import TYPE_CHECKING

from .contracts import TargetProfile

if TYPE_CHECKING:
    from .contracts import CampaignContext


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


class CampaignSpecParser:
    """Parse a campaign spec XLSX file into a CampaignContext.

    Supports two layouts:
      - Key-value: column A = field name, column B = value (one field per row)
      - Header-row: row 1 = field names, row 2 = values (one column per field)

    Any unrecognised fields are collected into extra_context and appended to
    brief_text so the existing CampaignBriefParser can extract ICP hints from them.
    """

    _FIELD_MAP: dict[str, str] = {
        "campaign id": "campaign_id", "campaign": "campaign_id", "id": "campaign_id",
        "campaign number": "campaign_id", "camp id": "campaign_id", "camp": "campaign_id",
        "campaign ref": "campaign_id", "reference": "campaign_id", "ref": "campaign_id",
        "campaign code": "campaign_id", "code": "campaign_id",
        "client id": "client_id", "client": "client_id", "advertiser": "client_id",
        "company": "client_id", "brand": "client_id", "account": "client_id",
        "client name": "client_id", "company name": "client_id", "brand name": "client_id",
        "account name": "client_id", "organization": "client_id", "org": "client_id",
        "customer": "client_id", "sponsor": "client_id",
        "campaign name": "campaign_name", "name": "campaign_name",
        "industry": "industries", "industries": "industries",
        "vertical": "industries", "target industry": "industries", "target industries": "industries",
        "geography": "geographies", "geographies": "geographies",
        "geo": "geographies", "region": "geographies",
        "target geo": "geographies", "target geography": "geographies",
        "company size": "company_sizes", "company sizes": "company_sizes",
        "firmographic": "company_sizes", "employee count": "company_sizes", "employees": "company_sizes",
        "job function": "job_functions", "job functions": "job_functions",
        "function": "job_functions", "functions": "job_functions", "department": "job_functions",
        "seniority": "seniorities", "seniorities": "seniorities",
        "level": "seniorities", "job level": "seniorities",
        "persona": "required_personas", "personas": "required_personas",
        "required personas": "required_personas", "buying committee": "required_personas",
        "target personas": "required_personas",
        "approval rate": "history_approval_rate", "historical rate": "history_approval_rate",
        "history approval rate": "history_approval_rate",
        "asset": "asset_name", "asset name": "asset_name",
        "brief": "brief_text", "description": "brief_text",
        "campaign brief": "brief_text", "objective": "brief_text",
    }
    _LIST_FIELDS = frozenset({
        "industries", "geographies", "company_sizes",
        "job_functions", "seniorities", "required_personas",
    })

    def parse(self, file_bytes: bytes, filename: str = "") -> "CampaignContext":
        """Parse a campaign spec file (CSV or XLSX) and return a CampaignContext."""
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        if ext == "csv" or (ext not in ("xlsx", "xls") and self._looks_like_csv(file_bytes)):
            return self._parse_csv(file_bytes)
        return self._parse_xlsx(file_bytes)

    def _looks_like_csv(self, file_bytes: bytes) -> bool:
        """Heuristic: CSV starts with printable ASCII, not the PK zip header of XLSX."""
        return not file_bytes.startswith(b"PK")

    def _parse_csv(self, file_bytes: bytes) -> "CampaignContext":
        """Parse a key-value or header-row CSV campaign spec."""
        import csv as csv_module

        text = file_bytes.decode("utf-8-sig", errors="replace")
        reader = list(csv_module.reader(io.StringIO(text)))
        if not reader:
            raise ValueError("Campaign spec CSV is empty")

        rows = [tuple(row) for row in reader]
        extracted = self._try_key_value(rows) or self._try_header_row(rows)
        if not extracted:
            raise ValueError(
                "Could not parse campaign spec CSV. Use key-value layout "
                "(col A = field name, col B = value) or header-row layout "
                "(row 1 = field names, row 2 = values)."
            )
        return self._build_context(extracted)

    def _parse_xlsx(self, file_bytes: bytes) -> "CampaignContext":
        """Parse an XLSX campaign spec using python-calamine (Rust-based, no XML dependency)."""
        try:
            import pandas as pd
            df = pd.read_excel(io.BytesIO(file_bytes), header=None, engine="calamine", dtype=str)
        except ImportError as exc:
            raise ValueError(
                "python-calamine is required for XLSX parsing. Run: pip install python-calamine"
            ) from exc
        except Exception as exc:
            raise ValueError(f"Could not open XLSX file: {exc}") from exc

        rows = [
            tuple(None if pd.isna(v) else str(v).strip() for v in row)
            for _, row in df.iterrows()
        ]
        rows = [r for r in rows if any(v for v in r)]

        if not rows:
            raise ValueError("Campaign spec XLSX is empty")

        extracted = self._try_key_value(rows) or self._try_header_row(rows)
        if not extracted:
            raise ValueError(
                "Could not parse campaign spec XLSX. Use key-value layout "
                "(col A = field name, col B = value) or header-row layout "
                "(row 1 = field names, row 2 = values)."
            )
        return self._build_context(extracted)

    def _normalise_key(self, raw) -> str:
        return str(raw or "").strip().lower().replace("_", " ").replace("-", " ")

    def _try_key_value(self, rows: list[tuple]) -> dict[str, list[str]] | None:
        if not rows or not rows[0] or len(rows[0]) < 2:
            return None
        text_rows = [r for r in rows if r and r[0] and isinstance(r[0], str)
                     and not str(r[0]).replace(".", "").isnumeric()]
        if len(text_rows) < 2:
            return None

        accumulated: dict[str, list[str]] = {}
        for row in rows:
            if not row or not row[0]:
                continue
            value_raw = row[1] if len(row) > 1 else None
            if value_raw is None or str(value_raw).strip() == "":
                continue
            canonical = self._FIELD_MAP.get(self._normalise_key(row[0]))
            self._accumulate(accumulated, canonical, str(row[0]), str(value_raw).strip())
        return accumulated or None

    def _try_header_row(self, rows: list[tuple]) -> dict[str, list[str]] | None:
        if len(rows) < 2:
            return None
        header_row, value_row = rows[0], rows[1]
        accumulated: dict[str, list[str]] = {}
        for col_idx, header in enumerate(header_row):
            if not header:
                continue
            value_raw = value_row[col_idx] if col_idx < len(value_row) else None
            if value_raw is None or str(value_raw).strip() == "":
                continue
            canonical = self._FIELD_MAP.get(self._normalise_key(header))
            self._accumulate(accumulated, canonical, str(header), str(value_raw).strip())
        return accumulated or None

    def _accumulate(
        self,
        acc: dict[str, list[str]],
        canonical: str | None,
        raw_key: str,
        value: str,
    ) -> None:
        if canonical in self._LIST_FIELDS:
            acc.setdefault(canonical, []).extend(p.strip() for p in value.split(",") if p.strip())
        elif canonical:
            acc[canonical] = [value]
        else:
            acc.setdefault("extra_context", []).append(f"{raw_key}: {value}")

    def _build_context(self, extracted: dict[str, list[str]]) -> "CampaignContext":
        import re
        import uuid
        from .contracts import CampaignContext, TargetProfile

        def first(key: str) -> str | None:
            vals = extracted.get(key, [])
            return vals[0] if vals else None

        def slugify(text: str) -> str:
            return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")

        campaign_id = first("campaign_id")
        client_id = first("client_id")
        campaign_name_val = first("campaign_name")

        if not campaign_id:
            campaign_id = slugify(campaign_name_val) if campaign_name_val else f"camp-{uuid.uuid4().hex[:8]}"

        if not client_id:
            first_word = (campaign_name_val or "").split()
            client_id = slugify(first_word[0]) if first_word else f"client-{uuid.uuid4().hex[:6]}"

        brief_parts = list(extracted.get("brief_text", []))
        extras = extracted.get("extra_context", [])
        if extras:
            brief_parts.append("\n".join(extras))
        brief_text = "\n".join(brief_parts) if brief_parts else None

        history_approval_rate: float | None = None
        raw_rate = first("history_approval_rate")
        if raw_rate:
            try:
                val = float(raw_rate.replace("%", "").strip())
                rate = val / 100.0 if val > 1.0 else val
                history_approval_rate = max(0.0, min(1.0, rate))
            except ValueError:
                pass

        return CampaignContext(
            campaign_id=campaign_id,
            client_id=client_id,
            campaign_name=first("campaign_name") or campaign_id,
            brief_text=brief_text,
            asset_name=first("asset_name"),
            target_profile=TargetProfile(
                industries=extracted.get("industries", []),
                geographies=extracted.get("geographies", []),
                company_sizes=extracted.get("company_sizes", []),
                job_functions=extracted.get("job_functions", []),
                seniorities=extracted.get("seniorities", []),
                required_personas=extracted.get("required_personas", []),
            ),
            history_approval_rate=history_approval_rate,
        )
