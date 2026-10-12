"""Actual distinct Git commit/view/task history and foreign-source substitutions.

Production Store/Coordinator/transport/predicates are used. Only OS/CMS/HTTPS are
the existing explicitly simulated test fixtures. No authority is established.
"""
import base64
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

import pytest

from bdb_audit.history.limited_protocol import LimitedProtocol
from bdb_audit.history.limited_wire import LimitedCommand
from bdb_audit.history.store import TransactionalHistoryStore
from bdb_audit.workflow.limited_intake import LimitedIntake, LimitedRequest
from bdb_audit.workflow.limited_transport import approved_git_view
from tests.product import test_limited_p0 as f
from tools.nf02_p0_q1 import reference_a, reference_b
from tools.nf02_p0_q1_adversarial import Audit, retained_authority, refs_paths
from tools.nf02_p0_q1_readback import ROOT, RUN, info
from tools.nf02_p0_reference import sha, fixed_zip, history

out = RUN / "distinct-source"
audit = Audit(out)
approved = "ef3073c7042b33db7a2f32bff812e2e1f0df9de5"
paths = ["pyproject.toml", "src/bdb_audit/version.py"]


def git(*args):
    return subprocess.check_output(["git", "--no-replace-objects", "-C", str(ROOT), *args])


algorithm = git("rev-parse", "--show-object-format").strip().decode()
commit = git("rev-parse", approved + "^{commit}").strip().decode()
commit_raw = git("cat-file", "commit", commit)
tree = next(line[5:].decode() for line in commit_raw.splitlines() if line.startswith(b"tree "))
tree_raw = git("cat-file", "tree", tree)
objects = []
for kind, oid, raw in (("commit", commit, commit_raw), ("tree", tree, tree_raw)):
    assert hashlib.new(algorithm, kind.encode() + b" " + str(len(raw)).encode() + b"\0" + raw).hexdigest() == oid
    objects.append({"kind": kind, "git_oid": oid, "raw_sha256": sha(raw), "raw_base64": base64.b64encode(raw).decode()})
