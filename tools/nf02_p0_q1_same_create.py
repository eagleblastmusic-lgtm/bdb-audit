"""Retain and regress the same-command Attempt binding; test-only authority."""
import argparse
from dataclasses import replace
import json
from pathlib import Path
import shutil

import pytest

from bdb_audit.core.errors import ValidationError
from bdb_audit.history.limited_protocol import LimitedProtocol
from bdb_audit.history.limited_wire import LimitedCommand
from bdb_audit.history.store import TransactionalHistoryStore
from bdb_audit.workflow.limited_intake import LimitedIntake, LimitedRequest
from bdb_audit.product_p0_cli import packet
from tools.nf02_p0_q1_adversarial import retained_authority
from tools.nf02_p0_q1 import reference_a, reference_b
from tools.nf02_p0_reference import sha
from tests.product import test_limited_p0 as f

ROOT = Path(__file__).resolve().parents[1]


def run(inputs: Path, output: Path, expect: str) -> None:
    inputs, output = inputs.resolve(), output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    if expect == "COUNTEREXAMPLE":
        authority, raws = retained_authority(inputs / "THREE_ATTEMPTS.sqlite")
        source = inputs / "states/third-create-input.sqlite"
        row = next(json.loads(raw) for raw in (inputs / "ADVERSARIAL_CASES.jsonl").read_bytes().splitlines() if json.loads(raw)["case"] == "THIRD_ATTEMPT-02-CREATE_ASSIGNMENT/LEGAL")
        proposal = row["inputs"]
    else:
        authority, raws = retained_authority(inputs / "ACCEPTED_COUNTEREXAMPLE.sqlite")
        source = inputs / "INPUT_STATE.sqlite"
        proposal = json.loads((inputs / "PROPOSAL.json").read_bytes())
    runtime = LimitedProtocol(authority, authority.leased)
    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr("bdb_audit.history.limited_protocol.LimitedMachineAuthority", lambda: authority)
        monkeypatch.setattr("bdb_audit.history.limited_protocol.verify_cms", f.simulated_verify)
        monkeypatch.setattr("bdb_audit.history.limited_authority.verify_cms", f.simulated_verify)
        working = output / "p0.sqlite"
        shutil.copyfile(source, working)
        shutil.copyfile(source, output / "INPUT_STATE.sqlite")
        intake = LimitedIntake(TransactionalHistoryStore.open_p0(working))
        request = LimitedRequest(LimitedCommand(proposal["command"], runtime), tuple(runtime.object(o["kind"], o["body"], o["version"]) for o in proposal["objects"]),
                                 tuple(proposal["command"]["events"]), {d: raws[d] for d in proposal["raw_digests"]})
        if expect == "COUNTEREXAMPLE":
            _, records, _ = intake.snapshot()
            previous = max((r for r in records.values() if r["object"].kind == "attempt"), key=lambda r: r["seq"])
            assignment = next(o for o in request.objects if o.kind == "assignment_manifest")
            bad = runtime.object(assignment.kind, {**assignment.body, "attempt_ref": previous["ref"]}, assignment.version)
            genesis = runtime.resolve(records, bad.body["campaign_ref"])["object"]
            source_object = runtime.resolve(records, bad.body["source_ref"])["object"]
            original_grant = next(g for g in authority.leased["grants"] if g["digest"] == proposal["command"]["grant_digest"])
            g = {**original_grant["body"], **runtime.auth_scope(genesis.body, source_object.body, bad.ref.as_dict(), f.AUDITOR)}
            raw = reference_a(g) + b"\n"
            assert raw == reference_b(g) + b"\n"
            grant = {"body": g, "raw": raw, "signature": f.test_signature(raw, f.OWNER), "digest": sha(raw)}
            authority.leased["grants"].append(grant)
            objects = tuple(bad if o.kind == bad.kind else o for o in request.objects)
            request = intake.prepare("CREATE_ASSIGNMENT", objects, actor_ref=g["actor_ref"], grant_digest=grant["digest"], command_id=request.command.command_id)
            (output / "EXACT_SCOPED_TEST_GRANT.json").write_bytes(raw)
        request = replace(request, command=LimitedCommand(request.command.body(), intake.runtime),
                          objects=tuple(intake.runtime.object(o.kind, o.body, o.version) for o in request.objects))
        proposal_raw = reference_a(packet(request)) + b"\n"
        signature = f.test_signature(request.signing_bytes(), f.COORDINATOR)
        if expect == "DENY":
            assert proposal_raw == (inputs / "PROPOSAL.json").read_bytes() and signature == (inputs / "COMMAND.p7s").read_bytes()
        (output / "PROPOSAL.json").write_bytes(proposal_raw)
        (output / "COMMAND.p7s").write_bytes(signature)
        before = f.snapshot(intake.store)
        try:
            result = intake.accept(request, signature)
            actual = "ACCEPTED_COUNTEREXAMPLE"
            assert expect == "COUNTEREXAMPLE" and result.head.commit_seq == 14
            shutil.copyfile(working, output / "ACCEPTED_COUNTEREXAMPLE.sqlite")
        except ValidationError as error:
            actual = "DENY_WITHOUT_MUTATION"
            assert expect == "DENY" and error.code == "P0_ASSIGNMENT_ATTEMPT_CONTENT_MISMATCH" and before == f.snapshot(intake.store)
        if expect == "DENY":
            try:
                TransactionalHistoryStore.open_p0(inputs / "ACCEPTED_COUNTEREXAMPLE.sqlite")
            except ValidationError as error:
                assert error.code == "P0_ASSIGNMENT_ATTEMPT_CONTENT_MISMATCH"
            else:
                raise AssertionError("Pre-fix invalid history accepted by final reader")
    report = {"status": "CONFIRMED_P0_DEFECT_NOT_VALID_HISTORY" if expect == "COUNTEREXAMPLE" else "PASS_SAME_CREATE_BINDING_AND_REPLAY_REGRESSION",
              "expected": "DENY_WITHOUT_MUTATION", "actual": actual, "normative": "M04; assignment_manifest/3.attempt_ref SAME_CREATE_ASSIGNMENT_CONTENT; M08/M15",
              "authority": "SIMULATED_OS_CMS_TEST_ONLY; grant matches the altered assignment exactly, so missing authority does not mask the semantic defect",
              "source_database_sha256": sha(source.read_bytes()), "proposal_transport_sha256": sha(proposal_raw), "command_signing_sha256": sha(request.signing_bytes()),
              "signature_sha256": sha(signature), "sut_file_sha256": sha((ROOT / "src/bdb_audit/history/limited_protocol.py").read_bytes()), "harness_sha256": sha(Path(__file__).read_bytes())}
    (output / "EXECUTION.json").write_bytes(reference_a(report) + b"\n")
    print(reference_a(report).decode(), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--expect", choices=("COUNTEREXAMPLE", "DENY"), required=True)
    args = parser.parse_args()
    run(args.inputs, args.output, args.expect)
