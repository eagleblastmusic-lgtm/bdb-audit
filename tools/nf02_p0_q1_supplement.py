"""Remaining finite Q1 joint contexts; real production code, test-only authority.

No certificate/key/independent qualification is created. Expected decisions are
literal M02/M05/M15 rules, not results learned from the production implementation.
"""
import argparse
import base64
from contextlib import redirect_stdout, redirect_stderr
from copy import deepcopy
import io
import json
from pathlib import Path
import shutil

import pytest

from bdb_audit.core.errors import ValidationError
from bdb_audit.history.limited_authority import LimitedMachineAuthority
from bdb_audit.history.limited_protocol import LimitedProtocol
from bdb_audit.history.limited_wire import LimitedCommand
from bdb_audit.history.store import TransactionalHistoryStore
from bdb_audit.workflow.limited_intake import LimitedIntake, LimitedRequest
from bdb_audit.product_p0_cli import packet, run_p0
from bdb_audit.p0_service import execute
from tools.nf02_p0_q1_adversarial import Audit, retained_authority
from tools.nf02_p0_q1 import reference_a, reference_b
from tools.nf02_p0_reference import sha, history
from tests.product import test_limited_p0 as f

ROOT = Path(__file__).resolve().parents[1]
ROLES = {
    "COORDINATOR": (f.COORDINATOR, ("INITIALIZE_P0_FROM_APPROVED_GIT", "CREATE_ASSIGNMENT", "BIND_PACKAGE", "START_ATTEMPT", "CONFIRM_DELIVERY", "INGEST_EVIDENCE", "ACCEPT_RESULT", "RELEASE_PACKAGE")),
    "AUDITOR": (f.AUDITOR, ("ACK_DELIVERY", "RETURN_AUDIT")),
    "OWNER_RECOVERY": (f.OWNER, ("ABORT_ATTEMPT",)),
}


