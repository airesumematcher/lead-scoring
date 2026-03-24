#!/usr/bin/env python3
import json
import requests
from datetime import datetime, timedelta

now = datetime.now()
yesterday = (now - timedelta(days=1)).isoformat().split('+')[0]
now_str = now.isoformat().split('+')[0]

# Create engagement events
engagement_events = [
    {"timestamp": now_str, "event_type": "open"},
    {"timestamp": (now - timedelta(hours=6)).isoformat().split('+')[0], "event_type": "click"},
    {"timestamp": (now - timedelta(hours=12)).isoformat().split('+')[0], "event_type": "download"},
    {"timestamp": (now - timedelta(hours=18)).isoformat().split('+')[0], "event_type": "visit"}
]

data = {
    'lead': {
        'lead_id': 'DEMO-001',
        'submission_timestamp': now_str,
        'source_partner': 'web',
        'contact': {
            'email': 'john@acmecorp.com',
            'phone': '+1-555-1234',
            'first_name': 'John',
            'last_name': 'Doe',
            'job_title': 'VP Sales'
        },
        'company': {
            'company_name': 'ACME Corporation',
            'domain': 'acmecorp.com',
            'industry': 'Enterprise Software',
            'company_size': '1000+',
            'geography': 'US'
        },
        'campaign': {
            'campaign_id': 'web-lead-01',
            'campaign_name': 'Website Lead Form',
            'program_type': 'nurture'
        },
        'delivery_date': yesterday,
        'delivery_attempt_count': 1,
        'engagement_events': engagement_events
    },
    'program_type': 'nurture'
}

print("Testing Lead Scoring API...")
print("=" * 60)

response = requests.post('http://localhost:8000/score', json=data)
result = response.json()

print(f"\nScore: {result.get('score')}/100")
print(f"Grade: {result.get('grade')}")
print(f"Confidence: {result.get('confidence')}")
print(f"Freshness: {result.get('freshness')}")
print(f"\nSummary:\n{result.get('summary')}")

if result.get('drivers'):
    print("\n✅ Positive Factors:")
    for driver in result.get('drivers', []):
        print(f"  • {driver}")

if result.get('limiters'):
    print("\n⚠️ Limiting Factors:")
    for limiter in result.get('limiters', []):
        print(f"  • {limiter}")

print("\n" + "=" * 60)
