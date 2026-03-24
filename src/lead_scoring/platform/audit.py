"""Persistence helpers for PRD-aligned score audit logs."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from lead_scoring.database.connection import get_session
from lead_scoring.database.models import ScoreAuditRecord

from .classifiers import TitleNormalizer
from .config import load_platform_config
from .contracts import BuyingGroupSummary, LeadRecord, LeadScoreResult, PersonaSnapshot, PredictedOutcome


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
    ) -> list[PersonaSnapshot]:
        """Load recent approved personas for an account from persisted audits."""
        cutoff = datetime.now(UTC) - timedelta(days=window_days)
        query = self.session.query(ScoreAuditRecord).filter(
            ScoreAuditRecord.account_domain == account_domain.lower(),
            ScoreAuditRecord.created_at >= cutoff,
        )
        if client_id:
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
