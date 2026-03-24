"""Sample lead data for testing and demonstration."""

from datetime import datetime, timedelta
from lead_scoring.models import (
    LeadInput, ContactFields, CompanyFields, CampaignFields,
    EngagementEvent, EngagementType, AccountLevelFields, ProgramType
)


def create_sample_lead_high_fit() -> LeadInput:
    """Create a high-fit lead for testing (Grade A expected)."""
    now = datetime.utcnow()
    
    return LeadInput(
        lead_id="L-10001",
        submission_timestamp=now - timedelta(days=10),
        source_partner="inbound-form",
        
        contact=ContactFields(
            email="jane.doe@acme-corp.com",
            phone="+1-650-555-0100",
            first_name="Jane",
            last_name="Doe",
            job_title="VP of Engineering",
            linkedin_url="https://linkedin.com/in/jane-doe",
        ),
        
        company=CompanyFields(
            company_name="Acme Corp Inc.",
            domain="acme-corp.com",
            industry="SaaS",
            company_size="100-1000",
            revenue_band="$50M-$100M",
            geography="United States",
            hq_location="San Francisco, CA",
        ),
        
        campaign=CampaignFields(
            campaign_id="CAMP-2026-Q1-001",
            campaign_name="Enterprise Security ABM",
            brief_objective="Position for cloud security platform",
            target_persona="CTO / VP Engineering",
            industry_focus="SaaS",
            asset_used="whitepaper",
            asset_stage_tag="consideration",
            program_type=ProgramType.ABM,
        ),
        
        delivery_date=now - timedelta(days=9),
        delivery_attempt_count=1,
        
        engagement_events=[
            EngagementEvent(
                timestamp=now - timedelta(days=5),
                event_type=EngagementType.OPEN,
            ),
            EngagementEvent(
                timestamp=now - timedelta(days=4),
                event_type=EngagementType.CLICK,
                url_clicked="https://acme-corp.com/security-whitepaper",
                asset_name="Enterprise Security Playbook",
            ),
            EngagementEvent(
                timestamp=now - timedelta(days=3),
                event_type=EngagementType.DOWNLOAD,
                asset_name="Enterprise Security Playbook",
            ),
        ],
        
        ip_address="203.0.113.45",
        
        account_context=AccountLevelFields(
            tal_match=True,
            historical_account_acceptance_rate=0.72,
            account_industry="SaaS",
            account_employee_count=850,
            account_revenue_band="$50M-$100M",
            abm_pulse_intent_score=0.85,
        ),
    )


def create_sample_lead_medium_fit() -> LeadInput:
    """Create a medium-fit lead (Grade B expected)."""
    now = datetime.utcnow()
    
    return LeadInput(
        lead_id="L-10002",
        submission_timestamp=now - timedelta(days=20),
        source_partner="content-download",
        
        contact=ContactFields(
            email="john.smith@techco.io",
            phone="+1-415-555-0200",
            first_name="John",
            last_name="Smith",
            job_title="IT Director",
            linkedin_url=None,
        ),
        
        company=CompanyFields(
            company_name="TechCo Inc.",
            domain="techco.io",
            industry="Software",
            company_size="50-100",
            revenue_band="$10M-$50M",
            geography="United States",
            hq_location="Seattle, WA",
        ),
        
        campaign=CampaignFields(
            campaign_id="CAMP-2026-Q1-002",
            campaign_name="Cloud Infrastructure Nurture",
            brief_objective="Nurture mid-market cloud buyers",
            target_persona="IT Director / Head of Ops",
            industry_focus="Software",
            asset_used="webinar",
            asset_stage_tag="awareness",
            program_type=ProgramType.NURTURE,
        ),
        
        delivery_date=now - timedelta(days=18),
        delivery_attempt_count=1,
        
        engagement_events=[
            EngagementEvent(
                timestamp=now - timedelta(days=14),
                event_type=EngagementType.OPEN,
            ),
        ],
        
        account_context=AccountLevelFields(
            tal_match=False,
            historical_account_acceptance_rate=0.55,
            account_industry="Software",
            account_employee_count=75,
        ),
    )


def create_sample_lead_no_engagement() -> LeadInput:
    """Create a lead with good fit but no engagement (Grade C expected)."""
    now = datetime.utcnow()
    
    return LeadInput(
        lead_id="L-10003",
        submission_timestamp=now - timedelta(days=25),
        source_partner="list-upload",
        
        contact=ContactFields(
            email="alex.jones@industri.com",
            phone="+1-800-555-0300",
            first_name="Alex",
            last_name="Jones",
            job_title="Operations Manager",
            linkedin_url=None,
        ),
        
        company=CompanyFields(
            company_name="Industrial Tech Corp",
            domain="industri.com",
            industry="Manufacturing",
            company_size="1000-5000",
            revenue_band="$100M-$500M",
            geography="United States",
            hq_location="Chicago, IL",
        ),
        
        campaign=CampaignFields(
            campaign_id="CAMP-2026-Q1-003",
            campaign_name="Ops Efficiency Outbound",
            brief_objective="Target operations leaders",
            target_persona="Operations Manager",
            industry_focus="Manufacturing",
            asset_used="report",
            asset_stage_tag="awareness",
            program_type=ProgramType.OUTBOUND,
        ),
        
        delivery_date=now - timedelta(days=22),
        delivery_attempt_count=1,
        
        engagement_events=[],  # No engagement
        
        account_context=AccountLevelFields(
            tal_match=True,
            historical_account_acceptance_rate=0.48,
            account_industry="Manufacturing",
        ),
    )


def create_sample_lead_bad_data() -> LeadInput:
    """Create a lead with bad data (Grade D expected, Accuracy gate triggered)."""
    now = datetime.utcnow()
    
    return LeadInput(
        lead_id="L-10004",
        submission_timestamp=now - timedelta(days=90),  # Very old
        source_partner="old-import",
        
        contact=ContactFields(
            email="unknown@example.com",  # Generic domain
            phone=None,  # Missing phone
            first_name="Unknown",
            last_name="User",
            job_title="Employee",  # Generic title
            linkedin_url=None,
        ),
        
        company=CompanyFields(
            company_name="Generic Corp",
            domain="example.com",  # Generic domain
            industry="Other",  # Non-target
            company_size=None,
            revenue_band=None,
            geography="International",
            hq_location=None,
        ),
        
        campaign=CampaignFields(
            campaign_id="CAMP-2026-Q1-OLD",
            campaign_name="Old Campaign",
            brief_objective="Legacy",
            target_persona="CTO",
            industry_focus="SaaS",
            asset_used=None,
            asset_stage_tag=None,
            program_type=ProgramType.NURTURE,
        ),
        
        delivery_date=now - timedelta(days=85),  # Delayed delivery
        delivery_attempt_count=3,
        
        engagement_events=[],
        
        account_context=None,
    )


def get_sample_leads() -> dict:
    """Get all sample leads keyed by ID."""
    leads = [
        create_sample_lead_high_fit(),
        create_sample_lead_medium_fit(),
        create_sample_lead_no_engagement(),
        create_sample_lead_bad_data(),
    ]
    return {lead.lead_id: lead for lead in leads}
