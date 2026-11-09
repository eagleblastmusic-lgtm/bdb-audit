"""Real LOCAL packages, journals and importer; AI inputs disclose TEST_FIXTURE.

Only the native dialog/clipboard boundary and deliberate crash points are mocked.
"""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import ctypes
import os
import sqlite3

import pytest

from bdb_audit.assurance.zip_safety import read_bytes
from bdb_audit.cli import run_cli
from bdb_audit.core.canonical_json import canonical_bytes, parse
from bdb_audit.core.errors import ValidationError
from bdb_audit.local_product.artifacts import WindowsActions
from bdb_audit.local_product.contract import (GENERATOR_VERSION, COMPLETIONS, DISPOSITIONS, SEVERITIES, FINDING_FIELDS,
                                            RESPONSE_FIELDS, result_filename, response_guide)
from bdb_audit.local_product import file_dialog
from bdb_audit.local_product.guided import CampaignController
from bdb_audit.local_product.profile import STAGES, LEGACY_RESPONSE_GUIDE
from bdb_audit.local_product.report import build_report, REPORT_JSON_LIMIT
from bdb_audit.local_product.store import sha
from bdb_audit.local_product.ui import run_local_ui, prompt_pages, parse_manual_paths, render_import_summary
from bdb_audit.local_product.workflow import LocalWorkflow
from bdb_audit.workflow.packaging import _deterministic_zip
from test_local_product import repo as repo_fixture, local as local_fixture, response


@pytest.fixture(name="repo")
def _repo(tmp_path):
    return repo_fixture.__wrapped__(tmp_path)


@pytest.fixture(name="local")
def _local(repo, tmp_path):
    workflow = local_fixture.__wrapped__(repo, tmp_path)
    workflow.prepare()
    return workflow


FINDING = {"id": "E1A-004", "title": "Static test fixture", "statement": "A static observation",
           "rationale": "Explicit fixture; no test execution claimed", "severity": "HIGH", "disposition": "CLAIM",
           "source_refs": [{"path": "app.py", "line": 2}]}


def emit(local, tmp_path, task="E1-A", *, zipped=False, name=None, **updates):
    body = response(local, task, **updates)
    name = name or result_filename(task, "zip" if zipped else "json")
    path = tmp_path / name
    raw = canonical_bytes(body)
    if zipped:
        body["evidence_files"] = [{"path": "observations.txt", "sha256": sha(b"static fixture"), "byte_length": 14}]
        raw = _deterministic_zip({"LOCAL_RESULT.json": canonical_bytes(body), "observations.txt": b"static fixture"})
    path.write_bytes(raw)
    return path


def enable(local):
    local.set_acceptance_policy(True, "TEST_FIXTURE policy authorizer")


class Actions(WindowsActions):
    def __init__(self, selection=None):
        self.selection = selection
        self.dialog_calls = 0
        self.copied = []

    def choose_results(self, *, interactive):
        self.dialog_calls += 1
        return self.selection

    def clipboard(self, value):
        self.copied.append(str(value))
        return True


def tui(local, tmp_path, inputs, actions=None, **kwargs):
    output = []
    iterator = iter(inputs)
    assert run_local_ui(lambda _: next(iterator), output.append, index_path=tmp_path / "recent.json",
                        actions=actions, actor="TEST_FIXTURE operator", **kwargs) == 0
    return "\n".join(output)


def test_five_mixed_results_auto_accept_and_explicit_e1_to_e2(local, tmp_path):
    enable(local)
    paths = [emit(local, tmp_path, task, zipped=i % 2 == 0) for i, task in enumerate(local._available_tasks())]
    # Deliberately misleading filename: canonical content, never name, assigns a task.
    paths[0] = paths[0].rename(tmp_path / "E6-FOLLOWUP_RESULT.zip")
    batch = local.import_results(paths)
    assert (batch["imported"], batch["accepted"], batch["rejected"], batch["duplicates"]) == (5, 5, 0, 0)
    assert local.stage == "E1" and len(local.accepted) == 5
    assert [r["task_id"] for r in batch["items"]] == [t for t, _, _ in STAGES["E1"]]
    assert all(local.store.vault.read_bytes(r["raw"]["raw_digest"]) == p.read_bytes() for r, p in zip(batch["items"], paths))
    restarted = LocalWorkflow(local.store.root)
    assert restarted.batch_summaries()[-1] == {k: v for k, v in batch.items() if k not in {"mode", "notice"}}
    controller = CampaignController(local.store.root)
    assert controller.view()["next"]["action"] == "advance"
    assert controller.advance(restarted.head)["stage"] == "E2"
    members = read_bytes(controller.workflow().store.vault.read_bytes(controller.workflow().packages["E2-CONVERGENCE"]["raw"]["raw_digest"]))
    assert len(parse(members["PRIOR_RESULTS.json"])) == 5


