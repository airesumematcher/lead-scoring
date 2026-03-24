#!/usr/bin/env python3
"""Extract portal-compatible lead CSV from Latest_leads_data.csv.

Parses the RESPONSE JSON column to pull contact details, then writes a
CSV in the exact format the portal's drag-and-drop uploader expects.

Usage:
    python3 scripts/extract_portal_leads.py [--limit N] [--output PATH]

    --limit   Max rows to extract (default: 500, use 0 for all)
    --output  Output CSV path (default: sample_data/portal_leads_sample.csv)
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
INPUT_FILE = ROOT / "sample_data" / "Latest_leads_data.csv"
DEFAULT_OUTPUT = ROOT / "sample_data" / "portal_leads_sample.csv"

# Map AUDIT_STATUS to portal-friendly status (informational column only)
STATUS_MAP = {
    "Approve - Final": "Accepted",
    "Reject - Lead Quality": "Rejected",
    "Reject - Weekly Pacing": "Rejected",
    "Refund": "Rejected",
    "Buy Back": "Rejected",
}

# Fake domain suffix used when domain can't be derived from email
FALLBACK_DOMAIN = "unknown.com"


def _parse_response(raw: str) -> dict:
    if not raw or pd.isna(raw):
        return {}
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {}


def _email_to_domain(email: str) -> str:
    """Extract domain from email address."""
    if "@" in str(email):
        return str(email).split("@", 1)[1].strip().lower()
    return FALLBACK_DOMAIN


def _split_name(full_email: str) -> tuple[str, str]:
    """Best-effort first/last name from email local part."""
    local = str(full_email).split("@")[0] if "@" in str(full_email) else ""
    # Handle patterns like firstname.lastname or firstname_lastname
    parts = re.split(r"[._\-]", local)
    parts = [p.capitalize() for p in parts if p and p.isalpha()]
    if len(parts) >= 2:
        return parts[0], " ".join(parts[1:])
    if parts:
        return parts[0], "Unknown"
    return "Unknown", "Unknown"


def _seniority_to_title(seniority: str, job_title_raw: str) -> str:
    """Use raw job title from RESPONSE if available, fallback to seniority."""
    if job_title_raw and str(job_title_raw).strip():
        return str(job_title_raw).strip()
    seniority_map = {
        "c-suite": "Chief Executive Officer",
        "vp": "Vice President",
        "director": "Director",
        "manager": "Manager",
        "professional": "Specialist",
        "practitioner": "Practitioner",
    }
    return seniority_map.get(str(seniority).lower(), "Business Professional")


def _engagement_flags(response: dict, submitted_at: str) -> dict:
    """Extract basic engagement flags from RESPONSE JSON."""
    # lastInteractionDate presence → email was opened
    last_interaction = response.get("lastInteractionDate", {})
    interaction_status = last_interaction.get("status", "")
    engaged = interaction_status in ("within_7_days", "within_30_days", "within_90_days")
    return {
        "email1_opened": "1" if engaged else "0",
        "email1_clicked": "0",
        "email2_opened": "0",
        "email2_clicked": "0",
        "download_count": "0",
        "visit_count": "0",
    }


def build(
    input_path: Path = INPUT_FILE,
    output_path: Path = DEFAULT_OUTPUT,
    limit: int = 500,
) -> pd.DataFrame:
    print(f"Reading {input_path} …")
    raw = pd.read_csv(input_path)
    print(f"  Loaded {len(raw):,} rows")

    # Take a stratified sample: mix of approved and rejected
    approved = raw[raw["AUDIT_STATUS"] == "Approve - Final"]
    rejected = raw[raw["AUDIT_STATUS"].isin(["Reject - Lead Quality", "Reject - Weekly Pacing"])]

    if limit > 0:
        n_approved = min(int(limit * 0.85), len(approved))
        n_rejected = min(limit - n_approved, len(rejected))
        sample = pd.concat([
            approved.sample(n=n_approved, random_state=42),
            rejected.sample(n=n_rejected, random_state=42),
        ]).sample(frac=1, random_state=42).reset_index(drop=True)
    else:
        sample = raw.copy()

    print(f"  Sampling {len(sample):,} rows "
          f"({(sample['AUDIT_STATUS']=='Approve - Final').sum()} approved, "
          f"{(sample['AUDIT_STATUS']!='Approve - Final').sum()} rejected)")

    rows = []
    skipped = 0
    for _, row in sample.iterrows():
        response = _parse_response(row.get("RESPONSE", ""))
        email_info = response.get("email", {})
        email = str(email_info.get("value", "")).strip()

        if not email or "@" not in email:
            skipped += 1
            continue

        job_title_info = response.get("jobTitle", {})
        job_title_raw = job_title_info.get("value", "")
        seniority = job_title_info.get("seniority", "professional")
        job_title = _seniority_to_title(seniority, job_title_raw)

        first_name, last_name = _split_name(email)
        domain = _email_to_domain(email)

        score_info = response.get("scoreInfo", {})
        company_size_info = response.get("companySize", {})
        company_size_label = company_size_info.get("value", "")
        size_normalized = _normalize_company_size(company_size_label)

        linkedin_info = response.get("linkedInUrl", {})
        linkedin_url = linkedin_info.get("value", "") or ""

        engagement = _engagement_flags(response, str(row.get("LAST_AUDIT_DATE", "")))

        # Map AUDIT_STATUS to approval_rate proxy for partner_signals
        is_approved = row.get("AUDIT_STATUS") == "Approve - Final"
        # Use PARTNER_NAME as source_partner
        partner_name = str(row.get("PARTNER_NAME", "")).strip() or None

        rows.append({
            "lead_id": f"LDS-{row.get('LEAD_EVENT_ID', '')}",
            "submitted_at": str(row.get("LAST_AUDIT_DATE", "")).strip() or "",
            "source_partner": partner_name or "",
            "email": email,
            "first_name": first_name,
            "last_name": last_name,
            "job_title": job_title,
            "linkedin_url": linkedin_url,
            "company_name": domain.split(".")[0].capitalize() + " Inc",
            "domain": domain,
            "industry": _infer_industry(domain, job_title),
            "geography": "United States",
            "company_size": size_normalized,
            "partner_id": partner_name or "",
            "approval_rate_6m": "",
            "approval_rate_client_6m": "",
            "approval_rate_vertical_6m": "",
            "client_acceptance_rate_6m": "",
            **engagement,
            # Extra context columns (ignored by portal but useful for inspection)
            "_audit_status": STATUS_MAP.get(str(row.get("AUDIT_STATUS", "")), "Unknown"),
            "_lead_score": str(row.get("LEAD_SCORE", "")),
            "_client": str(row.get("CLIENT", "")),
            "_campaign_id": str(row.get("CAMPAIGN_ID", "")),
        })

    output = pd.DataFrame(rows)
    if output.empty:
        print(f"  ERROR: No valid rows extracted (skipped {skipped} rows with missing email)")
        return output

    print(f"  Extracted {len(output):,} leads (skipped {skipped} with no email)")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output.to_csv(output_path, index=False)
    print(f"\nPortal-compatible CSV written to {output_path}")
    print(f"  Columns: {list(output.columns)}")
    print(f"  Status breakdown:\n{output['_audit_status'].value_counts().to_string()}")
    print(f"\nTo use in the portal:")
    print(f"  1. Start the API:  uvicorn lead_scoring.api.app:app --reload --port 8000")
    print(f"  2. Open:           http://localhost:8000")
    print(f"  3. Upload:         {output_path}")
    return output


def _normalize_company_size(label: str) -> str:
    label = str(label).strip()
    mapping = {
        "Micro": "1-9",
        "Small": "10-49",
        "Medium-Small": "50-199",
        "Medium ": "200-499",
        "Medium-Large": "500-999",
        "Large": "1000-4999",
        "XLarge": "5000-10000",
        "XXLarge": "10000+",
    }
    for key, val in mapping.items():
        if key.lower() in label.lower():
            return val
    return ""


def _infer_industry(domain: str, job_title: str) -> str:
    """Rough industry inference from domain TLD and job title keywords."""
    domain_lower = domain.lower()
    title_lower = job_title.lower()
    if any(k in domain_lower for k in ["health", "med", "hospital", "clinic", "pharma"]):
        return "Healthcare"
    if any(k in domain_lower for k in ["bank", "finance", "capital", "invest", "insur"]):
        return "Financial Services"
    if any(k in domain_lower for k in ["tech", "soft", "cloud", "data", "sys", "net"]):
        return "Technology"
    if any(k in title_lower for k in ["clinical", "medical", "health", "nurse", "physician"]):
        return "Healthcare"
    if any(k in title_lower for k in ["financial", "accounting", "bank", "treasury"]):
        return "Financial Services"
    return "Technology"


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract portal-compatible leads from Latest_leads_data.csv")
    parser.add_argument("--limit", type=int, default=500,
                        help="Max rows to extract (0 = all, default: 500)")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT,
                        help=f"Output CSV path (default: {DEFAULT_OUTPUT})")
    args = parser.parse_args()
    result = build(limit=args.limit, output_path=args.output)
    return 0 if not result.empty else 0


if __name__ == "__main__":
    sys.exit(main())
