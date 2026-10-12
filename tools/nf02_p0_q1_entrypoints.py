"""Semantic denial through each applicable production P0 entry, test-only CMS/OS."""
import argparse
from contextlib import redirect_stdout, redirect_stderr
from copy import deepcopy
from dataclasses import replace
import io
import json
from pathlib import Path
import shutil

import pytest

from bdb_audit.cli import run_cli
from bdb_audit.product_cli import run_product
from bdb_audit.product_p0_cli import run_p0, packet
from bdb_audit.p0_service import execute
from bdb_audit.core.errors import ValidationError
from bdb_audit.history.limited_protocol import LimitedProtocol
from bdb_audit.history.limited_wire import LimitedCommand
from bdb_audit.history.store import TransactionalHistoryStore
from bdb_audit.workflow.inbox import E1ResultInbox
from bdb_audit.workflow.limited_intake import LimitedIntake, LimitedRequest
from tools.nf02_p0_q1_adversarial import Audit, retained_authority, refs_paths
from tools.nf02_p0_q1_contexts import replaced
from tools.nf02_p0_q1 import reference_a
from tools.nf02_p0_reference import sha
from tests.product import test_limited_p0 as f

ROOT = Path(__file__).resolve().parents[1]


def run(source, templates_file, output):
    output = output.resolve()
    audit = Audit(output)
    authority, raws = retained_authority(source)
    runtime = LimitedProtocol(authority, authority.leased)
    selected = [t for t in json.loads(templates_file.read_bytes()) if t["label"] == "CAMPAIGN_A" or t["packet"]["command"]["operation"] == "ABORT_ATTEMPT"]
    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr("bdb_audit.history.limited_protocol.LimitedMachineAuthority", lambda: authority)
        monkeypatch.setattr("bdb_audit.history.limited_protocol.verify_cms", f.simulated_verify)
        monkeypatch.setattr("bdb_audit.history.limited_authority.verify_cms", f.simulated_verify)
        for t in selected:
            working = output / "working/p0.sqlite"
            shutil.copyfile(ROOT / t["state_file"], working)
            intake = LimitedIntake(TransactionalHistoryStore.open_p0(working))
            b = t["packet"]
            original = LimitedRequest(LimitedCommand(b["command"], runtime), tuple(runtime.object(o["kind"], o["body"], o["version"]) for o in b["objects"]),
                                      tuple(b["command"]["events"]), {d: raws[d] for d in b["raw_digests"]})
            op = original.command.command_kind
            if op == "START_ATTEMPT":
                event = deepcopy(original.events[0])
                event["binding_ref"]["logical_id"] = "assignment_package_binding_00000000-0000-4000-8000-000000000000"
                altered = intake.prepare(op, [], actor_ref=original.command.actor_ref, grant_digest=b["command"]["grant_digest"], events=[event], command_id=original.command.command_id)
            else:
                index, obj, path, ref = next((i, o, p, r) for i, o in enumerate(original.objects) for p, r in refs_paths(o.body))
                changed = replaced(obj.body, path, {**ref, "logical_id": ref["kind"] + "_00000000-0000-4000-8000-000000000000"})
                objects = tuple(runtime.object(o.kind, changed if i == index else o.body, o.version) for i, o in enumerate(original.objects))
                # All wrapper inputs carry this same semantically invalid but
                # correctly signed/closed packet through the central Store.
                altered = intake.prepare(op, objects, actor_ref=original.command.actor_ref, grant_digest=b["command"]["grant_digest"], raw=original.raw, command_id=original.command.command_id)
            for entry in ("INTAKE", "STORE", "STORE_GENERATORS", "P0_CLI", "SERVICE", "PRODUCT_ROUTER", "TOP_LEVEL_CLI", "E1_INBOX"):
                if entry == "E1_INBOX" and op not in {"INGEST_EVIDENCE", "ACCEPT_RESULT"}:
                    continue
                for legal in ((False, True) if entry in {"PRODUCT_ROUTER", "TOP_LEVEL_CLI"} else (False,)):
                    shutil.copyfile(ROOT / t["state_file"], working)
                    request = original if legal else altered
                    request = replace(request, command=LimitedCommand(request.command.body(), intake.runtime),
                                      objects=tuple(intake.runtime.object(o.kind, o.body, o.version) for o in request.objects))
                    signature = f.test_signature(request.signing_bytes(), t["cert"])
                    before = f.snapshot(intake.store)
                    response = {}
                    try:
                        if entry in {"P0_CLI", "SERVICE", "PRODUCT_ROUTER", "TOP_LEVEL_CLI"}:
                            raw_dir = output / "inputs"
                            for digest, raw in request.raw.items():
                                (raw_dir / digest).write_bytes(raw)
                            input_path, sig_path = raw_dir / "packet.json", raw_dir / "signature.p7s"
                            input_path.write_bytes(reference_a(packet(request)) + b"\n")
                            sig_path.write_bytes(signature)
                            args = ["accept", "--store", str(working), "--input", str(input_path), "--signature", str(sig_path), "--raw-dir", str(raw_dir)]
                            with redirect_stdout(io.StringIO()) as stdout, redirect_stderr(io.StringIO()) as stderr:
                                if entry == "SERVICE":
                                    code, raw_response = execute(args)
                                else:
                                    fn = {"P0_CLI": run_p0, "PRODUCT_ROUTER": run_product, "TOP_LEVEL_CLI": run_cli}[entry]
                                    prefix = [] if entry == "P0_CLI" else ["p0"] if entry == "PRODUCT_ROUTER" else ["product", "p0"]
                                    code = fn(prefix + args)
                                    raw_response = stdout.getvalue() + stderr.getvalue()
                            response = json.loads(raw_response)
                            if code:
                                raise ValidationError(response["error"])
                        elif entry == "E1_INBOX":
                            inbox = E1ResultInbox.for_p0(intake.store)
                            fn = inbox.accept_p0_evidence if op == "INGEST_EVIDENCE" else inbox.accept_p0_result
                            fn(request, authentication=signature)
                        elif entry == "INTAKE":
                            intake.accept(request, signature)
                        else:
                            supplied_objects = (o for o in request.objects) if entry == "STORE_GENERATORS" else request.objects
                            supplied_events = (e for e in request.events) if entry == "STORE_GENERATORS" else request.events
                            intake.store.accept(request.command, immutable_objects=supplied_objects, ordered_events=supplied_events, authentication=signature, raw_artifacts=request.raw)
                        actual = "ACCEPT_ONE_COMMIT"
                        assert legal and intake.store.head().commit_seq == t["post_head"]["commit_seq"]
                    except ValidationError as error:
                        actual = "DENY_WITHOUT_MUTATION"
                        assert not legal and before == f.snapshot(intake.store)
                        response = {"error": error.code}
                    audit.record(t["id"] + "/" + entry + ("/LEGAL" if legal else "/SEMANTIC_TARGET_DENIAL"), "ACCEPT_ONE_COMMIT" if legal else "DENY_WITHOUT_MUTATION", actual,
                                 {"entry": entry, "template": t["id"], "packet": packet(request), "signature_sha256": sha(signature), "signing_sha256": sha(request.signing_bytes()),
                                  "input_database_sha256": t["state_sha256"], "response": response})
    report = {"status": "PASS_LOCAL_PRODUCTION_ENTRY_POINTS", "case_count": len(audit.rows), "mismatches": [], "authority": "SIMULATED_OS_CMS_NO_REAL_QUALIFICATION",
              "source_database_sha256": sha(source.read_bytes()), "templates_sha256": sha(templates_file.read_bytes()), "harness_sha256": sha(Path(__file__).read_bytes())}
    (output / "ENTRYPOINT_EXECUTION.json").write_bytes(reference_a(report) + b"\n")
    print("ENTRYPOINT_PASS", len(audit.rows), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--templates", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run(args.source, args.templates, args.output)