def test_four_valid_one_invalid_preserves_accepted_files_and_raw(local, tmp_path):
    enable(local)
    paths = [emit(local, tmp_path, task) for task in local._available_tasks()]
    body = parse(paths[3].read_bytes())
    body["source_commit"] = "0" * 40
    paths[3].write_bytes(canonical_bytes(body))
    batch = local.import_results(paths)
    assert (batch["imported"], batch["rejected"]) == (4, 1)
    assert set(local.accepted) == {"E1-A", "E1-B", "E1-C", "E1-E"}
    assert batch["items"][3]["issues"] == ["LOCAL_CONTEXT_MISMATCH:source_commit"]
    assert local.store.vault.read_bytes(batch["items"][3]["raw"]["raw_digest"]) == paths[3].read_bytes()
    assert local.batch_item_info(batch["batch_id"], 3)["response"] == body
    with pytest.raises(ValidationError, match="LOCAL_STAGE_RESULTS_MISSING"):
        local.advance()
    assert LocalWorkflow(local.store.root).stage == "E1"


@pytest.mark.parametrize("field,value", [("campaign_id", "foreign"), ("stage_id", "E2"), ("task_id", "E1-UNKNOWN"),
    ("source_commit", "0" * 40), ("source_tree", "0" * 40), ("input_package_digest", "0" * 64),
    ("completion", "PASS"), ("mode", "HIGH_ASSURANCE"), ("source_transport_audit", {"note": "unsupported extra field"})])
def test_foreign_or_invalid_contract_is_refused_not_repaired(local, tmp_path, field, value):
    enable(local)
    file = emit(local, tmp_path, **{field: value}) if field != "task_id" else None
    if file is None:
        file = emit(local, tmp_path)
        body = parse(file.read_bytes())
        body[field] = value
        file.write_bytes(canonical_bytes(body))
    batch = local.import_results([file])
    assert batch["rejected"] == 1 and not local.results and not local.accepted
    assert batch["items"][0]["diagnostics"]
    assert LocalWorkflow(local.store.root).batch_summaries()[-1]["rejected"] == 1


@pytest.mark.parametrize("defect,code", [
    ("disposition", "LOCAL_FINDING_DISPOSITION_INVALID"), ("statement", "LOCAL_FINDING_FIELD_REQUIRED:statement"),
    ("rationale", "LOCAL_FINDING_FIELD_REQUIRED:rationale"), ("severity", "LOCAL_FINDING_SEVERITY_INVALID"),
    ("source_refs", "LOCAL_FINDING_SOURCE_REFS_REQUIRED"), ("duplicate_id", "LOCAL_FINDING_ID_INVALID_OR_DUPLICATE"),
    ("contradictions", "LOCAL_TEXT_LIST_REQUIRED:contradictions"),
    ("recommendations", "LOCAL_TEXT_LIST_REQUIRED:recommendations"),
    ("source_transport_audit", "LOCAL_UNKNOWN_RESPONSE_FIELDS:source_transport_audit")])
def test_real_campaign_observed_failures_have_polish_diagnostics(local, tmp_path, defect, code):
    body = response(local, findings=[deepcopy(FINDING)])
    if defect == "disposition":
        body["findings"][0][defect] = "STATIC_SOURCE_OBSERVATION"
    elif defect == "severity":
        body["findings"][0][defect] = "P1"
    elif defect in {"statement", "rationale", "source_refs"}:
        del body["findings"][0][defect]
    elif defect == "duplicate_id":
        body["findings"].append(deepcopy(FINDING))
    else:
        body[defect] = {"unsupported": "not a text list"}
    file = tmp_path / "bad real format.json"
    file.write_bytes(canonical_bytes(body))
    inspected = local.inspect(file)
    assert code in inspected["issues"] and inspected["diagnostics"]
    batch = local.import_results([file])
    text = render_import_summary(batch, details=True)
    assert code in text and "BŁĄD" in text and not local.accepted
    if defect == "disposition":
        assert "E1A-004" in text and "STATIC_SOURCE_OBSERVATION" in text and ", ".join(DISPOSITIONS) in text


@pytest.mark.parametrize("field", ["severity", "disposition", "id", "task_id", "completion"])
def test_invalid_diagnostic_values_cannot_become_journal_vault_references(local, tmp_path, field):
    enable(local)
    body = response(local, findings=[deepcopy(FINDING)])
    invalid_value = {"raw_digest": "0" * 64, "byte_length": 1}
    if field in {"task_id", "completion"}:
        body[field] = invalid_value
    else:
        body["findings"][0][field] = invalid_value
    bad = tmp_path / "bad-object.json"
    bad.write_bytes(canonical_bytes(body))
    good = emit(local, tmp_path, "E1-B")
    batch = local.import_results([bad, good])
    assert (batch["rejected"], batch["accepted"]) == (1, 1)
    assert LocalWorkflow(local.store.root).accepted.keys() == {"E1-B"}
    assert local.batch_item_info(batch["batch_id"], 0)["response"] == body


def test_large_invalid_diagnostics_are_bounded_without_losing_original_response(local, tmp_path):
    enable(local)
    body = response(local, findings=[{"id": str(i) + "x" * 5000, "severity": "UNKNOWN", "disposition": {"bad": "x" * 2000}}
                                     for i in range(200)])
    file = tmp_path / "large-invalid.json"
    file.write_bytes(canonical_bytes(body))
    batch = local.import_results([file, emit(local, tmp_path, "E1-B")])
    assert (batch["rejected"], batch["accepted"]) == (1, 1)
    assert len(canonical_bytes(batch["items"][0]["diagnostics"])) < 256 * 1024
    assert "Dalsze ustalenia" in render_import_summary(batch, details=True)
    assert local.batch_item_info(batch["batch_id"], 0)["response"] == body


