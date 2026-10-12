"""Reconstruct retained inputs faster, without replacing any production code.

Only the test-input constructor uses the independent schema interpreter in place
of repeated jsonschema construction. Exact full-input SHA-256 must still match
the originally executed input. Actual runtime decisions are never substituted.
"""
from tools import nf02_p0_q1_readback as readback
from tools.nf02_p0_q1 import Vectors, reference_a
from tools.nf02_p0_reference import valid
from tools.nf02_p0_reference import history, sha
from pathlib import Path
import base64
import hashlib


class ExactInputConstructor(Vectors):
    def __init__(self, documents):
        super().__init__(documents)
        self.reference_documents = {d["$id"]: d for d in documents.values()}

    def valid(self, schema, value):
        return valid(schema, value, self.reference_documents)


readback.Vectors = ExactInputConstructor
readback.run()
report_path = readback.RUN / "FINAL_Q1_AUDIT.json"
report = readback.read(report_path)
distinct = readback.RUN / "distinct-source"
extra = readback.read(distinct / "DISTINCT_SOURCE_EXECUTION.json")
assert not extra["mismatches"]
templates = {t["id"]: t for t in readback.read(readback.RUN / "adversarial-current-v2/TEMPLATES.json")}
case_file = readback.info(distinct / "ADVERSARIAL_CASES.jsonl")
cases = list(readback.jsonl(distinct / "ADVERSARIAL_CASES.jsonl"))
assert len(cases) == extra["case_count"]
for row in cases:
    inputs = row["inputs"]
    assert row["expected"] == row["actual"] and sha(reference_a(inputs)) == row["input_exact_json_sha256"]
    if "altered_body_sha256" in inputs:
        template = templates[inputs["template"]]
        assert sha(reference_a(template["packet"])) == inputs["template_packet_sha256"]
        original = template["packet"]["command"] if inputs["command"] else template["packet"]["objects"][inputs["object_index"]]["body"]
        changed = readback.replaced(original, inputs["path"], inputs["value"], remove=inputs["remove"])
        assert sha(reference_a(changed)) == inputs["altered_body_sha256"]
        assert readback.info(readback.ROOT / template["state_file"])["sha256"] == row["input_database_sha256"]
        kind = "command_envelope" if inputs["command"] else template["packet"]["objects"][inputs["object_index"]]["kind"]
        key = kind + "::" + str(inputs["path"][0])
        report["material_field_case_index"].setdefault(key, []).append({"file": case_file["file"], "case_id": row["id"], "variant": inputs["variant"], "input_sha256": row["input_exact_json_sha256"]})
for entry in extra["inputs"]:
    assert readback.info(readback.ROOT / entry["file"]) == entry
for obj in extra["actual_git_objects"]:
    raw = base64.b64decode(obj["raw_base64"])
    assert sha(raw) == obj["raw_sha256"]
    algorithm = "sha1" if len(obj["git_oid"]) == 40 else "sha256"
    assert hashlib.new(algorithm, obj["kind"].encode() + b" " + str(len(raw)).encode() + b"\0" + raw).hexdigest() == obj["git_oid"]
assert extra["distinct_scope"]["source_scope_digest"] != extra["original_scope"]["source_scope_digest"]
assert extra["distinct_scope"]["view_task_digest"] != extra["original_scope"]["view_task_digest"]
proof = history(distinct / "p0.sqlite")
(distinct / "FINAL_INDEPENDENT_HISTORY.json").write_bytes(reference_a(proof) + b"\n")
report["cases"]["distinct-source"] = len(cases)
report["distinct_source_proof"] = readback.info(distinct / "DISTINCT_SOURCE_EXECUTION.json")
report["inputs"].extend([readback.info(Path(__file__)), case_file, readback.info(distinct / "DISTINCT_SOURCE_EXECUTION.json"),
                          readback.info(distinct / "FINAL_INDEPENDENT_HISTORY.json"), readback.info(readback.RUN / "SCHEMA_INLINE_APPLICABILITY.json")])
report["input_constructor"] = "Independent reference interpreter accelerates construction only; every original full input hash/length and reference expected result rechecked. No production predicate/writer/parser/schema engine is replaced."
report_path.write_bytes(reference_a(report) + b"\n")
