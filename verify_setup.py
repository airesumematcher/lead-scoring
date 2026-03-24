#!/usr/bin/env python3
"""Verification script for the revised PRD-aligned platform."""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
import json
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))


def _set_test_database() -> str:
    tmpdir = tempfile.mkdtemp()
    db_path = Path(tmpdir) / "verify.db"
    os.environ["DATABASE_URL"] = f"sqlite:///{db_path}"
    return tmpdir


def check_imports() -> bool:
    print("📦 Checking revised platform imports...")
    try:
        from lead_scoring.platform import BuyingIntelligenceService, LeadRecord, load_platform_config
        from data.prd_sample_payloads import build_priority_lead

        config = load_platform_config()
        lead = build_priority_lead()
        assert isinstance(lead, LeadRecord)
        assert config
        assert BuyingIntelligenceService()
        print("  ✅ Revised platform imports OK")
        return True
    except Exception as exc:  # pragma: no cover - script diagnostics
        print(f"  ❌ Import failed: {exc}")
        import traceback

        traceback.print_exc()
        return False


def check_runtime_scoring() -> bool:
    print("\n🧠 Checking two-layer runtime scoring...")
    try:
        from data.prd_sample_payloads import build_priority_lead
        from lead_scoring.platform import BuyingIntelligenceService

        service = BuyingIntelligenceService()
        result = service.score_lead(build_priority_lead(), persist=False)
        assert result.approval_score >= 0
        assert len(result.top_reasons) == 3
        assert result.buying_group.unique_persona_count >= 1
        print(f"  ✅ Approval score: {result.approval_score}")
        print(f"  ✅ Quadrant: {result.quadrant.value}")
        print(f"  ✅ Buying group trigger: {result.buying_group.bdr_trigger}")
        return True
    except Exception as exc:  # pragma: no cover - script diagnostics
        print(f"  ❌ Runtime scoring failed: {exc}")
        import traceback

        traceback.print_exc()
        return False


def check_api_smoke() -> bool:
    print("\n🌐 Checking API smoke routes...")
    tempdir = _set_test_database()
    try:
        from fastapi.testclient import TestClient

        from data.prd_sample_payloads import build_priority_lead, build_supporting_it_lead
        from lead_scoring.api.app import app

        primary = build_priority_lead()
        secondary = build_supporting_it_lead()
        campaign_context = {
            "client_id": primary.campaign.client_id,
            "campaign_id": primary.campaign.campaign_id,
            "campaign_name": primary.campaign.campaign_name,
            "asset_name": primary.campaign.asset_name,
            "asset_type": primary.campaign.taxonomy.asset_type,
            "asset_stage_override": primary.campaign.taxonomy.asset_stage_override.value,
            "topic": primary.campaign.taxonomy.topic,
            "audience": primary.campaign.taxonomy.audience,
            "volume": primary.campaign.taxonomy.volume,
            "sequence": primary.campaign.taxonomy.sequence,
            "vertical_override": primary.campaign.taxonomy.vertical_override,
            "history_approval_rate": primary.campaign.history_approval_rate,
            "partner_id": primary.partner_signals.partner_id,
            "approval_rate_6m": primary.partner_signals.approval_rate_6m,
            "approval_rate_client_6m": primary.partner_signals.approval_rate_client_6m,
            "approval_rate_vertical_6m": primary.partner_signals.approval_rate_vertical_6m,
            "client_acceptance_rate_6m": primary.account_signals.client_acceptance_rate_6m,
            "brief_text": primary.campaign.brief_text,
        }
        portal_csv = "\n".join(
            [
                "Email Address,First Name,Last Name,Title,Company,Website,Vertical,Country",
                "nina.carter@northstarhealth.com,Nina,Carter,VP Clinical Operations,Northstar Health,northstarhealth.com,healthcare,United States",
            ]
        )

        with TestClient(app) as client:
            health = client.get("/health")
            score = client.post("/score", json={"lead": primary.model_dump(mode="json")})
            score_second = client.post("/score", json={"lead": secondary.model_dump(mode="json")})
            preview = client.post(
                "/buying-group/preview",
                json={"lead": secondary.model_dump(mode="json")},
            )
            report = client.get(f"/reports/campaign/{primary.campaign.campaign_id}")
            label = client.post(
                "/outcomes/label",
                json={
                    "lead_id": primary.lead_id,
                    "campaign_id": primary.campaign.campaign_id,
                    "outcome": "approved",
                    "notes": "Verified in QA",
                },
            )
            portal_import = client.post(
                "/portal/import-score",
                data={"campaign_context": json.dumps(campaign_context)},
                files={"file": ("leads.csv", portal_csv, "text/csv")},
            )

        assert health.status_code == 200
        assert score.status_code == 200
        assert score_second.status_code == 200
        assert preview.status_code == 200
        assert report.status_code == 200
        assert label.status_code == 200
        assert portal_import.status_code == 200
        assert report.json()["accounts_with_bdr_trigger"] >= 1
        print("  ✅ /health OK")
        print("  ✅ /score OK")
        print("  ✅ /buying-group/preview OK")
        print("  ✅ /reports/campaign/{campaign_id} OK")
        print("  ✅ /outcomes/label OK")
        print("  ✅ /portal/import-score OK")
        return True
    except Exception as exc:  # pragma: no cover - script diagnostics
        print(f"  ❌ API smoke check failed: {exc}")
        import traceback

        traceback.print_exc()
        return False
    finally:
        import shutil

        shutil.rmtree(tempdir, ignore_errors=True)