expected_entries, members = [], {}
for index, path in enumerate(sorted(paths, key=lambda value: value.encode("utf8")), 1):
    record = git("ls-tree", "-r", "--full-tree", commit, "--", path).strip()
    metadata, actual_path = record.split(b"\t", 1)
    mode, kind, oid = metadata.decode().split()
    assert actual_path.decode() == path and kind == "blob" and mode in {"100644", "100755"}
    raw = git("cat-file", "blob", oid)
    assert hashlib.new(algorithm, b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest() == oid
    member = "source/%08d.bin" % index
    expected_entries.append({"source_path": path, "transport_path": member, "mode": mode, "git_blob_oid": oid, "sha256": sha(raw), "bytes": len(raw)})
    members[member] = raw
    objects.append({"kind": "blob", "git_oid": oid, "raw_sha256": sha(raw), "raw_base64": base64.b64encode(raw).decode()})
expected_manifest = {"repository_id": "TEST_ONLY_REPOSITORY", "git_object_algorithm": algorithm, "commit_oid": commit, "tree_oid": tree, "entries": expected_entries}
manifest = reference_a(expected_manifest) + b"\n"
assert manifest == reference_b(expected_manifest) + b"\n"
_, actual_manifest, archive = approved_git_view(ROOT, approved, "TEST_ONLY_REPOSITORY", paths)
assert actual_manifest == manifest and archive == fixed_zip({"MANIFEST.json": manifest, **members})
(out / "SOURCE_MANIFEST.json").write_bytes(manifest)
(out / "SOURCE_ARCHIVE.zip").write_bytes(archive)
task = b"# TEST ONLY DISTINCT OWNER-APPROVED TASK\nAudit both files at the separately pinned commit.\n"
(out / "TASK.md").write_bytes(task)
with pytest.MonkeyPatch.context() as monkeypatch:
    audit.monkeypatch = monkeypatch
    setup = getattr(f.setup_p0, "__wrapped__")(getattr(f.corpus, "__wrapped__")(), out, monkeypatch)
    store, intake, authority, _, grant, source, genesis = setup
    c = intake.runtime.corpus
    body = {**source.body, "git_object_algorithm": algorithm, "git_commit_object_id": commit, "git_tree_object_id": tree,
            "source_manifest_raw_ref": c.raw_ref(manifest, "P0_BOOTSTRAP_SOURCE_V1", "application/json"),
            "source_archive_raw_ref": c.raw_ref(archive, "P0_BOOTSTRAP_SOURCE_V1", "application/zip"), "approved_view_digest": sha(manifest)}
    distinct_source = intake.runtime.object(source.kind, body, source.version)
    distinct_genesis = intake.runtime.object(genesis.kind, {**genesis.body, "source_ref": distinct_source.ref.as_dict(),
        "task_raw_ref": c.raw_ref(task, "P0_PACKAGE_TRANSPORT_V1", "text/markdown")}, genesis.version)
    scope = intake.runtime.auth_scope(distinct_genesis.body, body)
    request = intake.initialize(source=distinct_source, genesis=distinct_genesis, actor_ref="TEST_ONLY_COORDINATOR", grant_digest=grant(scope),
                                raw={sha(raw): raw for raw in (manifest, archive, task)})
    setup = store, intake, authority, request, grant, distinct_source, distinct_genesis
    audit.label = "DISTINCT_SOURCE"
    monkeypatch.setattr(f, "accept", audit.capture)
    flow = f.delivered(setup, monkeypatch)
    evidence, _ = f.evidence_request(flow)
    audit.capture(intake, evidence)
    audit.capture(intake, intake.result(actor_ref="TEST_ONLY_COORDINATOR", grant_digest=flow[4], admission_ref=evidence.objects[0].ref.as_dict()))
    monkeypatch.setattr(f, "accept", audit.original_accept)
    independent = history(Path(store.path))
    (out / "REFERENCE_HISTORY.json").write_bytes(reference_a(independent) + b"\n")
    source_authority, raws = retained_authority(RUN / "adversarial-final/CAMPAIGN_A/p0.sqlite")
    runtime = LimitedProtocol(source_authority, source_authority.leased)
    # Actual distinct source/task scope, not merely another UUID for equal bytes.
    original_genesis = next(r["body"] for r in json.loads((RUN / "adversarial-current-v2/ACCEPTED_TARGET_POOL.json").read_bytes()) if r["label"] == "CAMPAIGN_A" and r["kind"] == "campaign_genesis")
    original_source = next(r["body"] for r in json.loads((RUN / "adversarial-current-v2/ACCEPTED_TARGET_POOL.json").read_bytes()) if r["label"] == "CAMPAIGN_A" and r["kind"] == "nf02_p0_source_snapshot")
    original_scope = runtime.auth_scope(original_genesis, original_source)
    assert scope["source_scope_digest"] != original_scope["source_scope_digest"] and scope["view_task_digest"] != original_scope["view_task_digest"]
    monkeypatch.setattr("bdb_audit.history.limited_protocol.LimitedMachineAuthority", lambda: source_authority)
    for t in json.loads((RUN / "adversarial-current-v2/TEMPLATES.json").read_bytes()):
        if t["label"] == "CAMPAIGN_B":
            continue
        working = out / "working/p0.sqlite"
        shutil.copyfile(ROOT / t["state_file"], working)
        probe = LimitedIntake(TransactionalHistoryStore.open_p0(working))
        packet = t["packet"]
        original = LimitedRequest(LimitedCommand(packet["command"], probe.runtime), tuple(probe.runtime.object(o["kind"], o["body"], o["version"]) for o in packet["objects"]),
                                  tuple(packet["command"]["events"]), {d: raws[d] for d in packet["raw_digests"]})
        template = {**t, "request": original}
        for index, obj in enumerate(original.objects):
            for path, ref in refs_paths(obj.body):
                if ref["kind"] == "nf02_p0_source_snapshot":
                    audit.check_mutation(template, probe, index, path, distinct_source.ref.as_dict(), "ACTUAL_DIFFERENT_COMMIT_VIEW_TASK_SOURCE")
        for path, ref in refs_paths(original.command.body()):
            if ref["kind"] == "nf02_p0_source_snapshot":
                audit.check_mutation(template, probe, -1, path, distinct_source.ref.as_dict(), "COMMAND_ACTUAL_DIFFERENT_SOURCE", command=True)
report = {"status": "PASS_ACTUAL_DISTINCT_SOURCE_LOCAL_AUTHORITY", "case_count": len(audit.rows), "mismatches": [], "authority": "SIMULATED_OS_CMS_HTTPS_TEST_ONLY",
          "actual_git_objects": objects, "original_scope": original_scope, "distinct_scope": scope, "source_ref": distinct_source.ref.as_dict(),
          "inputs": [info(out / name) for name in ("SOURCE_MANIFEST.json", "SOURCE_ARCHIVE.zip", "TASK.md", "REFERENCE_HISTORY.json")],
          "protocol_sha256": sha((ROOT / "src/bdb_audit/history/limited_protocol.py").read_bytes()), "procedure": info(Path(__file__))}
(out / "DISTINCT_SOURCE_EXECUTION.json").write_bytes(reference_a(report) + b"\n")
print("DISTINCT_SOURCE_PASS", len(audit.rows), flush=True)
