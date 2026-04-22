"""FastAPI application for the revised PRD-aligned buying intelligence platform."""

from __future__ import annotations

from contextlib import asynccontextmanager
import json
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from lead_scoring.database.connection import DatabaseManager, init_db
from lead_scoring.database.models import Feedback
from lead_scoring.platform.brief_parser import CampaignSpecParser
from lead_scoring.platform.engine import BuyingIntelligenceService
from lead_scoring.portal import import_leads_file

from .schemas import (
    AccountScoreRequest,
    AccountScoreResult,
    BatchScoreRequest,
    BatchScoreResult,
    BuyingGroupPreviewRequest,
    BuyingGroupSummary,
    CampaignReport,
    DealOutcomeLabel,
    DriftStatusResponse,
    FeedbackClearResponse,
    FeedbackHistoryResponse,
    FeedbackItem,
    FeedbackStatusResponse,
    FeedbackSubmitRequest,
    FeedbackSubmitResponse,
    HealthCheckResponse,
    LeadScoreResult,
    OperationStatus,
    OutcomeLabel,
    PortalImportResponse,
    PortalLeadSummary,
    RetrainRequest,
    RetrainResult,
    ScoreLeadRequest,
)


SERVICE = BuyingIntelligenceService()


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Initialize the database and runtime services."""
    init_db()
    print("✅ Revised ACE buying intelligence platform initializing...")
    yield
    print("✅ Revised ACE buying intelligence platform shutting down...")


app = FastAPI(
    title="ACE Buying Intelligence Platform",
    description=(
        "Two-layer scoring platform aligned to the March 2026 revised PRD: "
        "pre-delivery lead quality plus buying-group signal aggregation."
    ),
    version="2.0.0",
    docs_url="/docs",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from lead_scoring.api.ml_scoring_enhanced import router as ml_enhanced_router  # noqa: E402
app.include_router(ml_enhanced_router)


@app.get("/", include_in_schema=False)
async def home() -> FileResponse:
    """Serve the operator landing page."""
    html_path = Path(__file__).resolve().parents[3] / "index.html"
    if not html_path.exists():
        raise HTTPException(status_code=404, detail="Landing page not found")
    return FileResponse(html_path, media_type="text/html")


@app.get("/health", response_model=HealthCheckResponse, tags=["Operations"])
async def health_check() -> HealthCheckResponse:
    """Operational health check."""
    runtime_model = "promoted-model" if SERVICE._runtime_bundle is not None else "heuristic-baseline"
    return HealthCheckResponse(
        status="healthy",
        version="2.0.0",
        architecture="two-layer-buying-intelligence",
        runtime_model=runtime_model,
    )


@app.post("/score", response_model=LeadScoreResult, tags=["Lead Quality"])
async def score_lead(request: ScoreLeadRequest) -> LeadScoreResult:
    """Score a lead and persist the audit trail."""
    return SERVICE.score_lead(request.lead, persist=True)


@app.post("/score/batch", response_model=BatchScoreResult, tags=["Lead Quality"])
async def score_batch(request: BatchScoreRequest) -> BatchScoreResult:
    """Score a batch of leads."""
    return SERVICE.score_batch(request.leads, persist=True)


@app.post("/buying-group/preview", response_model=BuyingGroupSummary, tags=["Buying Group"])
async def preview_buying_group(request: BuyingGroupPreviewRequest) -> BuyingGroupSummary:
    """Preview the account-level buying group signal."""
    return SERVICE.get_buying_group(request.lead)


@app.get("/reports/campaign/{campaign_id}", response_model=CampaignReport, tags=["Buying Group"])
async def get_campaign_report(campaign_id: str) -> CampaignReport:
    """Return the persisted account-level campaign report."""
    return SERVICE.get_campaign_report(campaign_id)


@app.post("/outcomes/label", response_model=OperationStatus, tags=["Operations"])
async def label_outcome(request: OutcomeLabel) -> OperationStatus:
    """Attach the actual client decision to the latest scored lead."""
    updated = SERVICE.label_outcome(
        lead_id=request.lead_id,
        campaign_id=request.campaign_id,
        outcome=request.outcome,
        notes=request.notes,
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Score audit not found for the given lead and campaign")
    return OperationStatus(success=True, message="Outcome label stored for retraining")


@app.post("/accounts/score", response_model=AccountScoreResult, tags=["Account Intelligence"])
async def score_account(request: AccountScoreRequest) -> AccountScoreResult:
    """Score an account's readiness to buy from external intent and firmographic signals.

    This is the account-first flow: identify in-market accounts before generating leads,
    then use missing_personas to guide targeted outreach that fills buying group gaps.
    """
    return SERVICE.score_account(request)


@app.get("/accounts/{domain}/profile", response_model=AccountScoreResult | None, tags=["Account Intelligence"])
async def get_account_profile(domain: str) -> AccountScoreResult | None:
    """Return the most recently persisted account score for a domain.

    Returns 404 if the account has never been scored.
    """
    from lead_scoring.platform.audit import AuditRepository

    repository = AuditRepository()
    try:
        account = repository.get_account(domain)
    finally:
        repository.close()

    if account is None:
        raise HTTPException(status_code=404, detail=f"No account profile found for domain '{domain}'")

    return AccountScoreResult(
        domain=account.domain,
        account_score=int(account.account_score or 0),
        intent_score=int(account.intent_score or 0),
        firmographic_score=int(account.firmographic_score or 0),
        buying_group_maturity=account.buying_group_maturity or "early",
        persona_count_platform_wide=0,
        persona_count_client=0,
        function_coverage=[],
        in_market_signals=[],
        missing_personas=[],
        recommended_action="hold",
        scored_at=account.last_enriched_at or account.created_at,
    )


@app.post("/deals/outcome", response_model=OperationStatus, tags=["Account Intelligence"])
async def record_deal_outcome(label: DealOutcomeLabel) -> OperationStatus:
    """Record a CRM deal outcome (qualified, closed_won, closed_lost, etc.) for a lead.

    This closes the learning loop beyond simple lead approval — the model can
    eventually be retrained on actual deal conversion rather than delivery acceptance.
    """
    success = SERVICE.record_deal_outcome(label)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to record deal outcome")
    return OperationStatus(success=True, message=f"Deal outcome '{label.deal_stage}' recorded for lead {label.lead_id}")


@app.post("/operations/retrain", response_model=RetrainResult, tags=["Operations"])
async def run_retrain(request: RetrainRequest) -> RetrainResult:
    """Run the monthly retrain job against a PRD feature table."""
    result = SERVICE.run_retrain(request.dataset_path, force_promote=request.force_promote)
    if not result.success:
        raise HTTPException(status_code=400, detail=result.message)
    return result


_campaign_spec_parser = CampaignSpecParser()


@app.post("/portal/parse-spec", tags=["Portal"])
async def parse_campaign_spec(
    campaign_spec_file: UploadFile = File(...),
) -> dict:
    """Parse a campaign spec XLSX/CSV and return the extracted CampaignContext as JSON."""
    try:
        spec_bytes = await campaign_spec_file.read()
        parsed = _campaign_spec_parser.parse(spec_bytes, filename=campaign_spec_file.filename or "")
        return parsed.model_dump()
    except (ValueError, Exception) as exc:
        raise HTTPException(status_code=422, detail=f"Campaign spec error: {exc}") from exc


@app.post("/portal/import-score", response_model=PortalImportResponse, tags=["Portal"])
async def import_and_score_portal_file(
    file: UploadFile = File(...),
    campaign_context: str = Form(default=""),
    campaign_spec_file: UploadFile = File(default=None),
) -> PortalImportResponse:
    """Accept CSV/Excel portal uploads, interpret headers, score, and return the report.

    Campaign context can be provided as either:
    - campaign_spec_file: an XLSX spec sheet (takes precedence if both are supplied)
    - campaign_context: a JSON string (fallback when no XLSX spec is provided)
    """
    if campaign_spec_file is not None:
        try:
            spec_bytes = await campaign_spec_file.read()
            parsed_context = _campaign_spec_parser.parse(spec_bytes, filename=campaign_spec_file.filename or "")
            campaign_payload = parsed_context.model_dump()
        except (ValueError, Exception) as exc:
            raise HTTPException(status_code=422, detail=f"Campaign spec error: {exc}") from exc
    elif campaign_context:
        try:
            campaign_payload = json.loads(campaign_context)
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=400, detail=f"campaign_context must be valid JSON: {exc}") from exc
    else:
        raise HTTPException(
            status_code=400,
            detail="Provide either campaign_spec_file (XLSX) or campaign_context (JSON).",
        )

    try:
        artifacts = import_leads_file(
            filename=file.filename or "upload",
            content=await file.read(),
            campaign_context=campaign_payload,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    batch_result = SERVICE.score_batch(artifacts.leads, persist=True)
    campaign_id = campaign_payload.get("campaign_id")
    campaign_report = SERVICE.get_campaign_report(campaign_id)

    from .schemas import AccountSummary
    domain_results: dict[str, list] = {}
    for result in batch_result.results:
        domain = result.buying_group.account_domain
        domain_results.setdefault(domain, []).append(result)

    accounts = [
        AccountSummary(
            domain=domain,
            lead_count=len(results),
            account_score=results[0].account_score,
        )
        for domain, results in domain_results.items()
        if len(results) >= 2
    ]

    return PortalImportResponse(
        filename=file.filename or "upload",
        detected_format=artifacts.detected_format,
        total_rows=artifacts.total_rows,
        interpreted_headers=artifacts.interpreted_headers,
        warnings=artifacts.warnings,
        imported_leads=[PortalLeadSummary(**item) for item in artifacts.lead_summaries],
        batch_result=batch_result,
        campaign_report=campaign_report,
        accounts=accounts,
    )


@app.post("/feedback", response_model=FeedbackSubmitResponse, status_code=201, tags=["Feedback"])
async def submit_feedback(request: FeedbackSubmitRequest) -> FeedbackSubmitResponse:
    """Record an outcome label for a previously scored lead."""
    db = DatabaseManager()
    try:
        db.add_feedback(
            lead_id=request.lead_id,
            outcome=request.outcome,
            reason=request.reason,
            notes=request.notes,
            provided_score=request.original_score,
            submitted_by=request.sal_decision_maker,
        )
        count = len(db.get_feedback_for_lead(request.lead_id))
    finally:
        db.close()
    return FeedbackSubmitResponse(feedback_count_stored=count)


@app.get("/feedback/status", response_model=FeedbackStatusResponse, tags=["Feedback"])
async def feedback_status() -> FeedbackStatusResponse:
    """Return aggregate feedback counts across all leads."""
    db = DatabaseManager()
    try:
        all_feedback = db.get_all_feedback()
    finally:
        db.close()
    by_outcome: dict[str, int] = {}
    for fb in all_feedback:
        by_outcome[fb.outcome] = by_outcome.get(fb.outcome, 0) + 1
    return FeedbackStatusResponse(
        total_feedback_items=len(all_feedback),
        feedback_by_outcome=by_outcome,
    )


@app.get("/feedback/{lead_id}", response_model=FeedbackHistoryResponse, tags=["Feedback"])
async def get_feedback_history(lead_id: str) -> FeedbackHistoryResponse:
    """Return all feedback entries for a specific lead."""
    db = DatabaseManager()
    try:
        entries = db.get_feedback_for_lead(lead_id)
    finally:
        db.close()
    if not entries:
        raise HTTPException(status_code=404, detail=f"No feedback found for lead {lead_id}")
    return FeedbackHistoryResponse(
        lead_id=lead_id,
        feedback_count=len(entries),
        feedback_history=[
            FeedbackItem(
                outcome=fb.outcome,
                reason=fb.reason,
                notes=fb.notes,
                submitted_at=fb.submitted_at,
            )
            for fb in entries
        ],
    )


@app.post("/feedback/clear", response_model=FeedbackClearResponse, tags=["Feedback"])
async def clear_feedback() -> FeedbackClearResponse:
    """Delete all stored feedback (use before retraining on fresh data)."""
    db = DatabaseManager()
    try:
        removed = db.delete_all_feedback()
    finally:
        db.close()
    return FeedbackClearResponse(message=f"Cleared {removed} feedback items")


@app.get("/drift-status", response_model=DriftStatusResponse, tags=["Feedback"])
async def drift_status() -> DriftStatusResponse:
    """Return a simple model drift assessment based on accumulated feedback."""
    db = DatabaseManager()
    try:
        all_feedback = db.get_all_feedback()
    finally:
        db.close()
    total = len(all_feedback)
    rejected = sum(1 for fb in all_feedback if fb.outcome == "rejected")
    rejection_rate = rejected / total if total > 0 else 0.0
    if total == 0:
        recommendation = "Insufficient feedback to assess drift."
    elif rejection_rate >= 0.4:
        recommendation = "High rejection rate detected. Consider retraining the model."
    elif rejection_rate >= 0.2:
        recommendation = "Moderate rejection rate. Monitor closely before next scheduled retrain."
    else:
        recommendation = "Feedback signals look healthy. No immediate retraining needed."
    return DriftStatusResponse(
        feedback_count=total,
        metrics={
            "rejection_rate": round(rejection_rate, 3),
            "rejected_count": rejected,
            "recommendation": recommendation,
        },
    )