def check_retrain_pipeline() -> bool:
    print("\n♻️  Checking retraining workflow...")
    backup_dir = Path(tempfile.mkdtemp())
    temp_csv_dir = Path(tempfile.mkdtemp())
    try:
        from lead_scoring.platform import BuyingIntelligenceService
        from lead_scoring.platform.training import FEATURE_COLUMNS, MODEL_DIR

        MODEL_DIR.mkdir(parents=True, exist_ok=True)
        for artifact in MODEL_DIR.iterdir():
            if artifact.is_file():
                shutil.copy2(artifact, backup_dir / artifact.name)

        tmp_csv = temp_csv_dir / "verify_prd_training.csv"
        frame = pd.DataFrame(
            [
                {
                    "status": "approved" if idx % 2 == 0 else "rejected",
                    **{column: 20 + idx * 5 + pos for pos, column in enumerate(FEATURE_COLUMNS)},
                }
                for idx in range(20)
            ]
        )
        frame.loc[frame["status"] == "approved", "fit_score"] += 20
        frame.loc[frame["status"] == "approved", "partner_signal_score"] += 15
        frame.to_csv(tmp_csv, index=False)

        service = BuyingIntelligenceService()
        result = service.run_retrain(str(tmp_csv), force_promote=True)
        assert result.success is True
        assert result.model_promoted is True
        print("  ✅ Retraining pipeline OK")
        return True
    except Exception as exc:  # pragma: no cover - script diagnostics
        print(f"  ❌ Retraining check failed: {exc}")
        import traceback

        traceback.print_exc()
        return False
    finally:
        from lead_scoring.platform.training import MODEL_DIR

        for artifact in MODEL_DIR.iterdir():
            if artifact.is_file():
                artifact.unlink()
        for artifact in backup_dir.iterdir():
            shutil.copy2(artifact, MODEL_DIR / artifact.name)
        shutil.rmtree(backup_dir, ignore_errors=True)
        shutil.rmtree(temp_csv_dir, ignore_errors=True)


def main() -> int:
    print("=" * 80)
    print("ACE BUYING INTELLIGENCE PLATFORM - REVISED PRD VERIFICATION")
    print("=" * 80)

    checks = [
        check_imports,
        check_runtime_scoring,
        check_api_smoke,
        check_retrain_pipeline,
    ]
    results = [check() for check in checks]

    print("\n" + "=" * 80)
    if all(results):
        print("✅ ALL CHECKS PASSED - Revised platform is ready to operate")
        print("=" * 80)
        return 0
    print("❌ SOME CHECKS FAILED - Fix issues before proceeding")
    print("=" * 80)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
