"""Exact local implementation/evidence readback. Never an NF02 qualification.

--capture writes the local evidence manifest after successful verification.
Without it, checks all exact recorded bytes, including frozen NF02 inputs.
"""
from __future__ import annotations

import argparse
import ast
import base64
from contextlib import redirect_stdout, redirect_stderr
import hashlib
import io
import json
from pathlib import Path
import subprocess
from typing import Any
import xml.etree.ElementTree as ET
import zipfile

from bdb_audit.cli import run_cli
from bdb_audit.history.store import TransactionalHistoryStore
from bdb_audit.core.errors import ValidationError
from bdb_audit.local_product.workflow import LocalWorkflow

ROOT = Path(__file__).resolve().parents[1]
HERE = ROOT / "docs/LOCAL_PRODUCT_MODE"
DEMO = ROOT / ".product-smoke/local-product-final"
MANIFEST = HERE / "EVIDENCE_MANIFEST.json"
FROZEN = ROOT / "docs/PRODUCT_V1/NF02_P0_LIMITED_MODEL/CANDIDATE_MANIFEST.json"


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def read(path: Path) -> Any:
    return json.loads(path.read_bytes())


def info(path: Path, role: str) -> dict:
    raw = path.read_bytes()
    return {"file": path.relative_to(ROOT).as_posix(), "sha256": sha(raw), "bytes": len(raw), "role": role}