@pytest.mark.parametrize("ref", [{"path": "source/0001.bin", "line": 1}, {"path": "app.py", "line": 3},
                                  {"path": "app.py", "line": 0}, {"path": "app.py", "line": True},
                                  {"path": "app.py", "line": 1, "authority": "verified"}])
def test_source_reference_uses_original_path_and_real_line_range(local, tmp_path, ref):
    finding = {**FINDING, "source_refs": [ref]}
    file = emit(local, tmp_path, findings=[finding])
    assert local.import_results([file])["items"][0]["issues"] == ["LOCAL_FINDING_SOURCE_REF_INVALID"]


@pytest.mark.parametrize("nested", ["finding", "producer", "output", "evidence"])
def test_new_package_contract_refuses_nested_extra_fields(local, tmp_path, nested):
    body = response(local, findings=[deepcopy(FINDING)])
    if nested == "finding":
        body["findings"][0]["confidence"] = "HIGH"
    elif nested == "producer":
        body["producer"]["identity_verified"] = True
    elif nested == "output":
        body["outputs"]["additional"] = "extra"
    else:
        body["evidence_files"] = [{"path": "e.txt", "sha256": sha(b"x"), "byte_length": 1, "signed": True}]
    file = tmp_path / "extra.zip"
    raw = canonical_bytes(body) if nested != "evidence" else _deterministic_zip({"LOCAL_RESULT.json": canonical_bytes(body), "e.txt": b"x"})
    file.write_bytes(raw)
    assert local.import_results([file])["rejected"] == 1


def test_identical_duplicates_are_idempotent_and_conflicts_cannot_replace(local, tmp_path):
    enable(local)
    first = emit(local, tmp_path, name="LOCAL_RESULT.json")
    duplicate = tmp_path / "stara nazwa żółć ze spacją.json"
    duplicate.write_bytes(first.read_bytes())
    batch = local.import_results([first, duplicate])
    assert (batch["accepted"], batch["duplicates"]) == (1, 1)
    accepted = dict(local.accepted)
    conflicting = emit(local, tmp_path, name="revision.json", limitations=["Changed claim; requires explicit review"])
    batch = local.import_results([duplicate, conflicting])
    assert (batch["duplicates"], batch["rejected"]) == (1, 1)
    assert batch["items"][1]["outcome"] == "CONFLICT" and local.accepted == accepted and len(local.results) == 1
    assert len([e for e in local.events if e["kind"] == "RESULT_ACCEPTED"]) == 1


def test_manual_policy_default_and_revocation_require_real_decision(local, tmp_path):
    first = emit(local, tmp_path)
    batch = local.import_results([first])
    rid = batch["items"][0]["result_id"]
    assert not local.acceptance_policy["enabled"] and not local.accepted and batch["items"][0]["outcome"] == "VALIDATED"
    with pytest.raises(ValidationError, match="LOCAL_MANUAL_CONFIRMATION_REQUIRED"):
        local.accept(rid, "fixture", confirm=False)
    local.accept(rid, "TEST_FIXTURE reviewer", confirm=True)
    assert local.result_info(rid)["acceptance_mechanism"] == "MANUAL"
    enable(local)
    assert len(local.accepted) == 1  # Policy change does not retroactively decide results.
    local.set_acceptance_policy(False, "TEST_FIXTURE authorizer")
    second = emit(local, tmp_path, "E1-B")
    assert local.import_results([second])["items"][0]["outcome"] == "VALIDATED"
    assert len(LocalWorkflow(local.store.root).accepted) == 1


def test_pending_conflict_requires_explicit_review(local, tmp_path):
    first = emit(local, tmp_path)
    local.import_results([first])
    second = emit(local, tmp_path, name="conflict.json", limitations=["different complete response"])
    batch = local.import_results([second])
    assert batch["items"][0]["outcome"] == "CONFLICT" and len(local.results) == 1 and not local.accepted


def test_conflict_can_be_manually_reviewed_using_retained_bytes_without_auto_replacement(local, tmp_path):
    enable(local)
    first = emit(local, tmp_path)
    local.import_results([first])
    previous = local.accepted["E1-A"]
    revision = emit(local, tmp_path, name="revision.json", limitations=["Explicit manual revision fixture"])
    batch = local.import_results([revision])
    retained = revision.read_bytes()
    revision.write_bytes(b"later path substitution must not be used")
    staged = local.review_batch_conflict(batch["batch_id"], 0)
    assert staged["status"] == "VALIDATED_STRUCTURE" and staged["raw_sha256"] == sha(retained)
    assert local.accepted["E1-A"] == previous
    with pytest.raises(ValidationError, match="LOCAL_EXPLICIT_REPLACEMENT_REQUIRED"):
        local.accept(staged["result_id"], "fixture reviewer", confirm=True)
    local.accept(staged["result_id"], "fixture reviewer", confirm=True, replaces=previous)
    assert LocalWorkflow(local.store.root).result_info(staged["result_id"])["acceptance_mechanism"] == "MANUAL"


