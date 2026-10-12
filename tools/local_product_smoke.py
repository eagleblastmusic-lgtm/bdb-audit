"""Real local controls and public CLI import, not external AI or fixture answers.

Creates an actual small Git repository with three intentional defects. The
control driver writes local observations from actual source/tests and explicitly
accepts them as an automated demo operator authorized by the owner. No fictional
auditor, model execution, producer certificate or qualification is generated.
"""
from __future__ import annotations

import argparse
from contextlib import redirect_stdout, redirect_stderr
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys

from bdb_audit.assurance.zip_safety import read_bytes
from bdb_audit.cli import run_cli
from bdb_audit.core.canonical_json import canonical_bytes, parse
from bdb_audit.local_product.profile import STAGES
from bdb_audit.local_product.workflow import LocalWorkflow
from bdb_audit.workflow.packaging import _deterministic_zip

APP = '''import sqlite3

def clamp(value):
    return min(value, 10)  # intentional missing lower bound

def users_by_name(connection, name):
    return connection.execute("SELECT name FROM users WHERE name = '" + name + "'").fetchall()

class Counter:
    def __init__(self):
        self.value = 0

    def increment(self, rendezvous):
        prior = self.value
        rendezvous.wait(timeout=5)
        self.value = prior + 1  # intentional lost update
'''
TESTS = '''import sqlite3
import threading
import unittest
from app import clamp, users_by_name, Counter

class KnownBehavior(unittest.TestCase):
    def test_in_range(self):
        self.assertEqual(clamp(5), 5)
    def test_upper_bound(self):
        self.assertEqual(clamp(50), 10)
    def test_lower_bound(self):
        self.assertEqual(clamp(-1), 0)
    def test_regular_lookup(self):
        db = sqlite3.connect(":memory:")
        db.execute("CREATE TABLE users(name TEXT)")
        db.execute("INSERT INTO users VALUES ('alice'), ('bob')")
        self.assertEqual(users_by_name(db, "alice"), [("alice",)])
    def test_injection(self):
        db = sqlite3.connect(":memory:")
        db.execute("CREATE TABLE users(name TEXT)")
        db.execute("INSERT INTO users VALUES ('alice'), ('bob')")
        self.assertEqual(users_by_name(db, "x' OR 1=1 --"), [])
    def test_concurrent_increment(self):
        counter = Counter()
        barrier = threading.Barrier(2)
        threads = [threading.Thread(target=counter.increment, args=(barrier,)) for _ in range(2)]
        for thread in threads: thread.start()
        for thread in threads: thread.join(6)
        self.assertTrue(all(not thread.is_alive() for thread in threads))
        self.assertEqual(counter.value, 2)

if __name__ == "__main__":
    unittest.main()
'''


