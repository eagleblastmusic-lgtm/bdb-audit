"""Retain author-only semantic vectors against the actual production writer.

OS/CMS/HTTPS are explicitly simulated by the existing test fixtures. Expected
denials follow M03/M04/M07, not the runtime's returned decisions. No key exists.
"""
import argparse
from collections import Counter
from copy import deepcopy
from pathlib import Path
import sqlite3
from typing import Any

import pytest

from bdb_audit.core.errors import ValidationError
from bdb_audit.history.limited_wire import LimitedCommand
from tests.product import test_limited_p0 as fixtures
from tools.nf02_p0_reference import history, reference_a, fixed_zip, sha


def run(output):
    if output.exists():
        raise ValueError("New evidence directory required; no overwrite")
    output.mkdir(parents=True)
    with pytest.MonkeyPatch.context() as monkeypatch:
        corpus = getattr(fixtures.corpus, "__wrapped__")()
        setup = getattr(fixtures.setup_p0, "__wrapped__")(corpus, output, monkeypatch)
        store, intake, authority, initial, grant, source, genesis = setup
        original_accept = fixtures.accept
        negatives: list[dict[str, Any]] = []
        positives: list[dict[str, Any]] = []

        def denial(request, contract, field, mutation, command_field=False):
            before = fixtures.snapshot(store)
            raw_before = Path(store.path).read_bytes()
            phase = "CONSTRUCTOR_SCHEMA"
            try:
                if command_field:
                    body = deepcopy(request.command.body())
                else:
                    target = next(o for o in request.objects if o.kind + "/" + o.version == contract)
                    body = deepcopy(target.body)
                if mutation == "ABSENT":
                    del body[field]
                else:
                    value = body[field]
                    if isinstance(value, list):
                        if not value:
                            return
                        value = value[0]
                    if value is None:
                        return  # Initial retry nullable branch is tested separately.
                    if mutation == "WRONG_KIND":
                        value["kind"] = "generic_import"
                    elif mutation == "WRONG_VERSION":
                        value["version"] = "999"
                    elif mutation == "WRONG_SCHEMA_RAW_DIGEST":
                        value["schema_revision_ref"]["raw_digest"] = "0" * 64
                    elif mutation == "WRONG_LOGICAL_ID":
                        value["logical_id"] = value["kind"] + "_00000000-0000-4000-8000-000000000000"
                    elif mutation == "WRONG_REVISION":
                        value["revision_digest"] = "0" * 64
                if command_field:
                    from dataclasses import replace
                    altered = replace(request, command=LimitedCommand(body, intake.runtime))
                else:
                    objects = tuple(intake.runtime.object(o.kind, body if o is target else o.body) for o in request.objects)
                    phase = "PREPARATION"
                    altered = intake.prepare(request.command.command_kind, objects,
                        actor_ref=request.command.actor_ref, grant_digest=request.command.body()["grant_digest"],
                        raw=request.raw, events=request.events if request.command.command_kind == "START_ATTEMPT" else None)
                phase = "STORE_ACCEPT"
                original_accept(intake, altered)
            except ValidationError as error:
                assert fixtures.snapshot(store) == before
                assert Path(store.path).read_bytes() == raw_before
                negatives.append({"id": f"SEMANTIC-{len(negatives)+1:04}", "operation": request.command.command_kind,
                    "contract": contract, "field": field, "mutation": mutation, "requirement": "M03/M04 EXACT REQUIRED FIELD/TYPED IDENTITY",
                    "expected": "DENY_WITHOUT_MUTATION", "actual": "DENY_WITHOUT_MUTATION", "phase": phase, "error_code": error.code})
                return
            raise AssertionError((contract, field, mutation, "Unexpected acceptance"))

        def capture(current_intake, request, cert=fixtures.COORDINATOR):
            for obj in request.objects:
                key = obj.kind + "/" + obj.version
                for ref in corpus.descriptor["canonical_contracts"][key]["material_refs"]:
                    for mutation in ("ABSENT", "WRONG_KIND", "WRONG_VERSION", "WRONG_SCHEMA_RAW_DIGEST", "WRONG_LOGICAL_ID", "WRONG_REVISION"):
                        denial(request, key, ref["field"], mutation)
            for ref in corpus.descriptor["canonical_contracts"]["command_envelope/3"]["material_refs"]:
                for mutation in ("ABSENT", "WRONG_KIND", "WRONG_VERSION", "WRONG_SCHEMA_RAW_DIGEST", "WRONG_LOGICAL_ID", "WRONG_REVISION"):
                    denial(request, "command_envelope/3", ref["field"], mutation, command_field=True)
            outcome = original_accept(current_intake, request, cert)
            positives.append({"operation": request.command.command_kind, "expected_commit_seq": len(positives)+1,
                              "actual_commit_seq": outcome.head.commit_seq, "receipt_digest": outcome.receipt.digest})
            assert outcome.head.commit_seq == len(positives)
            return outcome

        monkeypatch.setattr(fixtures, "accept", capture)
        flow = fixtures.delivered(setup, monkeypatch)
        assignment, gd, binding, delivery, job = flow[3], flow[4], flow[6], flow[7], flow[8]
        members = {"REPORT.md": b"# TEST ONLY\nUnqualified submissions.\n", "REPORT.txt": b"TEST ONLY\n",
                   "evidence/data.png": b"\x89PNG\r\n\x1a\nTEST_ONLY_OPAQUE", "logs/run.log": b"TEST ONLY local simulation\n"}
        payload = {"findings": [{"finding_id": f"submission_00000000-0000-4000-8000-{i:012d}", "severity": severity, "summary": "TEST ONLY " + severity,
            "details": "Unqualified auditor submission", "source_paths": ["pyproject.toml"], "evidence_paths": ["evidence/data.png"]}
            for i, severity in enumerate(("INFO", "LOW", "MEDIUM", "HIGH", "CRITICAL"), 1)],
            "report_paths": ["REPORT.md", "REPORT.txt"], "evidence_paths": ["evidence/data.png"],
            "log_paths": ["logs/run.log"], "notes": ["second note", "first note"]}
        mime = {".md": "text/markdown", ".txt": "text/plain", ".log": "text/plain", ".png": "image/png"}
        manifest = {"scope": job["scope"], "binding_ref": binding.ref.as_dict(), "delivery_ref": delivery.ref.as_dict(),
            "package_raw_ref": binding.body["package_raw_ref"], "payload": payload,
            "members": [{"path": name, "sha256": sha(data), "bytes": len(data), "media_type": mime[Path(name).suffix]}
                        for name, data in sorted(members.items())]}
        raw_zip = fixed_zip({"MANIFEST.json": reference_a(manifest) + b"\n", **members})
        returned = {"domain": "BDB_P0_AUDIT_RETURN/1", "scope": job["scope"], "binding_ref": binding.ref.as_dict(),
            "delivery_ref": delivery.ref.as_dict(), "result_raw_ref": corpus.raw_ref(raw_zip, "P0_RESULT_TRANSPORT_V1", "application/zip"),
            "auditor_certificate_sha256": fixtures.AUDITOR, "execution_declaration": "EXECUTED_ASSIGNED_AUDIT"}
        returned_raw = reference_a(returned) + b"\n"
        evidence = intake.evidence(actor_ref="TEST_ONLY_COORDINATOR", grant_digest=gd,
            assignment_ref=assignment.ref.as_dict(), binding_ref=binding.ref.as_dict(), delivery_ref=delivery.ref.as_dict(),
            result_zip=raw_zip, return_bytes=returned_raw, return_signature=fixtures.test_signature(returned_raw, fixtures.AUDITOR))
        capture(intake, evidence)
        result = intake.result(actor_ref="TEST_ONLY_COORDINATOR", grant_digest=gd, admission_ref=evidence.objects[0].ref.as_dict())
        assert result.objects[0].body["result_payload"] == payload
        capture(intake, result)
        monkeypatch.setattr(fixtures, "accept", original_accept)
        retained = history(store.path)
        (output / "EXPECTED_PAYLOAD.json").write_bytes(reference_a(payload) + b"\n")
        (output / "REFERENCE_HISTORY_CHECK.json").write_bytes(reference_a(retained) + b"\n")
        report = {"status": "LOCAL_AUTHOR_SEMANTIC_CASES_PASS_NOT_COMPLETE_Q1_OR_AUTHORITY", "authority": "SIMULATED_OS_CMS_HTTPS",
            "expected_basis": "M03/M04 exact required fields and typed identities; M05/M09-M14 literal 7-commit chronology; M07 one-based source indexing",
            "production_components": "Actual LimitedProtocol/Store/Coordinator/intake/transport/parser/CAS/replay; no predicate/writer replacement",
            "positive_steps": positives, "negative_cases": negatives, "phase_counts": dict(Counter(v["phase"] for v in negatives)),
            "local_history_file": "p0.sqlite", "history_sha256": sha(Path(store.path).read_bytes()),
            "limitations": ["No cross-campaign accepted target pool, every same/future-content/own-cut combination or every temporal material target variant is established here.",
                "Commit/receipt mutation replay variants require additional qualified fixtures; Q1 remains OPEN if mandatory coverage is absent.",
                "No genuine independent CMS/OS/transport/external audit assurance."]}
        # The test-only Store never uses a private-key table.
        with sqlite3.connect(store.path) as con:
            assert con.execute("SELECT count(*) FROM _store_private_authority").fetchone()[0] == 0
        (output / "SEMANTIC_EXECUTION.json").write_bytes(reference_a(report) + b"\n")
        print("LOCAL_SEMANTICS_PASS", "positive_steps=" + str(len(positives)), "negative_cases=" + str(len(negatives)))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    run(parser.parse_args().output)
