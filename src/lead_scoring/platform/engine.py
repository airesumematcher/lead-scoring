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
    BuyingGroupDefinition,
    BuyingGroupRole,
    BuyingGroupSummary,
    CampaignReport,
    CampaignReportItem,
    DeliveryDecision,
    FunnelStage,
    LeadAnalysis,
    LeadQuadrant,
    LeadQualityBreakdown,
    LeadRecord,
    LeadScoreResult,
    PersonaCoverageItem,
    PersonaSnapshot,
    PredictedOutcome,
    RetrainResult,
    SellingStory,
    SignalDetail,
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
        analysis = self._build_lead_analysis(
            lead=lead,
            title=title,
            asset=asset,
            target_profile=target_profile,
            buying_group=buying_group,
            features=features,
        )
        selling_story = self._build_selling_story(
            lead=lead,
            title=title,
            approval_score=int(round(approval_score)),
            buying_group=buying_group,
            features=features,
            quadrant=quadrant,
            delivery_decision=delivery_decision,
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
            analysis=analysis,
            buying_group=buying_group,
            selling_story=selling_story,
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
                product_category=item["summary"].product_category,
                decision_maker_coverage_pct=item["summary"].decision_maker_coverage_pct,
                role_coverage=item["summary"].role_coverage,
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

    # Maps ML Platform job_level labels → internal seniority labels
    _JOB_LEVEL_MAP: dict[str, str] = {
        "c-suite": "executive",
        "c suite": "executive",
        "c_suite": "executive",
        "csuite": "executive",
        "director": "director",
        "vice president": "vp",
        "vp": "vp",
        "manager": "manager",
        "senior": "practitioner",
        "individual contributor": "practitioner",
        "associate": "practitioner",
        "staff": "practitioner",
    }

    # Maps ML Platform job_function labels → internal job_function labels
    _JOB_FUNCTION_MAP: dict[str, str] = {
        "finance": "finance",
        "financial services": "finance",
        "procurement": "procurement",
        "purchasing": "procurement",
        "information technology (it)": "it",
        "information technology": "it",
        "it": "it",
        "network management": "it",
        "technology": "it",
        "operations": "operations",
        "supply chain": "operations",
        "marketing": "marketing",
        "demand generation": "marketing",
        "sales": "sales",
        "business development": "sales",
        "revenue": "sales",
        "clinical": "clinical",
        "medical": "clinical",
        "healthcare": "clinical",
        "customer service": "customer_service",
        "customer success": "customer_service",
        "support": "customer_service",
        "human resources": "line_of_business",
        "hr": "line_of_business",
        "legal": "line_of_business",
        "strategy": "line_of_business",
        "line of business": "line_of_business",
    }

    @classmethod
    def _normalise_job_level(cls, value: str) -> str:
        return cls._JOB_LEVEL_MAP.get(str(value or "").strip().lower(), "unknown")

    @classmethod
    def _normalise_bg_function(cls, value: str) -> str:
        return cls._JOB_FUNCTION_MAP.get(str(value or "").strip().lower(), str(value or "").strip().lower())

    def _build_buying_group_summary(
        self,
        lead: LeadRecord,
        title: NormalisedTitle,
        asset_stage: FunnelStage,
        target_profile,
        persisted_personas: list[PersonaSnapshot],
    ) -> BuyingGroupSummary:
        bg_definition: BuyingGroupDefinition | None = lead.campaign.buying_group_definition

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

        journey_stage = max(
            (persona.asset_stage or FunnelStage.TOFU for persona in active_personas),
            key=lambda stage: {"TOFU": 1, "MOFU": 2, "BOFU": 3}[stage.value],
        )
        account_history_score = round((lead.account_signals.client_acceptance_rate_6m or 0.5) * 100)
        buying_group_weights = self.config.get("weights", {}).get("buying_group", {})
        journey_stage_score = {"TOFU": 35, "MOFU": 65, "BOFU": 90}[journey_stage.value]

        # --- Structured definition path ---
        if bg_definition and bg_definition.personas:
            role_weights = self.config.get("buying_group_role_weights", {
                "Decision-Maker": 0.40,
                "Influencer": 0.25,
                "Champion": 0.15,
                "User": 0.10,
                "Gatekeeper": 0.10,
            })
            persona_coverage: list[PersonaCoverageItem] = []
            covered_weight = 0.0
            total_weight = 0.0
            role_counts: dict[str, int] = {}
            role_covered: dict[str, int] = {}
            dm_total = 0
            dm_covered = 0

            for slot in bg_definition.personas:
                slot_fn = self._normalise_bg_function(slot.job_function)
                slot_lvl = self._normalise_job_level(slot.job_level)
                weight = float(role_weights.get(slot.role.value, 0.10))
                total_weight += weight
                role_counts[slot.role.value] = role_counts.get(slot.role.value, 0) + 1
                if slot.role == BuyingGroupRole.DECISION_MAKER:
                    dm_total += 1

                # Find if any active persona covers this slot (match on function + level)
                covering: PersonaSnapshot | None = None
                for ap in active_personas:
                    ap_fn = ap.job_function or "unknown"
                    ap_lvl = ap.seniority or "unknown"
                    if ap_fn == slot_fn and ap_lvl == slot_lvl:
                        if (ap.status or "").lower() in {"approved", "accepted", "deliver", "delivered"}:
                            covering = ap
                            break

                is_covered = covering is not None
                if is_covered:
                    covered_weight += weight
                    role_covered[slot.role.value] = role_covered.get(slot.role.value, 0) + 1
                    if slot.role == BuyingGroupRole.DECISION_MAKER:
                        dm_covered += 1

                persona_coverage.append(PersonaCoverageItem(
                    job_function=slot.job_function,
                    job_level=slot.job_level,
                    role=slot.role,
                    covered=is_covered,
                    covered_by=(covering.lead_id or covering.email) if covering else None,
                ))

            completeness = int(round(covered_weight / total_weight * 100)) if total_weight > 0 else 0
            dm_coverage_pct = int(round(dm_covered / dm_total * 100)) if dm_total > 0 else 0
            role_coverage = {role: int(round(role_covered.get(role, 0) / cnt * 100)) for role, cnt in role_counts.items()}

            missing = [
                f"{slot.job_function} ({slot.job_level}) [{slot.role.value}]"
                for slot, item in zip(bg_definition.personas, persona_coverage)
                if not item.covered
            ]

            bdr_thresholds = self.config.get("thresholds", {})
            bdr_trigger = (
                dm_coverage_pct >= int(bdr_thresholds.get("bdr_dm_coverage_pct", 50))
                and len(functions) >= int(bdr_thresholds.get("bdr_trigger_personas", 2))
            )
            buying_group_score = (
                (completeness) * float(buying_group_weights.get("persona_completeness_score", 0.25))
                + min(len(functions), 4) / 4 * 100 * float(buying_group_weights.get("unique_persona_count", 0.35))
                + journey_stage_score * float(buying_group_weights.get("journey_stage_score", 0.20))
                + account_history_score * float(buying_group_weights.get("account_history_score", 0.20))
            )
            return BuyingGroupSummary(
                account_domain=lead.company.domain.lower(),
                unique_persona_count=len(functions),
                function_coverage=functions,
                seniority_coverage=seniorities,
                persona_completeness_score=completeness,
                journey_stage_reached=journey_stage,
                missing_personas=missing,
                bdr_trigger=bdr_trigger,
                buying_group_score=int(round(min(100, buying_group_score))),
                product_category=bg_definition.product_category,
                group_type=bg_definition.group_type,
                is_verified=bg_definition.is_verified,
                decision_maker_coverage_pct=dm_coverage_pct,
                role_coverage=role_coverage,
                persona_coverage=persona_coverage,
            )

        # --- Inferred path (no definition) ---
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

    def _build_selling_story(
        self,
        lead: LeadRecord,
        title: NormalisedTitle,
        approval_score: int,
        buying_group: BuyingGroupSummary,
        features: dict[str, float],
        quadrant: LeadQuadrant,
        delivery_decision: DeliveryDecision,
    ) -> SellingStory:
        """Synthesize a three-part selling narrative from all scoring signals."""
        full_name = f"{lead.contact.first_name} {lead.contact.last_name}".strip()
        company = lead.company.company_name
        domain = lead.company.domain
        role_label = f"{title.seniority} {title.job_function}".strip()
        engagement_count = len(lead.engagement_events)
        journey = buying_group.journey_stage_reached.value
        completeness = buying_group.persona_completeness_score
        dm_pct = buying_group.decision_maker_coverage_pct
        product = buying_group.product_category or "this product category"
        bg_type = buying_group.group_type
        is_verified = buying_group.is_verified

        # Find this lead's buying group role if matched
        lead_bg_role: str | None = None
        for item in buying_group.persona_coverage:
            if item.covered and item.covered_by in (lead.lead_id, str(lead.contact.email)):
                lead_bg_role = item.role.value
                break

        # Determine motion
        if approval_score >= 68 and buying_group.bdr_trigger and dm_pct >= 50:
            motion = "accelerate"
            confidence = "High"
        elif approval_score >= 50 and completeness >= 30:
            motion = "nurture"
            confidence = "Medium"
        else:
            motion = "hold"
            confidence = "Low"

        # Build missing role summary
        missing_dm = [
            m for m in buying_group.missing_personas
            if "Decision-Maker" in m
        ]
        missing_other = [m for m in buying_group.missing_personas if m not in missing_dm]
        missing_summary = ", ".join(buying_group.missing_personas[:3]) or "none"

        # Coverage summary line
        covered_roles = [role for role, pct in buying_group.role_coverage.items() if pct > 0]
        covered_summary = ", ".join(covered_roles) if covered_roles else "functions not yet categorized by role"

        bg_verified_note = (
            f"This buying group has been {'verified' if is_verified else 'recommended'} "
            f"{'by a CXM or Client user' if is_verified else 'by Madison Logic AI'} "
            f"for {product}."
        )

        # --- Lead narrative ---
        if motion == "accelerate":
            lead_narrative = (
                f"{full_name} is a {role_label} at {company} ({domain}) with an approval score of "
                f"{approval_score}/100, placing them in the {quadrant.value} quadrant. "
                f"They have generated {engagement_count} engagement event(s) on {journey}-stage content, "
                f"signaling active evaluation intent."
                + (f" As a {lead_bg_role} in the {product} buying committee, their engagement is strategically significant." if lead_bg_role else "")
                + f" Data quality, fit, and intent signals are all above threshold — this lead is ready for direct sales engagement."
            )
        elif motion == "nurture":
            lead_narrative = (
                f"{full_name}, a {role_label} at {company}, has a score of {approval_score}/100. "
                f"They have engaged {engagement_count} time(s) with {journey}-stage content, "
                f"showing {'moderate' if engagement_count >= 2 else 'early'} buying intent."
                + (f" Their role as {lead_bg_role} in the {product} committee makes them worth nurturing." if lead_bg_role else "")
                + f" Continue personalized outreach to deepen the relationship before advancing to sales."
            )
        else:
            lead_narrative = (
                f"{full_name}, a {role_label} at {company}, scored {approval_score}/100. "
                f"Engagement signals are {'limited' if engagement_count == 0 else 'insufficient'} "
                f"({engagement_count} event(s)) and fit or data quality flags are present. "
                f"Hold delivery until stronger signals emerge or data quality is enriched."
            )

        # --- Account narrative ---
        persona_count = buying_group.unique_persona_count
        function_str = ", ".join(buying_group.function_coverage) if buying_group.function_coverage else "no functions yet"
        client_rate = lead.account_signals.client_acceptance_rate_6m
        client_rate_str = f"{int(client_rate * 100)}%" if client_rate is not None else "unknown"

        if motion == "accelerate":
            account_narrative = (
                f"{company} has {persona_count} approved persona(s) engaged across the following functions: {function_str}. "
                f"The account has reached {journey}-stage content, indicating the evaluation is well underway. "
                f"The client's historical acceptance rate for this account is {client_rate_str}, reinforcing confidence in delivery. "
                f"BDR trigger conditions are met — the account is ready for coordinated outreach."
            )
        elif motion == "nurture":
            account_narrative = (
                f"{company} currently shows {persona_count} engaged persona(s) in {function_str}. "
                f"The account has progressed to {journey}-stage content but the buying group is only {completeness}% complete. "
                f"Historical client acceptance for this account is {client_rate_str}. "
                f"Targeted nurture across the missing roles will strengthen the account's conversion potential."
            )
        else:
            account_narrative = (
                f"{company} has limited buying group activity — {persona_count} persona(s) engaged in {function_str}. "
                f"The account is at {journey} stage with only {completeness}% buying group completeness. "
                f"Client acceptance rate of {client_rate_str} provides some baseline confidence, "
                f"but the account needs more engagement before a BDR investment is warranted."
            )

        # --- Buying group narrative ---
        role_coverage_str = ", ".join(
            f"{role}: {pct}%" for role, pct in buying_group.role_coverage.items()
        ) if buying_group.role_coverage else "no structured coverage yet"

        if motion == "accelerate":
            bg_narrative = (
                f"{bg_verified_note} "
                f"The buying group for {product} at {company} is {completeness}% complete, "
                f"with decision-maker coverage at {dm_pct}%. "
                f"Role coverage: {role_coverage_str}. "
                + (f"Missing: {missing_summary}. " if buying_group.missing_personas else "All required personas are represented. ")
                + f"The combination of {covered_summary} engagement creates a strong commercial signal. "
                f"Engage now while the committee is active."
            )
        elif motion == "nurture":
            missing_dm_str = f"Critical gap: decision-maker roles still missing ({', '.join(missing_dm[:2])}). " if missing_dm else ""
            bg_narrative = (
                f"{bg_verified_note} "
                f"The {product} buying group at {company} is {completeness}% complete. "
                f"Decision-maker coverage stands at {dm_pct}%. "
                f"Role coverage: {role_coverage_str}. "
                f"{missing_dm_str}"
                f"Prioritize outreach to {missing_summary} to advance committee completeness "
                f"and unlock the BDR trigger."
            )
        else:
            bg_narrative = (
                f"{bg_verified_note} "
                f"The {product} buying group at {company} is only {completeness}% complete. "
                f"Decision-maker coverage is {dm_pct}% — below the threshold needed for a confident handoff. "
                f"Missing personas: {missing_summary}. "
                f"Until key roles — especially decision-makers — engage, the account is not ready for BDR activation."
            )

        # --- Recommended action ---
        if motion == "accelerate":
            recommended_action = (
                f"Route {full_name} to BDR immediately. "
                + (f"Schedule discovery with focus on {product}. " if product != "this product category" else "")
                + (f"Coordinate outreach to fill remaining roles: {', '.join(missing_dm[:2] or missing_other[:2])}." if buying_group.missing_personas else "The buying committee is well covered — move to opportunity creation.")
            )
        elif motion == "nurture":
            recommended_action = (
                f"Enroll {full_name} in a targeted {journey}-stage nurture sequence. "
                + (f"Prioritize activating {', '.join(missing_dm[:2])} at {company} to hit decision-maker coverage." if missing_dm else f"Focus on engaging {missing_summary} to complete the buying committee.")
            )
        else:
            recommended_action = (
                f"Hold delivery for {full_name}. "
                f"Enrich contact data and target {missing_dm[0] if missing_dm else 'a decision-maker'} at {company} first "
                f"to establish a foundation for the {product} buying committee."
            )

        return SellingStory(
            motion=motion,
            confidence=confidence,
            lead_narrative=lead_narrative,
            account_narrative=account_narrative,
            buying_group_narrative=bg_narrative,
            recommended_action=recommended_action,
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

            # Extract per-lead SHAP contributions from the LightGBM booster.
            # pred_contrib=True returns shape (n_samples, n_features + 1);
            # the last column is the bias term — we drop it.
            booster = getattr(model, "booster_", None)
            if booster is not None:
                try:
                    shap_matrix = booster.predict(vector.values, pred_contrib=True)
                    contributions = {
                        col: float(shap_matrix[0][i])
                        for i, col in enumerate(columns)
                    }
                except Exception:
                    # Fallback: use gain-based feature importances from metadata
                    importances = metadata.get("feature_importances", {})
                    contributions = {
                        col: float(importances.get(col, features.get(col, 0.0)))
                        for col in columns
                    }
            else:
                # Non-LightGBM promoted model: use raw feature values as before
                contributions = {col: features.get(col, 0.0) for col in columns}

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
        """Translate model SHAP contributions into signed plain-English reasons.

        When the promoted LightGBM model is active, contributions are SHAP values:
        - Positive SHAP → feature pushed toward approval (driver message)
        - Negative SHAP → feature pushed toward rejection (flag message)
        Both are ranked by absolute magnitude so the most influential signal
        appears first regardless of direction.

        When the heuristic baseline is active, contributions are weighted
        feature scores (always positive), so all messages use the driver tone.
        """
        # --- Positive (driver) messages ---
        positive_messages: dict[str, str] = {
            "fit_score": f"Title and firmographic fit ({title.seniority} {title.job_function}) align strongly with the campaign ICP.",
            "intent_score": "Engagement depth and content stage signal active evaluation intent.",
            "partner_signal_score": "The partner's recent approval history is boosting delivery confidence.",
            "client_history_score": "This client's recent acceptance rate supports a likely approval.",
            "campaign_history_score": "Campaign-level approval history is above threshold.",
            "data_quality_score": "Contact and company data are complete and credible.",
            "icp_match_score": "Industry, geography, and role all match the inferred ICP profile.",
            "buying_group_score": (
                "Multiple approved personas are active — buying-group signal is strong."
                if buying_group.bdr_trigger
                else "Buying-group engagement is developing and contributing positively."
            ),
            "authority_score": f"Title seniority ({title.seniority}) carries meaningful decision authority.",
            "email_engagement_score": "Email engagement rate is above expectations for this stage.",
            "recency_score": "Recent engagement indicates the lead is actively in-market now.",
            "late_stage_signal": "Content engagement matches a late-stage evaluation pattern.",
            "second_touch_signal": "A second-touch email response signals sustained interest.",
            "unique_persona_count": "Multiple job functions from this account have engaged.",
        }
        # --- Negative (flag) messages — same features, opposite tone ---
        negative_messages: dict[str, str] = {
            "fit_score": f"Title or firmographic signals ({title.seniority} {title.job_function}) do not align well with the campaign ICP.",
            "intent_score": "Engagement is thin or misaligned with the asset stage — intent is unclear.",
            "partner_signal_score": "This partner's recent approval history is below the campaign baseline.",
            "client_history_score": "This client has a lower-than-average acceptance rate for similar leads.",
            "campaign_history_score": "Campaign-level approval history is below threshold — elevated risk.",
            "data_quality_score": "Data quality issues (missing title, generic domain, or incomplete firmographics) are reducing confidence.",
            "icp_match_score": "Industry, geography, or role mismatch against the inferred ICP is reducing the score.",
            "buying_group_score": "Buying-group coverage is incomplete — the account has not reached BDR readiness.",
            "authority_score": f"Title seniority ({title.seniority}) may be too junior to be a decision-maker for this campaign.",
            "email_engagement_score": "Email engagement is below expectations for this asset stage.",
            "recency_score": "Most recent engagement was too long ago — recency penalty applied.",
            "late_stage_signal": "Content engagement is not at the stage expected for a BOFU delivery.",
            "second_touch_signal": "No second-touch engagement detected — sustained interest is unconfirmed.",
            "unique_persona_count": "Only one job function from this account has engaged — thin account signal.",
        }

        ranked = sorted(
            (
                (key, float(value))
                for key, value in contributions.items()
                if key in positive_messages
            ),
            key=lambda item: abs(item[1]),
            reverse=True,
        )

        reasons: list[TopReason] = []
        for key, shap_value in ranked[:3]:
            is_positive = shap_value >= 0
            message = positive_messages[key] if is_positive else negative_messages[key]
            reasons.append(TopReason(feature=key, impact=round(shap_value, 4), message=message))

        # Pad to 3 if model returned fewer covered features
        if len(reasons) < 3:
            reasons.append(
                TopReason(
                    feature="buying_group_score",
                    impact=round(float(contributions.get("buying_group_score", features["buying_group_score"])), 4),
                    message=(
                        "A BDR trigger is active — multiple approved personas are engaging."
                        if buying_group.bdr_trigger
                        else "Only one persona is active — account-level buying signal is still forming."
                    ),
                )
            )
        return reasons[:3]

    def _build_lead_analysis(
        self,
        lead: LeadRecord,
        title: NormalisedTitle,
        asset,
        target_profile,
        buying_group: BuyingGroupSummary,
        features: dict[str, float],
    ) -> LeadAnalysis:
        """Build per-signal explanations with sub-component drivers and penalty flags."""
        # --- Fit ---
        industry_match = self._match_value(lead.company.industry, target_profile.industries)
        geography_match = self._match_value(lead.company.geography, target_profile.geographies)
        size_match = self._match_value(lead.company.company_size, target_profile.company_sizes)
        function_match = self._match_value(title.job_function, target_profile.job_functions)
        seniority_match = self._match_value(title.seniority, target_profile.seniorities)
        authority = title.authority_score

        fit_drivers, fit_flags = [], []
        fit_drivers.append(
            f"Title '{lead.contact.job_title}' → {title.seniority} {title.job_function} "
            f"(authority {int(authority)}/100, contributes {int(authority * 0.25)} pts)"
        )
        if industry_match:
            fit_drivers.append(f"Industry '{lead.company.industry}' matches target")
        elif target_profile.industries:
            fit_flags.append(
                f"Industry '{lead.company.industry}' does not match targets {target_profile.industries}"
            )
        else:
            fit_flags.append("No industry targets defined — industry match defaulted to 60%")

        if geography_match:
            fit_drivers.append(f"Geography '{lead.company.geography}' matches target")
        elif target_profile.geographies:
            fit_flags.append(
                f"Geography '{lead.company.geography}' does not match targets {target_profile.geographies}"
            )
        else:
            fit_flags.append("No geography targets defined — geo match defaulted to 60%")

        if size_match:
            fit_drivers.append(f"Company size '{lead.company.company_size}' matches target")
        elif target_profile.company_sizes:
            fit_flags.append(
                f"Company size '{lead.company.company_size}' not in targets {target_profile.company_sizes}"
            )
        else:
            fit_flags.append("No company size targets — size match defaulted to 60%")

        if function_match:
            fit_drivers.append(f"Job function '{title.job_function}' matches target functions")
        elif target_profile.job_functions:
            fit_flags.append(
                f"Job function '{title.job_function}' not in targets {target_profile.job_functions}"
            )

        if seniority_match:
            fit_drivers.append(f"Seniority '{title.seniority}' matches target seniorities")
        elif target_profile.seniorities:
            fit_flags.append(
                f"Seniority '{title.seniority}' not in targets {target_profile.seniorities}"
            )

        fit_detail = SignalDetail(score=int(round(features["fit_score"])), drivers=fit_drivers, flags=fit_flags)

        # --- ICP Match ---
        icp_drivers, icp_flags = [], []
        dims = [
            ("Industry", industry_match, lead.company.industry, target_profile.industries),
            ("Geography", geography_match, lead.company.geography, target_profile.geographies),
        ]
        func_seniority_match = max(function_match, seniority_match)
        for label, matched, actual, targets in dims:
            if matched:
                icp_drivers.append(f"{label}: '{actual}' matched (contributes 33pts to ICP)")
            elif targets:
                icp_flags.append(f"{label}: '{actual}' did not match targets {targets} (0 pts)")
            else:
                icp_flags.append(f"{label}: no targets defined (defaulted to 60%)")
        if func_seniority_match:
            matched_dim = "function" if function_match >= seniority_match else "seniority"
            icp_drivers.append(
                f"Role dimension: '{title.job_function}' function / '{title.seniority}' seniority matched on {matched_dim}"
            )
        else:
            if target_profile.job_functions or target_profile.seniorities:
                icp_flags.append(
                    f"Role dimension: neither function '{title.job_function}' nor seniority '{title.seniority}' matched targets"
                )

        icp_detail = SignalDetail(score=int(round(features["icp_match_score"])), drivers=icp_drivers, flags=icp_flags)

        # --- Intent ---
        engagement_metrics = self._calculate_engagement_metrics(lead.engagement_events, asset.stage_weight)
        intent_drivers, intent_flags = [], []
        event_types = [e.event_type for e in lead.engagement_events]
        event_counts: dict[str, int] = {}
        second_touch_count = sum(1 for e in lead.engagement_events if e.email_number == 2)
        for et in event_types:
            event_counts[et] = event_counts.get(et, 0) + 1

        if event_counts:
            summary = ", ".join(f"{count}x {etype}" for etype, count in event_counts.items())
            intent_drivers.append(f"Engagement events: {summary}")
        else:
            intent_flags.append("No engagement events recorded — engagement score is 0")

        if second_touch_count:
            intent_drivers.append(
                f"{second_touch_count} email #2 event(s) detected — 1.5× multiplier applied"
            )

        intent_drivers.append(
            f"Asset stage: {asset.stage.value} (stage weight {asset.stage_weight:.2f}) → "
            f"email_engagement={int(engagement_metrics['email_engagement_score'])}, "
            f"late_stage_signal={int(engagement_metrics['late_stage_signal'])}"
        )
        intent_drivers.append(
            f"Buying group contributed {int(buying_group.buying_group_score * 0.20)} pts "
            f"(buying_group_score={buying_group.buying_group_score})"
        )

        recency = engagement_metrics["recency_score"]
        if recency < 40:
            intent_flags.append(
                f"Low recency score ({int(recency)}/100) — most recent engagement was >21 days ago"
            )
        else:
            intent_drivers.append(f"Recency score: {int(recency)}/100")

        intent_detail = SignalDetail(score=int(round(features["intent_score"])), drivers=intent_drivers, flags=intent_flags)

        # --- Data Quality ---
        dq_drivers, dq_flags = [], []
        domain = str(lead.contact.email).split("@")[-1].lower()
        generic_domains = set(self.config.get("generic_domains", []))
        if domain in generic_domains:
            dq_flags.append(f"Generic email domain '{domain}' detected (-20 pts)")
        else:
            dq_drivers.append(f"Business email domain '{domain}' ✓")

        if lead.contact.job_title:
            dq_drivers.append(f"Job title present: '{lead.contact.job_title}' ✓")
        else:
            dq_flags.append("Missing job title (-15 pts)")

        if title.job_function != "unknown":
            dq_drivers.append(f"Job function resolved: '{title.job_function}' ✓")
        else:
            dq_flags.append(f"Job function could not be resolved from title (-12 pts)")

        if lead.company.company_size:
            dq_drivers.append(f"Company size provided: '{lead.company.company_size}' ✓")
        else:
            dq_flags.append("Missing company size (-10 pts)")

        if lead.company.geography:
            dq_drivers.append(f"Geography provided: '{lead.company.geography}' ✓")
        else:
            dq_flags.append("Missing geography (-8 pts)")

        dq_detail = SignalDetail(score=int(round(features["data_quality_score"])), drivers=dq_drivers, flags=dq_flags)

        # --- Partner Signal ---
        ps_drivers, ps_flags = [], []
        rates = {
            "overall_6m": lead.partner_signals.approval_rate_6m,
            "client_6m": lead.partner_signals.approval_rate_client_6m,
            "vertical_6m": lead.partner_signals.approval_rate_vertical_6m,
        }
        available = [(label, rate) for label, rate in rates.items() if rate is not None]
        if available:
            for label, rate in available:
                ps_drivers.append(f"Partner approval rate ({label}): {int(rate * 100)}%")
            avg = sum(r for _, r in available) / len(available)
            ps_drivers.append(f"Average across {len(available)} rate(s): {int(avg * 100)}%")
        else:
            ps_flags.append("No partner approval rates available — defaulted to 50 (neutral)")

        if lead.partner_signals.partner_id:
            ps_drivers.append(f"Partner ID: {lead.partner_signals.partner_id}")

        ps_detail = SignalDetail(score=int(round(features["partner_signal_score"])), drivers=ps_drivers, flags=ps_flags)

        # --- Client History ---
        ch_drivers, ch_flags = [], []
        rate = lead.account_signals.client_acceptance_rate_6m
        if rate is not None:
            ch_drivers.append(f"Client acceptance rate (6m): {int(rate * 100)}%")
            if rate >= 0.7:
                ch_drivers.append("Strong client acceptance history")
            elif rate < 0.4:
                ch_flags.append("Low client acceptance rate — elevated rejection risk")
        else:
            ch_flags.append("No client acceptance history — defaulted to 50% (neutral)")

        if lead.account_signals.account_id:
            ch_drivers.append(f"Account ID: {lead.account_signals.account_id}")

        ch_detail = SignalDetail(score=int(round(features["client_history_score"])), drivers=ch_drivers, flags=ch_flags)

        # --- Campaign History ---
        cah_drivers, cah_flags = [], []
        camp_rate = lead.campaign.history_approval_rate
        if camp_rate is not None:
            cah_drivers.append(f"Campaign approval rate (historical): {int(camp_rate * 100)}%")
            if camp_rate >= 0.65:
                cah_drivers.append("Above-average campaign approval history")
            elif camp_rate < 0.40:
                cah_flags.append("Below-average campaign approval rate — lower confidence in delivery")
        else:
            cah_flags.append("No campaign approval history — defaulted to 50% (neutral)")

        cah_detail = SignalDetail(
            score=int(round(features["campaign_history_score"])),
            drivers=cah_drivers,
            flags=cah_flags,
        )

        return LeadAnalysis(
            fit=fit_detail,
            intent=intent_detail,
            icp_match=icp_detail,
            data_quality=dq_detail,
            partner_signal=ps_detail,
            client_history=ch_detail,
            campaign_history=cah_detail,
        )

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
