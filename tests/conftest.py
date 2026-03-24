"""
Pytest configuration and shared fixtures.
"""

import pytest
from datetime import datetime, timedelta

from lead_scoring.models import (
    LeadInput, ContactFields, CompanyFields, CampaignFields,
    EngagementEvent, EngagementType, AccountLevelFields, ProgramType
)
from lead_scoring.config import load_config


@pytest.fixture
def config():
    """Load configuration."""
    return load_config()


@pytest.fixture
def sample_lead_high_fit():
    """Create a high-fit lead."""
    now = datetime.utcnow()
    
    return LeadInput(
        lead_id="TEST-HIGH-001",
        submission_timestamp=now - timedelta(days=10),
        source_partner="inbound-form",
        contact=ContactFields(
            email="jane.doe@acme-corp.com",
            phone="+1-650-555-0100",
            first_name="Jane",
            last_name="Doe",
            job_title="VP of Engineering",
        ),
        company=CompanyFields(
            company_name="Acme Corp Inc.",
            domain="acme-corp.com",
            industry="SaaS",
            company_size="100-1000",
            revenue_band="$50M-$100M",
            geography="United States",
        ),
        campaign=CampaignFields(
            campaign_id="CAMP-TEST-001",
            campaign_name="Test ABM Campaign",
            brief_objective="Test objective",
            target_persona="CTO",
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
                timestamp=now - timedelta(days=3),
                event_type=EngagementType.DOWNLOAD,
                asset_name="Test Asset",
            ),
        ],
        account_context=AccountLevelFields(
            tal_match=True,
            historical_account_acceptance_rate=0.72,
            account_industry="SaaS",
            account_employee_count=850,
        ),
    )


@pytest.fixture
def sample_lead_low_fit():
    """Create a low-fit lead."""
    now = datetime.utcnow()
    
    return LeadInput(
        lead_id="TEST-LOW-001",
        submission_timestamp=now - timedelta(days=90),
        source_partner="old-import",
        contact=ContactFields(
            email="unknown@example.com",
            phone=None,
            first_name="Generic",
            last_name="User",
            job_title="Employee",
        ),
        company=CompanyFields(
            company_name="Generic Corp",
            domain="example.com",
            industry="Other",
            company_size=None,
            revenue_band=None,
            geography="International",
        ),
        campaign=CampaignFields(
            campaign_id="CAMP-OLD",
            campaign_name="Old Campaign",
            brief_objective="Legacy",
            target_persona="CTO",
            industry_focus="SaaS",
            asset_used=None,
            program_type=ProgramType.NURTURE,
        ),
        delivery_date=now - timedelta(days=85),
        delivery_attempt_count=3,
        engagement_events=[],
        account_context=None,
    )


@pytest.fixture
def sample_lead_no_engagement():
    """Create a lead with no engagement."""
    now = datetime.utcnow()
    
    return LeadInput(
        lead_id="TEST-NOENGAGE-001",
        submission_timestamp=now - timedelta(days=25),
        source_partner="list-upload",
        contact=ContactFields(
            email="alex.jones@industri.com",
            phone="+1-800-555-0300",
            first_name="Alex",
            last_name="Jones",
            job_title="Operations Manager",
        ),
        company=CompanyFields(
            company_name="Industrial Tech Corp",
            domain="industri.com",
            industry="Manufacturing",
            company_size="1000-5000",
            revenue_band="$100M-$500M",
            geography="United States",
        ),
        campaign=CampaignFields(
            campaign_id="CAMP-OPS",
            campaign_name="Ops Efficiency Campaign",
            brief_objective="Target ops leaders",
            target_persona="Operations Manager",
            industry_focus="Manufacturing",
            asset_used="report",
            program_type=ProgramType.OUTBOUND,
        ),
        delivery_date=now - timedelta(days=22),
        delivery_attempt_count=1,
        engagement_events=[],
        account_context=AccountLevelFields(
            tal_match=True,
            historical_account_acceptance_rate=0.48,
            account_industry="Manufacturing",
        ),
    )
