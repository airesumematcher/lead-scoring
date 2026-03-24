"""Sample payloads for the PRD-aligned buying intelligence platform."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from lead_scoring.platform.contracts import (
    AccountSignals,
    CampaignContext,
    CampaignTaxonomy,
    CompanyPayload,
    ContactPayload,
    EngagementEvent,
    FunnelStage,
    LeadRecord,
    PartnerSignals,
    PersonaSnapshot,
    TargetProfile,
)


def build_priority_lead() -> LeadRecord:
    """High-fit, high-intent lead that should be delivered."""
    now = datetime.now(UTC)
    return LeadRecord(
        lead_id="ACE-PRD-001",
        submitted_at=now,
        source_partner="partner-alpha",
        contact=ContactPayload(
            email="nina.carter@northstarhealth.com",
            first_name="Nina",
            last_name="Carter",
            job_title="VP Clinical Operations",
        ),
        company=CompanyPayload(
            company_name="Northstar Health",
            domain="northstarhealth.com",
            industry="healthcare",
            geography="United States",
            company_size="1000+",
        ),
        campaign=CampaignContext(
            campaign_id="HC-BOFU-2026-01",
            client_id="client-health-01",
            campaign_name="Clinical ROI Acceleration",
            brief_text=(
                "Target healthcare provider executives across clinical, finance, and IT teams "
                "in the United States. Prioritize enterprise hospitals evaluating ROI and implementation readiness."
            ),
            asset_name="Clinical ROI Case Study",
            target_profile=TargetProfile(
                industries=["healthcare"],
                geographies=["united states"],
                company_sizes=["enterprise", "1000+"],
                job_functions=["clinical", "finance", "it"],
                seniorities=["executive", "vp", "director"],
                required_personas=["clinical", "finance", "it"],
            ),
            taxonomy=CampaignTaxonomy(
                asset_type="case study",
                topic="decision",
                audience="late stage shortlist",
                volume="highly targeted",
                sequence="decision",
                asset_stage_override=FunnelStage.BOFU,
                vertical_override="healthcare",
            ),
            history_approval_rate=0.77,
        ),
        partner_signals=PartnerSignals(
            partner_id="partner-alpha",
            approval_rate_6m=0.81,
            approval_rate_client_6m=0.79,
            approval_rate_vertical_6m=0.76,
        ),
        account_signals=AccountSignals(
            account_id="acct-northstar-health",
            client_acceptance_rate_6m=0.74,
            recent_personas=[
                PersonaSnapshot(
                    lead_id="ACE-HIST-100",
                    email="marta.fin@northstarhealth.com",
                    full_name="Marta Fin",
                    job_title="Director Finance",
                    job_function="finance",
                    seniority="director",
                    status="approved",
                    asset_name="ROI Checklist",
                    asset_stage=FunnelStage.BOFU,
                    occurred_at=now - timedelta(days=12),
                )
            ],
        ),
        engagement_events=[
            EngagementEvent(
                event_type="open",
                occurred_at=now - timedelta(days=6),
                asset_name="Clinical ROI Case Study",
                email_number=1,
            ),
            EngagementEvent(
                event_type="click",
                occurred_at=now - timedelta(days=5),
                asset_name="Clinical ROI Case Study",
                email_number=1,
            ),
            EngagementEvent(
                event_type="open",
                occurred_at=now - timedelta(days=2),
                asset_name="Clinical ROI Case Study",
                email_number=2,
            ),
            EngagementEvent(
                event_type="download",
                occurred_at=now - timedelta(days=1),
                asset_name="Clinical ROI Case Study",
                email_number=2,
            ),
        ],
    )


def build_supporting_it_lead() -> LeadRecord:
    """Second persona for the same account to activate the buying-group trigger."""
    lead = build_priority_lead()
    now = datetime.now(UTC)
    return lead.model_copy(
        update={
            "lead_id": "ACE-PRD-002",
            "contact": ContactPayload(
                email="owen.it@northstarhealth.com",
                first_name="Owen",
                last_name="Mills",
                job_title="Director IT Infrastructure",
            ),
            "engagement_events": [
                EngagementEvent(
                    event_type="open",
                    occurred_at=now - timedelta(days=4),
                    asset_name="Clinical ROI Case Study",
                    email_number=1,
                ),
                EngagementEvent(
                    event_type="click",
                    occurred_at=now - timedelta(days=3),
                    asset_name="Clinical ROI Case Study",
                    email_number=2,
                ),
            ],
        }
    )


def build_monitor_lead() -> LeadRecord:
    """Low-quality lead that should be held or reviewed."""
    now = datetime.now(UTC)
    return LeadRecord(
        lead_id="ACE-PRD-003",
        submitted_at=now,
        source_partner="partner-low",
        contact=ContactPayload(
            email="generic.buyer@gmail.com",
            first_name="Jamie",
            last_name="Cole",
            job_title="Coordinator",
        ),
        company=CompanyPayload(
            company_name="Unknown Industrial",
            domain="unknown-industrial.example.com",
            industry="manufacturing",
            geography="International",
            company_size=None,
        ),
        campaign=CampaignContext(
            campaign_id="MFG-TOFU-2026-07",
            client_id="client-mfg-02",
            campaign_name="Factory Benchmark Awareness",
            brief_text="Broad awareness campaign for manufacturing professionals.",
            asset_name="2026 Factory Benchmark Guide",
            taxonomy=CampaignTaxonomy(
                asset_type="guide",
                topic="awareness",
                audience="broad",
                volume="high",
                sequence="single",
                asset_stage_override=FunnelStage.TOFU,
                vertical_override="manufacturing",
            ),
            history_approval_rate=0.42,
        ),
        partner_signals=PartnerSignals(
            partner_id="partner-low",
            approval_rate_6m=0.39,
            approval_rate_client_6m=0.36,
            approval_rate_vertical_6m=0.41,
        ),
        engagement_events=[],
    )
