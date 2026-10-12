"""Exact final readback of retained Q1 inputs/results; never qualification authority."""
import argparse
from collections import Counter
import json
from pathlib import Path
import sqlite3
import shutil
from typing import Any

from tools.nf02_p0_q1 import Vectors, reference_a, reference_b
from tools.nf02_p0_q1_contexts import corpus, replaced
from tools.nf02_p0_q1_history import object_hash
from tools.nf02_p0_reference import sha, valid, history

ROOT = Path(__file__).resolve().parents[1]
HERE = ROOT / "docs/PRODUCT_V1/NF02_P0_Q1_FINAL_HANDOFF"
RUN = HERE / "evidence/q1-closure-4132c5d"


def info(path):
    raw = path.read_bytes()
    return {"file": path.relative_to(ROOT).as_posix(), "sha256": sha(raw), "bytes": len(raw)}


def read(path):
    return json.loads(path.read_bytes())


def jsonl(path):
    with path.open("rb") as stream:
        for raw in stream:
            yield json.loads(raw)


def replay_input(source, recipe, target):
    """Reconstruct exact mutated SQLite bytes from the preserved source and recipe."""
    shutil.copyfile(source, target)
    with sqlite3.connect(target) as con:
        if "last_commit_field" in recipe:
            seq, raw = con.execute("SELECT seq,body FROM commits ORDER BY seq DESC LIMIT 1").fetchone()
            body = {**json.loads(raw), recipe["last_commit_field"]: recipe["replacement"]}
            digest = object_hash("commit_body", "3", body)
            cid = body["command_ref"]["logical_id"]
            receipt = json.loads(con.execute("SELECT body FROM receipts WHERE command_id=?", (cid,)).fetchone()[0])
            receipt["commit_ref"]["revision_digest"] = digest
            receipt["accepted_head"]["commit_hash"] = digest
            rd = object_hash("command_receipt", "3", receipt)
            con.execute("UPDATE commits SET body=?,commit_hash=? WHERE seq=?", (reference_a(body), digest, seq))
            con.execute("UPDATE accepted_head SET commit_hash=?", (digest,))
            con.execute("UPDATE receipts SET body=?,receipt_digest=? WHERE command_id=?", (reference_a(receipt), rd, cid))
            con.execute("UPDATE command_index SET receipt_digest=? WHERE command_id=?", (rd, cid))
        elif recipe["table"] == "commits":
            body = json.loads(con.execute("SELECT body FROM commits WHERE seq=?", (recipe["seq"],)).fetchone()[0])
            del body[recipe["remove"]]
            con.execute("UPDATE commits SET body=? WHERE seq=?", (reference_a(body), recipe["seq"]))
        elif recipe["table"] == "receipts":
            cid = recipe["command_id"]
            body = json.loads(con.execute("SELECT body FROM receipts WHERE command_id=?", (cid,)).fetchone()[0])
            if "remove" in recipe:
                del body[recipe["remove"]]
            body.update(recipe.get("replace", {}))
            digest = object_hash("command_receipt", "3", body)
            con.execute("UPDATE receipts SET body=?,receipt_digest=? WHERE command_id=?", (reference_a(body), digest, cid))
            con.execute("UPDATE command_index SET receipt_digest=? WHERE command_id=?", (digest, cid))
        elif recipe["table"] == "immutable_raw_artifacts":
            con.execute("DELETE FROM immutable_raw_artifacts WHERE digest=?", (recipe["delete_digest"],))
        else:
            raise AssertionError(recipe)
    return sha(target.read_bytes())