@pytest.mark.parametrize("completion", ["NEEDS_WORK", "BLOCKED"])
def test_incomplete_observations_never_complete_and_can_be_corrected(local, tmp_path, completion):
    enable(local)
    file = emit(local, tmp_path, completion=completion, outputs={})
    batch = local.import_results([file])
    assert batch["items"][0]["outcome"] == "INCOMPLETE" and not local.accepted
    controller = CampaignController(local.store.root)
    assert controller.view()["next"]["action"] == "import" and "NIEKOMPLETNY" in controller.view()["packages"][0]["result_state"]
    with pytest.raises(ValidationError, match="LOCAL_STAGE_RESULTS_MISSING"):
        local.advance()
    complete = emit(local, tmp_path, name="corrected.json")
    assert local.import_results([complete])["accepted"] == 1 and len(local.results) == 2
    assert controller.view()["packages"][0]["result_state"] == "ZAAKCEPTOWANY_LOKALNIE"
    assert not local.completed


def test_policy_acceptance_history_and_report_never_claim_manual_or_truth(local, tmp_path):
    enable(local)
    policy = deepcopy(local.acceptance_policy)
    file = emit(local, tmp_path, findings=[FINDING])
    local.import_results([file])
    event = next(e for e in local.events if e["kind"] == "RESULT_ACCEPTED")
    assert event["payload"]["mechanism"] == "AUTO_POLICY" and event["payload"]["policy_event_hash"] == policy["event_hash"]
    report = build_report(LocalWorkflow(local.store.root))
    assert report["findings"][0]["truth_verified"] is False
    assert report["declared_producers"][0]["identity_verified"] is False
    facts = report["derived_report_model"]["facts"]
    assert any(f["record_kind"] == "local_policy_acceptance" for f in facts)
    assert not any(f["record_kind"] == "local_manual_acceptance" for f in facts)
    assert report["accepted_responses"][0]["acceptance_mechanism"] == "AUTO_POLICY"


@pytest.mark.parametrize("raw", [b"not JSON", b"PKbroken ZIP", b'{"a":1,"a":2}', b"[]",
    _deterministic_zip({"../escape.py": b"never executed"})])
def test_malformed_or_unsafe_raw_is_preserved_only_as_rejected_material(local, tmp_path, raw):
    file = tmp_path / "unsafe.zip"
    file.write_bytes(raw)
    batch = local.import_results([file])
    assert batch["rejected"] == 1 and not local.results and not local.accepted
    assert local.store.vault.read_bytes(batch["items"][0]["raw"]["raw_digest"]) == raw
    assert not (tmp_path / "escape.py").exists()


def test_modified_zip_attachment_is_rejected(local, tmp_path):
    file = emit(local, tmp_path, zipped=True)
    members = read_bytes(file.read_bytes())
    members["observations.txt"] = b"tampered"
    file.write_bytes(_deterministic_zip(members))
    batch = local.import_results([file])
    assert batch["rejected"] == 1 and "LOCAL_EVIDENCE_EXACT_BYTES_MISMATCH:observations.txt" in batch["items"][0]["issues"]


def test_batch_crash_between_files_and_restart_retry_has_no_duplicate_facts(local, tmp_path, monkeypatch):
    enable(local)
    files = [emit(local, tmp_path, task) for task in local._available_tasks()]
    original = local._import_batch_item
    def crash(bid, index, file):
        if index == 2:
            raise RuntimeError("TEST_FIXTURE crash between file transactions")
        return original(bid, index, file)
    monkeypatch.setattr(local, "_import_batch_item", crash)
    with pytest.raises(RuntimeError):
        local.import_results(files)
    restarted = LocalWorkflow(local.store.root)
    assert len(restarted.accepted) == 2
    batch = restarted.batch_summaries()[-1]
    assert batch["status"] == "INTERRUPTED" and batch["processed"] == 2 and len(batch["remaining_files"]) == 3
    retry = restarted.import_results(files)
    assert (retry["accepted"], retry["duplicates"], retry["rejected"]) == (3, 2, 0)
    assert len(restarted.accepted) == len(restarted.results) == 5
    assert sum(e["kind"] == "RESULT_ACCEPTED" for e in restarted.events) == 5


def test_crash_inside_one_file_transaction_rolls_back_all_facts(local, tmp_path, monkeypatch):
    enable(local)
    file = emit(local, tmp_path)
    read_refs = local.store._read_refs
    def crash(value):
        if isinstance(value, dict) and "outcome" in value:
            raise RuntimeError("TEST_FIXTURE crash after inserts before transaction commit")
        return read_refs(value)
    monkeypatch.setattr(local.store, "_read_refs", crash)
    with pytest.raises(RuntimeError):
        local.import_results([file])
    restarted = LocalWorkflow(local.store.root)
    assert not restarted.results and not restarted.accepted
    assert restarted.batch_summaries()[-1]["processed"] == 0
    assert restarted.import_results([file])["accepted"] == 1


def test_revocation_concurrent_with_batch_cas_prevents_auto_accept(local, tmp_path, monkeypatch):
    enable(local)
    file = emit(local, tmp_path)
    append = local.store.append_many
    def revoke(entries, head, **kwargs):
        if any(kind == "RESULT_ACCEPTED" for kind, _ in entries):
            LocalWorkflow(local.store.root).set_acceptance_policy(False, "TEST_FIXTURE revocation")
        return append(entries, head, **kwargs)
    monkeypatch.setattr(local.store, "append_many", revoke)
    with pytest.raises(ValidationError, match="LOCAL_CAS_CONFLICT"):
        local.import_results([file])
    restarted = LocalWorkflow(local.store.root)
    assert not restarted.results and not restarted.accepted and not restarted.acceptance_policy["enabled"]


