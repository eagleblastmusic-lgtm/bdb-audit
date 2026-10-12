"""LOCAL production interfaces. Responses here are explicit TEST_FIXTURE inputs."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import sqlite3
import subprocess
import sys

import pytest

from bdb_audit.cli import run_cli
from bdb_audit.core.canonical_json import canonical_bytes, parse
from bdb_audit.core.errors import ValidationError
from bdb_audit.history.store import TransactionalHistoryStore
from bdb_audit.local_product.store import LocalStore
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
