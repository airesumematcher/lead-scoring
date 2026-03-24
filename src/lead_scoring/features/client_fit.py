"""
Client Fit Pillar Feature Engineering.

Client Fit answers: Does this lead match the client's Ideal Customer Profile (ICP)?
High fit amplifies upside. Low fit accelerates freshness decay.
"""

from lead_scoring.models import LeadInput, ClientFitFeatures


def compute_industry_match(lead_industry: str, campaign_industry_focus: str) -> int:
    """
    Compute industry match score [0-25].
    Exact match = 25; Related = 15; No match = 0.
    """
    if not lead_industry or not campaign_industry_focus:
        return 0
    
    lead_ind = lead_industry.lower().strip()
    camp_ind = campaign_industry_focus.lower().strip()
    
    if lead_ind == camp_ind:
        return 25
    
    # Simple related industry mapping
    related_industries = {
        'saas': {'software', 'cloud', 'tech'},
        'software': {'saas', 'cloud', 'tech'},
        'cloud': {'saas', 'software', 'tech'},
        'finance': {'fintech', 'banking', 'insurance'},
        'banking': {'finance', 'fintech', 'insurance'},
        'manufacturing': {'industrial', 'operations'},
    }
    
    if lead_ind in related_industries and camp_ind in related_industries[lead_ind]:
        return 15
    
    return 0


def compute_company_size_match(lead_size: str, icp_size_range: str = "100-1000") -> int:
    """
    Compute company size match [0-25].
    Maps employee band to points.
    """
    if not lead_size:
        return 0
    
    lead_size_lower = lead_size.lower().strip()
    
    size_mapping = {
        '1-10': 0,
        '11-50': 5,
        '51-100': 10,
        '100-1000': 25,
        '1000-5000': 20,
        '5000+': 15,
        'enterprise': 15,
        'startup': 5,
        'small': 10,
        'medium': 25,
        'large': 20,
    }
    
    for size_key, score in size_mapping.items():
        if size_key in lead_size_lower:
            return score
    
    return 5  # Default partial match


def compute_revenue_match(lead_revenue: str) -> int:
    """Compute revenue band match [0-20]."""
    if not lead_revenue:
        return 0
    
    lead_rev_lower = lead_revenue.lower().strip()
    
    revenue_mapping = {
        '0-1m': 0,
        '1-10m': 5,
        '10-50m': 15,
        '50-100m': 20,
        '100m-1b': 20,
        '1b+': 15,
        'private': 10,
        'funded': 15,
    }
    
    for rev_key, score in revenue_mapping.items():
        if rev_key in lead_rev_lower:
            return score
    
    return 5  # Default


def compute_geography_match(lead_geo: str, campaign_geo: str) -> int:
    """Compute geography match [0-20]."""
    if not lead_geo or not campaign_geo:
        return 0
    
    lead_geo_lower = lead_geo.lower().strip()
    campaign_geo_lower = campaign_geo.lower().strip()
    
    if lead_geo_lower == campaign_geo_lower:
        return 20
    
    # Simple region matching (EMEA, APAC, AMER, etc.)
    region_mapping = {
        'us': {'north america', 'amer', 'usa'},
        'eu': {'emea', 'europe'},
        'apac': {'asia', 'australia'},
    }
    
    lead_region = next((region for region, countries in region_mapping.items() 
                        if any(c in lead_geo_lower for c in countries)), None)
    campaign_region = next((region for region, countries in region_mapping.items() 
                            if any(c in campaign_geo_lower for c in countries)), None)
    
    if lead_region and campaign_region and lead_region == campaign_region:
        return 15
    
    return 5  # Partial geography match


def match_job_title_to_persona(job_title: str, campaign_persona: str) -> int:
    """
    Match job title to campaign target persona [0-25].
    Exact = 25; Related = 15; No match = 0.
    """
    if not job_title or not campaign_persona:
        return 0
    
    title_lower = job_title.lower()
    persona_lower = campaign_persona.lower()
    
    # Persona keyword sets
    persona_keywords = {
        'cto': {'cto', 'chief technology', 'vp engineering', 'vp tech'},
        'cfo': {'cfo', 'chief financial', 'vp finance', 'controller'},
        'it director': {'it director', 'director it', 'head it', 'it manager'},
        'security': {'ciso', 'security officer', 'security manager', 'vp security'},
        'ops': {'coo', 'vp operations', 'operations manager', 'ops director'},
        'marketing': {'cmo', 'vp marketing', 'marketing director', 'marketing manager'},
    }
    
    # Check exact persona match
    if persona_lower in persona_keywords:
        keywords = persona_keywords[persona_lower]
        if any(kw in title_lower for kw in keywords):
            return 25
    
    # Check for related match (same domain but different level)
    for persona, keywords in persona_keywords.items():
        if any(kw in title_lower for kw in keywords):
            if persona_lower in title_lower or any(w in persona_lower for w in title_lower.split()):
                return 15
    
    return 0


def extract_client_fit_features(lead: LeadInput) -> ClientFitFeatures:
    """Extract all Client Fit pillar features."""
    
    # Industry match
    industry_match_pts = compute_industry_match(
        lead.company.industry,
        lead.campaign.industry_focus or ""
    )
    
    # Company size match
    company_size_match_pts = compute_company_size_match(lead.company.company_size or "")
    
    # Revenue band match (if available)
    revenue_match_pts = compute_revenue_match(lead.company.revenue_band or "")
    
    # Geography match
    geography_match_pts = compute_geography_match(
        lead.company.geography,
        lead.campaign.industry_focus or ""  # Simplified; would use campaign geo
    )
    
    # TAL (Target Account List) match
    tal_match = lead.account_context.tal_match if lead.account_context else False
    tal_match_pts = 20 if tal_match else -5  # TAL boost; non-TAL penalty
    
    # Job title persona match
    job_title_match_pts = match_job_title_to_persona(
        lead.contact.job_title,
        lead.campaign.target_persona or ""
    )
    
    # Historical account conversion (if available)
    historical_acct_conversion_pts = 0
    if lead.account_context and lead.account_context.historical_account_acceptance_rate:
        rate = lead.account_context.historical_account_acceptance_rate
        historical_acct_conversion_pts = min(15, int(rate * 15))  # Scale 0-15
    
    # Firmographic confidence (data freshness penalty/bonus)
    firmographic_confidence_pts = 0
    if lead.company.company_size or lead.company.revenue_band:
        # Assume fresh if just delivered; simplified
        firmographic_confidence_pts = 5  # +5 for available data
    
    # === Compute Client Fit Sub-score ===
    client_fit_subscore = min(100, max(0, 
        industry_match_pts +
        company_size_match_pts +
        revenue_match_pts +
        geography_match_pts +
        (20 if tal_match else 0) +  # Only positive count
        job_title_match_pts +
        historical_acct_conversion_pts +
        firmographic_confidence_pts
    ))
    
    return ClientFitFeatures(
        industry_match_pts=industry_match_pts,
        company_size_match_pts=company_size_match_pts,
        revenue_band_match_pts=revenue_match_pts,
        geography_match_pts=geography_match_pts,
        tal_match=tal_match,
        job_title_match_persona_pts=job_title_match_pts,
        historical_account_conversion=historical_acct_conversion_pts,
        firmographic_confidence=firmographic_confidence_pts,
        client_fit_subscore=client_fit_subscore,
    )