def test_all_e1_e6_tasks_names_prompts_contracts_and_batch_auto_accept(local, tmp_path):
    enable(local)
    controller = CampaignController(local.store.root, actions=Actions())
    for stage, definitions in STAGES.items():
        assert local.stage == stage
        while local.status()["missing_results"]:
            local.prepare()
            tasks = [t for t in local._available_tasks() if t not in local.accepted]
            files = []
            for task in tasks:
                assert result_filename(task) == task + "_RESULT.json"
                assert result_filename(task, "zip") == task + "_RESULT.zip"
                prompt = controller.prompt(task)
                package = local.packages[task]
                members = read_bytes(local.store.vault.read_bytes(package["raw"]["raw_digest"]))
                assert prompt["text"].encode() == members["PROMPT.md"]
                assert "".join(prompt_pages(prompt["text"], 7)) == prompt["text"]
                assert controller.copy_prompt(task)["copied"]
                assert controller.actions.copied[-1].encode() == members["PROMPT.md"]
                assert members["RESPONSE_FORMAT.md"].decode() == response_guide()
                template = parse(members["RESPONSE_TEMPLATE.json"])
                assert set(template) == set(RESPONSE_FIELDS)
                assert all(value in prompt["text"] for value in (*SEVERITIES, *DISPOSITIONS, *COMPLETIONS, *FINDING_FIELDS))
                assert result_filename(task) in prompt["text"] and result_filename(task, "zip") in prompt["text"]
                files.append(emit(local, tmp_path, task, zipped=len(files) % 2 == 0, findings=[FINDING]))
            batch = local.import_results(files)
            assert batch["accepted"] == len(tasks) and not batch["rejected"]
            assert local.stage == stage
        local.advance()
        local = LocalWorkflow(local.store.root)
    assert local.stage == "COMPLETE" and len(local.accepted) == sum(map(len, STAGES.values())) == 19
    assert not local.pending_runs and local.completed == list(STAGES)


@pytest.mark.parametrize("legacy_version", [1, 2])
def test_frozen_campaign_is_readable_and_new_stage_is_versioned(repo, tmp_path, legacy_version):
    local = LocalWorkflow.start(tmp_path / "legacy campaign", str(repo), "HEAD")
    expected_guide = LEGACY_RESPONSE_GUIDE if legacy_version == 1 else response_guide()
    for task in local._available_tasks():
        metadata, raw = local._package_bytes(task, legacy_version)
        local._append("PACKAGE_PREPARED", {**metadata, "raw": local.store.put(raw)})
    local.prepare()
    guide = local.store.root / "packages/RESPONSE_FORMAT.md"
    assert guide.read_bytes() == expected_guide.encode()
    packages = {t: local.store.vault.read_bytes(p["raw"]["raw_digest"]) for t, p in local.packages.items()}
    head = local.head
    prompt = LocalWorkflow(local.store.root).prompt("E1-A")
    assert prompt["text"].encode() == read_bytes(packages["E1-A"])["PROMPT.md"]
    assert LocalWorkflow(local.store.root).head == head
    enable(local)
    files = [emit(local, tmp_path, t, name=t + ".json") for t in local._available_tasks()]
    assert local.import_results(files)["accepted"] == 5
    local.advance()
    assert local.packages["E2-CONVERGENCE"]["generator_version"] == GENERATOR_VERSION
    assert all(local.store.vault.read_bytes(local.packages[t]["raw"]["raw_digest"]) == raw for t, raw in packages.items())
    assert guide.read_bytes() == expected_guide.encode()


@pytest.mark.parametrize("pipeline", ["batch", "single"])
def test_new_ingestion_of_legacy_task_checks_real_lines_without_changing_package(repo, tmp_path, pipeline):
    local = LocalWorkflow.start(tmp_path / "legacy task", str(repo), "HEAD")
    metadata, raw = local._package_bytes("E1-A", 1)
    local._append("PACKAGE_PREPARED", {**metadata, "raw": local.store.put(raw)})
    local.prepare()
    file = emit(local, tmp_path, findings=[{**FINDING, "source_refs": [{"path": "app.py", "line": 999}]}])
    assert local.inspect(file)["issues"] == ["LOCAL_FINDING_SOURCE_REF_INVALID"]
    if pipeline == "batch":
        assert local.import_results([file])["rejected"] == 1
    else:
        rid = local.import_result(file)["result_id"]
        assert local.validate(rid)["status"] == "REJECTED"
    assert not local.accepted and local.store.vault.read_bytes(local.packages["E1-A"]["raw"]["raw_digest"]) == raw


def test_prompt_copy_refuses_changed_published_zip(local):
    actions = Actions()
    controller = CampaignController(local.store.root, actions=actions)
    (local.store.root / "packages/E1-A.zip").write_bytes(b"changed")
    with pytest.raises(ValidationError, match="LOCAL_ARTIFACT_HASH_MISMATCH"):
        controller.copy_prompt("E1-A")
    assert not actions.copied


