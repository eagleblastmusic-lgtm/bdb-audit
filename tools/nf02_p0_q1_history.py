"""Independent-input replay mutation cases through the real P0 Store reader.

Retained test-only CMS/OS inputs stay test-only. Coherent rehash cases target
mandatory semantic mismatches, not undetectable arbitrary host rewrites.
"""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import shutil
import sqlite3
from typing import Any

import pytest

from bdb_audit.core.errors import ValidationError
from bdb_audit.history.store import TransactionalHistoryStore
from tools.nf02_p0_q1 import reference_a, reference_b
from tools.nf02_p0_reference import sha
from tools.nf02_p0_q1_adversarial import retained_authority
from tests.product import test_limited_p0 as f

ROOT = Path(__file__).resolve().parents[1]


def object_hash(kind, version, body):
    assert reference_a(body) == reference_b(body)
    return sha(("BDB2/" + kind + "/" + version).encode("ascii") + b"\0" + reference_b(body))


def run(source, output, reuse_cases=None):
    source, output = source.resolve(), output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    (output / "working").mkdir()
    working = output / "working/p0.sqlite"
    authority, raw_pool = retained_authority(source)
    rows: list[dict[str, Any]] = []
    previous = {r["case"]: r for r in (json.loads(raw) for raw in reuse_cases.read_bytes().splitlines())} if reuse_cases else {}
    with sqlite3.connect(source) as con:
        commits = [(seq, json.loads(raw)) for seq, raw in con.execute("SELECT seq,body FROM commits")]
        receipts = [(cid, json.loads(raw)) for cid, raw in con.execute("SELECT command_id,body FROM receipts")]
        raw_digests = [d for d, in con.execute("SELECT digest FROM immutable_raw_artifacts")]
    source_hash = sha(source.read_bytes())
    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr("bdb_audit.history.limited_protocol.LimitedMachineAuthority", lambda: authority)
        monkeypatch.setattr("bdb_audit.history.limited_protocol.verify_cms", f.simulated_verify)
        monkeypatch.setattr("bdb_audit.history.limited_authority.verify_cms", f.simulated_verify)

        def deny(label, mutation, *, input_recipe):
            shutil.copyfile(source, working)
            with sqlite3.connect(working) as con:
                mutation(con)
            if label in previous:
                row = previous[label]
                assert row["expected"] == row["actual"] == "DENY_WITHOUT_REPAIR_OR_MUTATION"
                assert row["source_database_sha256"] == source_hash and row["input_recipe"] == input_recipe
                assert row["input_database_sha256"] == sha(working.read_bytes())
                assert row["id"] == "REPLAY-%05d" % (len(rows) + 1)
                rows.append(row)
                with (output / "REPLAY_CASES.jsonl").open("ab") as stream:
                    stream.write(reference_a(row) + b"\n")
                return
            before = f.snapshot(type("Location", (), {"path": str(working)})())
            try:
                TransactionalHistoryStore.open_p0(working)
            except ValidationError as error:
                assert before == f.snapshot(type("Location", (), {"path": str(working)})())
                row = {"id": "REPLAY-%05d" % (len(rows) + 1), "case": label, "expected": "DENY_WITHOUT_REPAIR_OR_MUTATION",
                       "actual": "DENY_WITHOUT_REPAIR_OR_MUTATION", "error_code": error.code, "source_database_sha256": source_hash,
                       "input_database_sha256": sha(working.read_bytes()), "input_recipe": input_recipe, "normative": "M03/M04/M05/M14/M17"}
                rows.append(row)
                with (output / "REPLAY_CASES.jsonl").open("ab") as stream:
                    stream.write(reference_a(row) + b"\n")
                if len(rows) % 100 == 0:
                    print("REPLAY_CASES", len(rows), flush=True)
                return
            raise AssertionError((label, "Corrupted history accepted"))

        for seq, original in commits:
            for field in original:
                changed = {k: v for k, v in original.items() if k != field}
                def remove_commit_field(con, seq=seq, changed=changed):
                    con.execute("UPDATE commits SET body=? WHERE seq=?", (reference_a(changed), seq))
                deny("COMMIT_REQUIRED/" + str(seq) + "/" + field, remove_commit_field, input_recipe={"table": "commits", "seq": seq, "remove": field})
        for command_id, original in receipts:
            for field in original:
                changed = {k: v for k, v in original.items() if k != field}
                digest = object_hash("command_receipt", "3", changed)
                def remove_receipt_field(con, changed=changed, digest=digest, command_id=command_id):
                    con.execute("UPDATE receipts SET body=?,receipt_digest=? WHERE command_id=?", (reference_a(changed), digest, command_id))
                    con.execute("UPDATE command_index SET receipt_digest=? WHERE command_id=?", (digest, command_id))
                deny("RECEIPT_COHERENT_HASH_REQUIRED/" + command_id + "/" + field, remove_receipt_field,
                     input_recipe={"table": "receipts", "command_id": command_id, "remove": field, "rehash_receipt_and_index": True})
            variants = {"WRONG_COMMAND": {**original["command_ref"], "logical_id": "command_envelope_00000000-0000-4000-8000-000000000000"},
                        "WRONG_COMMIT": {**original["commit_ref"], "revision_digest": "0" * 64},
                        "WRONG_ACCEPTED_HEAD": {**original["accepted_head"], "commit_seq": original["accepted_head"]["commit_seq"] + 1}}
            for label, ref_value in variants.items():
                field = {"WRONG_COMMAND": "command_ref", "WRONG_COMMIT": "commit_ref", "WRONG_ACCEPTED_HEAD": "accepted_head"}[label]
                changed = {**original, field: ref_value}
                digest = object_hash("command_receipt", "3", changed)
                def replace_receipt_ref(con, changed=changed, digest=digest, command_id=command_id):
                    con.execute("UPDATE receipts SET body=?,receipt_digest=? WHERE command_id=?", (reference_a(changed), digest, command_id))
                    con.execute("UPDATE command_index SET receipt_digest=? WHERE command_id=?", (digest, command_id))
                deny("RECEIPT_COHERENT_HASH/" + command_id + "/" + label, replace_receipt_ref,
                     input_recipe={"table": "receipts", "command_id": command_id, "replace": {field: ref_value}, "rehash_receipt_and_index": True})
        seq, original = commits[-1]
        for field, value in (("actor_ref", "UNAUTHORIZED_ACTOR"), ("command_digest", "0" * 64), ("events", []),
                             ("previous_head", {**original["previous_head"], "commit_seq": seq + 1}),
                             ("policy_ref", {**original["policy_ref"], "logical_id": "policy_revision_00000000-0000-4000-8000-000000000000"}),
                             ("immutable_object_refs", list(reversed(original["immutable_object_refs"])))):
            changed = {**original, field: value}
            commit_digest = object_hash("commit_body", "3", changed)
            cid = original["command_ref"]["logical_id"]
            receipt = next(r for c, r in receipts if c == cid)
            receipt = deepcopy(receipt)
            receipt["commit_ref"]["revision_digest"] = commit_digest
            receipt["accepted_head"]["commit_hash"] = commit_digest
            receipt_digest = object_hash("command_receipt", "3", receipt)
            def replace_chain_context(con, changed=changed, commit_digest=commit_digest, receipt=receipt, receipt_digest=receipt_digest, cid=cid):
                con.execute("UPDATE commits SET body=?,commit_hash=? WHERE seq=?", (reference_a(changed), commit_digest, seq))
                con.execute("UPDATE accepted_head SET commit_hash=?", (commit_digest,))
                con.execute("UPDATE receipts SET body=?,receipt_digest=? WHERE command_id=?", (reference_a(receipt), receipt_digest, cid))
                con.execute("UPDATE command_index SET receipt_digest=? WHERE command_id=?", (receipt_digest, cid))
            deny("LAST_COMMIT_COHERENT_CHAIN/" + field, replace_chain_context,
                 input_recipe={"last_commit_field": field, "replacement": value, "rehash_commit_head_receipt_index": True})
        for digest in raw_digests:
            def remove_raw(con, digest=digest):
                con.execute("DELETE FROM immutable_raw_artifacts WHERE digest=?", (digest,))
            # Not every retained raw is referenced by accepted facts (outbox
            # sidecars can include extra current grants). Only mandatory reachable
            # raw is a replay prerequisite. Determine reachability independently.
            mandatory = set()
            def walk(v):
                if isinstance(v, dict):
                    if "raw_digest" in v:
                        mandatory.add(v["raw_digest"])
                    for x in v.values():
                        walk(x)
                elif isinstance(v, list):
                    for x in v:
                        walk(x)
            with sqlite3.connect(source) as con:
                for raw, in con.execute("SELECT body FROM immutable_objects UNION ALL SELECT body FROM commits"):
                    walk(json.loads(raw))
                for gd, sd in con.execute("SELECT grant_digest,signature_digest FROM p0_grant_proofs"):
                    mandatory.update((gd, sd))
            expanded: set[str] = set()
            while mandatory - expanded:
                d = next(iter(mandatory - expanded))
                expanded.add(d)
                try:
                    walk(json.loads(raw_pool[d]))
                except (ValueError, UnicodeDecodeError):
                    pass
            if digest in mandatory:
                deny("MISSING_MANDATORY_RAW/" + digest, remove_raw, input_recipe={"table": "immutable_raw_artifacts", "delete_digest": digest})
        # Current grants are not historical acceptance. Replay uses the retained
        # historical signed inputs; exact retry still requires current rights.
        shutil.copyfile(source, working)
        saved = authority.leased["grants"]
        authority.leased["grants"] = []
        before = working.read_bytes()
        store = TransactionalHistoryStore.open_p0(working)
        assert store.rebuild_projection()["state"] == "RESULT_ACCEPTED" and working.read_bytes() == before
        authority.leased["grants"] = saved
        report = {"status": "PASS_LOCAL_REPLAY_NEGATIVES", "case_count": len(rows), "positive_historical_grant_separation": True,
                  "source_file": source.relative_to(ROOT).as_posix(), "source_database_sha256": source_hash,
                  "authority": "SIMULATED_OS_CMS_NO_REAL_QUALIFICATION", "mismatches": [],
                  "reference_sha256": sha((ROOT / "tools/nf02_p0_reference.py").read_bytes()), "harness_sha256": sha(Path(__file__).read_bytes())}
        if reuse_cases:
            assert set(previous) <= {r["case"] for r in rows}
            report["reused_actual_execution"] = {"file": reuse_cases.resolve().relative_to(ROOT).as_posix(), "sha256": sha(reuse_cases.read_bytes()), "count": len(previous),
                "readback": "Every mutation independently reconstructed with exact SQLite SHA match; production source and fixtures unchanged; final positive native reader executed again. Prior final metadata path normalization repaired."}
        (output / "REPLAY_EXECUTION.json").write_bytes(reference_a(report) + b"\n")
        print("REPLAY_PASS", len(rows), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--reuse-cases", type=Path)
    args = parser.parse_args()
    run(args.source, args.output, args.reuse_cases)
