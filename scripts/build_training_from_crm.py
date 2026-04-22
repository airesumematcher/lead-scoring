"""
Build a PRD-compatible training CSV from CRM historical leads.

Converts raw CRM data (email, company_name, converted) into the 14-feature
format expected by run_monthly_retrain.py, then optionally triggers retraining.

Usage:
    python scripts/build_training_from_crm.py
    python scripts/build_training_from_crm.py --crm-path data_processed/crm_historical_leads.csv
    python scripts/build_training_from_crm.py --retrain

For real Salesforce data, export a CSV with at minimum these columns:
    email, company_name, job_title, industry, geography, company_size,
    created_date, converted (0/1 or approved/rejected)
"""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

# Add project root to path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from lead_scoring.platform.contracts import (
    CampaignContext,
    CampaignTaxonomy,
    CompanyPayload,
    ContactPayload,
    LeadRecord,
    PartnerSignals,
    TargetProfile,
)
from lead_scoring.platform.engine import BuyingIntelligenceService

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

# Generic campaign used for feature extraction when no campaign context is available
_DEFAULT_CAMPAIGN = CampaignContext(
    campaign_id="TRAINING-DEFAULT",
    client_id="TRAINING",
    campaign_name="Training Feature Extraction",
    target_profile=TargetProfile(),
    taxonomy=CampaignTaxonomy(asset_type="whitepaper"),
)


def _normalise_status(value) -> str | None:
    """Map various outcome representations to 'approved' / 'rejected'."""
    if pd.isna(value):
        return None
    v = str(value).strip().lower()
    if v in ("1", "true", "yes", "converted", "approved", "won", "closed won"):
        return "approved"
    if v in ("0", "false", "no", "unconverted", "rejected", "lost", "closed lost"):
        return "rejected"
    return None


def _build_lead_record(row: pd.Series, idx: int) -> LeadRecord:
    """Construct a minimal LeadRecord from a CRM row."""
    email = str(row.get("email", f"lead{idx}@unknown.com"))
    company = str(row.get("company_name", "Unknown Company"))
    job_title = str(row.get("job_title", "Unknown"))
    industry = str(row.get("industry", "Technology"))
    geography = str(row.get("geography", "US"))
    company_size = str(row.get("company_size", "Mid-Market"))
    domain = email.split("@")[-1] if "@" in email else "unknown.com"

    # Parse created_date for submitted_at
    raw_date = row.get("created_date") or row.get("submitted_at")
    try:
        submitted_at = pd.to_datetime(raw_date).to_pydatetime().replace(tzinfo=UTC)
    except Exception:
        submitted_at = datetime.now(UTC)

    return LeadRecord(
        lead_id=str(row.get("lead_id", f"CRM-TRAIN-{idx:05d}")),
        submitted_at=submitted_at,
        source_partner=str(row.get("source_partner", "CRM")),
        contact=ContactPayload(
            email=email,
            first_name=str(row.get("first_name", "Unknown")),
            last_name=str(row.get("last_name", "Lead")),
            job_title=job_title,
        ),
        company=CompanyPayload(
            company_name=company,
            domain=domain,
            industry=industry,
            geography=geography,
            company_size=company_size,
        ),
        campaign=_DEFAULT_CAMPAIGN,
        partner_signals=PartnerSignals(
            approval_rate_6m=row.get("partner_approval_rate") or None,
            approval_rate_client_6m=row.get("client_approval_rate") or None,
        ),
    )


def build_training_csv(
    crm_path: str = "data_processed/crm_historical_leads.csv",
    output_path: str = "data_processed/crm_training_features.csv",
) -> Path:
    crm_path = ROOT / crm_path
    output_path = ROOT / output_path

    print(f"Loading CRM data from: {crm_path}")
    crm = pd.read_csv(crm_path)
    print(f"  {len(crm)} rows loaded")

    # Determine outcome column
    outcome_col = None
    for col in ("status", "converted", "outcome", "approved", "won"):
        if col in crm.columns:
            outcome_col = col
            break

    if outcome_col is None:
        raise ValueError(
            f"No outcome column found in {crm_path}. "
            "Expected one of: status, converted, outcome, approved, won.\n"
            "For Salesforce exports, add a column 'converted' with 1=approved, 0=rejected."
        )

    print(f"  Outcome column: '{outcome_col}'")

    service = BuyingIntelligenceService()
    rows = []
    skipped = 0

    for idx, row in crm.iterrows():
        status = _normalise_status(row[outcome_col])
        if status is None:
            skipped += 1
            continue

        try:
            lead = _build_lead_record(row, idx)
            result = service.score_lead(lead)

            # Extract feature scores from the scored result
            # LeadScoreResult has: .breakdown (LeadQualityBreakdown), .buying_group (BuyingGroupSummary)
            bd = result.breakdown
            bg = result.buying_group
            features = {
                "status": status,
                "authority_score": bd.fit_score,       # closest proxy for authority
                "fit_score": bd.fit_score,
                "intent_score": bd.intent_score,
                "partner_signal_score": bd.partner_signal_score,
                "client_history_score": bd.client_history_score,
                "campaign_history_score": bd.campaign_history_score,
                "data_quality_score": bd.data_quality_score,
                "icp_match_score": bd.icp_match_score,
                "buying_group_score": bg.buying_group_score,
                "unique_persona_count": bg.unique_persona_count,
                "late_stage_signal": bd.intent_score,   # proxy
                "email_engagement_score": bd.intent_score,  # proxy
                "second_touch_signal": 0,
                "recency_score": 50,
            }
            rows.append(features)

        except Exception as e:
            print(f"  Warning: skipped row {idx} ({e})")
            skipped += 1

    if not rows:
        raise RuntimeError("No rows successfully processed. Check CRM data format.")

    df = pd.DataFrame(rows)
    # Ensure column order matches training expectations
    col_order = ["status"] + FEATURE_COLUMNS
    df = df[[c for c in col_order if c in df.columns]]

    df.to_csv(output_path, index=False)

    approved = (df["status"] == "approved").sum()
    rejected = (df["status"] == "rejected").sum()
    print(f"\n✅ Training CSV written to: {output_path}")
    print(f"   {len(df)} rows ({approved} approved, {rejected} rejected, {skipped} skipped)")
    print(f"   Class balance: {approved/len(df)*100:.1f}% approved")

    if approved < 10 or rejected < 10:
        print("\n⚠️  WARNING: Very few samples per class.")
        print("   For a meaningful model, you need 100+ labeled outcomes per class.")
        print("   Request a Salesforce export from Rev Ops with actual approved/rejected outcomes.")

    return output_path


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--crm-path", default="data_processed/crm_historical_leads.csv")
    parser.add_argument("--output-path", default="data_processed/crm_training_features.csv")
    parser.add_argument("--retrain", action="store_true", help="Run retraining after building CSV")
    parser.add_argument("--force-promote", action="store_true", help="Force model promotion even if AUC < baseline")
    args = parser.parse_args()

    output_path = build_training_csv(args.crm_path, args.output_path)

    if args.retrain:
        print("\nRunning retraining pipeline...")
        import subprocess
        cmd = [sys.executable, str(ROOT / "scripts/run_monthly_retrain.py"), str(output_path)]
        if args.force_promote:
            cmd.append("--force-promote")
        result = subprocess.run(cmd, capture_output=False)
        sys.exit(result.returncode)


if __name__ == "__main__":
    main()