def run(output: Path) -> dict:
    if output.exists():
        raise RuntimeError("Use a new output directory; existing evidence is never removed")
    output.mkdir(parents=True)
    repository = output / "known-defects-repository"
    repository.mkdir()
    (repository / "app.py").write_text(APP, encoding="utf-8", newline="\n")
    (repository / "test_app.py").write_text(TESTS, encoding="utf-8", newline="\n")
    (repository / "README.md").write_text("Real local control demo. Three intentional defects. No external AI responses.\n", encoding="utf-8")
    for command in (("init", "-q"), ("add", "."), ("-c", "user.name=Local control demo", "-c",
                    "user.email=local-control@example.invalid", "commit", "-qm", "Three intentional defects for real local audit")):
        subprocess.run(["git", "-C", str(repository), *command], capture_output=True, check=True)
    subprocess.run(["git", "-C", str(repository), "bundle", "create", str(output / "SOURCE.bundle"), "HEAD"], capture_output=True, check=True)
    campaign = output / "campaign"
    commands = []
    transcript = bytearray()
    def cli(*argv: str) -> dict:
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = run_cli(["product", "local", *argv])
        actual = (out.getvalue() + err.getvalue()).encode("utf-8")
        offset = len(transcript)
        transcript.extend(actual)
        commands.append({"argv": ["product", "local", *argv], "execution": "PUBLIC_CLI_ENTRY_POINT_IN_PROCESS",
                         "exit_code": code, "stdout_stderr_offset": offset, "byte_length": len(actual),
                         "sha256": hashlib.sha256(actual).hexdigest()})
        if code:
            raise RuntimeError(actual.decode("utf-8"))
        return parse(actual)
    cli("preflight", "--source", str(repository))
    cli("start", "--source", str(repository), "--campaign", str(campaign))
    control = cli("run-check", "--campaign", str(campaign), "--task", "E1-A", "--",
                  sys.executable, "-m", "unittest", "-v", "test_app")
    assert control["result"]["supervisor_status"] == "TARGET_NONZERO"
    stderr = LocalWorkflow(campaign).store.vault.read_bytes(control["files"]["stderr.bin"]["raw_digest"])
    assert b"Ran 6 tests" in stderr and b"failures=3" in stderr
    observation = cli("run-check", "--campaign", str(campaign), "--task", "E1-E", "--", sys.executable, "-c",
        "import ast,json; from pathlib import Path; t=ast.parse(Path('app.py').read_text()); print(json.dumps({'functions':[n.name for n in ast.walk(t) if isinstance(n,ast.FunctionDef)],'source_lines':len(Path('app.py').read_text().splitlines())},sort_keys=True))")
    assert observation["result"]["supervisor_status"] == "SUCCESS"
    claims = [
        {"id": "LOCAL-DEMO-LOWER-BOUND", "title": "Missing clamp lower bound", "severity": "MEDIUM",
         "statement": "clamp(-1) returned -1; the actual lower-bound test expected 0 and failed.",
         "rationale": "Actual test_lower_bound output plus app.py line 4; no prediction substituted for execution.",
         "disposition": "SUPPORTED", "source_refs": [{"path": "app.py", "line": 4}]},
        {"id": "LOCAL-DEMO-SQL", "title": "SQL expression injection", "severity": "HIGH",
         "statement": "The actual lookup with x' OR 1=1 -- returned alice and bob instead of an empty list.",
         "rationale": "Actual test_injection failed; app.py line 7 concatenates user input into SQL.",
         "disposition": "SUPPORTED", "source_refs": [{"path": "app.py", "line": 7}]},
        {"id": "LOCAL-DEMO-LOST-UPDATE", "title": "Concurrent counter loses an update", "severity": "MEDIUM",
         "statement": "Two real threads synchronized after reading value 0; final value was 1, expected 2.",
         "rationale": "Actual test_concurrent_increment failed with a real Barrier and two real threads; lines 14–16 lack mutual exclusion.",
         "disposition": "SUPPORTED", "source_refs": [{"path": "app.py", "line": 16}]},
    ]
    run_summary = f"Actual run {control['run_id']}: 6 tests executed, 3 passed and 3 failed on intentional defects. stderr SHA-256 {control['files']['stderr.bin']['raw_digest']}."
    # These are disclosed automated LOCAL_CONTROL reviews of the actual source
    # and run above, not generated answers impersonating five AI auditors.
    reviews = {
        "E1": {"inventory": "Actual source: clamp, users_by_name, Counter.__init__/increment; sqlite and threading tests are present.",
               "invariants": "Clamp must stay in [0,10]; user name must be treated as data; two increments must preserve both updates.",
               "coverage": run_summary + " The three other tests cover in-range, upper bound and ordinary lookup."},
        "E2": {"comparison": "Observed test failures support the three inspected code mechanisms. No independent models participated.",
               "contradictions": "No conflicting external auditor input was provided. One local control driver supplies these observations.",
               "evidence_gaps": "No production database, deployment, crash persistence or independent AI review was observed.",
               "claim_review": "Retain all three claims as locally supported, with unverified producer identity and limited scope.",
               "unresolved": "Application-level impact outside this small demonstrator is not established.",
               "verification_plan": "After changing source, start a new exact-commit campaign and rerun all six tests."},
        "E3": {"coverage_gaps": "Source has no persistent state or network layer. SQL unicode/length cases and more thread schedules are untested.",
               "novel_checks": "Propose property checks for clamp, parameterized queries, and locking/many-thread schedules; these proposals were not executed."},
        "E4": {"scenarios": "Trace: Counter reads prior, both threads wait, both write prior+1; observed final value 1 supports the mechanism.",
               "support": run_summary, "fault_analysis": "No durable writes exist in this source. Host crashes and recovery were not simulated as application guarantees.",
               "recovery_checks": "The local audit itself is resumed in a separate Python process below; no application recovery claim is inferred.",
               "causal_review": "Missing clamp lower bound, SQL interpolation, and separate counter read/write explain the actual three failing tests.",
               "alternatives": "Tests are part of the demonstrator and their oracles require review; no independent attestation is inferred."},
        "E5": {"attack_review": "Boundary -1, malicious SQL expression and synchronized race are actual executed contrasting cases. No other mutations were run.",
               "checks": run_summary + " Ordinary clamp and lookup succeeded; boundary and hostile/concurrent inputs failed.",
               "challenge_review": "Compare the actual stderr with source. SQLite injection was tested on an in-memory database only; deterministic rendezvous exposes the counter race.",
               "unresolved": "Severity is a local assessment; no production exposure, independent adjudicator or false-negative completeness is claimed."},
        "E6": {"followup_review": "No fixes have been applied to the audited source. All three observed defects require remediation and a new source campaign.",
               "residual_risks": "Unexplored input dimensions, thread schedules and deployment behavior remain. External AI answers were not supplied.",
               "completion_limits": "This demo completed local responses and manual CLI acceptance by an automated operator, not independent experts or normative E1–E6."},
    }
    inputs = output / "actual-local-responses"
    inputs.mkdir()
    for stage in STAGES:
        while True:
            workflow = LocalWorkflow(campaign)
            assert workflow.stage == stage
            pending = [task for task in workflow._available_tasks() if task not in workflow.accepted]
            if not pending:
                break
            cli("prepare", "--campaign", str(campaign))
            workflow = LocalWorkflow(campaign)
            for task in pending:
                package = workflow.packages[task]
                response = parse(read_bytes(workflow.store.vault.read_bytes(package["raw"]["raw_digest"]))["RESPONSE_TEMPLATE.json"])
                response.update(producer={"kind": "LOCAL_CONTROL", "declared_name": "local_product_smoke actual control driver; not external AI"},
                                completion="COMPLETE", outputs={key: reviews[stage][key] for key in package["required_outputs"]},
                                findings=claims, limitations=["One disclosed automated local control driver; not independent AI auditors.",
                                                             "Human review is still required before applying conclusions to a real application."],
                                recommendations=["Enforce the clamp lower bound, parameterize SQL, and synchronize counter updates; rerun a new exact-commit audit."],
                                evidence_files=[{"path": "actual-test-stderr.txt", "sha256": hashlib.sha256(stderr).hexdigest(), "byte_length": len(stderr)}])
                file = inputs / (task + ".zip")
                file.write_bytes(_deterministic_zip({"LOCAL_RESULT.json": canonical_bytes(response), "actual-test-stderr.txt": stderr}))
                cli("inspect", "--campaign", str(campaign), "--file", str(file))
                imported = cli("import", "--campaign", str(campaign), "--file", str(file))
                rid = imported["result_id"]
                validated = cli("validate", "--campaign", str(campaign), "--result", rid)
                assert validated["status"] == "VALIDATED_STRUCTURE"
                accepted = cli("accept", "--campaign", str(campaign), "--result", rid, "--confirm-local", "--actor", "owner-authorized automated demo operator")
                assert accepted["status"] == "USER_ACCEPTED_LOCAL"
        if stage == "E3":
            restart = subprocess.run([sys.executable, "-m", "bdb_audit", "product", "local", "resume", "--campaign", str(campaign)],
                                     capture_output=True, check=True)
            (output / "REAL_PROCESS_RESTART.json").write_bytes(restart.stdout)
            assert parse(restart.stdout)["stage"] == "E3"
        cli("advance", "--campaign", str(campaign))
    exported = cli("report", "--campaign", str(campaign), "--output", str(output / "final-report"))
    assert exported["workflow_status"] == "LOCAL_COMPLETED"
    (output / "CLI_TRANSCRIPT.txt").write_bytes(bytes(transcript))
    (output / "CLI_COMMANDS.json").write_bytes(canonical_bytes(commands) + b"\n")
    final = LocalWorkflow(campaign)
    record = {"status": "REAL_LOCAL_CONTROL_DEMO_COMPLETED", "mode": "LOCAL_PRODUCT",
              "external_ai_responses": 0, "test_fixtures_imported": 0, "local_control_responses_imported": len(final.accepted),
              "actual_test_execution": {"tests": 6, "pass": 3, "fail": 3, "error": 0,
                                        "meaning": "Intentional demonstrator defects were actually detected; not BDB regression failures"},
              "campaign_id": final.campaign_id, "source": final.source,
              "history_head": final.head, "real_process_restart": True, "production_cli_commands": len(commands),
              "report_directory": str(output / "final-report")}
    (output / "DEMO_RESULT.json").write_bytes(canonical_bytes(record) + b"\n")
    return record


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(run(args.output.resolve()), ensure_ascii=False, indent=2))
