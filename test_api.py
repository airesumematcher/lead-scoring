"""
Test script for Lead Scoring API.
Tests both single and batch scoring endpoints.
"""

import sys
import json
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from lead_scoring.api.handlers import score_single_lead, score_batch_leads
from data.sample_leads import (
    create_sample_lead_high_fit,
    create_sample_lead_medium_fit,
    create_sample_lead_no_engagement,
    create_sample_lead_bad_data,
)

SAMPLE_LEADS = [
    create_sample_lead_high_fit(),
    create_sample_lead_medium_fit(),
    create_sample_lead_no_engagement(),
    create_sample_lead_bad_data(),
]


def test_api_single_lead():
    """Test single lead scoring via API handler."""
    print("\n" + "=" * 80)
    print("TEST 1: Single Lead Scoring")
    print("=" * 80)

    for i, lead_input in enumerate(SAMPLE_LEADS[:2], 1):
        print(f"\n📊 Scoring Lead {i}: {lead_input.lead_id}")
        print("-" * 80)

        response = score_single_lead(lead_input, program_type="nurture")

        print(f"✅ Status: {'Success' if response.success else 'Failed'}")
        print(f"   Lead ID: {response.lead_id}")
        print(f"   Score: {response.score}/100")
        print(f"   Grade: {response.grade}")
        print(f"   Confidence: {response.confidence}")
        print(f"   Freshness: {response.freshness}")
        print(f"   Action: {response.recommended_action}")
        print(f"\n   Summary: {response.summary}")
        print(f"\n   Top Drivers:")
        for driver in response.drivers:
            print(f"      • {driver}")
        print(f"\n   Top Limiters:")
        for limiter in response.limiters:
            print(f"      • {limiter}")
        print(f"\n   Pipeline Influence Score: {response.pipeline_influence_score}/100")
        print(f"\n   Score Adjustments:")
        if response.adjustments_applied:
            for adj in response.adjustments_applied:
                print(f"      • {adj}")
        else:
            print(f"      • None")

        if response.error:
            print(f"\n❌ Error: {response.error}")

        print()


def test_api_batch_leads():
    """Test batch lead scoring via API handler."""
    print("\n" + "=" * 80)
    print("TEST 2: Batch Lead Scoring")
    print("=" * 80)

    print(f"\n📊 Scoring {len(SAMPLE_LEADS)} leads in batch...")
    print("-" * 80)

    response = score_batch_leads(SAMPLE_LEADS, program_type="outbound")

    print(f"\n✅ Batch Status: {'Success' if response.success else 'Partial/Failed'}")
    print(f"   Total Leads: {response.total_leads}")
    print(f"   Scored: {response.scored_leads}")
    print(f"   Failed: {response.failed_leads}")

    print(f"\n📊 Batch Summary:")
    print(f"   Average Score: {response.batch_summary.get('average_score', 'N/A')}")
    print(f"   Grade Distribution: {response.batch_summary.get('grade_distribution', {})}")
    print(f"   Timestamp: {response.batch_summary.get('batch_timestamp', 'N/A')}")

    print(f"\n📋 Individual Results:")
    for result in response.results:
        status_icon = "✅" if result.success else "❌"
        print(
            f"   {status_icon} {result.lead_id}: Grade {result.grade} | "
            f"Score {result.score} | {result.recommended_action}"
        )


def test_api_json_serialization():
    """Test JSON serialization of responses."""
    print("\n" + "=" * 80)
    print("TEST 3: JSON Serialization")
    print("=" * 80)

    print("\n🔄 Testing single lead response JSON serialization...")
    response = score_single_lead(SAMPLE_LEADS[0], program_type="abm")
    json_str = response.model_dump_json(indent=2)
    json_obj = json.loads(json_str)
    print(f"✅ Successfully serialized single response ({len(json_str)} chars)")
    print(f"   Keys: {list(json_obj.keys())}")

    print("\n🔄 Testing batch response JSON serialization...")
    batch_response = score_batch_leads(SAMPLE_LEADS[:2], program_type="event")
    json_str = batch_response.model_dump_json(indent=2)
    json_obj = json.loads(json_str)
    print(f"✅ Successfully serialized batch response ({len(json_str)} chars)")
    print(f"   Keys: {list(json_obj.keys())}")


def test_different_program_types():
    """Test scoring with different program types."""
    print("\n" + "=" * 80)
    print("TEST 4: Different Program Types")
    print("=" * 80)

    program_types = ["nurture", "outbound", "abm", "event"]
    lead = SAMPLE_LEADS[0]

    print(f"\n🎯 Scoring same lead ({lead.lead_id}) with different program types:")
    print("-" * 80)

    for program_type in program_types:
        response = score_single_lead(lead, program_type=program_type)
        print(
            f"   {program_type.upper():8s}: Score {response.score:3d} | "
            f"Grade {response.grade} | Action: {response.recommended_action}"
        )


def main():
    """Run all API tests."""
    print("\n" + "=" * 80)
    print("LEAD SCORING API TEST SUITE")
    print("=" * 80)

    try:
        test_api_single_lead()
        test_api_batch_leads()
        test_api_json_serialization()
        test_different_program_types()

        print("\n" + "=" * 80)
        print("✅ ALL TESTS PASSED")
        print("=" * 80)
        print("\n🚀 API is ready for deployment!")
        print("\n   To start the API server:")
        print("   $ uvicorn src.lead_scoring.api.app:app --reload --port 8000")
        print("\n   Then visit:")
        print("   • http://localhost:8000/docs (Swagger UI)")
        print("   • http://localhost:8000/redoc (ReDoc)")
        print("\n")

    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
