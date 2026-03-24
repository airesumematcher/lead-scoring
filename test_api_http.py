"""
Integration test for Lead Scoring REST API.
Tests actual HTTP endpoints using the FastAPI server.
"""

import sys
import json
import time
from pathlib import Path

import requests

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from data.sample_leads import (
    create_sample_lead_high_fit,
    create_sample_lead_medium_fit,
)

API_URL = "http://localhost:8001"
TIMEOUT = 5

SAMPLE_LEADS = [
    create_sample_lead_high_fit(),
    create_sample_lead_medium_fit(),
]


def test_health_check():
    """Test health check endpoint."""
    print("\n" + "=" * 80)
    print("TEST: Health Check Endpoint")
    print("=" * 80)

    try:
        response = requests.get(f"{API_URL}/health", timeout=TIMEOUT)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Health check passed")
            print(f"   Status: {data.get('status')}")
            print(f"   Version: {data.get('version')}")
            return True
        else:
            print(f"❌ Health check failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Failed to connect to {API_URL}/health")
        print(f"   Error: {str(e)}")
        return False


def test_single_lead_endpoint():
    """Test single lead scoring endpoint."""
    print("\n" + "=" * 80)
    print("TEST: Single Lead Scoring Endpoint")
    print("=" * 80)

    lead = SAMPLE_LEADS[0]
    request_body = {
        "lead": json.loads(lead.model_dump_json()),
        "program_type": "abm",
    }

    try:
        print(f"\n📊 Scoring lead {lead.lead_id}...")
        response = requests.post(
            f"{API_URL}/score", json=request_body, timeout=TIMEOUT
        )

        if response.status_code == 200:
            data = response.json()
            print(f"✅ Endpoint returned 200 OK")
            print(f"   Lead ID: {data.get('lead_id')}")
            print(f"   Score: {data.get('score')}/100")
            print(f"   Grade: {data.get('grade')}")
            print(f"   Confidence: {data.get('confidence')}")
            print(f"   Freshness: {data.get('freshness')}")
            print(f"   Action: {data.get('recommended_action')}")
            print(f"   Summary: {data.get('summary')[:80]}...")
            print(f"   Drivers: {', '.join(data.get('drivers', [])[:2])}")
            return True
        else:
            print(f"❌ Endpoint returned {response.status_code}")
            print(f"   Response: {response.text}")
            return False

    except Exception as e:
        print(f"❌ Failed to call /score endpoint")
        print(f"   Error: {str(e)}")
        return False


def test_batch_endpoint():
    """Test batch lead scoring endpoint."""
    print("\n" + "=" * 80)
    print("TEST: Batch Lead Scoring Endpoint")
    print("=" * 80)

    leads_data = [json.loads(lead.model_dump_json()) for lead in SAMPLE_LEADS]
    request_body = {"leads": leads_data, "program_type": "nurture"}

    try:
        print(f"\n📊 Scoring {len(SAMPLE_LEADS)} leads in batch...")
        response = requests.post(
            f"{API_URL}/score-batch", json=request_body, timeout=TIMEOUT
        )

        if response.status_code == 200:
            data = response.json()
            print(f"✅ Endpoint returned 200 OK")
            print(f"   Total Leads: {data.get('total_leads')}")
            print(f"   Scored: {data.get('scored_leads')}")
            print(f"   Failed: {data.get('failed_leads')}")
            batch_summary = data.get("batch_summary", {})
            print(f"   Average Score: {batch_summary.get('average_score')}")
            print(f"   Grade Distribution: {batch_summary.get('grade_distribution')}")
            return True
        else:
            print(f"❌ Endpoint returned {response.status_code}")
            print(f"   Response: {response.text}")
            return False

    except Exception as e:
        print(f"❌ Failed to call /score-batch endpoint")
        print(f"   Error: {str(e)}")
        return False


def test_swagger_docs():
    """Test Swagger documentation endpoint."""
    print("\n" + "=" * 80)
    print("TEST: Swagger API Documentation")
    print("=" * 80)

    try:
        response = requests.get(f"{API_URL}/docs", timeout=TIMEOUT)
        if response.status_code == 200:
            print(f"✅ Swagger UI available at {API_URL}/docs")
            return True
        else:
            print(f"❌ Swagger UI returned {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Failed to access Swagger UI")
        print(f"   Error: {str(e)}")
        return False


def main():
    """Run all API endpoint tests."""
    print("\n" + "=" * 80)
    print("LEAD SCORING API HTTP INTEGRATION TESTS")
    print("=" * 80)
    print(f"\nConnecting to API at {API_URL}...")
    print("(Make sure to start the API server first:)")
    print("  $ uvicorn src.lead_scoring.api.app:app --reload --port 8000")
    print()

    # Wait a moment for user to potentially start server
    time.sleep(2)

    tests = [
        ("Health Check", test_health_check),
        ("Single Lead Endpoint", test_single_lead_endpoint),
        ("Batch Endpoint", test_batch_endpoint),
        ("Swagger Docs", test_swagger_docs),
    ]

    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ Test {test_name} failed with error: {e}")
            results.append((test_name, False))

    # Summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    passed = sum(1 for _, result in results if result)
    total = len(results)
    print(f"\nResults: {passed}/{total} tests passed\n")

    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {status}: {test_name}")

    if passed == total:
        print("\n✅ ALL API ENDPOINTS WORKING!")
        print("\n🚀 API Server is ready for production!")
        print(f"\n   Access API at: {API_URL}")
        print(f"   Swagger Docs: {API_URL}/docs")
        print(f"   ReDoc: {API_URL}/redoc")
    else:
        print(
            f"\n⚠️  {total - passed} test(s) failed. Please start the API server and try again."
        )
        print(f"\n   Start API with: uvicorn src.lead_scoring.api.app:app --reload --port 8000")

    print("\n")


if __name__ == "__main__":
    main()