def run():
    c = corpus()
    docs = {document["$id"]: document for document in c.schemas.documents.values()}
    contexts = RUN / "contexts-final"
    execution = read(contexts / "CONTEXT_EXECUTION.json")
    assert execution["mismatches"] == [] and len(execution["per_schema"]) == 43
    bases = read(contexts / "CONTEXT_BASES.json")
    for digest, base in bases.items():
        assert sha(reference_a(base)) == digest and reference_a(base) == reference_b(base)
    constructor = Vectors(c.schemas.documents)
    samples: dict[bytes, list[Any]] = {}
    count = 0
    per_schema: Counter[str] = Counter()
    decisions: Counter[str] = Counter()
    for row in jsonl(contexts / "CONTEXT_CASES.jsonl"):
        assert row["expected_schema"] == row["actual_schema"]
        base = bases[row["base_sha256"]]
        if "replacement_recipe" not in row:
            value = row["replacement"]
        else:
            recipe = row["replacement_recipe"]
            if "integer_decimal" in recipe:
                value = int(recipe["integer_decimal"])
            elif "string_repeat" in recipe:
                value = recipe["string_repeat"] * recipe["count"]
            else:
                key = reference_a(recipe["array_samples"])
                pool = samples.setdefault(key, [])
                while len(pool) < recipe["count"]:
                    pool.append(constructor.sample(recipe["array_samples"], len(pool) + recipe["start_seed"]))
                value = pool[:recipe["count"]]
        full = replaced(base, row["path"], value, remove=row["remove"])
        assert valid(c.schemas.documents[row["schema"]], full, docs) == row["expected_schema"], row["id"]
        raw = reference_a(full)
        assert sha(raw) == row["input_exact_json_sha256"] and len(raw) == row["input_exact_json_bytes"], row["id"]
        if row["in_cjson_domain"]:
            assert raw == reference_b(full)
        assert sha(c.files["docs/PRODUCT_V1/NF02_P0_LIMITED_MODEL/schemas/" + row["schema"] + ".schema.json"]) == row["schema_sha256"]
        count += 1
        per_schema[row["schema"]] += 1
        decisions["ACCEPT_SCHEMA" if row["actual_schema"] else "DENY_SCHEMA"] += 1
        if count % 10000 == 0:
            print("READBACK_CONTEXTS", count, flush=True)
    assert count == execution["case_count"] and dict(per_schema) == execution["per_schema"]
    adversarial = RUN / "adversarial-current-v2"
    templates = {t["id"]: t for t in read(adversarial / "TEMPLATES.json")}
    for template in templates.values():
        assert sha((ROOT / template["state_file"]).read_bytes()) == template["state_sha256"]
    totals = {}
    field_cases: dict[str, list[dict[str, Any]]] = {}
    for directory, report_name in ((adversarial, "ADVERSARIAL_EXECUTION.json"), (RUN / "supplement-current", "SUPPLEMENT_EXECUTION.json"),
                                   (RUN / "entrypoints-current", "ENTRYPOINT_EXECUTION.json")):
        report = read(directory / report_name)
        case_file = info(directory / "ADVERSARIAL_CASES.jsonl")["file"]
        rows = list(jsonl(directory / "ADVERSARIAL_CASES.jsonl"))
        assert len(rows) == report["case_count"] and not report["mismatches"]
        for row in rows:
            inputs = row["inputs"]
            assert row["expected"] == row["actual"] and sha(reference_a(inputs)) == row["input_exact_json_sha256"], row["id"]
            if "altered_body_sha256" in inputs and inputs["template"] in templates:
                t = templates[inputs["template"]]
                assert sha(reference_a(t["packet"])) == inputs["template_packet_sha256"]
                original = t["packet"]["command"] if inputs["command"] else t["packet"]["objects"][inputs["object_index"]]["body"]
                altered = replaced(original, inputs["path"], inputs["value"], remove=inputs["remove"])
                assert sha(reference_a(altered)) == inputs["altered_body_sha256"]
                kind = "command_envelope" if inputs["command"] else t["packet"]["objects"][inputs["object_index"]]["kind"]
                field = str(inputs["path"][0])
                field_cases.setdefault(kind + "::" + field, []).append({"file": case_file, "case_id": row["id"], "variant": inputs["variant"], "input_sha256": row["input_exact_json_sha256"]})
        totals[directory.name] = len(rows)
    source = RUN / "adversarial-final/CAMPAIGN_A/p0.sqlite"
    source_sha = sha(source.read_bytes())
    replay_rows = list(jsonl(RUN / "replay-current/REPLAY_CASES.jsonl"))
    target = RUN / "readback-replay.sqlite"
    for row in replay_rows:
        assert row["expected"] == row["actual"] == "DENY_WITHOUT_REPAIR_OR_MUTATION"
        assert row["source_database_sha256"] == source_sha
        assert replay_input(source, row["input_recipe"], target) == row["input_database_sha256"], row["id"]
    replay_report = read(RUN / "replay-current/REPLAY_EXECUTION.json")
    assert replay_report["case_count"] == len(replay_rows) and not replay_report["mismatches"]
    counterexample = RUN / "same-create-counterexample-v2"
    fixed = RUN / "same-create-fixed"
    correction = read(fixed / "EXECUTION.json")
    assert correction["expected"] == correction["actual"] == "DENY_WITHOUT_MUTATION"
    assert correction["sut_file_sha256"] == sha((ROOT / "src/bdb_audit/history/limited_protocol.py").read_bytes())
    for name in ("PROPOSAL.json", "COMMAND.p7s", "INPUT_STATE.sqlite"):
        assert (counterexample / name).read_bytes() == (fixed / name).read_bytes()
    assert correction["proposal_transport_sha256"] == sha((fixed / "PROPOSAL.json").read_bytes())
    assert correction["source_database_sha256"] == sha((fixed / "INPUT_STATE.sqlite").read_bytes())
    assert correction["signature_sha256"] == sha((fixed / "COMMAND.p7s").read_bytes())
    assert sha((RUN / "SUT_BEFORE_SAME_CREATE_FIX.py").read_bytes()) == read(counterexample / "EXECUTION.json")["sut_file_sha256"]
    first = ["INITIALIZE_P0_FROM_APPROVED_GIT", "CREATE_ASSIGNMENT", "BIND_PACKAGE", "START_ATTEMPT", "CONFIRM_DELIVERY", "INGEST_EVIDENCE"]
    retried = first + ["ABORT_ATTEMPT", "CREATE_ASSIGNMENT", "BIND_PACKAGE", "START_ATTEMPT", "CONFIRM_DELIVERY", "INGEST_EVIDENCE"]
    proof: list[dict[str, Any]] = []
    for source_path, operations in ((source, retried + ["ACCEPT_RESULT"]), (RUN / "adversarial-verified/CAMPAIGN_B/p0.sqlite", first),
                                    (RUN / "supplement-current/THREE_ATTEMPTS.sqlite", retried + ["ABORT_ATTEMPT", "CREATE_ASSIGNMENT"])):
        result = history(source_path, expected_operations=operations)
        name = "INDEPENDENT_HISTORY_" + str(len(proof) + 1) + ".json"
        (RUN / name).write_bytes(reference_a({"source": info(source_path), "result": result, "reference": info(ROOT / "tools/nf02_p0_reference.py")}) + b"\n")
        proof.append(info(RUN / name))
    try:
        history(counterexample / "ACCEPTED_COUNTEREXAMPLE.sqlite", expected_operations=retried + ["ABORT_ATTEMPT", "CREATE_ASSIGNMENT"])
    except AssertionError as error:
        assert str(error) == "SAME_CREATE_ASSIGNMENT_CONTENT"
        independent_bad_history = "DENY_SAME_CREATE_ASSIGNMENT_CONTENT"
    else:
        raise AssertionError("Independent history procedure admitted the pre-fix counterexample")
    report = {"status": "PASS_FINAL_EXACT_INPUT_RESULT_READBACK_Q1_REMAINS_OPEN", "candidate_manifest_sha256": c.bindings()["candidate_manifest_sha256"],
              "contexts": count, "per_schema": dict(per_schema), "schema_decisions": dict(decisions), "cases": totals,
              "replay_cases": len(replay_rows), "source_database_sha256": source_sha, "material_field_case_index": field_cases,
              "authority": "LOCAL_SIMULATED_POSITIVES; PENDING_OWNER_PROVISIONING", "author_record_issued": False,
              "scope": "All retained full input recipes/exact hashes, execution expected/actual equality, schema identities and source states reread; execution decisions are retained results, not a second claimed execution.",
              "same_create_binding": correction,
              "independent_history_proofs": proof, "independent_counterexample_expected": "DENY_SAME_CREATE_ASSIGNMENT_CONTENT", "independent_counterexample_actual": independent_bad_history,
              "unexplained_mismatches": [], "inputs": [info(p) for p in [contexts / "CONTEXT_EXECUTION.json", contexts / "CONTEXT_BASES.json", contexts / "CONTEXT_CASES.jsonl", adversarial / "ADVERSARIAL_EXECUTION.json", adversarial / "ADVERSARIAL_CASES.jsonl", adversarial / "TEMPLATES.json", RUN / "supplement-current/SUPPLEMENT_EXECUTION.json", RUN / "supplement-current/ADVERSARIAL_CASES.jsonl", RUN / "entrypoints-current/ENTRYPOINT_EXECUTION.json", RUN / "entrypoints-current/ADVERSARIAL_CASES.jsonl", RUN / "replay-current/REPLAY_EXECUTION.json", RUN / "replay-current/REPLAY_CASES.jsonl", fixed / "EXECUTION.json", fixed / "PROPOSAL.json", counterexample / "ACCEPTED_COUNTEREXAMPLE.sqlite", ROOT / "src/bdb_audit/history/limited_protocol.py", Path(__file__)]]}
    (RUN / "FINAL_Q1_AUDIT.json").write_bytes(reference_a(report) + b"\n")
    print("FINAL_READBACK_PASS", count, totals, "replay", len(replay_rows), flush=True)


if __name__ == "__main__":
    argparse.ArgumentParser().parse_args()
    run()
