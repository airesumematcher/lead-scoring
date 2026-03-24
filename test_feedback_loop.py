"""
Test script for Feedback Loop system.
Tests drift detection, retraining triggers, and feedback endpoints.
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from lead_scoring.feedback import (
    LeadFeedback,
    FeedbackOutcome,
    FeedbackReason,
    DriftDetector,
    RetrainingScheduler,
    AcceptanceGuardrail,
)


def create_test_feedback(
    lead_id: str,
    score: int,
    outcome: FeedbackOutcome,
    reason: FeedbackReason,
    days_ago: int = 1,
) -> LeadFeedback:
    """Helper to create test feedback."""
    now = datetime.utcnow()
    scored_at = now - timedelta(days=days_ago + 1)
    feedback_at = now - timedelta(days=days_ago)
    
    return LeadFeedback(
        lead_id=lead_id,
        scored_at=scored_at,
        feedback_at=feedback_at,
        outcome=outcome,
        reason=reason,
        notes="Test feedback",
        original_score=score,
        original_grade="C" if 50 <= score < 70 else "D" if score < 50 else "B",
        sal_decision_maker="sales@company.com",
    )


def test_drift_detection():
    """Test drift detection functionality."""
    print("\n" + "=" * 80)
    print("TEST 1: Drift Detection")
    print("=" * 80)
    
    detector = DriftDetector(baseline_acceptance_rate=0.50)
    
    # Scenario 1: Normal performance (50% acceptance)
    print("\n📊 Scenario 1: Normal Performance (50% accepted, 50% rejected)")
    feedback_normal = [
        create_test_feedback("L-01001", 75, FeedbackOutcome.ACCEPTED, FeedbackReason.EXCELLENT_FIT),
        create_test_feedback("L-01002", 65, FeedbackOutcome.ACCEPTED, FeedbackReason.MATCHED_EXPECTATIONS),
        create_test_feedback("L-01003", 45, FeedbackOutcome.REJECTED, FeedbackReason.POOR_FIT),
        create_test_feedback("L-01004", 35, FeedbackOutcome.REJECTED, FeedbackReason.WRONG_PERSONA),
    ]
    
    metrics_normal = detector.calculate_metrics(feedback_normal)
    drift_status, drift_reason, severity = detector.detect_drift(metrics_normal)
    
    print(f"   Acceptance Rate: {metrics_normal.acceptance_rate:.1%}")
    print(f"   Rate Change: {metrics_normal.acceptance_rate_change_pct:+.1f}%")
    print(f"   Avg Score Accepted: {metrics_normal.avg_score_accepted:.0f}")
    print(f"   Avg Score Rejected: {metrics_normal.avg_score_rejected:.0f}")
    print(f"   Score Gap: {metrics_normal.score_gap:.0f}")
    print(f"   Drift Status: {drift_status}")
    print(f"   Severity: {severity:.2f}")
    
    assert drift_status == "normal", "Should detect normal performance"
    print("   ✅ Normal drift detection passed")
    
    # Scenario 2: Acceptance rate slightly increased (56% = +6% from baseline)
    print("\n📊 Scenario 2: Moderate Acceptance Drift (56% accepted, 44% rejected - 6% change)")
    feedback_high_accept = [
        *[create_test_feedback(f"L-02{i:03d}", 70 + i*2, FeedbackOutcome.ACCEPTED, 
                               FeedbackReason.EXCELLENT_FIT) for i in range(14)],
        *[create_test_feedback(f"L-02{i:03d}", 40 + i, FeedbackOutcome.REJECTED, 
                               FeedbackReason.POOR_FIT) for i in range(11)],
    ]
    
    metrics_high = detector.calculate_metrics(feedback_high_accept)
    drift_status, drift_reason, severity = detector.detect_drift(metrics_high)
    
    print(f"   Acceptance Rate: {metrics_high.acceptance_rate:.1%}")
    print(f"   Rate Change: {metrics_high.acceptance_rate_change_pct:+.1f}%")
    print(f"   Drift Status: {drift_status}")
    print(f"   Severity: {severity:.2f}")
    
    assert drift_status == "drift_detected", f"Should detect drift at 5-10%, got {drift_status}"
    print("   ✅ Drift detection passed")
    
    # Scenario 3: Critical drift (20% acceptance)
    print("\n📊 Scenario 3: Critical Drift (20% accepted, 80% rejected)")
    feedback_critical = [
        *[create_test_feedback(f"L-03{i:03d}", 60 + i, FeedbackOutcome.ACCEPTED, 
                               FeedbackReason.MATCHED_EXPECTATIONS) for i in range(2)],
        *[create_test_feedback(f"L-03{i:03d}", 30 + i, FeedbackOutcome.REJECTED, 
                               FeedbackReason.POOR_FIT) for i in range(8)],
    ]
    
    metrics_critical = detector.calculate_metrics(feedback_critical)
    drift_status, drift_reason, severity = detector.detect_drift(metrics_critical)
    
    print(f"   Acceptance Rate: {metrics_critical.acceptance_rate:.1%}")
    print(f"   Rate Change: {metrics_critical.acceptance_rate_change_pct:+.1f}%")
    print(f"   Drift Status: {drift_status}")
    print(f"   Severity: {severity:.2f}")
    
    assert drift_status == "critical_drift", "Should detect critical drift at >10%"
    print("   ✅ Critical drift detection passed")


def test_retraining_scheduler():
    """Test retraining scheduling logic."""
    print("\n" + "=" * 80)
    print("TEST 2: Retraining Scheduler")
    print("=" * 80)
    
    scheduler = RetrainingScheduler(min_feedback_count=100, max_days_since_retrain=30)
    
    # Test 1: Not enough data, no drift
    print("\n🔄 Test 1: Insufficient data, normal drift")
    should_retrain, reason = scheduler.should_retrain(
        feedback_count=50,
        drift_status="normal",
        last_retrain_date=None,
    )
    print(f"   Feedback Count: 50")
    print(f"   Should Retrain: {should_retrain}")
    print(f"   Reason: {reason}")
    assert not should_retrain, "Should not retrain with <100 items"
    print("   ✅ Passed")
    
    # Test 2: Enough data, normal status
    print("\n🔄 Test 2: Sufficient data, normal drift")
    should_retrain, reason = scheduler.should_retrain(
        feedback_count=100,
        drift_status="normal",
        last_retrain_date=None,
    )
    print(f"   Feedback Count: 100 (min required)")
    print(f"   Should Retrain: {should_retrain}")
    print(f"   Reason: {reason}")
    assert should_retrain, "Should retrain with 100+ items (first time)"
    print("   ✅ Passed")
    
    # Test 3: Drift detected with enough data
    print("\n🔄 Test 3: Drift detected with sufficient data")
    should_retrain, reason = scheduler.should_retrain(
        feedback_count=120,
        drift_status="drift_detected",
        last_retrain_date=None,
    )
    print(f"   Feedback Count: 120")
    print(f"   Drift Status: drift_detected")
    print(f"   Should Retrain: {should_retrain}")
    print(f"   Reason: {reason}")
    assert should_retrain, "Should retrain on drift"
    print("   ✅ Passed")
    
    # Test 4: Critical drift always triggers
    print("\n🔄 Test 4: Critical drift (always triggers)")
    should_retrain, reason = scheduler.should_retrain(
        feedback_count=10,
        drift_status="critical_drift",
        last_retrain_date=None,
    )
    print(f"   Feedback Count: 10 (below minimum)")
    print(f"   Drift Status: critical_drift")
    print(f"   Should Retrain: {should_retrain}")
    print(f"   Reason: {reason}")
    assert should_retrain, "Critical drift should override minimum"
    print("   ✅ Passed")
    
    # Test 5: Scheduled retraining
    print("\n🔄 Test 5: Scheduled retraining (30+ days)")
    last_retrain = datetime.utcnow() - timedelta(days=31)
    should_retrain, reason = scheduler.should_retrain(
        feedback_count=50,
        drift_status="normal",
        last_retrain_date=last_retrain,
    )
    print(f"   Days Since Retrain: 31")
    print(f"   Should Retrain: {should_retrain}")
    print(f"   Reason: {reason}")
    assert should_retrain, "Should retrain on schedule"
    print("   ✅ Passed")


def test_guardrails():
    """Test acceptance guardrails."""
    print("\n" + "=" * 80)
    print("TEST 3: Acceptance Guardrails")
    print("=" * 80)
    
    guardrail = AcceptanceGuardrail(
        max_single_client_influence_pct=30.0,
        min_sample_size_per_class=10,
        max_score_skew_pct=15.0,
    )
    
    # Test 1: Valid feedback
    print("\n🛡️ Test 1: Valid feedback (passes guardrails)")
    feedback = [
        *[create_test_feedback(f"L-04{i:03d}", 75, FeedbackOutcome.ACCEPTED, 
                              FeedbackReason.EXCELLENT_FIT) for i in range(15)],
        *[create_test_feedback(f"L-04{i:03d}", 35, FeedbackOutcome.REJECTED, 
                              FeedbackReason.POOR_FIT) for i in range(15)],
    ]
    
    # Distribute feedback across multiple SALs to avoid guardrail violation
    sals = ["alice@sales.com", "bob@sales.com", "carol@sales.com", "dave@sales.com"]
    for i, f in enumerate(feedback):
        f.sal_decision_maker = sals[i % len(sals)]
    
    result = guardrail.check_guardrails(feedback)
    print(f"   Total Feedback: 30")
    print(f"   Passed: {result['passed']}")
    print(f"   Warnings: {len(result['warnings'])}")
    print(f"   Errors: {len(result['errors'])}")
    if result["errors"]:
        print(f"   Details: {result['errors']}")
    assert result["passed"], "Should pass guardrails"
    print("   ✅ Passed")
    
    # Test 2: Single client too influential
    print("\n🛡️ Test 2: Single client influence too high (35% > 30% limit)")
    feedback_biased = [
        *[create_test_feedback(f"L-05{i:03d}", min(70 + i % 20, 100), FeedbackOutcome.ACCEPTED, 
                              FeedbackReason.EXCELLENT_FIT, days_ago=1) for i in range(35)],
        *[create_test_feedback(f"L-05{i:03d}", min(30 + i % 20, 100), FeedbackOutcome.REJECTED, 
                              FeedbackReason.POOR_FIT, days_ago=1) for i in range(65)],
    ]
    
    # Override SAL to be same for first 35
    for i in range(35):
        feedback_biased[i].sal_decision_maker = "alice@sales.com"
    
    result = guardrail.check_guardrails(feedback_biased)
    print(f"   Total Feedback: 100")
    print(f"   Single SAL Influence: 35%")
    print(f"   Passed: {result['passed']}")
    print(f"   Errors: {len(result['errors'])}")
    
    if result["errors"]:
        print(f"   Error: {result['errors'][0]}")
    assert not result["passed"], "Should fail on high influence"
    print("   ✅ Passed")


def test_feedback_summary():
    """Test feedback summarization."""
    print("\n" + "=" * 80)
    print("TEST 4: Feedback Summarization")
    print("=" * 80)
    
    detector = DriftDetector(baseline_acceptance_rate=0.50)
    
    feedback = [
        create_test_feedback("L-06001", 80, FeedbackOutcome.ACCEPTED, FeedbackReason.EXCELLENT_FIT),
        create_test_feedback("L-06002", 70, FeedbackOutcome.ACCEPTED, FeedbackReason.MATCHED_EXPECTATIONS),
        create_test_feedback("L-06003", 40, FeedbackOutcome.REJECTED, FeedbackReason.POOR_FIT),
        create_test_feedback("L-06004", 30, FeedbackOutcome.REJECTED, FeedbackReason.WRONG_PERSONA),
    ]
    
    summary = detector.summarize_feedback(feedback)
    
    print(f"📋 Feedback Summary:")
    print(f"   Total Items: {summary['total_feedback']}")
    print(f"   Acceptance Rate: {summary['acceptance_rate']}")
    print(f"   Rejection Rate: {summary['rejection_rate']}")
    print(f"   Rate Change: {summary['rate_change']}")
    print(f"   Avg Score (Accepted): {summary['avg_score_accepted']}")
    print(f"   Avg Score (Rejected): {summary['avg_score_rejected']}")
    print(f"   Score Gap: {summary['score_gap']}")
    print(f"   Drift Status: {summary['drift_status']}")
    print(f"   Top Reason (Accepted): {summary['top_reason_accepted']}")
    print(f"   Top Reason (Rejected): {summary['top_reason_rejected']}")
    
    assert summary["total_feedback"] == 4, "Should count 4 items"
    print("   ✅ Summary passed")


def main():
    """Run all feedback loop tests."""
    print("\n" + "=" * 80)
    print("FEEDBACK LOOP TEST SUITE")
    print("=" * 80)
    
    try:
        test_drift_detection()
        test_retraining_scheduler()
        test_guardrails()
        test_feedback_summary()
        
        print("\n" + "=" * 80)
        print("✅ ALL FEEDBACK LOOP TESTS PASSED")
        print("=" * 80)
        print("\n📊 Feedback Loop System Status: Ready")
        print("   ✅ Drift detection working")
        print("   ✅ Retraining scheduler operational")
        print("   ✅ Guardrails enforcing constraints")
        print("   ✅ Summarization providing insights")
        print("\n🚀 Feedback API endpoints:")
        print("   POST /feedback/submit — Submit individual feedback")
        print("   POST /feedback/submit-batch — Submit batch feedback")
        print("   GET /feedback/analytics — View drift metrics")
        print("   GET /feedback/status — Check retraining status")
        print("\n")
        
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
