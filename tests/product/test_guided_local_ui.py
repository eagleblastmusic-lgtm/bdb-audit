"""Guided UX acceptance regressions. Inputs disclose TEST_FIXTURE provenance."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import os
import shutil
import subprocess

import pytest

from bdb_audit.core.canonical_json import canonical_bytes, parse
from bdb_audit.core.errors import ValidationError
from bdb_audit.local_product.artifacts import WindowsActions
from bdb_audit.local_product.guided import CampaignController
from bdb_audit.local_product.profile import STAGES
from bdb_audit.local_product.recent import RecentCampaigns
from bdb_audit.local_product.store import sha
from bdb_audit.local_product.ui import run_local_ui
from bdb_audit.local_product.workflow import LocalWorkflow
from bdb_audit.workflow.packaging import _deterministic_zip
from test_local_product import local as local_fixture, repo as repo_fixture, response, accept_fixture


@pytest.fixture(name="repo")
def _repo(tmp_path):
    return repo_fixture.__wrapped__(tmp_path)


@pytest.fixture(name="local")
def _local(repo, tmp_path):
    return local_fixture.__wrapped__(repo, tmp_path)


class RecordedActions(WindowsActions):
    def __init__(self):
        self.calls = []

    def select(self, path):
        self.calls.append(("select", str(path)))

    def folder(self, path):
        self.calls.append(("folder", str(path)))

    def clipboard(self, path):
        self.calls.append(("clipboard", str(path)))
        return False

    def document(self, path):
        self.calls.append(("document", str(path)))


def tui(tmp_path, inputs, actions=None):
    output = []
    iterator = iter(inputs)
    assert run_local_ui(lambda _: next(iterator), output.append, index_path=tmp_path / "recent.json",
                        actions=actions, actor="explicit TEST_FIXTURE operator") == 0
    return "\n".join(output)


def snapshot(workflow):
    current = LocalWorkflow(workflow.store.root)
    return current.head, current.store.path.read_bytes(), sorted(str(p) for p in current.store.root.rglob("*"))


def test_main_menu_has_four_product_actions_and_no_startup_open(tmp_path):
    actions = RecordedActions()
    text = tui(tmp_path, ["0"], actions)
    menu = text.split("BDB Audit                         LOCAL PRODUCT MODE")[-1].strip().splitlines()
    assert menu == ["1 Nowy audyt", "2 Moje audyty", "3 Raporty", "4 Ustawienia i narzędzia", "0 Wyjście"]
    assert not actions.calls and not (tmp_path / "recent.json").exists()


def test_screen_is_read_only_and_restores_exact_package_status(local):
    controller = CampaignController(local.store.root)
    before = snapshot(local)
    first = controller.view()
    assert first["next"]["action"] == "prepare" and len(first["packages"]) == 5
    assert snapshot(local) == before
    controller.prepare()
    before = snapshot(local)
    view = controller.view()
    assert all(row["raw_verified"] and row["expected_sha256"] == row["actual_sha256"] for row in view["packages"])
    assert view["next"]["action"] == "import"
    assert CampaignController(local.store.root).view() == view and snapshot(local) == before


def test_stage_lists_use_engine_and_e5_gate(local, tmp_path):
    controller = CampaignController(local.store.root)
    for stage, definitions in STAGES.items():
        controller.prepare()
        view = controller.view()
        assert view["stage"] == stage
        assert [row["task_id"] for row in view["packages"]] == [task for task, _, _ in definitions]
        assert [row["title"] for row in view["packages"]] == [title for _, title, _ in definitions]
        assert sum(row["path"] is not None for row in view["packages"]) == (3 if stage == "E5" else len(definitions))
        while True:
            workflow = controller.workflow()
            pending = [task for task in workflow._available_tasks() if task not in workflow.accepted]
            if not pending:
                break
            controller.prepare()
            for task in pending:
                accept_fixture(controller.workflow(), tmp_path, task)
        # E5-B is prepared only after the actual accepted A inputs.
        assert controller.view()["next"]["action"] == "advance"
        controller.advance(controller.workflow().head)
    view = controller.view()
    assert view["workflow_stage"] == "COMPLETE" and view["accepted_count"] == 19
    report = controller.export_report()
    assert controller.view()["next"]["label"] == "Otwórz raport"
    body = parse(controller.open_report(report["output"], "json").encode())
    assert body["contains_test_fixtures"] and len(body["accepted_responses"]) == 19
    assert {p["declared_producer"]["kind"] for p in body["declared_producers"]} == {"TEST_FIXTURE"}
    actions = RecordedActions()
    before = snapshot(controller.workflow())
    text = tui(tmp_path, ["2", "O", str(local.store.root), "", "0", "0"], actions)
    assert actions.calls == [("document", str(Path(report["output"]) / "REPORT.md"))]
    assert "Działanie raportu:" not in text and snapshot(controller.workflow()) == before


@pytest.mark.parametrize("action", ["select", "folder", "clipboard", "copy"])
def test_changed_zip_refuses_every_file_action_without_mutation(local, tmp_path, action):
    local.prepare()
    actions = RecordedActions()
    controller = CampaignController(local.store.root, actions=actions)
    path = local.store.root / "packages/E1-A.zip"
    path.write_bytes(b"substituted bytes")
    before = snapshot(local)
    destination = tmp_path / "copy destination"
    destination.mkdir()
    with pytest.raises(ValidationError, match="LOCAL_ARTIFACT_HASH_MISMATCH"):
        if action == "select":
            controller.select_package("E1-A")
        elif action == "folder":
            controller.open_package_folder()
        elif action == "clipboard":
            controller.copy_package_path("E1-A")
        else:
            controller.export_package("E1-A", destination)
    assert controller.view()["packages"][0]["state"] == "NIESPÓJNA"
    assert not actions.calls and snapshot(local) == before and not list(destination.iterdir())


def test_missing_zip_restores_from_vault_without_new_history(local):
    local.prepare()
    path = local.store.root / "packages/E1-A.zip"
    raw = path.read_bytes()
    path.unlink()
    controller = CampaignController(local.store.root, actions=RecordedActions())
    before = local.head
    assert controller.view()["packages"][0]["state"] == "BRAK PLIKU"
    with pytest.raises(ValidationError, match="LOCAL_ARTIFACT_MISSING"):
        controller.select_package("E1-A")
    controller.prepare()
    assert path.read_bytes() == raw and controller.workflow().head == before


@pytest.mark.parametrize("redirect", ["directory", "file"])
def test_actual_reparse_or_symlink_is_refused(local, tmp_path, redirect):
    local.prepare()
    foreign = tmp_path / "outside artifacts żółć"
    foreign.mkdir()
    source = local.store.root / "packages"
    actions = RecordedActions()
    if redirect == "directory":
        shutil.copyfile(source / "E1-A.zip", foreign / "E1-A.zip")
        backup = source.with_name("original-packages")
        assert source.resolve().is_relative_to(tmp_path) and backup.absolute().is_relative_to(tmp_path)
        source.rename(backup)
        if os.name == "nt":
            result = subprocess.run(["cmd", "/c", "mklink", "/J", str(source), str(foreign)], capture_output=True)
            assert result.returncode == 0, result.stderr
        else:
            source.symlink_to(foreign, target_is_directory=True)
    else:
        path = source / "E1-A.zip"
        shutil.copyfile(path, foreign / "E1-A.zip")
        path.unlink()
        try:
            path.symlink_to(foreign / "E1-A.zip")
        except OSError as exc:
            if os.name == "nt" and getattr(exc, "winerror", None) == 1314:
                pytest.skip("Host lacks file symlink privilege; actual Windows junction is tested separately")
            raise
    before = snapshot(local)
    controller = CampaignController(local.store.root, actions=actions)
    with pytest.raises(ValidationError, match="LOCAL_ARTIFACT_REDIRECTED"):
        controller.select_package("E1-A")
    with pytest.raises(ValidationError, match="LOCAL_ARTIFACT_REDIRECTED"):
        controller.prepare()
    assert controller.view()["packages"][0]["state"] == "NIESPÓJNA"
    assert not actions.calls and snapshot(local) == before


def test_unicode_space_paths_clipboard_fallback_and_exclusive_copy(repo, tmp_path):
    workflow = LocalWorkflow.start(tmp_path / "kampania ze spacją żółć", str(repo), "HEAD")
    workflow.prepare()
    actions = RecordedActions()
    controller = CampaignController(workflow.store.root, actions=actions)
    path = controller.select_package("E1-A")
    assert "żółć" in str(path) and " " in str(path)
    assert controller.open_package_folder() == path.parent
    assert controller.copy_package_path("E1-A") == {"path": str(path), "copied": False}
    destination = tmp_path / "kopie żółć"
    destination.mkdir()
    before = snapshot(workflow)
    copy = controller.export_package("E1-A", destination)
    assert sha(copy.read_bytes()) == sha(path.read_bytes())
    with pytest.raises(FileExistsError):
        controller.export_package("E1-A", destination)
    with pytest.raises(ValidationError, match="LOCAL_COPY_PROTECTED_PATH"):
        controller.export_package("E1-A", workflow.store.root)
    assert snapshot(workflow) == before


def test_windows_explorer_argument_vector_and_error_reporting(local, tmp_path, monkeypatch):
    if os.name != "nt":
        pytest.skip("Windows argument-vector test")
    local.prepare()
    calls = []
    class Process:
        def wait(self, timeout):
            return 0
    def launch(argv, **kwargs):
        calls.append((argv, kwargs))
        return Process()
    monkeypatch.setattr("bdb_audit.local_product.artifacts.subprocess.Popen", launch)
    controller = CampaignController(local.store.root)
    path = controller.select_package("E1-A")
    assert calls[0][0][1:] == ["/select,", str(path)] and calls[0][1]["shell"] is False
    def failed(argv, **kwargs):
        raise PermissionError("actual injected launch refusal")
    monkeypatch.setattr("bdb_audit.local_product.artifacts.subprocess.Popen", failed)
    before = snapshot(local)
    text = tui(tmp_path, ["2", "O", str(local.store.root), "2", "1", "1", "0", "0", "0"])
    assert "actual injected launch refusal" in text and str(path) in text
    assert "Przekazano Eksploratorowi zaznaczenie" not in text and snapshot(local) == before


def test_explorer_handoff_requires_successful_shell_confirmation(monkeypatch, tmp_path):
    actions = WindowsActions()
    path = tmp_path / "spacja żółć.zip"
    monkeypatch.setattr(actions, "_explorer", lambda *args: 1)
    calls = []
    def confirm(selected):
        calls.append(selected)
    monkeypatch.setattr(actions, "_select_with_shell", confirm)
    actions.select(path)
    assert calls == [path]
    def fail(selected):
        raise OSError("Shell HRESULT refused")
    monkeypatch.setattr(actions, "_select_with_shell", fail)
    with pytest.raises(OSError, match="Shell HRESULT refused"):
        actions.select(path)
    monkeypatch.setattr(actions, "_explorer", lambda *args: 2)
    with pytest.raises(OSError, match="kodem 2"):
        actions.select(path)


@pytest.mark.parametrize("defect", ["context", "path", "unsafe_zip", "malformed", "attachment"])
def test_import_preflight_negative_cases_leave_no_mutation(local, tmp_path, defect):
    body = response(local)
    path = tmp_path / "bad.zip"
    if defect == "context":
        body["campaign_id"] = "foreign"
        raw = canonical_bytes(body)
    elif defect == "path":
        body["artifact_path"] = str(tmp_path / "outside.zip")
        raw = canonical_bytes(body)
    elif defect == "unsafe_zip":
        raw = _deterministic_zip({"LOCAL_RESULT.json": canonical_bytes(body), "../outside.zip": b"evil"})
    elif defect == "attachment":
        body["evidence_files"] = [{"path": "e.txt", "sha256": "0" * 64, "byte_length": 1}]
        raw = _deterministic_zip({"LOCAL_RESULT.json": canonical_bytes(body), "e.txt": b"x"})
    else:
        raw = b"{malformed"
    path.write_bytes(raw)
    before = snapshot(local)
    with pytest.raises(ValidationError):
        CampaignController(local.store.root).import_result(path)
    assert snapshot(local) == before


def test_import_preview_cancel_resume_and_separate_accept(local, tmp_path):
    path = tmp_path / "response.json"
    path.write_bytes(canonical_bytes(response(local)))
    text = tui(tmp_path, ["2", "O", str(local.store.root), "", str(path), "", "0", "0"])
    current = LocalWorkflow(local.store.root)
    assert not current.accepted
    assert next(iter(current.results.values()))["state"] == "VALIDATED_STRUCTURE"
    assert "PODGLĄD" in text and "WYMAGA_DECYZJI" in text
    before = snapshot(current)
    tui(tmp_path, ["2", "1", "0", "0"])
    assert snapshot(current) == before
    text = tui(tmp_path, ["2", "1", "", "AKCEPTUJ LOCAL", "0", "0"])
    current = LocalWorkflow(local.store.root)
    assert current.accepted["E1-A"] in current.results and "USER_ACCEPTED_LOCAL" in text


def test_explicit_reject_and_stale_preview_cannot_accept(local, tmp_path):
    path = tmp_path / "response.json"
    path.write_bytes(canonical_bytes(response(local)))
    controller = CampaignController(local.store.root)
    rid = controller.import_result(path)["result_id"]
    preview = controller.preview(rid)
    other = deepcopy(response(local, "E1-B"))
    other_path = tmp_path / "other.json"
    other_path.write_bytes(canonical_bytes(other))
    controller.import_result(other_path)
    before = snapshot(local)
    with pytest.raises(ValidationError, match="LOCAL_SCREEN_CHANGED"):
        controller.decide(rid, "AKCEPTUJ LOCAL", actor="fixture", expected_head=preview["history_head"])
    assert snapshot(local) == before
    fresh = controller.preview(rid)
    controller.decide(rid, "ODRZUC", actor="fixture", expected_head=fresh["history_head"], reason="fixture rejection")
    assert controller.view()["packages"][0]["result_state"] == "ODRZUCONY"
    assert not controller.workflow().accepted


def test_stage_transition_requires_all_results_and_confirmation(local, tmp_path):
    local.prepare()
    controller = CampaignController(local.store.root)
    before = snapshot(local)
    with pytest.raises(ValidationError, match="LOCAL_STAGE_RESULTS_MISSING"):
        controller.advance(local.head)
    assert snapshot(local) == before
    for task in local._available_tasks():
        accept_fixture(local, tmp_path, task)
    before = snapshot(local)
    text = tui(tmp_path, ["2", "O", str(local.store.root), "", "", "0", "0"])
    assert "Przejdź do E2" in text and snapshot(local) == before
    tui(tmp_path, ["2", "1", "", "PRZEJDZ E2", "0", "0"])
    assert LocalWorkflow(local.store.root).stage == "E2"


def test_reports_from_tui_validate_hashes_and_do_not_overwrite(local, tmp_path):
    local.prepare()
    actions = RecordedActions()
    text = tui(tmp_path, ["2", "O", str(local.store.root), "5", "n", "", "1", "2", "3", "0", "0", "0", "0"], actions)
    controller = CampaignController(local.store.root, actions=actions)
    rows = controller.reports()
    root = Path(rows[0]["path"])
    assert rows[0]["verified"] and "BDB_LOCAL_AUDIT_REPORT_1" in text
    assert actions.calls == [("document", str(root / "REPORT.md")), ("folder", str(root))]
    head = controller.workflow().head
    with pytest.raises(ValidationError, match="LOCAL_REPORT_OUTPUT_EXISTS"):
        controller.export_report(root)
    (root / "REPORT.md").write_text("changed report", encoding="utf-8")
    count = len(actions.calls)
    with pytest.raises(ValidationError, match="LOCAL_ARTIFACT_HASH_MISMATCH"):
        controller.open_report(root, "markdown")
    assert len(actions.calls) == count and controller.workflow().head == head


def test_recent_index_is_shortcut_and_missing_store_is_not_recreated(local, tmp_path):
    recent = RecentCampaigns(tmp_path / "recent.json")
    recent.remember(local)
    (local.store.path).rename(local.store.path.with_suffix(".saved"))
    before = sorted(str(p) for p in local.store.root.rglob("*"))
    row = recent.entries()[0]
    assert row["state"] == "BRAK / NIESPÓJNY STORE" and "LOCAL_CAMPAIGN_NOT_FOUND" in row["error"]
    with pytest.raises(ValidationError, match="LOCAL_CAMPAIGN_NOT_FOUND"):
        CampaignController(row["path"])
    assert sorted(str(p) for p in local.store.root.rglob("*")) == before


def test_navigation_never_auto_accepts_untrusted_results(local, tmp_path):
    path = tmp_path / "untrusted.json"
    path.write_bytes(canonical_bytes(response(local)))
    local.import_result(path)
    before = snapshot(local)
    text = tui(tmp_path, ["2", "O", str(local.store.root), "6", "1", "4", "0", "0", "4", "0", "0"])
    assert "R Odzyskaj receipt" not in text and "A Porzuć" not in text
    assert snapshot(local) == before and not LocalWorkflow(local.store.root).accepted


def test_pending_tools_require_explicit_abandonment_and_keep_reason(local, tmp_path, monkeypatch):
    local.prepare()
    def interrupted(self, spec):
        raise RuntimeError("explicit pending-run fixture; no completed execution")
    monkeypatch.setattr("bdb_audit.local_product.workflow.ToolSupervisor.run", interrupted)
    with pytest.raises(RuntimeError):
        local.run_check("E1-A", ["fixture-never-executed"])
    current = LocalWorkflow(local.store.root)
    run_id = next(iter(current.pending_runs))
    before = snapshot(current)
    text = tui(tmp_path, ["2", "O", str(local.store.root), "", "a", run_id, "fixture reason", "", "0", "0", "0"])
    assert "Odzyskaj receipt" in text and snapshot(current) == before
    tui(tmp_path, ["2", "1", "", "a", run_id, "fixture reason", "PORZUC", "0", "0", "0"])
    current = LocalWorkflow(local.store.root)
    assert not current.pending_runs and current.abandoned_runs[0]["reason"] == "fixture reason"
    assert not current.accepted and current.stage == "E1"


def test_invalid_source_wizard_preserves_campaign_absence(tmp_path):
    campaign = tmp_path / "must-not-be-created"
    text = tui(tmp_path, ["1", str(tmp_path / "missing-source"), "", "", str(campaign), "0"])
    assert "ODMOWA:" in text and not campaign.exists()


def test_untrusted_directional_characters_are_visible_in_review(local, tmp_path):
    body = response(local, limitations=["Untrusted directional marker: \u202e disguised text"])
    path = tmp_path / "directional.json"
    path.write_bytes(canonical_bytes(body))
    text = tui(tmp_path, ["2", "O", str(local.store.root), "3", str(path), "", "0", "0"])
    assert "\\u202e" in text and "\u202e" not in text
    assert not LocalWorkflow(local.store.root).accepted


@pytest.mark.parametrize("defect", ["root", "missing_hash", "missing_responses", "path_type"])
def test_malformed_report_refuses_without_crash_or_open(local, defect):
    controller = CampaignController(local.store.root, actions=RecordedActions())
    root = Path(controller.export_report()["output"])
    manifest = parse((root / "EVIDENCE_MANIFEST.json").read_bytes())
    if defect in {"root", "missing_responses"}:
        body = parse((root / "REPORT.json").read_bytes())
        if defect == "root":
            body = 1
        else:
            del body["accepted_responses"]
        raw = canonical_bytes(body)
        (root / "REPORT.json").write_bytes(raw)
        entry = next(e for e in manifest["reports"] if e["path"] == "REPORT.json")
        entry.update(sha256=sha(raw), byte_length=len(raw))
    elif defect == "missing_hash":
        del manifest["reports"][0]["sha256"]
    else:
        manifest["reports"][0]["path"] = ["REPORT.json"]
    (root / "EVIDENCE_MANIFEST.json").write_bytes(canonical_bytes(manifest))
    before = snapshot(local)
    with pytest.raises(ValidationError):
        controller.open_report(root, "markdown")
    assert not controller.actions.calls and snapshot(local) == before
    assert controller.reports()[0]["verified"] is False
