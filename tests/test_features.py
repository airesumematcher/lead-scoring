"""Tests for the current feature extraction contracts."""

from lead_scoring.features.accuracy import (
    AccuracyFeatures,
    extract_accuracy_features,
)
from lead_scoring.features.client_fit import (
    ClientFitFeatures,
    extract_client_fit_features,
)
from lead_scoring.features.engagement import (
    EngagementFeatures,
    extract_engagement_features,
)
from lead_scoring.features.extractor import extract_all_features


class TestAccuracyFeatures:
    def test_valid_email_for_high_fit(self, sample_lead_high_fit):
        features = extract_accuracy_features(sample_lead_high_fit)
        assert isinstance(features, AccuracyFeatures)
        assert features.email_valid is True
        assert features.phone_valid is True

    def test_low_fit_has_lower_accuracy_signal(self, sample_lead_low_fit):
        features = extract_accuracy_features(sample_lead_low_fit)
        assert isinstance(features, AccuracyFeatures)
        assert features.phone_valid is False
        assert features.accuracy_subscore < 100

    def test_delivery_latency_present(self, sample_lead_high_fit):
        features = extract_accuracy_features(sample_lead_high_fit)
        assert features.delivery_latency_days >= 0


class TestClientFitFeatures:
    def test_icp_match_high_fit(self, sample_lead_high_fit):
        features = extract_client_fit_features(sample_lead_high_fit)
        assert isinstance(features, ClientFitFeatures)
        assert features.industry_match_pts > 0

    def test_icp_mismatch_low_fit(self, sample_lead_low_fit):
        features = extract_client_fit_features(sample_lead_low_fit)
        assert isinstance(features, ClientFitFeatures)
        assert features.client_fit_subscore >= 0

    def test_persona_alignment_field(self, sample_lead_high_fit):
        features = extract_client_fit_features(sample_lead_high_fit)
        assert hasattr(features, "job_title_match_persona_pts")


class TestEngagementFeatures:
    def test_engagement_depth_high_fit(self, sample_lead_high_fit):
        features = extract_engagement_features(sample_lead_high_fit)
        assert isinstance(features, EngagementFeatures)
        assert features.engagement_sequence_depth == 2

    def test_no_engagement_flag(self, sample_lead_no_engagement):
        features = extract_engagement_features(sample_lead_no_engagement)
        assert features.engagement_absent_flag is True
        assert features.engagement_recency_days >= 999

    def test_recency_field(self, sample_lead_high_fit):
        features = extract_engagement_features(sample_lead_high_fit)
        assert hasattr(features, "engagement_recency_days")
        assert features.engagement_recency_days >= 0


class TestFeatureExtractionIntegration:
    def test_all_features_extracted_high_fit(self, sample_lead_high_fit):
        features = extract_all_features(sample_lead_high_fit)
        assert isinstance(features.accuracy, AccuracyFeatures)
        assert isinstance(features.client_fit, ClientFitFeatures)
        assert isinstance(features.engagement, EngagementFeatures)

    def test_feature_consistency(self, sample_lead_high_fit):
        features_1 = extract_accuracy_features(sample_lead_high_fit)
        features_2 = extract_accuracy_features(sample_lead_high_fit)
        assert features_1.email_valid == features_2.email_valid
        assert features_1.accuracy_subscore == features_2.accuracy_subscore
