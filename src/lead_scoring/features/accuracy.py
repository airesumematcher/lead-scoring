"""
Accuracy Pillar Feature Engineering.

Accuracy answers: Is this lead real, reachable, and operationally usable?
Hard gate: Poor accuracy applies a score ceiling.
"""

import re
from datetime import datetime, timedelta
from typing import Optional, Tuple
import socket
from lead_scoring.models import LeadInput, AccuracyFeatures


def validate_email(email: str) -> bool:
    """Check email format validity."""
    if not email:
        return False
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


def validate_phone(phone: Optional[str]) -> bool:
    """Check phone format (E.164 or basic)."""
    if not phone:
        return False
    # Remove spaces, dashes, parens
    cleaned = re.sub(r'[\s\-().]', '', phone)
    # E.164 format: + optional, 7-15 digits
    return bool(re.match(r'^\+?[1-9]\d{6,14}$', cleaned))


def check_domain_credibility(domain: str) -> Tuple[int, bool]:
    """
    Check domain credibility (domain age, DNS records, etc.).
    Returns (credibility_score [0-100], is_valid_domain).
    
    Simplified version; production would use WHOIS, DNS verification.
    """
    if not domain or not isinstance(domain, str):
        return 0, False
    
    domain = domain.lower().strip()
    
    # Basic validation: must have TLD
    if '.' not in domain:
        return 0, False
    
    parts = domain.split('.')
    if len(parts) < 2 or any(len(part) == 0 for part in parts):
        return 0, False
    
    # Check for suspicious TLDs
    suspicious_tlds = {'.tk', '.ml', '.ga', '.cf'}
    tld = '.' + parts[-1]
    if tld in suspicious_tlds:
        return 50, True  # Valid but sketchy
    
    # Default: valid domain, good credibility
    # In production: check WHOIS age, DNS records, reputation DB
    credibility_score = 80  # Placeholder; would be computed from WHOIS
    return credibility_score, True


def calculate_job_title_seniority(job_title: str) -> int:
    """
    Parse job title and assign seniority score [1-5].
    1=IC, 2=Manager, 3=Sr.Manager, 4=Director, 5=VP+, C-suite.
    """
    if not job_title:
        return 0
    
    title_lower = job_title.lower()
    
    c_level_keywords = {'ceo', 'cfo', 'cto', 'coo', 'cmo', 'chief'}
    vp_keywords = {'vp', 'vice president', 'evp', 'senior vp', 'general manager'}
    director_keywords = {'director', 'head of'}
    sr_manager_keywords = {'senior manager', 'sr. manager', 'sr manager', 'principal'}
    manager_keywords = {'manager', 'lead'}
    
    if any(kw in title_lower for kw in c_level_keywords):
        return 5
    elif any(kw in title_lower for kw in vp_keywords):
        return 5
    elif any(kw in title_lower for kw in director_keywords):
        return 4
    elif any(kw in title_lower for kw in sr_manager_keywords):
        return 3
    elif any(kw in title_lower for kw in manager_keywords):
        return 2
    else:
        return 1  # Individual Contributor


def extract_accuracy_features(lead: LeadInput) -> AccuracyFeatures:
    """
    Extract all Accuracy pillar features.
    
    Accuracy gate: if email_valid=False OR delivery_success=False,
    accuracy_subscore is capped at 40 (blocks high composite scores).
    """
    
    # Email validation
    email_valid = validate_email(lead.contact.email)
    
    # Phone validation
    phone_valid = validate_phone(lead.contact.phone)
    
    # Job title present & seniority
    job_title_present = bool(lead.contact.job_title and len(lead.contact.job_title.strip()) > 0)
    job_title_seniority = calculate_job_title_seniority(lead.contact.job_title) if job_title_present else 0
    
    # Company validation
    company_name_valid = bool(lead.company.company_name and len(lead.company.company_name.strip()) > 0)
    
    # Domain credibility (0-100)
    domain_credibility_score, _ = check_domain_credibility(lead.company.domain)
    
    # Company size confidence (whether data is available and recent)
    company_size_confidence = 0.8 if lead.company.company_size else 0.0
    
    # Geography match (binary for now; simplification)
    # In production: compute weighted by region priority
    geo_match = 1.0 if lead.company.geography and lead.campaign.industry_focus else 0.5
    
    # Delivery success check
    call_delivery_attempt_count = lead.delivery_attempt_count or 0
    lead_delivery_success = (
        lead.delivery_date is not None and call_delivery_attempt_count <= 3
    )
    
    # Delivery latency (days from submission to delivery)
    delivery_latency_days = 999  # Default if no delivery date
    if lead.delivery_date and lead.submission_timestamp:
        delta = lead.delivery_date - lead.submission_timestamp
        delivery_latency_days = max(0, delta.days)
    
    # Engagement data availability
    engagement_data_available = len(lead.engagement_events or []) > 0
    
    # Duplicate risk (very simplified; in production would query DB)
    duplicate_risk = False  # Placeholder
    
    # === Compute Accuracy Sub-score ===
    accuracy_subscore = 100
    
    # Email + Phone valid (20 pts baseline)
    email_phone_pts = 0
    if email_valid and phone_valid:
        email_phone_pts = 20
    elif email_valid or phone_valid:
        email_phone_pts = 12
    # else: 0
    
    # Delivery success (15 pts)
    delivery_success_pts = 15 if lead_delivery_success else 5
    
    # Company data quality (20 pts)
    company_data_pts = 0
    if company_name_valid and domain_credibility_score >= 70 and lead.company.industry:
        company_data_pts = 20
    elif company_name_valid and domain_credibility_score >= 50:
        company_data_pts = 15
    else:
        company_data_pts = 5
    
    # Delivery latency (15 pts)
    if delivery_latency_days <= 30:
        latency_pts = 15
    elif delivery_latency_days <= 60:
        latency_pts = 10
    else:
        latency_pts = 5
    
    # Job title seniority (15 pts)
    seniority_pts = job_title_seniority * 3  # Scale to 0-15
    
    # No duplicates (15 pts)
    duplicate_pts = 15 if not duplicate_risk else 0
    
    # Sum (capped at 100)
    accuracy_subscore = min(100, email_phone_pts + delivery_success_pts + company_data_pts + 
                            latency_pts + seniority_pts + duplicate_pts)
    
    # Apply hard gate: if critical failures, cap at 40
    if not email_valid or not lead_delivery_success:
        accuracy_subscore = min(40, accuracy_subscore)
    
    return AccuracyFeatures(
        email_valid=email_valid,
        phone_valid=phone_valid,
        job_title_present=job_title_present,
        job_title_seniority_score=job_title_seniority,
        company_name_valid=company_name_valid,
        domain_credibility=domain_credibility_score,
        company_size_confidence=company_size_confidence,
        geo_match_with_campaign=geo_match,
        lead_delivery_success=lead_delivery_success,
        delivery_latency_days=delivery_latency_days,
        engagement_data_available=engagement_data_available,
        duplicate_risk=duplicate_risk,
        accuracy_subscore=accuracy_subscore,
    )
