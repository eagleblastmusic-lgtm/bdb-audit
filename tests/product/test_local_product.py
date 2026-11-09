"""LOCAL production interfaces. Responses here are explicit TEST_FIXTURE inputs."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import os
import shutil
import sqlite3
import subprocess
import sys

import pytest

from bdb_audit.cli import run_cli
from bdb_audit.core.canonical_json import canonical_bytes, parse
from bdb_audit.core.errors import ValidationError
from bdb_audit.history.store import TransactionalHistoryStore
from bdb_audit.local_product.store import LocalStore, sha
from bdb_audit.local_product.workflow import LocalWorkflow
from bdb_audit.assurance.zip_safety import read_bytes
from bdb_audit.workflow.packaging import _deterministic_zip


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "repository"
    root.mkdir()
    (root / "app.py").write_text("def clamp(n):\n    return min(n, 10)  # known missing lower bound\n", encoding="utf-8")
    for args in (("init", "-q"), ("add", "app.py"),
                 ("-c", "user.name=LOCAL test", "-c", "user.email=local-test@example.invalid", "commit", "-qm", "known defect")):
        subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)
    return root


@pytest.fixture
def local(repo, tmp_path):
    return LocalWorkflow.start(tmp_path / "campaign", str(repo), "HEAD")


def response(local, task="E1-A", **updates):
    local.prepare()
    package = local.packages[task]
    archive = local.store.vault.read_bytes(package["raw"]["raw_digest"])
    body = parse(read_bytes(archive)["RESPONSE_TEMPLATE.json"])
    body.update(producer={"kind": "TEST_FIXTURE", "declared_name": "explicit fixture, not AI"}, completion="COMPLETE")
    body["outputs"] = {key: "Explicit fixture output for test of " + key for key in package["required_outputs"]}
    body.update(updates)
    return body


def imported(local, tmp_path, body, name="response.json"):
    path = tmp_path / name
    path.write_bytes(canonical_bytes(body))
    return local.import_result(path)["result_id"]


def test_import_validation_acceptance_resume(local, tmp_path):
    rid = imported(local, tmp_path, response(local))
    assert local.result_info(rid)["status"] == "IMPORTED_UNTRUSTED"
    assert local.validate(rid)["status"] == "VALIDATED_STRUCTURE"
    before = local.head
    with pytest.raises(ValidationError, match="LOCAL_MANUAL_CONFIRMATION_REQUIRED"):
        local.accept(rid, "user", confirm=False)
    assert local.head == before
    assert local.accept(rid, "user", confirm=True)["status"] == "USER_ACCEPTED_LOCAL"
    recovered = LocalWorkflow(local.store.root)
    assert recovered.head == local.head
    assert recovered.accepted == {"E1-A": rid}
    assert recovered.result_info(rid)["response"]["producer"]["kind"] == "TEST_FIXTURE"


@pytest.mark.parametrize("field,value", [("campaign_id", "foreign"), ("stage_id", "E2"),
                                         ("source_commit", "0" * 40), ("source_tree", "0" * 40),
                                         ("input_package_digest", "0" * 64), ("mode", "HIGH_ASSURANCE")])
def test_foreign_context_rejected_with_no_acceptance(local, tmp_path, field, value):
    body = response(local)
    body[field] = value
    rid = imported(local, tmp_path, body)
    assert local.validate(rid)["status"] == "REJECTED"
    before = local.head
    with pytest.raises(ValidationError):
        local.accept(rid, "user", confirm=True)
    assert local.head == before
    assert not local.accepted


@pytest.mark.parametrize("raw", [b"not JSON", b'{"a":1,"a":2}', b"[]", b"PKbadzip",
                                _deterministic_zip({"../evil.py": b"raise RuntimeError()"})],
                         ids=["invalid-json", "duplicate-key", "wrong-root", "broken-zip", "traversal"])
def test_unsafe_file_refusal_no_mutation(local, tmp_path, raw):
    before = local.store.path.read_bytes(), local.head, sorted(p.name for p in local.store.vault.meta_root.iterdir())
    file = tmp_path / "bad"
    file.write_bytes(raw)
    with pytest.raises(ValidationError):
        local.import_result(file)
    assert before == (local.store.path.read_bytes(), local.head, sorted(p.name for p in local.store.vault.meta_root.iterdir()))


def test_exact_attachment_hash_and_no_execution(local, tmp_path):
    body = response(local)
    body["evidence_files"] = [{"path": "payload.py", "sha256": "0" * 64, "byte_length": 30}]
    raw = _deterministic_zip({"LOCAL_RESULT.json": canonical_bytes(body), "payload.py": b"raise RuntimeError('never run')"})
    path = tmp_path / "reply.zip"
    path.write_bytes(raw)
    rid = local.import_result(path)["result_id"]
    assert "LOCAL_EVIDENCE_EXACT_BYTES_MISMATCH:payload.py" in local.validate(rid)["issues"]
    assert not (local.store.root / "payload.py").exists()


def test_duplicate_and_explicit_revision(local, tmp_path):
    body = response(local)
    rid = imported(local, tmp_path, body)
    head = local.head
    assert imported(local, tmp_path, body) == rid
    assert local.head == head
    local.validate(rid)
    local.accept(rid, "user", confirm=True)
    body["limitations"] = ["Corrected response revision, explicit fixture"]
    revised = imported(local, tmp_path, body, "revised.json")
    local.validate(revised)
    head = local.head
    with pytest.raises(ValidationError, match="LOCAL_EXPLICIT_REPLACEMENT_REQUIRED"):
        local.accept(revised, "user", confirm=True)
    assert local.head == head
    local.accept(revised, "user", confirm=True, replaces=rid)
    assert LocalWorkflow(local.store.root).accepted["E1-A"] == revised
    assert local.results[rid]["superseded_by"] == revised


def test_incomplete_result_cannot_complete_task(local, tmp_path):
    rid = imported(local, tmp_path, response(local, completion="NEEDS_WORK", outputs={}))
    assert local.validate(rid)["status"] == "VALIDATED_STRUCTURE"
    with pytest.raises(ValidationError, match="LOCAL_REQUIRED_RESULTS_INCOMPLETE"):
        local.accept(rid, "user", confirm=True)
    assert not local.accepted
    broken = response(local, outputs={})
    rid = imported(local, tmp_path, broken, "broken.json")
    assert local.validate(rid)["status"] == "REJECTED"


def test_cas_and_vault_readback(local, tmp_path):
    body = response(local)
    stale = LocalWorkflow(local.store.root)
    imported(local, tmp_path, body)
    with pytest.raises(ValidationError, match="LOCAL_CAS_CONFLICT"):
        stale.store.append("RESULT_REJECTED", {}, stale.head)
    ref = local.genesis["source_snapshot"]["raw_digest"]
    blob, _ = local.store.vault._paths(ref)
    blob.write_bytes(b"corruption")
    with pytest.raises(ValidationError, match="RAW_VAULT_READBACK_FAILED"):
        LocalWorkflow(local.store.root)


def test_modes_cannot_be_flipped_or_shared(local, tmp_path):
    before = local.store.path.read_bytes()
    with pytest.raises(ValidationError, match="LOCAL_STORE_CANNOT_BECOME_QUALIFIED"):
        TransactionalHistoryStore(local.store.path)
    assert local.store.path.read_bytes() == before
    with sqlite3.connect(local.store.path) as con:
        con.execute("UPDATE local_meta SET value='HIGH_ASSURANCE' WHERE key='mode'")
    with pytest.raises(ValidationError, match="LOCAL_PERMANENT_MODE_MISMATCH"):
        LocalWorkflow(local.store.root)
    other = tmp_path / "formal"
    other.mkdir()
    TransactionalHistoryStore(other / "local.sqlite3")
    before = (other / "local.sqlite3").read_bytes()
    with pytest.raises(ValidationError, match="LOCAL_STORE_FORMAT_REQUIRED"):
        LocalStore(other)
    assert (other / "local.sqlite3").read_bytes() == before
    assert not (other / "vault").exists()


def test_production_cli_import_and_accept(local, tmp_path, capsys):
    body = response(local)
    path = tmp_path / "real-file.fixture.json"
    path.write_bytes(canonical_bytes(body))
    base = ["product", "local"]
    assert run_cli([*base, "import", "--campaign", str(local.store.root), "--file", str(path)]) == 0
    rid = parse(capsys.readouterr().out.encode())["result_id"]
    assert run_cli([*base, "validate", "--campaign", str(local.store.root), "--result", rid]) == 0
    capsys.readouterr()
    assert run_cli([*base, "accept", "--campaign", str(local.store.root), "--result", rid, "--confirm-local"]) == 0
    assert parse(capsys.readouterr().out.encode())["status"] == "USER_ACCEPTED_LOCAL"
    assert run_cli([*base, "resume", "--campaign", str(local.store.root)]) == 0
    assert parse(capsys.readouterr().out.encode())["stage"] == "E1"


def accept_fixture(local, tmp_path, task):
    rid = imported(local, tmp_path, response(local, task), task + ".json")
    local.validate(rid)
    local.accept(rid, "fixture operator", confirm=True)
    return rid


def test_e1_completion_requires_every_real_input(local, tmp_path):
    local.prepare()
    head = local.head
    with pytest.raises(ValidationError, match="LOCAL_STAGE_RESULTS_MISSING"):
        local.advance()
    assert local.head == head
    for task in list(local._available_tasks()):
        accept_fixture(local, tmp_path, task)
    assert local.advance()["stage"] == "E2"
    resumed = LocalWorkflow(local.store.root)
    assert resumed.completed == ["E1"]
    archive = read_bytes(resumed.store.vault.read_bytes(resumed.packages["E2-CONVERGENCE"]["raw"]["raw_digest"]))
    prior = parse(archive["PRIOR_RESULTS.json"])
    assert len(prior) == 5
    assert all(item["response"]["producer"]["kind"] == "TEST_FIXTURE" for item in prior)


def test_actual_control_uses_exact_commit_and_restart_receipt(local, tmp_path, repo):
    local.prepare()
    (repo / "app.py").write_text("def clamp(n):\n    return 0\n", encoding="utf-8")
    result = local.run_check("E1-A", [sys.executable, "-c", "from app import clamp; assert clamp(-1) == 0"], timeout=10)
    assert result["result"]["supervisor_status"] == "TARGET_NONZERO"
    assert result["result"]["target_exit_code"] != 0
    assert result["context"]["source_commit"] == local.source["commit"]
    resumed = LocalWorkflow(local.store.root)
    assert len(resumed.runs) == 1 and not resumed.pending_runs
    assert b"AssertionError" in resumed.store.vault.read_bytes(result["files"]["stderr.bin"]["raw_digest"])


def test_fast_control_output_is_bounded(local):
    local.prepare()
    result = local.run_check("E1-E", [sys.executable, "-c", "print('x' * 100000)"], timeout=10, max_output=1024)
    assert result["result"]["supervisor_status"] == "OUTPUT_LIMIT"
    assert result["result"]["stdout_bytes"] + result["result"]["stderr_bytes"] <= 1024


def test_all_stages_and_frozen_e5_challenge_inputs(local, tmp_path):
    for stage in ("E1", "E2", "E3", "E4", "E5", "E6"):
        assert local.stage == stage
        while local.status()["missing_results"]:
            local.prepare()
            tasks = [task for task in local._available_tasks() if task not in local.accepted]
            assert tasks
            for task in tasks:
                accept_fixture(local, tmp_path, task)
            if stage == "E5" and tasks[0].startswith("E5-A-"):
                local.prepare()
                assert "E5-B1" in local.packages
                body = response(local, "E5-A-INTERACTION", limitations=["new explicit test revision"])
                rid = imported(local, tmp_path, body, "frozen-revision.json")
                local.validate(rid)
                before = local.head
                with pytest.raises(ValidationError, match="LOCAL_CHALLENGE_INPUT_FROZEN"):
                    local.accept(rid, "user", confirm=True, replaces=local.accepted["E5-A-INTERACTION"])
                assert local.head == before
                archive = read_bytes(local.store.vault.read_bytes(local.packages["E5-B1"]["raw"]["raw_digest"]))
                assert sum(r["response"]["task_id"].startswith("E5-A-") for r in parse(archive["PRIOR_RESULTS.json"])) == 3
        local.advance()
        local = LocalWorkflow(local.store.root)
    assert local.status()["status"] == "LOCAL_COMPLETED"
    assert local.completed == ["E1", "E2", "E3", "E4", "E5", "E6"]
    assert len(local.accepted) == 19
    head = local.head
    with pytest.raises(ValidationError, match="LOCAL_CAMPAIGN_ALREADY_COMPLETED"):
        local.advance()
    assert local.head == head


def test_crash_after_run_before_journal_can_recover(local, monkeypatch):
    local.prepare()
    original = local.recover_check
    def simulate_crash(run_id):
        raise RuntimeError("explicit test crash after receipt publication")
    monkeypatch.setattr(local, "recover_check", simulate_crash)
    with pytest.raises(RuntimeError):
        local.run_check("E1-A", [sys.executable, "-c", "print('actual check')"])
    restarted = LocalWorkflow(local.store.root)
    run_id = next(iter(restarted.pending_runs))
    assert restarted.recover_check(run_id)["result"]["supervisor_status"] == "SUCCESS"
    assert not LocalWorkflow(local.store.root).pending_runs


def test_missing_control_receipt_requires_explicit_abandonment(local, monkeypatch):
    local.prepare()
    def interrupt(self, spec):
        raise RuntimeError("explicit test interruption before execution")
    monkeypatch.setattr("bdb_audit.local_product.workflow.ToolSupervisor.run", interrupt)
    with pytest.raises(RuntimeError):
        local.run_check("E1-A", [sys.executable, "-c", "print('not run')"])
    restarted = LocalWorkflow(local.store.root)
    run_id = next(iter(restarted.pending_runs))
    with pytest.raises(ValidationError, match="TOOL_RUN_EVIDENCE_INCOMPLETE"):
        restarted.recover_check(run_id)
    restarted.abandon_check(run_id, "Actual execution has no complete receipt; not a passed check")
    assert len(LocalWorkflow(local.store.root).abandoned_runs) == 1
    assert not restarted.runs


def test_reports_keep_claims_separate_and_export_exact_evidence(local, tmp_path):
    from bdb_audit.local_product.report import build_report, export_report
    finding = {"id": "F1", "title": "<script>alert(1)</script>", "statement": "Negative clamp is wrong",
               "rationale": "Explicit fixture assertion, not independent AI evidence", "severity": "HIGH",
               "disposition": "CLAIM", "source_refs": [{"path": "app.py", "line": 2}]}
    rid = imported(local, tmp_path, response(local, findings=[finding]))
    local.validate(rid)
    local.accept(rid, "user", confirm=True)
    altered = deepcopy(finding)
    altered.update(severity="LOW", disposition="DISPUTED")
    rid = imported(local, tmp_path, response(local, "E1-B", findings=[altered]), "B.json")
    local.validate(rid)
    local.accept(rid, "user", confirm=True)
    report = build_report(local)
    assert report["status"] == "NEEDS_REAL_RESULTS" and report["contains_test_fixtures"]
    assert len(report["findings"]) == 2 and not any(f["truth_verified"] for f in report["findings"])
    assert report["contradictions"][0]["classification"] == "POTENTIAL_DISAGREEMENT_REQUIRES_REVIEW"
    assert all(item["record_kind"] != "local_finding_claim" for item in report["derived_report_model"]["facts"])
    exported = export_report(local, tmp_path / "report")
    assert exported["status"] == "EXPORTED_LOCAL"
    md = (tmp_path / "report" / "REPORT.md").read_text(encoding="utf-8")
    assert "<script>" not in md and "&lt;script&gt;" in md
    manifest = parse((tmp_path / "report" / "EVIDENCE_MANIFEST.json").read_bytes())
    from hashlib import sha256
    for item in manifest["reports"]:
        raw = (tmp_path / "report" / item["path"]).read_bytes()
        assert item["sha256"] == sha256(raw).hexdigest()
    head = local.head
    with pytest.raises(ValidationError, match="LOCAL_REPORT_OUTPUT_EXISTS"):
        export_report(local, tmp_path / "report")
    with pytest.raises(ValidationError, match="LOCAL_REPORT_PROTECTED_PATH"):
        export_report(local, local.store.root / "vault" / "new-report")
    assert local.head == head


def test_tui_real_file_import_and_explicit_accept(local, tmp_path):
    from bdb_audit.local_product.ui import run_local_ui
    path = tmp_path / "fixture.json"
    path.write_bytes(canonical_bytes(response(local)))
    inputs = iter(["2", "O", str(local.store.root), "3", str(path), "AKCEPTUJ LOCAL", "0", "0"])
    output = []
    assert run_local_ui(lambda _: next(inputs), output.append, index_path=tmp_path / "recent.json") == 0
    restarted = LocalWorkflow(local.store.root)
    assert restarted.results[restarted.accepted["E1-A"]]["state"] == "USER_ACCEPTED_LOCAL"
    assert any("VALIDATED_STRUCTURE" in text for text in output)


def test_tui_exit_does_not_create_or_accept_campaign():
    from bdb_audit.local_product.ui import run_local_ui
    output = []
    assert run_local_ui(lambda _: "0", output.append) == 0
    assert any("bez certyfikatów" in line for line in output)


def test_wrong_raw_digest_and_qualified_import_refuse_without_mutation(local, tmp_path, capsys):
    file = tmp_path / "local.json"
    file.write_bytes(canonical_bytes(response(local)))
    head, raw_db = local.head, local.store.path.read_bytes()
    with pytest.raises(ValidationError, match="LOCAL_RAW_SHA256_MISMATCH"):
        local.import_result(file, "0" * 64)
    assert local.head == head and local.store.path.read_bytes() == raw_db
    assert run_cli(["product", "import", "--store", str(local.store.path), "--zip", str(file), "--json"]) == 2
    data = parse(capsys.readouterr().err.encode())
    assert data["external_ingestion"] == "BLOCKED"
    assert local.store.path.read_bytes() == raw_db


def test_real_remote_fetch_path_with_local_bare_remote(repo, tmp_path):
    # Real git fetch and objects, no network/authority simulation. Public GitHub
    # itself is separately exercised in retained live smoke evidence.
    from bdb_audit.local_product.workflow import capture_source
    commit = subprocess.check_output(["git", "-C", str(repo), "rev-parse", "HEAD"]).decode().strip()
    source, raw = capture_source(str(repo), commit, "github")
    assert source["commit"] == commit and source["target_type"] == "github"
    assert "MANIFEST.json" in read_bytes(raw)


def test_package_publication_crash_and_resume_restore_exact_bytes(local, monkeypatch):
    def crash(path, raw):
        raise RuntimeError("explicit test crash before package publication")
    with monkeypatch.context() as patch:
        patch.setattr("bdb_audit.local_product.workflow._publish_exact", crash)
        with pytest.raises(RuntimeError):
            local.prepare()
    restarted = LocalWorkflow(local.store.root)
    head = restarted.head
    assert len(restarted.packages) == 5 and not (local.store.root / "packages").exists()
    restarted.prepare()
    assert restarted.head == head
    for task, package in restarted.packages.items():
        assert (local.store.root / "packages" / (task + ".zip")).read_bytes() == restarted.store.vault.read_bytes(package["raw"]["raw_digest"])


def test_crash_after_raw_before_event_never_accepts_orphan(local, tmp_path, monkeypatch):
    body = response(local)
    file = tmp_path / "response.json"
    file.write_bytes(canonical_bytes(body))
    head = local.head
    def crash(kind, payload, expected_head):
        raise RuntimeError("explicit test crash after raw publication before SQLite append")
    with monkeypatch.context() as patch:
        patch.setattr(local.store, "append", crash)
        with pytest.raises(RuntimeError):
            local.import_result(file)
    restarted = LocalWorkflow(local.store.root)
    assert restarted.head == head and not restarted.results
    assert restarted.import_result(file)["status"] == "IMPORTED_UNTRUSTED"


def test_real_concurrent_import_has_one_journal_event(local, tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    file = tmp_path / "response.json"
    file.write_bytes(canonical_bytes(response(local)))
    writers = [LocalWorkflow(local.store.root), LocalWorkflow(local.store.root)]
    ready = Barrier(2)
    def import_one(writer):
        ready.wait(timeout=5)
        try:
            return writer.import_result(file)["status"]
        except ValidationError as exc:
            return exc.code
    with ThreadPoolExecutor(2) as pool:
        statuses = list(pool.map(import_one, writers))
    assert statuses.count("IMPORTED_UNTRUSTED") == 1
    assert all(status in {"IMPORTED_UNTRUSTED", "LOCAL_CAS_CONFLICT"} for status in statuses)
    restarted = LocalWorkflow(local.store.root)
    assert len(restarted.results) == 1 and not restarted.accepted


def test_launcher_does_not_import_from_the_callers_directory(tmp_path):
    shell = shutil.which("pwsh") or shutil.which("powershell")
    if os.name != "nt" or shell is None:
        pytest.skip("Windows PowerShell launcher required")
    marker = "CWD_IMPORT_EXECUTED"
    (tmp_path / "bdb_audit.py").write_text(f"print({marker!r})", encoding="utf-8")
    launcher = Path(__file__).resolve().parents[2] / "Run-Local-Audit.ps1"
    result = subprocess.run([shell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(launcher),
                             "-NoGui", "-Index", str(tmp_path / "index.json")],
                            cwd=tmp_path, input="0\n", text=True, capture_output=True, timeout=60)
    assert result.returncode == 0, result.stderr
    assert "LOCAL PRODUCT MODE" in result.stdout and marker not in result.stdout


def test_nested_git_location_is_refused_and_explicit_path_from_root_is_exact(repo, tmp_path):
    folder = repo / "nested"
    folder.mkdir()
    (folder / "app.py").write_bytes(b"# nested file\n")
    for args in (("add", "nested/app.py"),
                 ("-c", "user.name=LOCAL test", "-c", "user.email=local-test@example.invalid", "commit", "-qm", "nested")):
        subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)
    bad = tmp_path / "bad-campaign"
    with pytest.raises(ValidationError, match="LOCAL_SOURCE_REPOSITORY_ROOT_REQUIRED"):
        LocalWorkflow.start(bad, str(folder), "HEAD")
    assert not bad.exists()
    good = LocalWorkflow.start(tmp_path / "scoped", str(repo), "HEAD", paths=["nested/app.py"])
    assert good.source["paths"] == ["nested/app.py"]
    entry = good.source_manifest["entries"][0]
    assert good.source_members[entry["transport_path"]] == b"# nested file\n"


@pytest.mark.parametrize("tamper_before_capture", [False, True])
def test_check_recovery_uses_supervisor_evidence_anchored_in_journal(local, monkeypatch, tamper_before_capture):
    from bdb_audit.runner.supervisor import ToolSupervisor

    local.prepare()
    run = ToolSupervisor.run
    def fake_receipt(evidence):
        path = evidence / "RUN_RECEIPT.json"
        receipt = parse(path.read_bytes())
        receipt.pop("receipt_digest")
        receipt.update(supervisor_status="SUCCESS", target_exit_code=0)
        receipt["receipt_digest"] = sha(canonical_bytes(receipt))
        path.write_bytes(canonical_bytes(receipt))

    def tamper_then_return(supervisor, spec):
        result = run(supervisor, spec)
        fake_receipt(Path(spec.evidence_dir))
        return result

    def crash_after_capture(run_id):
        raise RuntimeError("crash after evidence capture")

    if tamper_before_capture:
        monkeypatch.setattr(ToolSupervisor, "run", tamper_then_return)
        with pytest.raises(ValidationError, match="LOCAL_CHECK_RECEIPT_MISMATCH"):
            local.run_check("E1-A", [sys.executable, "-c", "raise SystemExit(19)"])
    else:
        monkeypatch.setattr(local, "recover_check", crash_after_capture)
        with pytest.raises(RuntimeError, match="crash after evidence capture"):
            local.run_check("E1-A", [sys.executable, "-c", "raise SystemExit(19)"])

    reopened = LocalWorkflow(local.store.root)
    run_id = next(iter(reopened.pending_runs))
    if tamper_before_capture:
        with pytest.raises(ValidationError, match="TOOL_RUN_EVIDENCE_INCOMPLETE"):
            reopened.recover_check(run_id)
        assert not reopened.runs
    else:
        fake_receipt(local.store.root / "checks" / run_id)
        data = reopened.recover_check(run_id)
        assert data["result"]["supervisor_status"] == "TARGET_NONZERO"
        assert data["result"]["target_exit_code"] == 19
        assert LocalWorkflow(local.store.root).runs == reopened.runs