def run(source, template_file, output, reuse_preparation=None):
    source, template_file, output = source.resolve(), template_file.resolve(), output.resolve()
    audit = Audit(output)
    if reuse_preparation:
        prior = reuse_preparation.resolve()
        rows = [json.loads(raw) for raw in (prior / "ADVERSARIAL_CASES.jsonl").read_bytes().splitlines()]
        rows = [r for r in rows if r["case"].endswith(("/STATUS", "/PREPARE", "/PREPARE_OVERWRITE"))]
        assert len(rows) == 48
        for row in rows:
            assert row["expected"] == row["actual"] and sha(reference_a(row["inputs"])) == row["input_exact_json_sha256"]
        audit.rows.extend(rows)
        (output / "ADVERSARIAL_CASES.jsonl").write_bytes(b"".join(reference_a(r) + b"\n" for r in rows))
        for path in (prior / "working").glob("CAMPAIGN*.json"):
            shutil.copyfile(path, output / "working" / path.name)
        (output / "PREPARATION_REUSE.json").write_bytes(reference_a({"case_count": 48, "execution_procedure_sha256": sha((prior / "EXECUTED_PREPARATION_PROCEDURE.py").read_bytes()),
            "prior_cases_sha256": sha((prior / "ADVERSARIAL_CASES.jsonl").read_bytes()), "reason": "Prepared/status/overwrite checks completed; corrected HTTPS assertion to use package from binding/release job, not nonexistent delivery.package_raw_ref."}) + b"\n")
    authority, raws = retained_authority(source)
    runtime = LimitedProtocol(authority, authority.leased)

    def grant(scope, role):
        cert, operations = ROLES[role]
        body = {"installation_digest": runtime.identity, "actor_ref": "TEST_ONLY_" + role, "certificate_sha256": cert,
                "role": role, **scope, "operations": sorted(operations), "not_before": "2020-01-01T00:00:00Z", "not_after": "2099-01-01T00:00:00Z"}
        raw = reference_a(body) + b"\n"
        assert raw == reference_b(body) + b"\n"
        item = {"body": body, "raw": raw, "signature": f.test_signature(raw, f.OWNER), "digest": sha(raw)}
        authority.leased["grants"].append(item)
        return item["digest"]

    with pytest.MonkeyPatch.context() as monkeypatch:
        audit.monkeypatch = monkeypatch
        monkeypatch.setattr("bdb_audit.history.limited_protocol.LimitedMachineAuthority", lambda: authority)
        monkeypatch.setattr("bdb_audit.history.limited_protocol.verify_cms", f.simulated_verify)
        monkeypatch.setattr("bdb_audit.history.limited_authority.verify_cms", f.simulated_verify)
        working = output / "working/p0.sqlite"
        templates = json.loads(template_file.read_bytes())
        selected = [t for t in templates if t["label"] == "CAMPAIGN_A" or t["packet"]["command"]["operation"] == "ABORT_ATTEMPT"]

        def invoke(entry, args):
            with redirect_stdout(io.StringIO()) as stdout, redirect_stderr(io.StringIO()) as stderr:
                if entry == "PRODUCT_CLI":
                    code = run_p0(args)
                    raw_response = stdout.getvalue() + stderr.getvalue()
                else:
                    code, raw_response = execute(args)
            return code, json.loads(raw_response)

        # The Store projection calls an allocated, still empty DB CREATED;
        # the command-state matrix calls the absence of accepted history EMPTY.
        states = {"INITIALIZE_P0_FROM_APPROVED_GIT": "CREATED", "CREATE_ASSIGNMENT": "GENESIS", "BIND_PACKAGE": "ASSIGNED",
                  "START_ATTEMPT": "BOUND", "CONFIRM_DELIVERY": "STARTED", "INGEST_EVIDENCE": "DELIVERED",
                  "ACCEPT_RESULT": "EVIDENCE_ACCEPTED", "ABORT_ATTEMPT": "EVIDENCE_ACCEPTED"}
        for t in selected:
            if reuse_preparation:
                continue
            body = t["packet"]
            op = body["command"]["operation"]
            request = LimitedRequest(LimitedCommand(body["command"], runtime), tuple(runtime.object(o["kind"], o["body"], o["version"]) for o in body["objects"]),
                                     tuple(body["command"]["events"]), {d: raws[d] for d in body["raw_digests"]})
            for entry in ("PRODUCT_CLI", "SERVICE_EXECUTE"):
                shutil.copyfile(ROOT / t["state_file"], working)
                before = working.read_bytes()
                code, result = invoke(entry, ["status", "--store", str(working)])
                assert code == 0 and result["state"] == states[op] and before == working.read_bytes(), result
                audit.record(t["id"] + "/" + entry + "/STATUS", states[op], result["state"],
                             {"input_database_sha256": sha(before), "response": result})
                draft = {"operation": op, "objects": body["objects"], "raw_digests": body["raw_digests"],
                         "actor_ref": body["command"]["actor_ref"], "grant_digest": body["command"]["grant_digest"],
                         "events": body["command"]["events"], "command_id": body["command"]["command_id"]}
                input_path = output / "inputs/draft.json"
                input_path.write_bytes(reference_a(draft) + b"\n")
                for digest, raw in request.raw.items():
                    (output / "inputs" / digest).write_bytes(raw)
                prepared = output / "working" / (t["id"] + "-" + entry + ".json")
                args = ["prepare", "--store", str(working), "--input", str(input_path), "--raw-dir", str(output / "inputs"), "--output", str(prepared)]
                code, result = invoke(entry, args)
                assert code == 0 and prepared.read_bytes() == reference_a(packet(request)) + b"\n"
                assert base64.b64decode(result["signing_preimage_base64"]) == request.signing_bytes() and before == working.read_bytes()
                audit.record(t["id"] + "/" + entry + "/PREPARE", "EXACT_UNSIGNED_PACKET_NO_HISTORY_WRITE", "EXACT_UNSIGNED_PACKET_NO_HISTORY_WRITE",
                             {"draft": draft, "input_database_sha256": sha(before), "prepared_transport_sha256": sha(prepared.read_bytes()), "signing_sha256": sha(request.signing_bytes())})
                stable = f.snapshot(type("Location", (), {"path": str(working)})())
                code, result = invoke(entry, args)
                assert code == 2 and stable == f.snapshot(type("Location", (), {"path": str(working)})())
                audit.record(t["id"] + "/" + entry + "/PREPARE_OVERWRITE", "DENY_WITHOUT_MUTATION", "DENY_WITHOUT_MUTATION",
                             {"draft_sha256": sha(reference_a(draft) + b"\n"), "output_sha256": sha(prepared.read_bytes()), "error": result["error"]})

        # Release entry points exercise the same bound bytes and installed grant
        # predicates. Only HTTPS/OS/CMS are simulated, never the outbox writer.
        t = next(t for t in selected if t["packet"]["command"]["operation"] == "CONFIRM_DELIVERY")
        for entry in ("PRODUCT_CLI", "SERVICE_EXECUTE"):
            shutil.copyfile(ROOT / t["state_file"], working)
            intake = LimitedIntake(TransactionalHistoryStore.open_p0(working))
            delivery_body = t["packet"]["objects"][0]["body"]
            binding_ref = delivery_body["binding_ref"]
            ref_file = output / "inputs/binding-ref.json"
            ref_file.write_bytes(reference_a(binding_ref) + b"\n")
            prepared = output / "working" / (entry + "-release.json")
            gd = t["packet"]["command"]["grant_digest"]
            job = intake.release_job(binding_ref=binding_ref, grant_digest=gd)
            statement = runtime.release_statement(job)
            code, result = invoke(entry, ["prepare-release", "--store", str(working), "--binding-ref", str(ref_file), "--grant-digest", gd, "--output", str(prepared)])
            assert code == 0 and prepared.read_bytes() == reference_b(statement)
            audit.record(entry + "/PREPARE_RELEASE", "EXACT_RELEASE_STATEMENT", "EXACT_RELEASE_STATEMENT",
                         {"input_database_sha256": t["state_sha256"], "statement": statement, "statement_sha256": sha(prepared.read_bytes())})
            signature = output / "inputs/release.p7s"
            signature.write_bytes(b"TEST_ONLY_NO_AUTHORITY")
            args = ["release", "--store", str(working), "--input", str(prepared), "--signature", str(signature)]
            stable = f.snapshot(intake.store)
            code, result = invoke(entry, args)
            assert code == 2 and stable == f.snapshot(intake.store)
            audit.record(entry + "/RELEASE_UNSIGNED", "DENY_WITHOUT_MUTATION", "DENY_WITHOUT_MUTATION",
                         {"statement_sha256": sha(prepared.read_bytes()), "signature_sha256": sha(signature.read_bytes()), "error": result["error"]})
            signature.write_bytes(f.test_signature(prepared.read_bytes(), f.COORDINATOR))
            before_head = intake.store.head()
            calls = []
            def send(files, supplied, raw):
                assert raw == raws[job["package_raw_ref"]["raw_digest"]]
                calls.append((supplied["release_id"], sha(raw)))
                return {"http_status": 202, "response_sha256": sha(b"TEST_ONLY_SUPPLEMENT"), "response_bytes": b"TEST_ONLY_SUPPLEMENT"}
            monkeypatch.setattr("bdb_audit.workflow.limited_delivery.deliver_installed", send)
            for retry in range(2):
                code, result = invoke(entry, args)
                assert code == 0 and calls[-1] == (job["release_id"], job["package_raw_ref"]["raw_digest"]) and intake.store.head() == before_head, (code, result, calls)
                audit.record(entry + "/RELEASE_SIGNED_LOCAL/" + str(retry), "SAME_BOUND_BYTES_ID_NO_CANONICAL_APPEND", "SAME_BOUND_BYTES_ID_NO_CANONICAL_APPEND",
                             {"statement_sha256": sha(prepared.read_bytes()), "signature_sha256": sha(signature.read_bytes()), "release_id": calls[-1][0], "package_sha256": calls[-1][1]})

        # Three real attempts distinguish immediate predecessor from an older
        # genuinely accepted attempt/abort, rather than an unknown fake ref.
        final_result = next(t for t in templates if t["label"] == "CAMPAIGN_A_RETRY" and t["packet"]["command"]["operation"] == "ACCEPT_RESULT")
        shutil.copyfile(ROOT / final_result["state_file"], working)
        intake = LimitedIntake(TransactionalHistoryStore.open_p0(working))
        _, records, _ = intake.snapshot()
        assignments = sorted((r for r in records.values() if r["object"].kind == "assignment_manifest"), key=lambda r: r["seq"])
        second = assignments[-1]["object"]
        genesis = intake.runtime.resolve(records, second.body["campaign_ref"])["object"]
        source_obj = intake.runtime.resolve(records, second.body["source_ref"])["object"]
        scope = runtime.auth_scope(genesis.body, source_obj.body, second.ref.as_dict(), f.AUDITOR)
        recovery = grant(scope, "OWNER_RECOVERY")
        audit.label = "THIRD_ATTEMPT"
        audit.capture(intake, intake.abort(actor_ref="TEST_ONLY_OWNER_RECOVERY", grant_digest=recovery, assignment_ref=second.ref.as_dict(), reason="OWNER_CANCELLED"), f.OWNER)
        attempt3, assignment3 = intake.draft_assignment(auditor_certificate_sha256=f.AUDITOR)
        gd3 = grant(runtime.auth_scope(genesis.body, source_obj.body, assignment3.ref.as_dict(), f.AUDITOR), "COORDINATOR")
        request3 = intake.prepare("CREATE_ASSIGNMENT", [attempt3, assignment3], actor_ref="TEST_ONLY_COORDINATOR", grant_digest=gd3)
        state3 = output / "states/third-create-input.sqlite"
        shutil.copyfile(working, state3)
        template3 = {"id": "THIRD_CREATE", "request": request3, "packet": packet(request3), "state_sha256": sha(state3.read_bytes()), "cert": f.COORDINATOR}
        _, records, _ = intake.snapshot()
        for field, kind in (("retry_of_attempt_ref", "attempt"), ("abort_basis_ref", "nf02_p0_abort")):
            old = min((r for r in records.values() if r["object"].kind == kind), key=lambda r: r["seq"])
            audit.check_mutation(template3, intake, 0, (field,), old["ref"], "NON_IMMEDIATE_ACCEPTED_PREDECESSOR/" + field)
        audit.capture(intake, request3)
        ops = ["INITIALIZE_P0_FROM_APPROVED_GIT", "CREATE_ASSIGNMENT", "BIND_PACKAGE", "START_ATTEMPT", "CONFIRM_DELIVERY", "INGEST_EVIDENCE", "ABORT_ATTEMPT", "CREATE_ASSIGNMENT", "BIND_PACKAGE", "START_ATTEMPT", "CONFIRM_DELIVERY", "INGEST_EVIDENCE", "ABORT_ATTEMPT", "CREATE_ASSIGNMENT"]
        (output / "THREE_ATTEMPTS_REFERENCE.json").write_bytes(reference_a(history(working, expected_operations=ops)) + b"\n")
        shutil.copyfile(working, output / "THREE_ATTEMPTS.sqlite")

        # Literal role-operation matrix and every grant scope/time predicate.
        selector = LimitedMachineAuthority()
        operations = [op for _, ops in ROLES.values() for op in ops]
        base_scope = runtime.auth_scope(genesis.body, source_obj.body, second.ref.as_dict(), f.AUDITOR)
        for role, (cert, allowed) in ROLES.items():
            digest = grant(base_scope, role)
            item = next(g for g in authority.leased["grants"] if g["digest"] == digest)
            for operation in operations:
                for variant in ("VALID", "INSTALLATION", "CAMPAIGN", "SOURCE", "VIEW_TASK", "ASSIGNMENT", "ACTOR", "CERTIFICATE", "NOT_YET_VALID", "EXPIRED", "MISSING", "DUPLICATE"):
                    leased = {**authority.leased, "grants": [deepcopy(item)]}
                    actor, certificate = item["body"]["actor_ref"], cert
                    grant_field = {"INSTALLATION": "installation_digest", "CAMPAIGN": "campaign_id", "SOURCE": "source_scope_digest", "VIEW_TASK": "view_task_digest", "ASSIGNMENT": "assignment_scope_digest"}.get(variant)
                    if grant_field:
                        leased["grants"][0]["body"][grant_field] = "0" * 64
                    if variant == "ACTOR":
                        actor = "UNAUTHORIZED_ACTOR"
                    if variant == "CERTIFICATE":
                        certificate = "0" * 64
                    if variant in {"EXPIRED", "NOT_YET_VALID"}:
                        leased["grants"][0]["body"]["not_after" if variant == "EXPIRED" else "not_before"] = "2001-01-01T00:00:00Z" if variant == "EXPIRED" else "2098-01-01T00:00:00Z"
                    if variant == "MISSING":
                        leased["grants"] = []
                    if variant == "DUPLICATE":
                        leased["grants"] *= 2
                    expected = "ALLOW_EXACT_ONE_GRANT" if variant == "VALID" and operation in allowed else "DENY"
                    try:
                        selector.select_grant(leased, operation=operation, actor=actor, certificate=certificate, digest=digest, scope=base_scope, at="2026-10-12T00:00:00Z")
                        actual = "ALLOW_EXACT_ONE_GRANT"
                    except ValidationError:
                        actual = "DENY"
                    audit.record("ROLE_SCOPE/" + role + "/" + operation + "/" + variant, expected, actual,
                                 {"role": role, "operation": operation, "grants": [g["body"] for g in leased["grants"]], "selector": {"actor": actor, "certificate": certificate, "digest": digest, "scope": base_scope, "at": "2026-10-12T00:00:00Z"}})
    report = {"status": "PASS_LOCAL_FINITE_JOINT_CONTEXTS", "case_count": len(audit.rows), "mismatches": [],
              "authority": "SIMULATED_OS_CMS_HTTPS_NOT_REAL_AUTHORITY", "source_database_sha256": sha(source.read_bytes()),
              "templates_sha256": sha(template_file.read_bytes()), "harness_sha256": sha(Path(__file__).read_bytes())}
    (output / "SUPPLEMENT_EXECUTION.json").write_bytes(reference_a(report) + b"\n")
    print("SUPPLEMENT_PASS", len(audit.rows), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--templates", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--reuse-preparation", type=Path)
    args = parser.parse_args()
    run(args.source, args.templates, args.output, args.reuse_preparation)
