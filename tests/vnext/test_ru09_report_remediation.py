from __future__ import annotations

import json

import pytest

from bdb_audit.coordinator.operations import AuditOperationApi
from bdb_audit.core.errors import ValidationError
from bdb_audit.remediation.models import RemediationPlan, RepairUnit
from bdb_audit.remediation.planner import RemediationPlanner, validate_remediation_plan
from bdb_audit.report.builder import ReportBuilder
from bdb_audit.report.bundle import export_report_bundle, verify_report_bundle
from bdb_audit.report.models import ReportSnapshot


def _snapshot() -> ReportSnapshot:
    ref = {
        "kind": "finding_claim_revision",
        "revision_digest": "a" * 64,
        "digest_profile": "BDB-OBJECT-DIGEST-1",
        "schema_revision_ref": "BDB_SCHEMA_REGISTRY::finding_claim_revision/1",
        "ref_class": "CONTENT_OR_PRIOR",
    }
    return ReportSnapshot(
        campaign_id="campaign_test",
        history_cut={"variant": "ACCEPTED_HISTORY_CUT", "accepted_head_seq": 7, "accepted_head_hash": "b" * 64},
        source_identity={"git_commit_object_id": "c" * 40},
        report_status="PARTIAL_BOUNDED",
        termination_state="OPEN",
        campaign_completed=False,
        findings=({
            "finding_ref": ref,
            "claim_id": "finding_claim_revision_test",
            "statement": "Accepted claim text",
            "lifecycle_status": "CONFIRMED_CURRENT",
            "scope_refs": [],
            "evidence_qualification_refs": [],
            "axes": {},
        },),
        unknowns=({"type": "CAMPAIGN_NOT_CONCLUDED", "termination_state": "OPEN"},),
    )


def test_report_builder_on_genesis_is_bounded_not_false_pass(tmp_path):
    db = tmp_path / "campaign.sqlite"
    AuditOperationApi().create_campaign(db, seed="ru09-report")
    report = ReportBuilder.from_path(db).build().as_dict()
    assert report["report_status"] == "PARTIAL_BOUNDED"
    assert report["campaign_completed"] is False
    assert any(item["type"] == "CAMPAIGN_NOT_CONCLUDED" for item in report["unknowns"])
    assert report["findings"] == []
    assert report["coverage"] == []


def test_remediation_plan_is_proposal_and_traceable():
    plan = RemediationPlanner(_snapshot()).build()
    body = plan.as_dict()
    assert body["status"] == "PROPOSED"
    assert len(body["repair_units"]) == 1
    unit = body["repair_units"][0]
    assert unit["finding_ref"]["revision_digest"] == "a" * 64
    assert unit["statement"] == "Accepted claim text"
    assert unit["priority"] == "UNPRIORITIZED"
    assert validate_remediation_plan(plan)["status"] == "PASS"


def test_unadjudicated_finding_is_not_promoted_to_repair_unit():
    body = _snapshot().as_dict()
    body["findings"][0]["lifecycle_status"] = "UNADJUDICATED"
    plan = RemediationPlanner(body).build().as_dict()
    assert plan["repair_units"] == []
    assert plan["unresolved_inputs"][0]["reason"] == "UNADJUDICATED"


def test_remediation_cycle_rejected():
    ref = _snapshot().findings[0]["finding_ref"]
    p = RemediationPlan(
        campaign_id="c",
        history_cut={},
        repair_units=(
            RepairUnit("u1", ref, "one", dependency_unit_ids=("u2",)),
            RepairUnit("u2", ref, "two", dependency_unit_ids=("u1",)),
        ),
    )
    with pytest.raises(ValidationError) as exc:
        validate_remediation_plan(p)
    assert exc.value.code == "REMEDIATION_CYCLE"


def test_report_bundle_deterministic_and_tamper_evident(tmp_path):
    snapshot = _snapshot()
    plan = RemediationPlanner(snapshot).build().as_dict()
    first = tmp_path / "first"
    second = tmp_path / "second"
    m1 = export_report_bundle(snapshot, plan, first)
    m2 = export_report_bundle(snapshot, plan, second)
    assert m1["manifest_sha256"] == m2["manifest_sha256"]
    assert verify_report_bundle(first)["status"] == "PASS"
    assert (first / "FEATURE_STATUS_MATRIX.json").read_text(encoding="utf-8").find("NOT_ASSESSED") >= 0

    report = json.loads((first / "REPORT.json").read_text(encoding="utf-8"))
    report["report_status"] = "FINAL"
    (first / "REPORT.json").write_text(json.dumps(report), encoding="utf-8")
    with pytest.raises(ValidationError) as exc:
        verify_report_bundle(first)
    assert exc.value.code == "REPORT_BUNDLE_TAMPERED"
