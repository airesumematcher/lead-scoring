"""Persistence helpers for PRD-aligned score audit logs."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from lead_scoring.database.connection import get_session
from lead_scoring.database.models import Account, DealOutcome, ScoreAuditRecord

from .classifiers import TitleNormalizer
from .config import load_platform_config
from .contracts import (
    AccountScoreResult,
    BuyingGroupSummary,
    DealOutcomeLabel,
    FirmographicTrajectory,
    LeadRecord,
    LeadScoreResult,
    PersonaSnapshot,
    PredictedOutcome,
    ThirdPartyIntentSignal,
)


class AuditRepository:
    """Store and retrieve PRD score audit records."""

    def __init__(self, session: Session | None = None):
        self._owns_session = session is None
        self.session = session or get_session()

    def close(self) -> None:
        if self._owns_session:
            self.session.close()

    def save_score(
        self,
        lead: LeadRecord,
        result: LeadScoreResult,
        features: dict,
    ) -> int:
        """Persist a scored lead with the exact feature payload used."""
        record = ScoreAuditRecord(
            lead_id=lead.lead_id,
            campaign_id=lead.campaign.campaign_id,
            client_id=lead.campaign.client_id,
            account_domain=lead.company.domain.lower(),
            predicted_outcome=result.predicted_outcome.value,
            delivery_decision=result.delivery_decision.value,
            approval_score=result.approval_score,
            quadrant=result.quadrant.value,
            campaign_mode=result.campaign_mode.value,
            model_version=result.model_version,
            reasons_json=_dump_json([reason.model_dump() for reason in result.top_reasons]),
            features_json=_dump_json(features),
            request_json=_dump_json(lead.model_dump(mode="json")),
            response_json=_dump_json(result.model_dump(mode="json")),
        )
        self.session.add(record)
        self.session.commit()
        self.session.refresh(record)
        return int(record.id)

    def label_outcome(
        self,
        lead_id: str,
        campaign_id: str,
        outcome: PredictedOutcome,
        notes: str | None = None,
    ) -> bool:
        """Attach an actual client outcome to the most recent audit row."""
        record = (
            self.session.query(ScoreAuditRecord)
            .filter(
                ScoreAuditRecord.lead_id == lead_id,
                ScoreAuditRecord.campaign_id == campaign_id,
            )
            .order_by(ScoreAuditRecord.created_at.desc())
            .first()
        )
        if record is None:
            return False
        record.actual_outcome = outcome.value
        record.outcome_notes = notes
        self.session.commit()
        return True

    def get_recent_personas(
        self,
        account_domain: str,
        client_id: str | None = None,
        window_days: int = 90,
        platform_wide: bool = False,
    ) -> list[PersonaSnapshot]:
        """Load recent personas for an account from persisted audits.

        Args:
            platform_wide: When True, ignores client_id and aggregates personas
                across all clients/campaigns for this domain. This gives a
                truer picture of buying-group maturity than per-client isolation.
        """
        cutoff = datetime.now(UTC) - timedelta(days=window_days)
        query = self.session.query(ScoreAuditRecord).filter(
            ScoreAuditRecord.account_domain == account_domain.lower(),
            ScoreAuditRecord.created_at >= cutoff,
        )
        if client_id and not platform_wide:
            query = query.filter(ScoreAuditRecord.client_id == client_id)

        try:
            records = query.order_by(ScoreAuditRecord.created_at.desc()).all()
        except OperationalError:
            return []
        normalizer = TitleNormalizer(load_platform_config())
        personas: list[PersonaSnapshot] = []
        for record in records:
            payload = _load_json(record.request_json)
            if not payload:
                continue
            contact = payload.get("contact", {})
            title = normalizer.normalise(contact.get("job_title"))
            personas.append(
                PersonaSnapshot(
                    lead_id=record.lead_id,
                    email=contact.get("email"),
                    full_name=f"{contact.get('first_name', '')} {contact.get('last_name', '')}".strip() or None,
                    job_title=contact.get("job_title"),
                    job_function=title.job_function,
                    seniority=title.seniority,
                    status=record.actual_outcome or record.predicted_outcome,
                    asset_stage=record.campaign_mode,
                    occurred_at=record.created_at,
                )
            )
        return personas

    def upsert_account(self, result: AccountScoreResult) -> None:
        """Persist or update the account-level score snapshot."""
        record = (
            self.session.query(Account)
            .filter(Account.domain == result.domain.lower())
            .first()
        )
        firmographic_json: str | None = None
        intent_json: str | None = None

        if record is None:
            record = Account(domain=result.domain.lower())
            self.session.add(record)

        record.account_score = float(result.account_score)
        record.intent_score = float(result.intent_score)
        record.firmographic_score = float(result.firmographic_score)
        record.buying_group_maturity = result.buying_group_maturity
        record.last_enriched_at = result.scored_at
        if firmographic_json is not None:
            record.firmographic_snapshot = firmographic_json
        if intent_json is not None:
            record.intent_signals_snapshot = intent_json
        self.session.commit()

    def get_account(self, domain: str) -> Account | None:
        """Retrieve a persisted account record by domain."""
        try:
            return (
                self.session.query(Account)
                .filter(Account.domain == domain.lower())
                .first()
            )
        except Exception:
            return None

    def save_deal_outcome(self, label: DealOutcomeLabel) -> int:
        """Persist a CRM deal outcome so retraining can use conversion instead of delivery."""
        record = DealOutcome(
            lead_id=label.lead_id,
            account_domain=label.account_domain.lower(),
            campaign_id=label.campaign_id,
            opportunity_id=label.opportunity_id,
            deal_stage=label.deal_stage,
            closed_at=label.closed_at,
            revenue_usd=label.revenue_usd,
            crm_source=label.crm_source,
        )
        self.session.add(record)
        self.session.commit()
        self.session.refresh(record)
        return int(record.id)

    def build_campaign_report_records(
        self,
        campaign_id: str,
    ) -> list[tuple[dict, BuyingGroupSummary]]:
        """Return stored request/response pairs for a campaign."""
        try:
            records = (
                self.session.query(ScoreAuditRecord)
                .filter(ScoreAuditRecord.campaign_id == campaign_id)
                .order_by(ScoreAuditRecord.created_at.desc())
                .all()
            )
        except OperationalError:
            return []
        output: list[tuple[dict, BuyingGroupSummary]] = []
        for record in records:
            request_payload = _load_json(record.request_json)
            response_payload = _load_json(record.response_json)
            if request_payload and response_payload:
                output.append((request_payload, BuyingGroupSummary.model_validate(response_payload["buying_group"])))
        return output


def _dump_json(payload: dict | list) -> str:
    return json.dumps(payload, default=str)


def _load_json(raw: str | None) -> dict:
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}