def test_windows_clipboard_sends_entire_frozen_prompt_as_unicode(local, monkeypatch):
    if os.name != "nt":
        pytest.skip("Windows clip.exe boundary")
    prompt = local.prompt("E1-A")["text"]
    calls = []
    def capture(argv, **kwargs):
        calls.append((argv, kwargs))
    monkeypatch.setattr("bdb_audit.local_product.artifacts.subprocess.run", capture)
    assert WindowsActions().clipboard(prompt)
    assert len(calls) == 1
    argv, options = calls[0]
    assert Path(argv[0]).name == "clip.exe" and options["shell"] is False and options["check"] is True
    assert options["input"].decode("utf-16") == prompt and options["timeout"] == 5


@pytest.mark.parametrize("selection", ["single", "ctrl_shift", "ctrl_a", "cancel"])
def test_tui_one_native_selection_imports_all_files_or_cancels(local, tmp_path, selection):
    files = [emit(local, tmp_path, t, zipped=i % 2 == 0, name=f"wynik żółć {i}." + ("zip" if i % 2 == 0 else "json"))
             for i, t in enumerate(local._available_tasks())]
    chosen = files[:1] if selection == "single" else files[:3] if selection == "ctrl_shift" else files if selection == "ctrl_a" else []
    enable(local)
    before = local.store.path.read_bytes()
    actions = Actions(chosen)
    text = tui(local, tmp_path, ["2", "O", str(local.store.root), "3", "0", "0"], actions)
    assert actions.dialog_calls == 1
    current = LocalWorkflow(local.store.root)
    assert len(current.accepted) == len(chosen)
    assert "AKCEPTUJ LOCAL" not in text
    if not chosen:
        assert "Anulowano" in text and local.store.path.read_bytes() == before
    else:
        assert "IMPORT WYNIKÓW" in text and "Przyjęto AUTO: " + str(len(chosen)) in text


@pytest.mark.parametrize("payload,expected", [("C:\\wyniki\\a żółć.json\0\0", 1),
    ("C:\\wyniki ze spacją\0a żółć.json\0b.zip\0c.json\0\0", 3),
    ("C:\\wyniki\0a.json\0b.zip\0c.json\0d.zip\0e.json\0\0", 5), ("", 0)])
def test_native_unicode_multi_buffer_parser(payload, expected):
    files = file_dialog.parse_selection(payload)
    assert len(files) == expected
    if expected == 3:
        assert files[0].name == "a żółć.json" and str(files[0].parent).endswith("wyniki ze spacją")


@pytest.mark.parametrize("payload,error", [("C:\\wyniki ze spacją\0a żółć.json\0b.zip\0\0", 0), ("", 0), ("", 0x3003)])
def test_windows_native_api_filter_flags_cancel_and_error_adapter(monkeypatch, payload, error):
    if os.name != "nt":
        pytest.skip("Native Windows ctypes ABI")
    calls = []
    def native(pointer):
        options = pointer._obj
        filter_address = ctypes.c_void_p.from_address(ctypes.addressof(options) + type(options).lpstrFilter.offset).value
        calls.append((options.Flags, ctypes.wstring_at(filter_address, len(file_dialog.FILTER)), options.nMaxFile, ctypes.sizeof(options)))
        if payload:
            address = ctypes.c_void_p.from_address(ctypes.addressof(options) + type(options).lpstrFile.offset).value
            data = ctypes.create_unicode_buffer(payload)
            ctypes.memmove(address, data, ctypes.sizeof(data))
        return bool(payload)
    class Library:
        GetOpenFileNameW = staticmethod(native)
        CommDlgExtendedError = staticmethod(lambda: error)
    monkeypatch.setattr(ctypes, "WinDLL", lambda *args, **kwargs: Library())
    if error:
        with pytest.raises(OSError, match="00003003"):
            file_dialog.choose_files(interactive=True)
    else:
        files = file_dialog.choose_files(interactive=True)
        assert len(files) == (2 if payload else 0)
    assert len(calls) == 1
    flags, actual_filter, size, struct_size = calls[0]
    assert flags & 0x200 and flags & 0x80000 and flags & 0x8 and size == file_dialog.BUFFER_CHARS
    assert actual_filter == file_dialog.FILTER
    assert "*.json;*.zip\0" in file_dialog.FILTER and struct_size == (152 if ctypes.sizeof(ctypes.c_void_p) == 8 else 88)


def test_headless_and_other_platform_never_open_dialog(monkeypatch):
    def fail():
        raise AssertionError("headless must not invoke native UI")
    monkeypatch.setattr(file_dialog, "_native_dialog", fail)
    assert file_dialog.choose_files(interactive=False) is None
    monkeypatch.setattr(file_dialog.os, "name", "posix")
    assert file_dialog.choose_files(interactive=True) is None


def test_manual_paths_mixed_unicode_and_tui_policy_are_campaign_scoped(local, tmp_path):
    files = [emit(local, tmp_path, "E1-A", name="a żółć.json"), emit(local, tmp_path, "E1-B", zipped=True, name="b ze spacją.zip")]
    value = ' | '.join('"' + str(p) + '"' for p in files)
    assert parse_manual_paths(value) == list(map(str, files))
    text = tui(local, tmp_path, ["2", "O", str(local.store.root), "7", "WLACZ AUTO LOCAL", "m", value, "0", "0"], Actions())
    assert "Zapisano politykę" in text and "Przyjęto AUTO: 2" in text
    current = LocalWorkflow(local.store.root)
    assert current.acceptance_policy["enabled"] and len(current.accepted) == 2


