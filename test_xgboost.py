import requests
from datetime import datetime, timedelta

# Test XGBoost model via API
now = datetime.utcnow()

lead_data = {
    "lead": {
        "lead_id": "PHASE1-XGB-TEST",
        "submission_timestamp": (now - timedelta(days=5)).isoformat(),
        "source_partner": "test",
        "contact": {
            "email": "john.doe@acmecorp.com",
            "phone": "+1-650-555-0100",
            "first_name": "John",
            "last_name": "Doe",
            "job_title": "VP Sales",
        },
        "company": {
            "company_name": "ACME Corporation",
            "domain": "acmecorp.com",
            "industry": "Technology",
            "company_size": "1001-5000",
            "geography": "United States"
        },
        "campaign": {
            "campaign_id": "TEST-2026",
            "campaign_name": "Test Campaign",
            "program_type": "nurture"
        },
        "delivery_date": (now - timedelta(days=4)).isoformat(),
        "delivery_attempt_count": 1,
        "engagement_events": [
            {
                "timestamp": (now - timedelta(days=3)).isoformat(),
                "event_type": "open"
            },
            {
                "timestamp": (now - timedelta(days=2)).isoformat(),
                "event_type": "click",
                "url_clicked": "http://example.com"
            }
        ]
    },
    "program_type": "nurture"
}

response = requests.post("http://localhost:8000/score", json=lead_data)
print(f"Status: {response.status_code}")
if response.status_code == 200:
    data = response.json()
    print("\n✅ XGBoost Model Test Results:")
    print(f"  Composite Score: {data.get('score')}/100")
    print(f"  Grade: {data.get('grade')}")
    
    if 'model_metrics' in data and data['model_metrics']:
        metrics = data['model_metrics']
        print(f"\n  Model Metrics ({len(metrics)} models):")
        for metric in metrics:
            name = metric.get('model_name', 'Unknown')
            pred = metric.get('prediction', '?')
            r2 = metric.get('r2_score', 0)
            print(f"    {name:20s}: {pred:6.1f}/100  (R²={r2:.4f})")
    else:
        print("  No model metrics in response")
else:
    print(f"Error: {response.text}")
