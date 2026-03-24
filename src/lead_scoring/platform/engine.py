"""PRD-aligned buying intelligence service."""

from __future__ import annotations

import json
import math
import pickle
from datetime import UTC, datetime
from typing import Any

import pandas as pd

from .audit import AuditRepository
from .brief_parser import CampaignBriefParser
from .classifiers import AssetClassifier, CampaignModeInferrer, NormalisedTitle, TitleNormalizer
from .config import load_platform_config
from .contracts import (
    BatchScoreResult,
    BuyingGroupSummary,
    CampaignReport,
    CampaignReportItem,
    DeliveryDecision,
    FunnelStage,
    LeadQuadrant,
    LeadQualityBreakdown,
    LeadRecord,
    LeadScoreResult,
    PersonaSnapshot,
    PredictedOutcome,
    RetrainResult,
    TopReason,
)
from .training import FEATURE_COLUMNS, MODEL_DIR, run_monthly_retrain


class BuyingIntelligenceService:
    """Two-layer service described in the revised PRD."""

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or load_platform_config()
        self.title_normalizer = TitleNormalizer(self.config)
        self.asset_classifier = AssetClassifier(self.config)
        self.mode_inferrer = CampaignModeInferrer(self.config)
        self.brief_parser = CampaignBriefParser(self.config)
        self._runtime_bundle = self._load_runtime_bundle()

    def score_lead(self, lead: LeadRecord, persist: bool = True) -> LeadScoreResult:
        """Score a single lead using Layer 1 plus Layer 2 context."""
        title = self.title_normalizer.normalise(lead.contact.job_title)
        asset = self.asset_classifier.classify(
            lead.campaign.asset_name or self._latest_asset_name(lead),
            taxonomy=lead.campaign.taxonomy.model_dump(),
        )
        campaign_mode = self.mode_inferrer.infer(
            lead.campaign.taxonomy.model_dump(),
            asset.stage,
        )
        target_profile = self._merge_target_profiles(
            self.brief_parser.parse(lead.campaign.brief_text),
            lead.campaign.target_profile,
        )
        persisted_personas = self._load_persisted_personas(
            lead.company.domain,
            lead.campaign.client_id,
        )
        buying_group = self._build_buying_group_summary(
            lead=lead,
            title=title,
            asset_stage=asset.stage,
            target_profile=target_profile,
            persisted_personas=persisted_personas,
        )
        features = self._build_feature_vector(
            lead=lead,
            title=title,
            asset=asset,
            campaign_mode=campaign_mode,
            target_profile=target_profile,
            buying_group=buying_group,
        )
        approval_score, contributions, model_version = self._predict_approval(features)
        predicted_outcome = self._predict_outcome(approval_score)
        delivery_decision = self._delivery_decision(approval_score)
        quadrant = self._determine_quadrant(
            features["fit_score"],
            features["intent_score"],
        )
        breakdown = LeadQualityBreakdown(
            fit_score=int(round(features["fit_score"])),
            intent_score=int(round(features["intent_score"])),
            partner_signal_score=int(round(features["partner_signal_score"])),
            client_history_score=int(round(features["client_history_score"])),
            campaign_history_score=int(round(features["campaign_history_score"])),
            data_quality_score=int(round(features["data_quality_score"])),
            icp_match_score=int(round(features["icp_match_score"])),
        )
        top_reasons = self._build_top_reasons(
            lead=lead,
            title=title,
            buying_group=buying_group,
            features=features,
            contributions=contributions,
        )
        result = LeadScoreResult(
            lead_id=lead.lead_id,
            campaign_id=lead.campaign.campaign_id,
            client_id=lead.campaign.client_id,
            model_version=model_version,
            predicted_outcome=predicted_outcome,
            delivery_decision=delivery_decision,
            approval_score=int(round(approval_score)),
            campaign_mode=campaign_mode,
            quadrant=quadrant,
            breakdown=breakdown,
            top_reasons=top_reasons,
            buying_group=buying_group,
        )
        if persist:
            repository = AuditRepository()
            try:
                audit_id = repository.save_score(lead, result, features)
                result.score_audit_id = audit_id
            finally:
                repository.close()
        return result

    def score_batch(self, leads: list[LeadRecord], persist: bool = True) -> BatchScoreResult:
        """Score a batch of leads."""
        results = [self.score_lead(lead, persist=persist) for lead in leads]
        return BatchScoreResult(
            total_leads=len(leads),
            scored_leads=len(results),
            results=results,
        )

    def get_buying_group(self, lead: LeadRecord) -> BuyingGroupSummary:
        """Preview the buying group summary for a lead without writing a new score."""
        title = self.title_normalizer.normalise(lead.contact.job_title)
        asset = self.asset_classifier.classify(
            lead.campaign.asset_name or self._latest_asset_name(lead),
            taxonomy=lead.campaign.taxonomy.model_dump(),
        )
        target_profile = self._merge_target_profiles(
            self.brief_parser.parse(lead.campaign.brief_text),
            lead.campaign.target_profile,
        )
        persisted_personas = self._load_persisted_personas(
            lead.company.domain,
            lead.campaign.client_id,
        )
        return self._build_buying_group_summary(
            lead=lead,
            title=title,
            asset_stage=asset.stage,
            target_profile=target_profile,
            persisted_personas=persisted_personas,
        )

    def get_campaign_report(self, campaign_id: str) -> CampaignReport:
        """Build a campaign report from persisted score audits."""
        repository = AuditRepository()
        try:
            records = repository.build_campaign_report_records(campaign_id)
        finally:
            repository.close()
        if not records:
            return CampaignReport(
                campaign_id=campaign_id,
                total_accounts=0,
                accounts_with_bdr_trigger=0,
                report_items=[],
            )

        grouped: dict[str, dict[str, Any]] = {}
        client_id: str | None = None
        for request_payload, summary in records:
            account_domain = request_payload["company"]["domain"].lower()
            grouped.setdefault(
                account_domain,
                {
                    "client_id": request_payload["campaign"]["client_id"],
                    "lead_ids": [],
                    "summary": summary,
                },
            )
            grouped[account_domain]["lead_ids"].append(request_payload["lead_id"])
            current_summary = grouped[account_domain]["summary"]
            if summary.buying_group_score >= current_summary.buying_group_score:
                grouped[account_domain]["summary"] = summary
            client_id = request_payload["campaign"]["client_id"]

        report_items = [
            CampaignReportItem(
                account_domain=account_domain,
                client_id=item["client_id"],
                campaign_id=campaign_id,
                unique_persona_count=item["summary"].unique_persona_count,
                persona_completeness_score=item["summary"].persona_completeness_score,
                function_coverage=item["summary"].function_coverage,
                journey_stage_reached=item["summary"].journey_stage_reached,
                bdr_trigger=item["summary"].bdr_trigger,
                missing_personas=item["summary"].missing_personas,
                accounts_leads=sorted(set(item["lead_ids"])),
            )
            for account_domain, item in grouped.items()
        ]
        report_items.sort(
            key=lambda item: (
                not item.bdr_trigger,
                -item.persona_completeness_score,
                -item.unique_persona_count,
            )
        )
        return CampaignReport(
            campaign_id=campaign_id,
            client_id=client_id,
            total_accounts=len(report_items),
            accounts_with_bdr_trigger=sum(1 for item in report_items if item.bdr_trigger),
            report_items=report_items,
        )

    def label_outcome(self, lead_id: str, campaign_id: str, outcome: PredictedOutcome, notes: str | None) -> bool:
        """Persist the actual client decision for a lead."""
        repository = AuditRepository()
        try:
            return repository.label_outcome(lead_id, campaign_id, outcome, notes)
        finally:
            repository.close()

    def run_retrain(self, dataset_path: str, force_promote: bool = False) -> RetrainResult:
        """Trigger the monthly retrain workflow."""
        return run_monthly_retrain(dataset_path=dataset_path, force_promote=force_promote)

    def _build_buying_group_summary(
        self,
        lead: LeadRecord,
        title: NormalisedTitle,
        asset_stage: FunnelStage,
        target_profile,
        persisted_personas: list[PersonaSnapshot],
    ) -> BuyingGroupSummary:
        recent_personas = list(lead.account_signals.recent_personas) + list(persisted_personas)
        current_persona = PersonaSnapshot(
            lead_id=lead.lead_id,
            email=str(lead.contact.email),
            full_name=f"{lead.contact.first_name} {lead.contact.last_name}".strip(),
            job_title=lead.contact.job_title,
            job_function=title.job_function,
            seniority=title.seniority,
            status="approved",
            asset_name=lead.campaign.asset_name or self._latest_asset_name(lead),
            asset_stage=asset_stage,
            occurred_at=lead.submitted_at,
        )
        recent_personas.append(current_persona)

        unique_personas: dict[str, PersonaSnapshot] = {}
        for persona in recent_personas:
            key = persona.email or f"{persona.job_function}:{persona.seniority}:{persona.job_title}"
            unique_personas[key] = persona

        active_personas = list(unique_personas.values())
        functions = sorted(
            {
                (persona.job_function or "unknown")
                for persona in active_personas
                if (persona.status or "").lower() in {"approved", "accepted", "deliver", "delivered"}
            }
        )
        seniorities = sorted(
            {
                persona.seniority or "unknown"
                for persona in active_personas
                if (persona.status or "").lower() in {"approved", "accepted", "deliver", "delivered"}
            }
        )
        vertical = (
            target_profile.industries[0]
            if target_profile.industries
            else self.asset_classifier.classify(lead.campaign.asset_name, lead.campaign.taxonomy.model_dump()).vertical
        )
        required_personas = self._required_personas(vertical, target_profile.required_personas)
        missing = [persona for persona in required_personas if persona not in functions]
        completeness = 0
        if required_personas:
            completeness = round(100 * (len(required_personas) - len(missing)) / len(required_personas))

        journey_stage = max(
            (persona.asset_stage or FunnelStage.TOFU for persona in active_personas),
            key=lambda stage: {"TOFU": 1, "MOFU": 2, "BOFU": 3}[stage.value],
        )
        account_history_score = round((lead.account_signals.client_acceptance_rate_6m or 0.5) * 100)
        buying_group_weights = self.config.get("weights", {}).get("buying_group", {})
        journey_stage_score = {"TOFU": 35, "MOFU": 65, "BOFU": 90}[journey_stage.value]
        buying_group_score = (
            min(len(functions), 4) / 4 * 100 * float(buying_group_weights.get("unique_persona_count", 0.35))
            + completeness * float(buying_group_weights.get("persona_completeness_score", 0.25))
            + journey_stage_score * float(buying_group_weights.get("journey_stage_score", 0.20))
            + account_history_score * float(buying_group_weights.get("account_history_score", 0.20))
        )
        bdr_trigger = len(functions) >= int(
            self.config.get("thresholds", {}).get("bdr_trigger_personas", 2)
        )
        return BuyingGroupSummary(
            account_domain=lead.company.domain.lower(),
            unique_persona_count=len(functions),
            function_coverage=functions,
            seniority_coverage=seniorities,
            persona_completeness_score=int(round(completeness if required_personas else min(100, buying_group_score))),
            journey_stage_reached=journey_stage,
            missing_personas=missing,
            bdr_trigger=bdr_trigger,
            buying_group_score=int(round(min(100, buying_group_score))),
        )

    def _build_feature_vector(
        self,
        lead: LeadRecord,
        title: NormalisedTitle,
        asset,
        campaign_mode: FunnelStage,
        target_profile,
        buying_group: BuyingGroupSummary,
    ) -> dict[str, float]:
        industry_match = self._match_value(lead.company.industry, target_profile.industries)
        geography_match = self._match_value(lead.company.geography, target_profile.geographies)
        size_match = self._match_value(lead.company.company_size, target_profile.company_sizes)
        function_match = self._match_value(title.job_function, target_profile.job_functions)
        seniority_match = self._match_value(title.seniority, target_profile.seniorities)
        icp_match_score = round((industry_match + geography_match + max(function_match, seniority_match)) / 3 * 100)

        fit_components = [
            title.authority_score * 0.25,
            industry_match * 100 * 0.20,
            geography_match * 100 * 0.15,
            size_match * 100 * 0.10,
            function_match * 100 * 0.20,
            seniority_match * 100 * 0.10,
        ]
        fit_score = min(100.0, sum(fit_components))

        engagement_metrics = self._calculate_engagement_metrics(lead.engagement_events, asset.stage_weight)
        intent_score = min(
            100.0,
            engagement_metrics["email_engagement_score"] * 0.60
            + engagement_metrics["late_stage_signal"] * 0.20
            + buying_group.buying_group_score * 0.20,
        )

        partner_rates = [
            rate
            for rate in (
                lead.partner_signals.approval_rate_6m,
                lead.partner_signals.approval_rate_client_6m,
                lead.partner_signals.approval_rate_vertical_6m,
            )
            if rate is not None
        ]
        partner_signal_score = round(100 * (sum(partner_rates) / len(partner_rates))) if partner_rates else 50
        client_history_score = round(100 * (lead.account_signals.client_acceptance_rate_6m or 0.5))
        campaign_history_score = round(100 * (lead.campaign.history_approval_rate or 0.5))
        data_quality_score = self._data_quality_score(lead, title)
        return {
            "authority_score": float(title.authority_score),
            "fit_score": float(fit_score),
            "intent_score": float(intent_score),
            "partner_signal_score": float(partner_signal_score),
            "client_history_score": float(client_history_score),
            "campaign_history_score": float(campaign_history_score),
            "data_quality_score": float(data_quality_score),
            "icp_match_score": float(icp_match_score),
            "buying_group_score": float(buying_group.buying_group_score),
            "unique_persona_count": float(buying_group.unique_persona_count),
            "late_stage_signal": float(engagement_metrics["late_stage_signal"]),
            "email_engagement_score": float(engagement_metrics["email_engagement_score"]),
            "second_touch_signal": float(engagement_metrics["second_touch_signal"]),
            "recency_score": float(engagement_metrics["recency_score"]),
            "campaign_mode_score": float({"TOFU": 40, "MOFU": 70, "BOFU": 90}[campaign_mode.value]),
        }

    def _predict_approval(self, features: dict[str, float]) -> tuple[float, dict[str, float], str]:
        """Predict approval probability via promoted model or heuristic baseline."""
        if self._runtime_bundle is not None:
            model, metadata = self._runtime_bundle
            columns = metadata.get("feature_columns", FEATURE_COLUMNS)
            vector = pd.DataFrame(
                [[features.get(column, 0.0) for column in columns]],
                columns=columns,
            )
            if hasattr(model, "predict_proba"):
                score = float(model.predict_proba(vector)[0][1] * 100)
            else:
                score = float(model.predict(vector)[0] * 100)
            contributions = {
                column: features.get(column, 0.0)
                for column in columns
            }
            return score, contributions, str(metadata.get("model_version", "prd_runtime_model"))

        weights = self.config.get("weights", {}).get("approval", {})
        contributions = {
            name: features.get(name, 0.0) * float(weights.get(name, 0.0))
            for name in (
                "fit_score",
                "intent_score",
                "partner_signal_score",
                "client_history_score",
                "campaign_history_score",
                "data_quality_score",
                "icp_match_score",
            )
        }
        score = sum(contributions.values())
        if features["data_quality_score"] < 45:
            score -= 8
        if features["partner_signal_score"] < 40:
            score -= 10
        return max(0.0, min(100.0, score)), contributions, "prd_runtime_heuristic_v1"

    def _build_top_reasons(
        self,
        lead: LeadRecord,
        title: NormalisedTitle,
        buying_group: BuyingGroupSummary,
        features: dict[str, float],
        contributions: dict[str, float],
    ) -> list[TopReason]:
        """Translate feature contributions into plain-English reasons."""
        messages = {
            "fit_score": (
                "fit_score",
                f"Title and firmographic fit align with the campaign ICP ({title.seniority} {title.job_function}).",
            ),
            "intent_score": (
                "intent_score",
                "Engagement depth and content stage indicate active evaluation intent.",
            ),
            "partner_signal_score": (
                "partner_signal_score",
                "The partner's recent approval history is boosting confidence for this delivery.",
            ),
            "client_history_score": (
                "client_history_score",
                "This client's recent acceptance pattern supports a likely approval outcome.",
            ),
            "campaign_history_score": (
                "campaign_history_score",
                "Campaign-level approval history suggests this delivery is on-target.",
            ),
            "data_quality_score": (
                "data_quality_score",
                f"Data quality is {'strong' if features['data_quality_score'] >= 70 else 'at risk'} based on email, title, and company completeness.",
            ),
            "icp_match_score": (
                "icp_match_score",
                "Industry, geography, and role alignment match the inferred ICP profile.",
            ),
            "buying_group_score": (
                "buying_group_score",
                (
                    "Multiple personas are already active at this account."
                    if buying_group.bdr_trigger
                    else "Buying-group coverage is still incomplete, so this account needs further nurture."
                ),
            ),
        }
        ranked = sorted(
            (
                (key, float(value))
                for key, value in contributions.items()
                if key in messages
            ),
            key=lambda item: abs(item[1]),
            reverse=True,
        )
        reasons = [
            TopReason(feature=messages[key][0], impact=round(value, 2), message=messages[key][1])
            for key, value in ranked[:3]
        ]
        if len(reasons) < 3:
            reasons.append(
                TopReason(
                    feature="buying_group_score",
                    impact=float(features["buying_group_score"]),
                    message=(
                        "A BDR trigger is active because multiple approved personas are engaging."
                        if buying_group.bdr_trigger
                        else "Only one persona is active, so account-level buying signal is still forming."
                    ),
                )
            )
        return reasons[:3]

    def _calculate_engagement_metrics(self, events, stage_weight: float) -> dict[str, float]:
        weights = self.config.get("engagement_weights", {})
        total = 0.0
        second_touch_signal = 0.0
        most_recent: datetime | None = None
        for event in events:
            base = float(weights.get(event.event_type, 0))
            if event.email_number == 2:
                base *= float(weights.get("email_two_multiplier", 1.5))
                second_touch_signal += base
            total += base
            if most_recent is None or event.occurred_at > most_recent:
                most_recent = event.occurred_at
        recency_score = 35.0
        if most_recent is not None:
            age_days = max((datetime.now(UTC) - most_recent).days, 0)
            recency_score = 100 * math.exp(
                -math.log(2) * age_days / max(float(weights.get("recency_half_life_days", 21)), 1.0)
            )
        email_engagement_score = min(100.0, total * stage_weight)
        late_stage_signal = min(100.0, stage_weight * 20.0)
        return {
            "email_engagement_score": email_engagement_score,
            "late_stage_signal": late_stage_signal,
            "second_touch_signal": min(100.0, second_touch_signal),
            "recency_score": min(100.0, recency_score),
        }

    def _data_quality_score(self, lead: LeadRecord, title: NormalisedTitle) -> int:
        score = 100
        domain = str(lead.contact.email).split("@")[-1].lower()
        if domain in set(self.config.get("generic_domains", [])):
            score -= 20
        if not lead.contact.job_title:
            score -= 15
        if title.job_function == "unknown":
            score -= 12
        if not lead.company.company_size:
            score -= 10
        if not lead.company.geography:
            score -= 8
        return max(0, score)

    def _match_value(self, value: str | None, accepted_values: list[str]) -> float:
        if not accepted_values:
            return 0.6
        lowered = str(value or "").lower()
        return 1.0 if any(token in lowered for token in accepted_values) else 0.0

    def _predict_outcome(self, approval_score: float) -> PredictedOutcome:
        threshold = float(self.config.get("thresholds", {}).get("predicted_approval_score", 55))
        return PredictedOutcome.APPROVED if approval_score >= threshold else PredictedOutcome.REJECTED

    def _delivery_decision(self, approval_score: float) -> DeliveryDecision:
        thresholds = self.config.get("thresholds", {})
        if approval_score >= float(thresholds.get("deliver_score", 68)):
            return DeliveryDecision.DELIVER
        if approval_score >= float(thresholds.get("review_score", 50)):
            return DeliveryDecision.REVIEW
        return DeliveryDecision.HOLD

    def _determine_quadrant(self, fit_score: float, intent_score: float) -> LeadQuadrant:
        thresholds = self.config.get("thresholds", {})
        high_fit = fit_score >= float(thresholds.get("high_fit_score", 65))
        high_intent = intent_score >= float(thresholds.get("high_intent_score", 55))
        if high_fit and high_intent:
            return LeadQuadrant.PRIORITY
        if high_fit and not high_intent:
            return LeadQuadrant.NURTURE
        if (not high_fit) and high_intent:
            return LeadQuadrant.CHAMPION
        return LeadQuadrant.MONITOR

    def _required_personas(self, vertical: str, explicit: list[str]) -> list[str]:
        if explicit:
            return explicit
        vertical_map = self.config.get("vertical_personas", {})
        return vertical_map.get(vertical, vertical_map.get("default", []))

    @staticmethod
    def _load_persisted_personas(account_domain: str, client_id: str) -> list[PersonaSnapshot]:
        repository = AuditRepository()
        try:
            return repository.get_recent_personas(account_domain, client_id=client_id)
        finally:
            repository.close()

    def _merge_target_profiles(self, parsed_profile, explicit_profile):
        return explicit_profile.model_copy(
            update={
                "industries": explicit_profile.industries or parsed_profile.industries,
                "geographies": explicit_profile.geographies or parsed_profile.geographies,
                "company_sizes": explicit_profile.company_sizes or parsed_profile.company_sizes,
                "job_functions": explicit_profile.job_functions or parsed_profile.job_functions,
                "seniorities": explicit_profile.seniorities or parsed_profile.seniorities,
                "required_personas": explicit_profile.required_personas or parsed_profile.required_personas,
            }
        )

    @staticmethod
    def _latest_asset_name(lead: LeadRecord) -> str | None:
        if not lead.engagement_events:
            return None
        latest = max(lead.engagement_events, key=lambda event: event.occurred_at)
        return latest.asset_name

    @staticmethod
    def _load_runtime_bundle() -> tuple[Any, dict[str, Any]] | None:
        model_path = MODEL_DIR / "lead_quality_model.pkl"
        metadata_path = MODEL_DIR / "model_metadata.json"
        if not model_path.exists() or not metadata_path.exists():
            return None
        try:
            with open(model_path, "rb") as handle:
                model = pickle.load(handle)
            with open(metadata_path, "r", encoding="utf-8") as handle:
                metadata = json.load(handle)
            return model, metadata
        except Exception:
            return None