def test_gui_failure_falls_back_to_manual_without_losing_the_batch(local, tmp_path):
    enable(local)
    file = emit(local, tmp_path)
    class Unavailable(Actions):
        def choose_results(self, *, interactive):
            self.dialog_calls += 1
            raise OSError("TEST_FIXTURE GUI unavailable")
    actions = Unavailable()
    text = tui(local, tmp_path, ["2", "O", str(local.store.root), "3", str(file), "0", "0"], actions)
    assert actions.dialog_calls == 1 and "Dostępne ręczne wskazanie" in text
    assert LocalWorkflow(local.store.root).accepted.keys() == {"E1-A"}


def test_tui_conflict_keeps_explicit_manual_replacement_and_full_preview(local, tmp_path):
    enable(local)
    local.import_results([emit(local, tmp_path)])
    previous = local.accepted["E1-A"]
    revision = emit(local, tmp_path, name="manual revision.json", limitations=["Disclosed manual revision"])
    local.import_results([revision])
    text = tui(local, tmp_path, ["2", "O", str(local.store.root), "i", "w", "1", "s", "1", "ROZPATRZ REWIZJE",
                                "AKCEPTUJ LOCAL", previous, "0", "0", "0"], Actions())
    current = LocalWorkflow(local.store.root)
    assert current.accepted["E1-A"] != previous and current.results[current.accepted["E1-A"]]["acceptance_mechanism"] == "MANUAL"
    assert "Disclosed manual revision" in text and "Oddzielny ręczny podgląd" in text


def test_new_campaign_retains_technical_json_view(repo, tmp_path):
    campaign = tmp_path / "new campaign"
    text = tui(None, tmp_path, ["1", str(repo), "HEAD", "", str(campaign), "0", "0"], Actions())
    assert '"paths"' in text and '"app.py"' in text and '"snapshot_sha256"' in text and '"campaign_id"' in text
    assert LocalWorkflow(campaign).stage == "E1"


def test_cli_preflight_prompt_and_batch_use_production_validator(local, tmp_path, capsys):
    file = emit(local, tmp_path)
    base = ["product", "local"]
    campaign = ["--campaign", str(local.store.root)]
    before = local.store.path.read_bytes()
    assert run_cli([*base, "prompt", *campaign, "--task", "E1-A"]) == 0
    assert parse(capsys.readouterr().out.encode())["text"] == local.prompt("E1-A")["text"]
    assert run_cli([*base, "inspect", *campaign, "--file", str(file)]) == 0
    assert parse(capsys.readouterr().out.encode())["issues"] == []
    assert local.store.path.read_bytes() == before
    assert run_cli([*base, "policy", *campaign, "--auto-accept", "on", "--actor", "TEST_FIXTURE authorizer"]) == 0
    capsys.readouterr()
    bad = emit(LocalWorkflow(local.store.root), tmp_path, "E1-B", name="bad.json", source_commit="0" * 40)
    assert run_cli([*base, "import-batch", *campaign, "--file", str(file), "--file", str(bad)]) == 2
    batch = parse(capsys.readouterr().err.encode())
    assert (batch["accepted"], batch["rejected"]) == (1, 1)


def test_batch_file_and_input_limits_fail_closed(local, tmp_path, monkeypatch):
    from dataclasses import replace
    from bdb_audit.local_product import workflow
    before = local.head
    with pytest.raises(ValidationError, match="LOCAL_BATCH_FILE_LIMIT"):
        local.import_results([tmp_path / "never opened"] * 129)
    assert local.head == before
    assert local.import_results([])["status"] == "CANCELLED" and local.head == before
    monkeypatch.setattr(workflow, "RESULT_LIMITS", replace(workflow.RESULT_LIMITS, input_bytes=8))
    file = tmp_path / "oversized.json"
    file.write_bytes(b"x" * 9)
    batch = local.import_results([file, tmp_path / "missing.json"])
    assert batch["rejected"] == 2 and "raw" not in batch["items"][0]
    assert not local.results


def test_out_of_range_integer_rejects_one_file_and_keeps_processing(local, tmp_path):
    bad = tmp_path / "huge-integer.json"
    bad.write_bytes(b'{"untrusted":' + b"9" * 4301 + b"}")
    good = emit(local, tmp_path)
    result = local.import_results([bad, good])
    assert result["status"] == "FINISHED" and result["processed"] == 2
    assert result["items"][0]["issues"] == ["CJSON_INTEGER_RANGE"]
    assert result["items"][1]["outcome"] == "VALIDATED"
    assert local.batch_item_info(result["batch_id"], 0)["parse_error"] == "CJSON_INTEGER_RANGE"


def test_concurrent_batch_returns_its_own_summary(local, tmp_path, monkeypatch):
    good = emit(local, tmp_path)
    other_file = tmp_path / "other.json"
    other_file.write_text("invalid", encoding="utf-8")
    append_many = local.store.append_many
    other = {}

    def interleave(entries, expected_head, **kwargs):
        head = append_many(entries, expected_head, **kwargs)
        if entries[0][0] == "BATCH_FINISHED":
            other.update(LocalWorkflow(local.store.root).import_results([other_file]))
        return head

    monkeypatch.setattr(local.store, "append_many", interleave)
    result = local.import_results([good])
    assert result["batch_id"] != other["batch_id"]
    assert result["items"][0]["file"] == str(good)
    assert result["items"][0]["outcome"] == "VALIDATED"
    assert local.batch_summaries()[-1]["batch_id"] == other["batch_id"]


