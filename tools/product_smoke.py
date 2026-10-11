"""Real subprocess demonstration on a non-sensitive Git target; no fake AI result."""
from __future__ import annotations

import hashlib
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--standalone", type=Path)
    parser.add_argument("--output-dir", type=Path, help="Write fresh evidence here, preserving earlier smoke artifacts")
    args = parser.parse_args()
    scratch = ROOT / ".product-smoke" / uuid.uuid4().hex
    repo = scratch / "target"
    repo.mkdir(parents=True)
    (repo / "calculator.py").write_text("def add(a, b):\n    return a + b\n\ndef clamp(value, low, high):\n    return min(low, max(high, value))\n", encoding="utf-8")
    (repo / "test_calculator.py").write_text("import unittest\nfrom calculator import add, clamp\n\nclass CalculatorTest(unittest.TestCase):\n    def test_sum(self):\n        self.assertEqual(add(2, 3), 5)\n    def test_clamp_midpoint(self):\n        self.assertEqual(clamp(5, 0, 10), 5)\n", encoding="utf-8")
    for git_args in (["init"], ["add", "."], ["-c", "user.name=Product demo", "-c", "user.email=product@example.invalid", "commit", "-m", "non-sensitive audit target with known clamp defect"]):
        subprocess.run(["git", "-C", str(repo), *git_args], check=True, capture_output=True)
    sha = subprocess.check_output(["git", "-C", str(repo), "rev-parse", "HEAD"], text=True).strip()
    env = {**os.environ, "PYTHONPATH": str(ROOT / "src"), "PYTHONUTF8": "1"}
    records = []
    def cli(argv, expected=0):
        command = ([sys.executable, "-I", str(args.standalone.resolve())] if args.standalone
                   else [sys.executable, "-m", "bdb_audit"])
        proc = subprocess.run([*command, *argv], env=env, capture_output=True, text=True, encoding="utf-8")
        assert proc.returncode == expected, (argv, proc.stdout, proc.stderr)
        payload = json.loads(proc.stderr if expected else proc.stdout)
        records.append({"argv": argv, "exit_code": proc.returncode, "result": payload})
        return payload
    store = scratch / "work/campaign.sqlite"
    created = cli(["product", "start", "--repo", str(repo), "--ref", sha, "--store", str(store), "--json"])
    assert created["source"]["exact_commit_sha"] == sha and len(created["packages"]) == 5
    # Clean target equals committed files; exact Git raw bytes are independently verified.
    for name in ("calculator.py", "test_calculator.py"):
        raw = subprocess.check_output(["git", "-C", str(repo), "show", f"{sha}:{name}"])
        assert (repo / name).read_bytes() == raw
    passed = scratch / "checks-pass"
    failed = scratch / "checks-detected-defect"
    for run_id, evidence, test in (("sum-control", passed, "test_calculator.CalculatorTest.test_sum"), ("clamp-defect", failed, "test_calculator.CalculatorTest.test_clamp_midpoint")):
        result = cli(["tools", "run", "--source", str(repo), "--evidence", str(evidence), "--run-id", run_id, "--json", "--", sys.executable, "-m", "unittest", test])
        assert result["supervisor_status"] == ("SUCCESS" if run_id == "sum-control" else "TARGET_NONZERO")
        cli(["tools", "results", "--evidence", str(evidence), "--json"])
    # Actual local tool output is never disguised as the assigned AI auditor.
    # Inspection must identify the executor mismatch without granting authority.
    job = created["packages"][0]
    result_zip = scratch / "LOCAL_TOOL_RESULT_UNTRUSTED.zip"
    with zipfile.ZipFile(result_zip, "w") as archive:
        archive.writestr("MANIFEST.json", json.dumps({
            "kind": "bdb_audit_lane_result", "version": "1",
            "campaign_id": created["campaign_id"], "stage_id": "E1", "lane_slot": job["lane_slot"],
            "source_commit_sha": sha, "input_package_digest": job["package_digest"],
            "history_cut": created["assignment_input_history_cut"],
            "executor_profile": "LOCAL_DISPOSABLE_SUBPROCESS_V1", "executor_model": "Python unittest",
            "findings": [{"finding_id": "LOCAL-CLAMP", "statement": "The actual midpoint test failed for clamp(5, 0, 10)", "severity": "UNKNOWN"}],
        }))
        for file in sorted(failed.rglob("*")):
            if file.is_file():
                archive.writestr("LOCAL_EVIDENCE/" + file.relative_to(failed).as_posix(), file.read_bytes())
    before = {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in store.parent.rglob("*") if path.is_file()}
    inspected = cli(["product", "inspect-result", "--store", str(store), "--zip", str(result_zip), "--json"], expected=2)
    assert inspected["error"] == "RESULT_CONTEXT_CLAIM_MISMATCH" and "executor_profile" in inspected["detail"]
    cli(["product", "import", "--store", str(store), "--zip", str(scratch / "unauthorized.zip"), "--json"], expected=2)
    resumed = cli(["product", "resume", "--store", str(store), "--json"])
    assert resumed["campaign_id"] == created["campaign_id"]
    after = {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in store.parent.rglob("*") if path.is_file()}
    assert before == after
    destination = args.output_dir.resolve() if args.output_dir else ROOT / "docs/PRODUCT_V1"
    destination.mkdir(parents=True, exist_ok=True)
    report = destination / "DEMO_AUDIT_REPORT.md"
    # Each run uses its own export; retain an existing earlier demonstration.
    export = scratch / "AUDIT_REPORT.md"
    cli(["product", "report", "--store", str(store), "--output", str(export), "--run-evidence", str(passed), "--run-evidence", str(failed), "--json"])
    report.write_bytes(export.read_bytes())
    evidence = {"kind": "REAL_LOCAL_SUBPROCESS_SMOKE", "synthetic_external_results": False,
                "distribution": "standalone -I" if args.standalone else "source",
                "target_type": "created non-sensitive Git repository with explicit known defect",
                "target_commit": sha, "campaign_id": created["campaign_id"], "store": str(store),
                "rejection_and_restart_no_mutation": True, "external_audit": "BLOCKED_NF02_OPEN",
                "local_checks": "one actual passing control and one actual detected clamp defect",
                "local_result_zip": str(result_zip), "local_result_inspection": "REJECTED_EXECUTOR_MISMATCH; no AI result fabricated",
                "records": records}
    (destination / "SMOKE_EVIDENCE.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "PRODUCT_SMOKE_PASS", "campaign_id": created["campaign_id"], "target_commit": sha, "report": str(report), "external_audit": "NOT_COMPLETED"}))


if __name__ == "__main__":
    main()
