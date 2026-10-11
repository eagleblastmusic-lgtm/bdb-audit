"""Read-only manual transport controls are distinct from NF02 acceptance."""
from copy import deepcopy
import json
from pathlib import Path
import zipfile

import pytest

from bdb_audit.cli import run_cli
from bdb_audit.core.errors import ValidationError
from bdb_audit.history.store import TransactionalHistoryStore
from bdb_audit.history.store import _get_or_create_ingestion_authority_key
from bdb_audit.workflow.package_resume import load_e1_batch
from bdb_audit.workflow.result_proposal import inspect_result_zip
from bdb_audit.workflow.inbox import E1ResultInbox
from bdb_audit.workflow.manual_stage import StageBatch, StageResultInbox
from tests.product.test_product_v1 import campaign as product_campaign, _bytes

campaign = product_campaign


def _result(path, created):
    job = created["packages"][0]
    with zipfile.ZipFile(job["package_zip_path"]) as archive:
        package = json.loads(archive.read("MANIFEST.json"))
    manifest = {
        "kind": "bdb_audit_lane_result", "version": "1",
        "campaign_id": created["campaign_id"], "stage_id": "E1", "lane_slot": job["lane_slot"],
        "source_commit_sha": created["source"]["exact_commit_sha"],
        "input_package_digest": job["package_digest"],
        "history_cut": created["assignment_input_history_cut"],
        "executor_profile": package["execution_mode"], "executor_model": package["model"],
        "assignment_ref": job["assignment_ref"], "attempt_ref": job["attempt_ref"],
        "findings": [{"finding_id": "MANUAL-1", "statement": "Untrusted test claim", "severity": "HIGH"}],
    }
    return manifest


def _write(path, manifest):
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("MANIFEST.json", json.dumps(manifest))
    return path


def test_manual_inspection_and_report_never_grant_acceptance(campaign, capsys):
    path, _, created = campaign
    result = _write(path.parent / "manual.zip", _result(path, created))
    before = _bytes(path.parent)
    assert run_cli(["product", "inspect-result", "--store", str(path), "--zip", str(result), "--json"]) == 0
    inspection = json.loads(capsys.readouterr().out)
    assert inspection["status"] == "INSPECTED_UNTRUSTED" and inspection["accepted"] is False
    assert inspection["external_ingestion"] == "BLOCKED"
    assert inspection["producer_authorization"] == "NOT_ESTABLISHED"
    assert inspection["byte_context_checks"] == "MATCH"
    assert inspection["isolation_enforcement"] == "NOT_ESTABLISHED"
    assert inspection["findings"][0]["statement"] == "Untrusted test claim"
    assert _bytes(path.parent) == before
    history = TransactionalHistoryStore(path)
    batch, _ = load_e1_batch(history, path.parent / "artifacts")
    inbox = E1ResultInbox(history, batch)
    assert inbox.inspect_zip(result)["status"] == "INSPECTED_UNTRUSTED"
    assert not batch.batch_ticket
    for kind in ("bdb_audit_lane_result", "lane_result_admission_evidence", "lane_completion", "stage_completion"):
        assert not history.accepted_records(kind, inspection["accepted_history_cut"])
    con = history._connect()
    try:
        assert con.execute("SELECT COUNT(*) FROM _store_private_authority").fetchone()[0] == 0
        assert con.execute("SELECT COUNT(*) FROM immutable_raw_artifacts").fetchone()[0] == 0
    finally:
        con.close()
    output = path.parent / "manual-report.md"
    assert run_cli(["product", "report", "--store", str(path), "--output", str(output), "--result-zip", str(result), "--json"]) == 0
    capsys.readouterr()
    report = output.read_text(encoding="utf-8")
    assert "INSPECTED_UNTRUSTED" in report and "**NOT_COMPLETED**" in report
    assert "Untrusted test claim" in report
    assert {k: v for k, v in _bytes(path.parent).items() if k != output.name} == before