def test_old_batch_stays_available_and_task_id_cannot_add_a_tui_row(local, tmp_path):
    first = emit(local, tmp_path, name="first.json", task_id="E1-A\n2. forged.json | OK — accepted\u2028")
    second = emit(local, tmp_path, name="second.json", task_id="unknown")
    first_batch = local.import_results([first])
    local.import_results([second])
    screen = tui(local, tmp_path, ["2", "O", str(local.store.root), "I", "H", "2", "W", "1", "0", "0", "0"])
    assert first_batch["batch_id"] in screen
    assert "1. first.json" in screen and "REFUSED_UNTRUSTED" in screen
    assert "\n2. forged.json" not in screen
    assert r"\u000a2. forged.json" in screen and "\u2028" not in screen


def test_batch_does_not_reread_the_verified_prefix_for_each_file(local, tmp_path, monkeypatch):
    paths = []
    for index in range(32):
        path = tmp_path / f"rejected-{index}.json"
        path.write_bytes(f"invalid JSON {index}".encode())
        paths.append(path)
    read_bytes = local.store.vault.read_bytes
    reads = 0

    def count_read(digest):
        nonlocal reads
        reads += 1
        return read_bytes(digest)

    monkeypatch.setattr(local.store.vault, "read_bytes", count_read)
    assert local.import_results(paths)["rejected"] == len(paths)
    assert reads < 5 * len(paths) + 100


@pytest.mark.parametrize("old_stage_already_committed", [False, True])
def test_prior_attachment_overflow_preserves_identities_and_keeps_stage_usable(local, tmp_path, old_stage_already_committed):
    enable(local)
    attachments = {f"note-{i:03}.txt": b"a" for i in range(412)}
    refs = [{"path": name, "sha256": sha(data), "byte_length": len(data)} for name, data in attachments.items()]
    files = []
    for task in local._available_tasks():
        body = response(local, task, evidence_files=refs)
        file = tmp_path / f"{task}.zip"
        file.write_bytes(_deterministic_zip({"LOCAL_RESULT.json": canonical_bytes(body), **attachments}))
        files.append(file)
    assert local.import_results(files)["accepted"] == 5
    if old_stage_already_committed:
        # The former path committed this event before failing to build E2.
        local._append("STAGE_COMPLETED", local._finish_payload())
        local = LocalWorkflow(local.store.root)
        assert local.prepare()["stage"] == "E2"
    else:
        assert local.advance()["stage"] == "E2"
    reopened = LocalWorkflow(local.store.root)
    task = "E2-CONVERGENCE"
    archive = read_bytes(reopened.store.vault.read_bytes(reopened.packages[task]["raw"]["raw_digest"]))
    manifest = parse(archive["MANIFEST.json"])
    prior = parse(archive["PRIOR_RESULTS.json"])
    assert manifest["prior_attachments"] == "RETAINED_IN_VAULT"
    assert len(prior) == 5 and all(p["response"]["evidence_files"] == refs for p in prior)
    assert not any(name.startswith("prior/") for name in archive)
    assert "Treat absent attachments as unreviewed" in reopened.prompt(task)["text"]
    assert all(reopened.store.vault.read_bytes(r["raw"]["raw_digest"]) in [p.read_bytes() for p in files]
               for r in reopened.results.values())


def test_failed_package_preparation_does_not_commit_stage_transition(local, tmp_path, monkeypatch):
    enable(local)
    assert local.import_results([emit(local, tmp_path, task) for task in local._available_tasks()])["accepted"] == 5
    before = local.head
    package_bytes = local._package_bytes

    def fail_next_package(task, generator_version, *, stage=None):
        if stage == "E2" and task == local._available_tasks("E2")[-1]:
            raise ValidationError("LOCAL_PACKAGE_RESOURCE_LIMIT")
        return package_bytes(task, generator_version, stage=stage)

    monkeypatch.setattr(local, "_package_bytes", fail_next_package)
    with pytest.raises(ValidationError, match="LOCAL_PACKAGE_RESOURCE_LIMIT"):
        local.advance()
    reopened = LocalWorkflow(local.store.root)
    assert reopened.head == before and reopened.stage == "E1" and not reopened.completed
    assert reopened.advance()["stage"] == "E2"


def test_large_valid_results_can_be_exported_and_verified(local, tmp_path):
    enable(local)
    limitations = ["a" * 95_000] * 19
    files = [emit(local, tmp_path, task, limitations=limitations) for task in local._available_tasks()]
    assert local.import_results(files)["accepted"] == 5
    controller = CampaignController(local.store.root)
    root = Path(controller.export_report()["output"])
    assert (root / "REPORT.json").stat().st_size > 16 * 1024 * 1024
    verified = controller.verify_report(root)
    assert verified["verified"] and verified["accepted_count"] == 5
    raw = controller.open_report(root, "json").encode("utf-8")
    assert parse(raw, max_bytes=REPORT_JSON_LIMIT)["accepted_responses"][0]["response"]["limitations"] == limitations
