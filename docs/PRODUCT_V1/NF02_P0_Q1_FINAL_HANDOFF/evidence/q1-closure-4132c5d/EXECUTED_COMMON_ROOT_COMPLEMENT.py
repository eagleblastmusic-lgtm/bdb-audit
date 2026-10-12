"""Actual full-document denials for the deliberately uninhabitable COMMON root."""
from pathlib import Path
from bdb_audit.core.errors import ValidationError
from tools.nf02_p0_q1_contexts import corpus
from tools.nf02_p0_q1 import reference_a, reference_b
from tools.nf02_p0_q1_readback import RUN, read, info
from tools.nf02_p0_reference import valid, sha

c = corpus()
directory = RUN / "contexts-final"
report = read(directory / "CONTEXT_EXECUTION.json")
assert len(report["per_schema"]) == 42 and "wire/COMMON__1" not in report["per_schema"]
prior_report = info(directory / "CONTEXT_EXECUTION.json")
schema = c.schemas.documents["wire/COMMON__1"]
assert schema["not"] == {}
bases = read(directory / "CONTEXT_BASES.json")
base_sha = sha(reference_a({}))
bases[base_sha] = {}
rows = []
for value in (None, False, 0, "TEST_ONLY_ROOT_STRING", [], {}, {"TEST_ONLY_EXTRA": True}):
    expected = valid(schema, value, {d["$id"]: d for d in c.schemas.documents.values()})
    assert not expected
    try:
        c.schemas.validate("wire/COMMON__1", value)
    except ValidationError:
        actual = False
    else:
        raise AssertionError("COMMON/1 library root unexpectedly accepted a document")
    raw = reference_a(value)
    assert raw == reference_b(value)
    rows.append({"id": "CTX-%06d" % (report["case_count"] + len(rows) + 1), "schema": "wire/COMMON__1", "base_sha256": base_sha,
        "path": [], "mutation": "UNINHABITABLE_COMMON_LIBRARY_ROOT", "remove": False, "replacement": value,
        "input_exact_json_sha256": sha(raw), "input_exact_json_bytes": len(raw), "in_cjson_domain": True,
        "schema_sha256": sha(c.files["docs/PRODUCT_V1/NF02_P0_LIMITED_MODEL/schemas/wire/COMMON__1.schema.json"]),
        "expected_schema": expected, "actual_schema": actual})
with (directory / "CONTEXT_CASES.jsonl").open("ab") as stream:
    for row in rows:
        stream.write(reference_a(row) + b"\n")
(directory / "CONTEXT_BASES.json").write_bytes(reference_a(bases) + b"\n")
report["case_count"] += len(rows)
report["per_schema"]["wire/COMMON__1"] = len(rows)
report["root_complement"] = {"prior_report_identity": prior_report, "procedure": info(Path(__file__)), "case_count": len(rows),
    "reason": "COMMON/1 is an offline $defs library with deliberate not:{} root; no legal full root exists. Reachable definitions have real enclosing field contexts and the unused State enum has explicit node/FSM evidence."}
(directory / "CONTEXT_EXECUTION.json").write_bytes(reference_a(report) + b"\n")
print("COMPLETE_43_SCHEMA_CONTEXTS_PASS", report["case_count"], flush=True)
