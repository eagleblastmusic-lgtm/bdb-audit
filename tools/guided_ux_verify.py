"""Exact guided LOCAL delivery readback; this is not NF02 qualification."""
from __future__ import annotations

import argparse
from contextlib import redirect_stderr, redirect_stdout
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
from typing import Any
import xml.etree.ElementTree as ET

from bdb_audit.cli import run_cli
from bdb_audit.local_product.guided import CampaignController
from bdb_audit.local_product.profile import STAGES
from bdb_audit.local_product.workflow import LocalWorkflow
from tools.local_product_verify import frozen_readback

ROOT = Path(__file__).resolve().parents[1]
HERE = ROOT / "docs/GUIDED_UX"
DEMO = ROOT / ".product-smoke/guided-ux-20261012-v4"
CAMPAIGN = DEMO / "campaign ze spacją żółć"
MANIFEST = HERE / "EVIDENCE_MANIFEST.json"
ARTIFACT = ROOT / "dist/BDB_AUDIT_LOCAL_PRODUCT.py"


def file_info(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def build_readback() -> dict[str, Any]:
    spec = importlib.util.spec_from_file_location("guided_ux_artifact_readback", ARTIFACT)
    assert spec is not None and spec.loader is not None
    artifact = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(artifact)
    verified = artifact.verify_embedded_payload()
    files = list((ROOT / "src").rglob("*.py")) + list((ROOT / "src/bdb_audit/core").glob("*.json"))
    for path in files:
        relative = path.relative_to(ROOT / "src").as_posix()
        assert artifact.get_embedded_resource(relative) == path.read_bytes().replace(b"\r\n", b"\n"), relative
    return {"status": "EXACT_SOURCE_AND_PAYLOAD_PASS", "embedded_files": len(verified),
            "source_files_checked": len(files), "payload_manifest_digest": artifact.PAYLOAD_MANIFEST_DIGEST,
            "artifact": file_info(ARTIFACT)}


def high_assurance_boundary() -> dict[str, Any]:
    workflow = LocalWorkflow(CAMPAIGN)
    before = workflow.store.path.read_bytes()
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = run_cli(["product", "import", "--store", str(workflow.store.path),
                        "--zip", str(DEMO / "actual-local-responses/E1-A.zip"), "--json"])
    reply = json.loads(out.getvalue() + err.getvalue())
    assert code == 2 and reply["external_ingestion"] == "BLOCKED"
    assert workflow.store.path.read_bytes() == before
    return {"status": "BLOCKED_AS_REQUIRED", "exit_code": code, "external_ingestion": reply["external_ingestion"],
            "local_database_unchanged": True, "frozen_model": frozen_readback()}


def demo_readback() -> dict[str, Any]:
    workflow = LocalWorkflow(CAMPAIGN)
    assert workflow.stage == "COMPLETE" and workflow.completed == list(STAGES)
    assert len(workflow.accepted) == sum(len(tasks) for tasks in STAGES.values()) == 19
    producers = [r["response"]["producer"]["kind"] for r in workflow.results.values()]
    assert set(producers) == {"LOCAL_CONTROL"}
    controller = CampaignController(CAMPAIGN)
    report = json.loads(controller.open_report(DEMO / "final-report", "json"))
    assert report["status"] == "LOCAL_COMPLETED" and not report["contains_test_fixtures"]
    assert report["input_history_head"] == workflow.head and len(report["accepted_responses"]) == 19
    assert all(not item["identity_verified"] for item in report["declared_producers"])
    assert len(workflow.runs) == 2 and not workflow.pending_runs
    stderr = workflow.store.vault.read_bytes(workflow.runs[0]["files"]["stderr.bin"]["raw_digest"])
    assert b"Ran 6 tests" in stderr and b"failures=3" in stderr
    sessions = json.loads((DEMO / "TUI_SESSIONS.json").read_bytes())
    transcript = (DEMO / "TUI_TRANSCRIPT.txt").read_bytes()
    for session in sessions:
        raw = transcript[session["offset"]:session["offset"] + session["byte_length"]]
        assert hashlib.sha256(raw).hexdigest() == session["sha256"]
        assert session["exit_code"] == 0
        assert (b"ODMOWA:" in raw) == session["expected_refusal"]
    assert len(sessions) == 41 and sum(s["expected_refusal"] for s in sessions) == 2
    assert (DEMO / "REAL_TUI_PROCESS_RESTART.txt").is_file()
    assert all(row["raw_verified"] for row in controller.view()["packages"])
    return {"status": "REAL_GUIDED_LOCAL_E1_E6_PASS", "campaign_id": workflow.campaign_id,
            "history_head": workflow.head, "accepted_local_controls": len(workflow.accepted),
            "imported_local_controls": len(producers), "rejected_local_controls": sum(r["state"] == "REJECTED" for r in workflow.results.values()),
            "external_ai": 0, "test_fixtures": 0, "actual_tool_runs": 2, "guided_tui_sessions": len(sessions),
            "source_commit": workflow.source["commit"], "source_tree": workflow.source["tree"],
            "actual_demo_tests": {"total": 6, "pass": 3, "intentional_defects_detected": 3},
            "report_verified": True, "restart_without_acceptance_verified": True}


def test_readback() -> dict[str, Any]:
    ids: set[str] = set()
    skips = []
    for path in (HERE / "evidence").glob("*.xml"):
        cases = list(ET.parse(path).iter("testcase"))
        assert cases, str(path)
        for case in cases:
            assert case.find("failure") is None and case.find("error") is None, (str(path), case.attrib)
            key = case.attrib.get("classname", "") + "::" + case.attrib["name"]
            if case.find("skipped") is not None:
                assert "test_actual_reparse_or_symlink_is_refused[file]" in key, key
                skips.append(key)
            else:
                ids.add(key)
    assert any("test_main_menu_has_four_product_actions" in key for key in ids)
    assert any("test_wrong_raw_digest_and_qualified_import_refuse_without_mutation" in key for key in ids)
    assert any("test_pending_tools_require_explicit_abandonment" in key for key in ids)
    return {"passed_unique_cases": len(ids), "allowed_skips": sorted(set(skips)), "failures": 0, "errors": 0}


def standalone_checks(*, open_explorer: bool = False) -> None:
    evidence = HERE / "evidence"
    evidence.mkdir(parents=True, exist_ok=True)
    def command(name: str, args: list[str], answers: str | None = None) -> bytes:
        proc = subprocess.run([sys.executable, "-I", "-S", str(ARTIFACT), *args],
                              input=None if answers is None else answers.encode("utf-8"), capture_output=True)
        (evidence / name).write_bytes(proc.stdout + proc.stderr)
        assert proc.returncode == 0, proc.stderr.decode("utf-8", errors="replace")
        return proc.stdout
    assert json.loads(command("standalone-payload.json", ["--verify-payload"]))["status"] == "PASS"
    assert json.loads(command("standalone-resume.json", ["product", "local", "resume", "--campaign", str(CAMPAIGN)]))["stage"] == "COMPLETE"
    before = LocalWorkflow(CAMPAIGN).head
    # Read-only navigation is the default. Native opening was exercised in the
    # retained live smoke and is repeated only when explicitly requested.
    answers = "2\n1\n2\n1\n1\n0\n0\n0\n" if open_explorer else "2\n1\n5\n1\n2\n0\n0\n0\n0\n"
    text = command("standalone-tui.txt", ["product", "local", "ui", "--index", str(DEMO / "recent.json")], answers)
    assert b"E6-FOLLOWUP" in text and b"ODMOWA:" not in text and "Raport gotowy".encode() in text
    assert LocalWorkflow(CAMPAIGN).head == before
    export = DEMO / "standalone-report"
    if not export.exists():
        command("standalone-export.json", ["product", "local", "report", "--campaign", str(CAMPAIGN), "--output", str(export)])
    CampaignController(CAMPAIGN).verify_report(export)


def capture() -> dict[str, Any]:
    state: dict[str, Any] = {"format": "BDB_GUIDED_UX_DELIVERY_1", "base_commit": "3c129a2856f29742b406076927ab4a75e921a856",
             "branch": subprocess.check_output(["git", "branch", "--show-current"], cwd=ROOT).decode().strip(),
             "build": build_readback(), "demo": demo_readback(), "tests": test_readback(),
             "high_assurance": high_assurance_boundary()}
    sources = list((ROOT / "src/bdb_audit/local_product").glob("*.py"))
    sources += [ROOT / "pyproject.toml", ROOT / "tools/local_product_smoke.py", Path(__file__),
                ROOT / "tests/product/test_guided_local_ui.py", ROOT / "tests/product/test_local_product.py",
                ROOT / "Run-Local-Audit.ps1", ROOT / "docs/LOCAL_PRODUCT_MODE/README.md"]
    sources += list(HERE.glob("*.md"))
    evidence = list((HERE / "evidence").glob("*"))
    demo_files = [path for path in DEMO.rglob("*") if path.is_file() and ".git" not in path.parts and path.name != "recent.json"]
    # The native window observation was captured during the preceding smoke;
    # its original transcripts stay bound as supporting evidence.
    preceding = ROOT / ".product-smoke/guided-ux-20261012-v3"
    demo_files += [preceding / name for name in ("TUI_SESSIONS.json", "TUI_TRANSCRIPT.txt")]
    state["files"] = [file_info(p) for p in sorted(set(sources + evidence + demo_files + [ARTIFACT])) if p.is_file()]
    MANIFEST.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return state


def verify() -> dict[str, Any]:
    state = json.loads(MANIFEST.read_bytes())
    for info in state["files"]:
        assert file_info(ROOT / info["path"]) == info, info["path"]
    assert build_readback() == state["build"]
    assert demo_readback() == state["demo"]
    assert test_readback() == state["tests"]
    assert high_assurance_boundary() == state["high_assurance"]
    return {"status": "PASS", "scope": "GUIDED_LOCAL_UX_ONLY", "files_verified": len(state["files"]),
            "tests": state["tests"], "demo": state["demo"], "high_assurance": "BLOCKED_AS_REQUIRED"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--standalone-checks", action="store_true")
    parser.add_argument("--open-explorer", action="store_true", help="Explicitly request native Explorer selection during standalone checks")
    parser.add_argument("--capture", action="store_true")
    args = parser.parse_args()
    if args.standalone_checks:
        standalone_checks(open_explorer=args.open_explorer)
    result = capture() if args.capture else verify()
    if args.capture:
        result = {"status": "CAPTURED", "tests": result["tests"], "demo": result["demo"], "high_assurance": result["high_assurance"]}
    print(json.dumps(result, ensure_ascii=False, indent=2))
