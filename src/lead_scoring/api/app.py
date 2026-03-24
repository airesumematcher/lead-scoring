"""FastAPI application for the revised PRD-aligned buying intelligence platform."""

from __future__ import annotations

from contextlib import asynccontextmanager
import json
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from lead_scoring.database.connection import init_db
from lead_scoring.platform.engine import BuyingIntelligenceService
from lead_scoring.portal import import_leads_file

from .schemas import (
    BatchScoreRequest,
    BatchScoreResult,
    BuyingGroupPreviewRequest,
    BuyingGroupSummary,
    CampaignReport,
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


@app.post("/operations/retrain", response_model=RetrainResult, tags=["Operations"])
async def run_retrain(request: RetrainRequest) -> RetrainResult:
    """Run the monthly retrain job against a PRD feature table."""
    result = SERVICE.run_retrain(request.dataset_path, force_promote=request.force_promote)
    if not result.success:
        raise HTTPException(status_code=400, detail=result.message)
    return result


@app.post("/portal/import-score", response_model=PortalImportResponse, tags=["Portal"])
async def import_and_score_portal_file(
    file: UploadFile = File(...),
    campaign_context: str = Form(...),
) -> PortalImportResponse:
    """Accept CSV/Excel portal uploads, interpret headers, score, and return the report."""
    try:
        campaign_payload = json.loads(campaign_context)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"campaign_context must be valid JSON: {exc}") from exc

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
    return PortalImportResponse(
        filename=file.filename or "upload",
        detected_format=artifacts.detected_format,
        total_rows=artifacts.total_rows,
        interpreted_headers=artifacts.interpreted_headers,
        warnings=artifacts.warnings,
        imported_leads=[PortalLeadSummary(**item) for item in artifacts.lead_summaries],
        batch_result=batch_result,
        campaign_report=campaign_report,
    )
