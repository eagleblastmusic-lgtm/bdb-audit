"""Every schema-allowed but operation-inapplicable basis target denies centrally."""
from copy import deepcopy
import json
from pathlib import Path
import shutil

import pytest

from bdb_audit.core.errors import ValidationError
from bdb_audit.history.limited_protocol import LimitedProtocol
from bdb_audit.history.limited_wire import LimitedCommand
from bdb_audit.history.store import TransactionalHistoryStore
from bdb_audit.workflow.limited_intake import LimitedIntake, LimitedRequest
from tests.product import test_limited_p0 as f
from tools.nf02_p0_q1 import reference_a, reference_b
from tools.nf02_p0_q1_adversarial import retained_authority
from tools.nf02_p0_q1_readback import ROOT, RUN, read, info
from tools.nf02_p0_reference import sha

out = RUN / "basis-applicability"
out.mkdir(exist_ok=False)
excluded = {"artifact_contract_registry", "schema_registry", "policy_revision", "spec_revision", "trust_profile", "installation_bootstrap_profile", "bdb_audit_lane_result"}
pool = read(RUN / "adversarial-current-v2/ACCEPTED_TARGET_POOL.json")
targets = {kind: next(r["ref"] for r in pool if r["label"] == "CAMPAIGN_A" and r["kind"] == kind) for kind in sorted(excluded)}
templates = [t for t in read(RUN / "adversarial-current-v2/TEMPLATES.json") if t["label"] == "CAMPAIGN_A" or t["packet"]["command"]["operation"] == "ABORT_ATTEMPT"]
assert len(templates) == 8
authority, raws = retained_authority(RUN / "adversarial-final/CAMPAIGN_A/p0.sqlite")
rows = []
with pytest.MonkeyPatch.context() as monkeypatch:
    monkeypatch.setattr("bdb_audit.history.limited_protocol.LimitedMachineAuthority", lambda: authority)
    monkeypatch.setattr("bdb_audit.history.limited_protocol.verify_cms", f.simulated_verify)
    monkeypatch.setattr("bdb_audit.history.limited_authority.verify_cms", f.simulated_verify)
    for t in templates:
        working = out / "p0.sqlite"
        shutil.copyfile(ROOT / t["state_file"], working)
        intake = LimitedIntake(TransactionalHistoryStore.open_p0(working))
        p = t["packet"]
        for kind, target in targets.items():
            body = deepcopy(p["command"])
            body["basis_refs"] = sorted([*body["basis_refs"], target], key=lambda r: (r["kind"], r["logical_id"], r["revision_digest"]))
            request = LimitedRequest(LimitedCommand(body, intake.runtime), tuple(intake.runtime.object(o["kind"], o["body"], o["version"]) for o in p["objects"]),
                                     tuple(body["events"]), {d: raws[d] for d in p["raw_digests"]})
            before = f.snapshot(intake.store)
            signature = f.test_signature(request.signing_bytes(), t["cert"])
            try:
                intake.accept(request, signature)
            except ValidationError as error:
                assert error.code == "P0_COMMAND_PRIOR_BASIS" and before == f.snapshot(intake.store), error.code
            else:
                raise AssertionError("Operation-inapplicable schema target admitted as basis")
            raw = reference_a(body)
            assert raw == reference_b(body)
            rows.append({"id": "BASIS-%03d" % (len(rows) + 1), "operation": body["operation"], "target_kind": kind, "template": t["id"],
                "input_command": body, "input_command_cjson_sha256": sha(raw), "input_database": info(ROOT / t["state_file"]),
                "signature_sha256": sha(signature), "signing_preimage_sha256": sha(request.signing_bytes()),
                "expected": "DENY_P0_COMMAND_PRIOR_BASIS_WITHOUT_MUTATION", "actual": "DENY_P0_COMMAND_PRIOR_BASIS_WITHOUT_MUTATION",
                "normative": "M04/M05: exact operation prior basis excludes initial pins/content and terminal result; schema union alone does not confer applicability"})
report = {"status": "PASS_ALL_SEVEN_EXCLUDED_BASIS_TARGETS_IN_ALL_EIGHT_OPERATIONS", "case_count": len(rows), "mismatches": [],
          "authority": "SIMULATED_OS_CMS_TEST_ONLY", "procedure": info(Path(__file__)), "runtime": info(ROOT / "src/bdb_audit/history/limited_protocol.py")}
assert len(rows) == 56
(out / "BASIS_CASES.jsonl").write_bytes(b"".join(reference_a(r) + b"\n" for r in rows))
(out / "BASIS_EXECUTION.json").write_bytes(reference_a(report) + b"\n")
print("BASIS_APPLICABILITY_PASS", len(rows), flush=True)
