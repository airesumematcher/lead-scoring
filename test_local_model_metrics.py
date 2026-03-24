#!/usr/bin/env python3
"""
Local test for updated API with model metrics
Tests single lead and batch scoring with model performance display
"""

import json
import requests
import time
from pathlib import Path

API_URL = "http://localhost:8000"

def test_single_lead():
    """Test single lead scoring with model metrics"""
    print("\n" + "="*80)
    print("TEST 1: Single Lead Scoring with Model Metrics")
    print("="*80)
    
    lead_data = {
        "lead": {
            "lead_id": "TEST-001",
            "submission_timestamp": "2026-03-13T12:00:00",
            "source_partner": "test",
            "contact": {
                "email": "jane@techcorp.com",
                "phone": "+1-555-1234",
                "first_name": "Jane",
                "last_name": "Smith",
                "job_title": "CTO"
            },
            "company": {
                "company_name": "TechCorp Inc",
                "domain": "techcorp.com",
                "industry": "SaaS",
                "company_size": "500-1000",
                "geography": "US"
            },
            "campaign": {
                "campaign_id": "test-campaign",
                "campaign_name": "Test Campaign",
                "program_type": "nurture"
            },
            "delivery_date": "2026-03-12T12:00:00",
            "engagement_events": [
                {"timestamp": "2026-03-13T10:00:00", "event_type": "open"},
                {"timestamp": "2026-03-13T09:00:00", "event_type": "click"},
                {"timestamp": "2026-03-13T08:00:00", "event_type": "download"}
            ]
        }
    }
    
    try:
        response = requests.post(f"{API_URL}/score", json=lead_data, timeout=30)
        
        if response.status_code != 200:
            print(f"❌ Error: {response.status_code}")
            print(f"Response: {response.text}")
            return False
        
        result = response.json()
        
        print(f"\n✅ Single Lead Scored Successfully")
        print(f"   Lead ID: {result['lead_id']}")
        print(f"   Score: {result['score']}/100")
        print(f"   Grade: {result['grade']}")
        print(f"   Confidence: {result['confidence']}")
        
        if result.get('model_metrics'):
            print(f"\n📊 Model Metrics ({len(result['model_metrics'])} models):")
            for metric in result['model_metrics']:
                print(f"   {metric['model_name']:20s} | Pred: {metric['prediction']:5.1f} | R²: {metric['r2_score']:.4f} | MAE: ±{metric['mae']:.2f} | RMSE: {metric['rmse']:.2f}")
            
            if result.get('ensemble_confidence'):
                print(f"\n🎯 Ensemble Average Confidence: {result['ensemble_confidence']*100:.1f}%")
        else:
            print("\n⚠️  No model metrics in response")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def test_batch_upload():
    """Test batch scoring with model metrics"""
    print("\n" + "="*80)
    print("TEST 2: Batch Scoring with Model Metrics")
    print("="*80)
    
    leads = [
        {
            "lead_id": "BATCH-001",
            "submission_timestamp": "2026-03-13T12:00:00",
            "source_partner": "batch",
            "contact": {
                "email": "lead1@company.com",
                "phone": "+1-555-0001",
                "first_name": "John",
                "last_name": "Doe",
                "job_title": "VP Sales"
            },
            "company": {
                "company_name": "Company A",
                "domain": "companya.com",
                "industry": "Enterprise Software",
                "company_size": "1000+",
                "geography": "US"
            },
            "campaign": {
                "campaign_id": "batch-test",
                "campaign_name": "Batch Test",
                "program_type": "nurture"
            },
            "delivery_date": "2026-03-12T12:00:00",
            "engagement_events": [
                {"timestamp": "2026-03-13T10:00:00", "event_type": "open"},
                {"timestamp": "2026-03-13T09:00:00", "event_type": "click"}
            ]
        },
        {
            "lead_id": "BATCH-002",
            "submission_timestamp": "2026-03-13T12:00:00",
            "source_partner": "batch",
            "contact": {
                "email": "lead2@startup.com",
                "phone": "+1-555-0002",
                "first_name": "Jane",
                "last_name": "Smith",
                "job_title": "Product Manager"
            },
            "company": {
                "company_name": "Startup XYZ",
                "domain": "startupxyz.com",
                "industry": "AI/ML",
                "company_size": "11-50",
                "geography": "US"
            },
            "campaign": {
                "campaign_id": "batch-test",
                "campaign_name": "Batch Test",
                "program_type": "outbound"
            },
            "delivery_date": "2026-03-12T12:00:00",
            "engagement_events": []
        }
    ]
    
    batch_request = {
        "leads": leads,
        "program_type": "nurture"
    }
    
    try:
        response = requests.post(f"{API_URL}/score-batch", json=batch_request, timeout=30)
        
        if response.status_code != 200:
            print(f"❌ Error: {response.status_code}")
            print(f"Response: {response.text}")
            return False
        
        result = response.json()
        
        print(f"\n✅ Batch Scoring Successful")
        print(f"   Total Leads: {result['total_leads']}")
        print(f"   Scored: {result['scored_leads']}")
        print(f"   Failed: {result['failed_leads']}")
        
        if result.get('batch_summary'):
            summary = result['batch_summary']
            print(f"\n📊 Batch Summary:")
            print(f"   Average Score: {summary.get('average_score', 'N/A')}")
            grade_dist = summary.get('grade_distribution', {})
            print(f"   Grade Distribution: A={grade_dist.get('A', 0)}, B={grade_dist.get('B', 0)}, C={grade_dist.get('C', 0)}, D={grade_dist.get('D', 0)}")
        
        for i, lead_result in enumerate(result.get('results', []), 1):
            print(f"\n   Lead {i}: {lead_result['lead_id']}")
            print(f"      Score: {lead_result['score']}/100, Grade: {lead_result['grade']}")
            
            if lead_result.get('model_metrics'):
                best_model = max(lead_result['model_metrics'], key=lambda m: m['r2_score'])
                print(f"      Models: {len(lead_result['model_metrics'])} | Best: {best_model['model_name']} (R²={best_model['r2_score']:.4f})")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def test_health():
    """Test API health"""
    print("\n" + "="*80)
    print("Pre-Test: Checking API Health")
    print("="*80)
    
    try:
        response = requests.get(f"{API_URL}/health", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ API is healthy")
            print(f"   Status: {data.get('status')}")
            print(f"   Version: {data.get('version')}")
            return True
        else:
            print(f"❌ API returned {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Cannot connect to API: {e}")
        return False


if __name__ == "__main__":
    print("\n" + "="*80)
    print("LOCAL API TEST - Model Metrics & Batch Upload")
    print("="*80)
    print(f"Testing API at: {API_URL}")
    
    # Test health first
    if not test_health():
        print("\n❌ API is not running. Start it with:")
        print("   cd /Users/schadha/Desktop/lead-scoring")
        print("   python3 -m uvicorn src.lead_scoring.api.app:app --host 0.0.0.0 --port 8000 --reload")
        exit(1)
    
    # Run tests
    single_ok = test_single_lead()
    time.sleep(1)
    batch_ok = test_batch_upload()
    
    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    print(f"Single Lead Test: {'✅ PASS' if single_ok else '❌ FAIL'}")
    print(f"Batch Upload Test: {'✅ PASS' if batch_ok else '❌ FAIL'}")
    print("\n" + "="*80)
    
    if single_ok and batch_ok:
        print("✅ ALL TESTS PASSED")
        exit(0)
    else:
        print("❌ SOME TESTS FAILED")
        exit(1)
