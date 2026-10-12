"""Retain all 72 actual input/state outcomes from the unchanged production test."""
from copy import deepcopy
import json
from pathlib import Path
import shutil
import sys

import pytest

from bdb_audit.core.errors import ValidationError
from bdb_audit.product_p0_cli import packet
from tests.product import test_limited_p0 as f
from tests.product import test_limited_p0_state_matrix as matrix
from tools.nf02_p0_q1 import reference_a, reference_b
from tools.nf02_p0_q1_readback import ROOT, RUN, info
from tools.nf02_p0_reference import sha

out = RUN / "state-retained"
out.mkdir(exist_ok=False)
allowed = {
    "INITIALIZE_P0_FROM_APPROVED_GIT": {"EMPTY_HISTORY"}, "CREATE_ASSIGNMENT": {"GENESIS", "ABORTED"},
    "BIND_PACKAGE": {"ASSIGNED"}, "START_ATTEMPT": {"BOUND"}, "CONFIRM_DELIVERY": {"STARTED"},
    "INGEST_EVIDENCE": {"DELIVERED"}, "ACCEPT_RESULT": {"EVIDENCE_ACCEPTED"},
    "ABORT_ATTEMPT": {"ASSIGNED", "BOUND", "STARTED", "DELIVERED", "EVIDENCE_ACCEPTED"},
}
rows, active = [], {}
original_accept = f.accept


def accept(intake, request, cert=f.COORDINATOR):
    if not active:
        return original_accept(intake, request, cert)
    before = f.snapshot(intake.store)
    signature = f.test_signature(request.signing_bytes(), cert)
    active["signature_sha256"] = sha(signature)
    active["signing_preimage_sha256"] = sha(request.signing_bytes())
    try:
        result = original_accept(intake, request, cert)
    except ValidationError as error:
        assert before == f.snapshot(intake.store)
        active.update(actual="DENY_WITHOUT_MUTATION", error_code=error.code)
        rows[active["row_index"]] = {k: v for k, v in active.items() if k != "row_index"}
        raise
    else:
        active.update(actual="ACCEPT_ONE_COMMIT", accepted_head=result.head.as_dict(), receipt_digest=result.receipt.digest)
        rows[active["row_index"]] = {k: v for k, v in active.items() if k != "row_index"}
        return result


def trace(frame, event, arg):
    if frame.f_code.co_name != "candidate" or frame.f_code.co_filename != matrix.__file__:
        return None
    values = frame.f_locals
    if event == "call":
        operation, state = values["operation"], values["state"]
        active.clear()
        state_path = frame.f_back.f_locals["states"][state]
        active.update(id="STATE-%03d" % (len(rows) + 1), operation=operation, input_state=state,
            expected="ACCEPT_ONE_COMMIT" if state in allowed[operation] else "DENY_WITHOUT_MUTATION",
            input_database=info(state_path), authority="SIMULATED_OS_CMS_HTTPS_TEST_ONLY")
        rows.append(active.copy())
        active["row_index"] = len(rows) - 1
    elif event in {"return", "exception"}:
        if "command" in values:
            proposal = {"command": deepcopy(values["command"]), "objects": [{"kind": o.kind, "version": o.version, "body": o.body} for o in values["objects"]],
                        "raw_digests": sorted(values["prototype"].raw)}
            raw = reference_a(proposal)
            assert raw == reference_b(proposal)
            active.update(input_packet=proposal, input_packet_cjson_sha256=sha(raw))
        if event == "exception":
            error = arg[1]
            if isinstance(error, ValidationError):
                active.update(actual="DENY_WITHOUT_MUTATION", error_code=error.code, phase="CONSTRUCTOR_OR_PREPARE")
        rows[active["row_index"]] = {k: v for k, v in active.items() if k != "row_index"}
    return trace


with pytest.MonkeyPatch.context() as monkeypatch:
    monkeypatch.setattr(f, "accept", accept)
    setup = getattr(f.setup_p0, "__wrapped__")(getattr(f.corpus, "__wrapped__")(), out, monkeypatch)
    previous_trace = sys.gettrace()
    sys.settrace(trace)
    try:
        matrix.test_all_72_operation_state_pairs_in_central_store(setup, monkeypatch)
    finally:
        sys.settrace(previous_trace)
    # Store outcomes occur after candidate returns; complete the row from each
    # observed accept wrapper and the final iteration before serializing below.
    rows[active["row_index"]] = {k: v for k, v in active.items() if k != "row_index"}
assert len(rows) == 72
for row in rows:
    assert row.get("actual") == row["expected"], row
    assert info(ROOT / row["input_database"]["file"]) == row["input_database"]
report = {"status": "PASS_72_RETAINED_OPERATION_STATE_INPUTS", "allowed": sum(r["actual"] == "ACCEPT_ONE_COMMIT" for r in rows),
          "denied": sum(r["actual"] == "DENY_WITHOUT_MUTATION" for r in rows), "case_count": 72, "mismatches": [],
          "expected_basis": "Literal frozen M05 FSM sets, independent of observed Store outcomes", "test": info(Path(matrix.__file__)),
          "procedure": info(Path(__file__)), "runtime": info(ROOT / "src/bdb_audit/history/limited_protocol.py"),
          "retention": "Unchanged production test assertions check one-commit legal results and byte-identical no-mutation denials; wrapper records actual decisions only"}
assert (report["allowed"], report["denied"]) == (13, 59)
(out / "STATE_CASES.jsonl").write_bytes(b"".join(reference_a(r) + b"\n" for r in rows))
(out / "STATE_EXECUTION.json").write_bytes(reference_a(report) + b"\n")
print("STATE_RETENTION_PASS", 72, 13, 59, flush=True)