def frozen_readback() -> dict:
    assert sha(FROZEN.read_bytes()) == "278d45caa8fe3a814c2d16c3706c93454cdd04676207b3159f57166a611d7ee9"
    manifest = read(FROZEN)
    for category, domain in (("normative", "BDB-NF02-P0-NORMATIVE-SET/1"), ("machine", "BDB-NF02-P0-MACHINE-SET/1")):
        entries = manifest[category + "_files"]
        canonical = json.dumps(entries, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        assert sha(domain.encode("ascii") + b"\x00" + canonical) == manifest[category + "_set_sha256"]
        for entry in entries:
            raw = (ROOT / entry["file"]).read_bytes()
            assert sha(raw) == entry["sha256"] and len(raw) == entry["bytes"], entry["file"]
    return {"status": "EXACT_BYTES_UNCHANGED", "model": manifest["model_id"],
            "manifest_sha256": sha(FROZEN.read_bytes()), "normative_set_sha256": manifest["normative_set_sha256"],
            "machine_set_sha256": manifest["machine_set_sha256"], "qualification_claim": "NONE"}


def check_demo() -> dict:
    record = read(DEMO / "DEMO_RESULT.json")
    workflow = LocalWorkflow(DEMO / "campaign")
    assert workflow.stage == "COMPLETE" and len(workflow.accepted) == 19 and not workflow.pending_runs
    assert workflow.head == record["history_head"]
    assert all(result["response"]["producer"]["kind"] == "LOCAL_CONTROL" for result in workflow.results.values())
    assert record["external_ai_responses"] == 0 and record["test_fixtures_imported"] == 0
    source = DEMO / "known-defects-repository"
    commit = subprocess.check_output(["git", "-C", str(source), "rev-parse", "HEAD"]).decode().strip()
    tree = subprocess.check_output(["git", "-C", str(source), "rev-parse", "HEAD^{tree}"]).decode().strip()
    assert commit == workflow.source["commit"] and tree == workflow.source["tree"]
    subprocess.run(["git", "-C", str(source), "bundle", "verify", str(DEMO / "SOURCE.bundle")], capture_output=True, check=True)
    transcript = (DEMO / "CLI_TRANSCRIPT.txt").read_bytes()
    commands = read(DEMO / "CLI_COMMANDS.json")
    for command in commands:
        offset, length = command["stdout_stderr_offset"], command["byte_length"]
        assert sha(transcript[offset:offset + length]) == command["sha256"] and command["exit_code"] == 0
    for directory in ("final-report", "standalone-report"):
        report = read(DEMO / directory / "REPORT.json")
        evidence = read(DEMO / directory / "EVIDENCE_MANIFEST.json")
        assert report["status"] == "LOCAL_COMPLETED" and not report["contains_test_fixtures"]
        assert report["input_history_head"] == workflow.head and len(report["local_checks"]) == 2
        for entry in evidence["reports"]:
            assert sha((DEMO / directory / entry["path"]).read_bytes()) == entry["sha256"]
        for entry in report["raw_evidence"]:
            raw = workflow.store.vault.read_bytes(entry["raw_digest"])
            assert len(raw) == entry["byte_length"]
    before = sha(workflow.store.path.read_bytes())
    output = io.StringIO()
    with redirect_stdout(output), redirect_stderr(output):
        code = run_cli(["product", "import", "--store", str(workflow.store.path), "--zip", str(DEMO / "actual-local-responses/E1-A.zip"), "--json"])
    assert code == 2 and json.loads(output.getvalue())["external_ingestion"] == "BLOCKED"
    try:
        TransactionalHistoryStore(workflow.store.path)
    except ValidationError as exc:
        assert exc.code == "LOCAL_STORE_CANNOT_BECOME_QUALIFIED"
    else:
        raise AssertionError("LOCAL opened as qualified/foundation history")
    assert sha(workflow.store.path.read_bytes()) == before
    return {"status": "PASS_LOCAL_READBACK", "campaign_id": workflow.campaign_id, "history_head": workflow.head,
            "source_commit": commit, "source_tree": tree, "accepted_local_responses": 19,
            "producer_provenance": "ACTUAL_LOCAL_CONTROLS; no external AI or independent authority",
            "actual_demo_tests": record["actual_test_execution"], "public_cli_commands": len(commands),
            "high_assurance_import": "BLOCKED", "high_assurance_store": "REFUSED_LOCAL_FORMAT"}


def test_totals() -> dict:
    # Only terminal runs count; earlier debugging failures remain documented as
    # superseded. Duplicate test nodes across suites count once, latest wins.
    names = ["high-assurance-regression.xml", "source-regression.xml", "final-local-and-boundaries.xml",
             "final-local-vault.xml", "runner-native-windows.xml", "final-local-interface.xml"]
    nodes: dict[tuple[str, str], str] = {}
    runs = []
    for name in names:
        path = HERE / "evidence" / name
        tree = ET.parse(path)
        cases = tree.findall(".//testcase")
        counts = {"pass": 0, "fail": 0, "error": 0, "skip": 0}
        for case in cases:
            outcome = ("fail" if case.find("failure") is not None else "error" if case.find("error") is not None
                       else "skip" if case.find("skipped") is not None else "pass")
            counts[outcome] += 1
            nodes[(case.attrib.get("classname", ""), case.attrib["name"])] = outcome
        assert counts["fail"] == counts["error"] == counts["skip"] == 0, (name, counts)
        runs.append({"file": path.relative_to(ROOT).as_posix(), **counts})
    totals = {status: sum(outcome == status for outcome in nodes.values()) for status in ("pass", "fail", "error", "skip")}
    return {"terminal_runs": runs, "distinct_test_nodes": totals}


def source_artifact_readback() -> dict:
    from build.build_single_file import collect_source_files, parse_runtime_lock
    artifact = ROOT / "dist/BDB_AUDIT_LOCAL_PRODUCT.py"
    assignments = {}
    for node in ast.parse(artifact.read_bytes()).body:
        if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
            name = node.targets[0].id
            if name in {"PAYLOAD_MANIFEST", "EMBEDDED_PAYLOAD_B85", "PAYLOAD_RAW_DIGEST", "PAYLOAD_SIZE"}:
                assignments[name] = ast.literal_eval(node.value)
    payload = base64.b85decode(assignments["EMBEDDED_PAYLOAD_B85"].strip())
    assert sha(payload) == assignments["PAYLOAD_RAW_DIGEST"] and len(payload) == assignments["PAYLOAD_SIZE"]
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        manifest = assignments["PAYLOAD_MANIFEST"]
        names = archive.namelist()
        assert len(names) == len(set(names)) and set(names) == set(manifest)
        for name in names:
            raw = archive.read(name)
            assert sha(raw) == manifest[name]["sha256"] and len(raw) == manifest[name]["size"]
        source = collect_source_files(ROOT / "src")
        for name, normalized in source:
            assert archive.read(name) == normalized, name
        assert json.loads(archive.read("__bdb_runtime__/lock.json")) == parse_runtime_lock()
        platform = json.loads(archive.read("__bdb_runtime__/platform.json"))
    return {"status": "PASS_EXACT_SOURCE_ARTIFACT", "artifact_sha256": sha(artifact.read_bytes()),
            "source_files": len(source), "embedded_files": len(names), "runtime_platform": platform,
            "source_normalization": "Builder's existing UTF-8 CRLF/CR to LF rule; raw source bytes separately retained in evidence manifest"}


def capture() -> dict:
    result = {"mode": "LOCAL_PRODUCT", "assurance": "LOCAL_IMPLEMENTATION_EVIDENCE_ONLY", "frozen_high_assurance": frozen_readback(),
              "demo": check_demo(), "tests": test_totals(), "source_artifact": source_artifact_readback()}
    paths: dict[Path, str] = {}
    for base, role in ((ROOT / "src/bdb_audit", "PRODUCT_SOURCE"), (HERE, "LOCAL_DOCUMENT_OR_EVIDENCE"),
                       (DEMO, "REAL_LOCAL_DEMO"), (ROOT / ".product-smoke/github-local-first", "REAL_GITHUB_START")):
        for path in base.rglob("*"):
            if path.is_file() and not any(part in {"__pycache__", ".git"} for part in path.relative_to(base).parts):
                if path not in {MANIFEST, HERE / "POST_COMMIT_READBACK.json"}:
                    paths[path] = role
    for name in ("tools/local_product_smoke.py", "tools/local_product_verify.py", "tests/product/test_local_product.py",
                 "Run-Local-Audit.ps1", "dist/BDB_AUDIT_LOCAL_PRODUCT.py", "build/build_single_file.py",
                 "requirements-f2.lock", "pyproject.toml", "docs/PRODUCT_V1/NF02_P0_LIMITED_MODEL/CANDIDATE_MANIFEST.json"):
        paths[ROOT / name] = "LOCAL_IMPLEMENTATION_OR_BUILD_INPUT"
    for entry in read(FROZEN)["normative_files"] + read(FROZEN)["machine_files"]:
        paths[ROOT / entry["file"]] = "FROZEN_HIGH_ASSURANCE_INPUT"
    result["files"] = [info(path, paths[path]) for path in sorted(paths)]
    MANIFEST.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    return verify()


def verify() -> dict:
    manifest = read(MANIFEST)
    for entry in manifest["files"]:
        path = (ROOT / entry["file"]).resolve()
        assert path.is_relative_to(ROOT)
        raw = path.read_bytes()
        assert sha(raw) == entry["sha256"] and len(raw) == entry["bytes"], entry["file"]
    frozen_readback()
    check_demo()
    assert source_artifact_readback() == manifest["source_artifact"]
    assert test_totals() == manifest["tests"]
    return {"status": "PASS_LOCAL_EXACT_READBACK", "manifest_sha256": sha(MANIFEST.read_bytes()),
            "verified_files": len(manifest["files"]), "test_nodes": manifest["tests"]["distinct_test_nodes"],
            "production_qualified_import": "BLOCKED", "qualified_claim": "NONE"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture", action="store_true")
    args = parser.parse_args()
    print(json.dumps(capture() if args.capture else verify(), ensure_ascii=False, indent=2))
