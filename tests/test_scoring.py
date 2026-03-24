"""Tests for the current scoring pipeline."""

from lead_scoring.config import load_config
from lead_scoring.features.extractor import extract_all_features
from lead_scoring.scoring.layer1_gate import apply_accuracy_gates
from lead_scoring.scoring.layer2_scorer import compute_composite_score
from lead_scoring.scoring.score_builder import assemble_lead_score, map_score_to_grade
from lead_scoring.scoring.scorer import score_lead


class TestLayer1Gating:
    def test_pass_high_fit_lead(self, sample_lead_high_fit):
        config = load_config()
        features = extract_all_features(sample_lead_high_fit)
        gate_result = apply_accuracy_gates(features, config)
        assert gate_result.passed is True
        assert gate_result.recommended_accuracy_ceiling == 100

    def test_gate_evaluation_type(self, sample_lead_low_fit):
        config = load_config()
        features = extract_all_features(sample_lead_low_fit)
        gate_result = apply_accuracy_gates(features, config)
        assert hasattr(gate_result, "passed")
        assert hasattr(gate_result, "reason")
        assert hasattr(gate_result, "recommended_accuracy_ceiling")


class TestLayer2Scoring:
    def test_composite_score_high_fit(self, sample_lead_high_fit):
        config = load_config()
        features = extract_all_features(sample_lead_high_fit)
        composite = compute_composite_score(
            features,
            sample_lead_high_fit.campaign.program_type.value,
            config,
        )
        assert composite.composite_score >= 0
        assert composite.accuracy_subscore >= 0

    def test_composite_score_no_engagement(self, sample_lead_no_engagement):
        config = load_config()
        features = extract_all_features(sample_lead_no_engagement)
        composite = compute_composite_score(
            features,
            sample_lead_no_engagement.campaign.program_type.value,
            config,
        )
        assert composite is not None
        assert composite.composite_score > 0


class TestScoreBuilder:
    def test_score_grade_mapping(self):
        config = load_config()
        assert map_score_to_grade(90, config).value == "A"
        assert map_score_to_grade(75, config).value == "B"
        assert map_score_to_grade(65, config).value == "C"
        assert map_score_to_grade(45, config).value == "D"

    def test_all_score_fields_populated(self, sample_lead_high_fit):
        config = load_config()
        features = extract_all_features(sample_lead_high_fit)
        gate_result = apply_accuracy_gates(features, config)
        scoring_result = compute_composite_score(
            features,
            sample_lead_high_fit.campaign.program_type.value,
            config,
            accuracy_ceiling=gate_result.recommended_accuracy_ceiling,
        )
        score = assemble_lead_score(
            sample_lead_high_fit,
            features,
            gate_result,
            scoring_result,
            config,
        )
        assert score.lead_id == sample_lead_high_fit.lead_id
        assert score.score is not None
        assert score.grade is not None


class TestScoringOrchestration:
    def test_score_lead_high_fit(self, sample_lead_high_fit):
        config = load_config()
        score = score_lead(sample_lead_high_fit, config)
        assert score.lead_id == sample_lead_high_fit.lead_id
        assert 0 <= score.score <= 100

    def test_score_lead_low_fit(self, sample_lead_low_fit):
        config = load_config()
        score = score_lead(sample_lead_low_fit, config)
        assert score.lead_id == sample_lead_low_fit.lead_id

    def test_score_lead_deterministic(self, sample_lead_high_fit):
        config = load_config()
        score_1 = score_lead(sample_lead_high_fit, config)
        score_2 = score_lead(sample_lead_high_fit, config)
        assert score_1.score == score_2.score
        assert score_1.grade == score_2.grade