@pytest.mark.parametrize("field,value,code", [
    ("assignment_ref", {}, "RESULT_CONTEXT_CLAIM_MISMATCH"),
    ("attempt_ref", {}, "RESULT_CONTEXT_CLAIM_MISMATCH"),
    ("lane_slot", "foreign-slot", "UNKNOWN_LANE"),
    ("campaign_id", "foreign-campaign", "RESULT_CONTEXT_CLAIM_MISMATCH"),
    ("source_commit_sha", "f" * 40, "RESULT_CONTEXT_CLAIM_MISMATCH"),
    ("input_package_digest", "f" * 64, "RESULT_CONTEXT_CLAIM_MISMATCH"),
    ("phase_id", "foreign-phase", "RESULT_CONTEXT_CLAIM_MISMATCH"),
    ("executor_model", "self-selected", "RESULT_CONTEXT_CLAIM_MISMATCH"),
    ("history_cut", {}, "STALE_CUT"),
    ("findings", "fabricated", "INVALID_FINDING_STRUCTURE"),
    ("admission_evidence_ref", {}, "UNAUTHORIZED_PRODUCER_AUTHORITY"),
])
def test_inspection_rejects_conflicting_claim_without_mutation(campaign, capsys, field, value, code):
    path, _, created = campaign
    manifest = deepcopy(_result(path, created))
    manifest[field] = value
    result = _write(path.parent / "hostile.zip", manifest)
    before = _bytes(path.parent)
    assert run_cli(["product", "inspect-result", "--store", str(path), "--zip", str(result), "--json"]) == 2
    assert json.loads(capsys.readouterr().err)["error"] == code
    assert _bytes(path.parent) == before


def test_inspection_checks_package_snapshot_even_after_batch_was_loaded(campaign):
    path, _, created = campaign
    history = TransactionalHistoryStore(path)
    batch, _ = load_e1_batch(history, path.parent / "artifacts")
    result = _write(path.parent / "manual.zip", _result(path, created))
    package = batch.get_job(created["packages"][0]["lane_slot"]).package_zip_path
    package.write_bytes(b"substituted after resume")
    before = _bytes(path.parent)
    with pytest.raises(ValidationError, match="ASSIGNED_PACKAGE_TAMPERED"):
        inspect_result_zip(history, batch, result)
    assert _bytes(path.parent) == before


def test_inspection_does_not_initialize_missing_campaign(tmp_path, capsys):
    path = tmp_path / "absent.sqlite"
    before = _bytes(tmp_path)
    assert run_cli(["product", "inspect-result", "--store", str(path), "--zip", str(tmp_path / "missing.zip"), "--json"]) == 2
    assert json.loads(capsys.readouterr().err)["error"] == "CAMPAIGN_NOT_FOUND"
    assert _bytes(tmp_path) == before


def test_old_key_reader_never_mints_authority(campaign):
    path, _, _ = campaign
    history = TransactionalHistoryStore(path)
    before = _bytes(path.parent)
    con = history._connect()
    try:
        with pytest.raises(ValidationError, match="UNAUTHORIZED_PRODUCER_AUTHORITY"):
            _get_or_create_ingestion_authority_key(con)
        assert con.execute("SELECT COUNT(*) FROM _store_private_authority").fetchone()[0] == 0
    finally:
        con.close()
    assert _bytes(path.parent) == before


def test_unsafe_zip_and_member_findings_use_read_only_shared_transform(campaign, capsys):
    path, _, created = campaign
    manifest = _result(path, created)
    findings = manifest.pop("findings")
    result = path.parent / "members.zip"
    with zipfile.ZipFile(result, "w") as archive:
        archive.writestr("MANIFEST.json", json.dumps(manifest))
        archive.writestr("FINDINGS.json", json.dumps(findings))
    history = TransactionalHistoryStore(path)
    batch, _ = load_e1_batch(history, path.parent / "artifacts")
    before = _bytes(path.parent)
    inspected = inspect_result_zip(history, batch, result)
    assert inspected["findings"] == findings and not inspected["accepted"]
    assert _bytes(path.parent) == before
    for name, members in (("unsafe.zip", {"../escape": "outside"}),
                          ("duplicate.zip", {"a/./file.txt": "one", "a/file.txt": "two"}),
                          ("strict-json.zip", {"MANIFEST.json": '{"kind":"one","kind":"two"}'})):
        hostile = path.parent / name
        with zipfile.ZipFile(hostile, "w") as archive:
            for member, data in members.items():
                archive.writestr(member, data)
        before = _bytes(path.parent)
        with pytest.raises(ValidationError):
            inspect_result_zip(history, batch, hostile)
        assert _bytes(path.parent) == before


def test_stage_inbox_inspection_rejects_without_acceptance(campaign):
    path, _, created = campaign
    history = TransactionalHistoryStore(path)
    batch = StageBatch(created["campaign_id"], "E2", "E2-BLIND", created["assignment_input_history_cut"], {}, {})
    inbox = StageResultInbox(history, batch)
    result = _write(path.parent / "unassigned-stage.zip", {"lane_slot": "E2-CONVERGENCE"})
    before = _bytes(path.parent)
    with pytest.raises(ValidationError, match="UNKNOWN_LANE"):
        inbox.inspect_zip(result)
    assert _bytes(path.parent) == before
