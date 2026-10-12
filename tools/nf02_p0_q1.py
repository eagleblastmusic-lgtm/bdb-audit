"""Reproducible Q1 inputs for the approved model; never issue qualification.

All sample identities are SHAPE ONLY and cannot be installed as authority.
Primitive reference procedures are separate from the implementation under test.
Schema vectors include every schema node/union/enum/bound, with compact recipes.
"""

import argparse
import base64
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
from typing import Any

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

ROOT = Path(__file__).resolve().parents[1]
BASE = "docs/PRODUCT_V1/NF02_P0_LIMITED_MODEL/"
ZERO = "0" * 64


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def reference_a(value):
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf8")


def reference_b(value):
    """Hand-written ASCII-key/scalar UTF8 encoder; no production/json encoder."""

    def string(s):
        escapes = {
            8: "\\b",
            9: "\\t",
            10: "\\n",
            12: "\\f",
            13: "\\r",
            34: '\\"',
            92: "\\\\",
        }
        out = ['"']
        for c in s:
            n = ord(c)
            if 0xD800 <= n <= 0xDFFF:
                raise ValueError("surrogate")
            out.append(escapes[n] if n in escapes else "\\u%04x" % n if n < 32 else c)
        return "".join(out) + '"'

    def encode(v):
        if v is None:
            return "null"
        if type(v) is bool:
            return "true" if v else "false"
        if type(v) is int and abs(v) <= 2**53 - 1:
            return str(v)
        if type(v) is str:
            return string(v)
        if type(v) is list:
            return "[" + ",".join(encode(i) for i in v) + "]"
        if type(v) is dict and all(type(k) is str and k.isascii() for k in v):
            return (
                "{" + ",".join(string(k) + ":" + encode(v[k]) for k in sorted(v)) + "}"
            )
        raise ValueError("outside CJSON domain")

    return encode(value).encode("utf8")


class Unsatisfiable(ValueError):
    pass


def merge(a, b):
    out = deepcopy(a)
    for key, value in b.items():
        if key in {"$schema", "$id", "$defs", "title", "description"}:
            continue
        if key == "properties":
            out[key] = {**out.get(key, {})}
            for name, prop in value.items():
                out[key][name] = merge(out[key].get(name, {}), prop)
        elif key == "required":
            out[key] = sorted(set(out.get(key, [])) | set(value))
        elif key == "enum" and key in out:
            out[key] = [v for v in out[key] if v in value]
            if not out[key]:
                raise Unsatisfiable("empty enum")
        elif key == "const" and key in out and out[key] != value:
            raise Unsatisfiable("conflicting constants")
        elif key in {"minimum", "minLength", "minItems"}:
            out[key] = max(out.get(key, value), value)
        elif key in {"maximum", "maxLength", "maxItems"}:
            out[key] = min(out.get(key, value), value)
        elif key == "pattern" and key in out and out[key] != value:
            out.setdefault("allOf", []).append({"pattern": value})
        else:
            out[key] = deepcopy(value)
    if "const" in out and "enum" in out and out["const"] not in out["enum"]:
        raise Unsatisfiable("constant outside enum")
    return out


class Vectors:
    def __init__(self, documents):
        self.docs = documents
        self.registry = Registry().with_resources(
            (d["$id"], Resource.from_contents(d)) for d in documents.values()
        )

    def valid(self, schema, value):
        return Draft202012Validator(schema, registry=self.registry).is_valid(value)

    def resolve(self, schema):
        s = deepcopy(schema)
        if "$ref" in s:
            target = self.registry.resolver().lookup(s.pop("$ref")).contents
            s = merge(target, s)
        for part in s.pop("allOf", []):
            s = merge(s, self.resolve(part))
        return s

    def sample(self, schema, seed=0):
        s = self.resolve(schema)
        for union in ("oneOf", "anyOf"):
            if union in s:
                choices = s.pop(union)
                for branch in (
                    choices[seed % len(choices) :] + choices[: seed % len(choices)]
                ):
                    try:
                        value = self.sample(merge(s, self.resolve(branch)), seed)
                        if self.valid(schema, value):
                            return value
                    except Unsatisfiable:
                        continue
                raise Unsatisfiable("union")
        if "const" in s:
            result = deepcopy(s["const"])
        elif "enum" in s:
            result = deepcopy(s["enum"][seed % len(s["enum"])])
        elif s.get("type") == "null":
            result = None
        elif s.get("type") == "boolean":
            result = False
        elif s.get("type") == "integer":
            result = s.get("minimum", 0)
        elif s.get("type") == "array":
            result = [
                self.sample(s.get("items", {}), seed + i + 1)
                for i in range(s.get("minItems", 0))
            ]
        elif s.get("type") == "object" or "properties" in s:
            props = s.get("properties", {})
            result = {k: self.sample(props[k], seed) for k in props}
        elif s.get("type") == "string" or "pattern" in s:
            uuid = "00000000-0000-4000-8000-%012x" % seed
            pattern = s.get("pattern", "")
            prefix = (
                pattern[1:] if re.fullmatch(r"\^[a-z_]+_", pattern) else "shape_only_"
            )
            candidates = [
                prefix + uuid,
                *[
                    d["$id"].split(":")[-1].split("/")[0] + "_" + uuid
                    for d in self.docs.values()
                    if ":canonical:" in d["$id"]
                ],
                ZERO,
                "a" * 40,
                "2026-10-11T00:00:00Z",
                "SHAPE_ONLY.bin",
                "SHAPE_ONLY",
                "",
            ]
            result = next((v for v in candidates if self.valid(s, v)), None)
            if result is None:
                raise Unsatisfiable("string")
        else:
            result = {}
        if "if" in s:
            branch = (
                s.get("then", {}) if self.valid(s["if"], result) else s.get("else", {})
            )
            result = self.sample(
                merge(
                    {k: v for k, v in s.items() if k not in {"if", "then", "else"}},
                    self.resolve(branch),
                ),
                seed,
            )
        if not self.valid(schema, result):
            raise Unsatisfiable("sample does not satisfy node")
        return result

    def walk(self, value, pointer=""):
        if not isinstance(value, dict):
            return
        yield pointer, value
        for key in ("properties", "$defs"):
            for name, child in value.get(key, {}).items():
                yield from self.walk(child, pointer + "/" + key + "/" + name)
        for key in ("items", "if", "then", "else", "not"):
            if isinstance(value.get(key), dict):
                yield from self.walk(value[key], pointer + "/" + key)
        for key in ("oneOf", "anyOf", "allOf"):
            for i, child in enumerate(value.get(key, [])):
                yield from self.walk(child, pointer + "/" + key + "/" + str(i))

    def cases(self):
        cases, unsatisfiable = [], []
        for name, doc in sorted(self.docs.items()):
            for pointer, node in self.walk(doc):
                if pointer.endswith("/not"):
                    continue
                # Bound tests isolate the exact keyword; recipes avoid huge copies.
                for keyword in (
                    "minItems",
                    "maxItems",
                    "minLength",
                    "maxLength",
                    "minimum",
                    "maximum",
                ):
                    if keyword in node:
                        boundary = node[keyword]
                        for offset in (-1, 0, 1):
                            amount = boundary + offset
                            if amount < 0 and keyword not in {"minimum", "maximum"}:
                                continue
                            kind = (
                                "array"
                                if "Items" in keyword
                                else "string"
                                if "Length" in keyword
                                else "integer"
                            )
                            recipe = {"type": kind, "amount": amount}
                            if abs(amount) > 2**53 - 1:
                                # The negative test value is outside CJSON. Its
                                # recipe transport must remain inside CJSON.
                                recipe = {"type": kind, "amount_decimal": str(amount)}
                            constraint = {"type": kind, keyword: boundary}
                            expected = (
                                amount >= boundary
                                if keyword.startswith("min")
                                else amount <= boundary
                            )
                            assert self.valid(constraint, expand(recipe)) == expected
                            cases.append(
                                {
                                    "schema": name,
                                    "pointer": pointer,
                                    "constraint": constraint,
                                    "recipe": recipe,
                                    "expected": expected,
                                }
                            )
                try:
                    sample = self.sample(node)
                except Unsatisfiable as exc:
                    unsatisfiable.append(
                        {"schema": name, "pointer": pointer, "reason": str(exc)}
                    )
                    continue
                values = [("POSITIVE_SHAPE_ONLY", sample, True)]
                values += [
                    ("ENUM_BRANCH_" + str(i), v, True)
                    for i, v in enumerate(node.get("enum", []))
                ]
                if node.get("additionalProperties") is False and isinstance(
                    sample, dict
                ):
                    values.append(
                        (
                            "UNKNOWN_FIELD",
                            {**sample, "FORBIDDEN_EXTRA_FIELD": True},
                            False,
                        )
                    )
                for required in node.get("required", []):
                    if isinstance(sample, dict) and required in sample:
                        values.append(
                            (
                                "MISSING_" + required,
                                {k: v for k, v in sample.items() if k != required},
                                False,
                            )
                        )
                wrong_values: list[object] = [None, True, 0, "INVALID", [], {}]
                for v in wrong_values:
                    if not self.valid(node, v):
                        values.append(("WRONG_TYPE_CONST_ENUM_PATTERN", v, False))
                for label, value, expected in values:
                    if self.valid(node, value) != expected:
                        raise AssertionError((name, pointer, label))
                    cases.append(
                        {
                            "schema": name,
                            "pointer": pointer,
                            "case": label,
                            "value": value,
                            "expected": expected,
                        }
                    )
        return cases, unsatisfiable


def expand(recipe):
    kind = recipe["type"]
    amount = (
        int(recipe["amount_decimal"])
        if "amount_decimal" in recipe
        else recipe["amount"]
    )
    return (
        [None] * amount
        if kind == "array"
        else "x" * amount
        if kind == "string"
        else amount
    )


def finite_inputs(corpus):
    """Manual M04/M05 expectations, independent of the runtime's dispatch table.

    DAG probes use ordering-only stubs, never accepted objects/authority.
    State cases are a qualification worklist, not executed admission tests.
    """
    from types import SimpleNamespace
    from bdb_audit.core.errors import ValidationError
    from bdb_audit.history.limited_protocol import LimitedProtocol

    shapes = [
        (
            "assignment_manifest",
            "assignment_manifest_00000000-0000-4000-8000-000000000001",
            "1" * 64,
        ),
        ("attempt", "attempt_00000000-0000-4000-8000-000000000001", "2" * 64),
        (
            "command_envelope",
            "command_envelope_00000000-0000-4000-8000-000000000001",
            "3" * 64,
        ),
        ("attempt", "attempt_00000000-0000-4000-8000-000000000002", "4" * 64),
        ("attempt", "attempt_00000000-0000-4000-8000-000000000001", "5" * 64),
    ]
    dags = []
    # (label, nodes in input order, dependency edges, expected index sequence/error).
    for label, indexes, edges, expected in (
        ("EMPTY_FACTS", [], {}, []),
        ("SINGLE", [1], {}, [1]),
        ("KIND_TIE_BREAK", [2, 1, 0], {}, [0, 1, 2]),
        ("LOGICAL_ID_TIE_BREAK", [3, 1], {}, [1, 3]),
        ("DIGEST_TIE_BREAK", [4, 1], {}, [1, 4]),
        ("FACTS_BEFORE_DEPENDENT_COMMAND", [2, 0, 1], {0: [1], 2: [0, 1]}, [1, 0, 2]),
        ("CYCLE", [0, 1], {0: [1], 1: [0]}, "P0_CONTENT_CYCLE"),
        ("SELF", [1], {1: [1]}, "P0_CONTENT_CYCLE"),
        ("DUPLICATE", [1, 1], {}, "P0_DUPLICATE_OBJECT"),
    ):
        nodes = []
        for i in indexes:
            kind, logical, digest = shapes[i]
            refs = []
            for j in edges.get(i, []):
                target_kind, target_logical, target_digest = shapes[j]
                refs.append(
                    {
                        "kind": target_kind,
                        "version": corpus.versions[target_kind],
                        "logical_id": target_logical,
                        "revision_digest": target_digest,
                        "digest_profile": "BDB-OBJECT-DIGEST-1",
                        "schema_revision_ref": corpus.schema_ref(target_kind),
                    }
                )
            nodes.append(
                SimpleNamespace(
                    kind=kind, logical_id=logical, digest=digest, body={"refs": refs}
                )
            )
        actual: list[Any] | str
        try:
            actual = [n.digest for n in LimitedProtocol.order(LimitedProtocol.__new__(LimitedProtocol), nodes)]
        except ValidationError as exc:
            actual = exc.code
        wanted = (
            expected if isinstance(expected, str) else [shapes[i][2] for i in expected]
        )
        assert actual == wanted, label
        dags.append(
            {"case": label, "nodes": [vars(n) for n in nodes], "expected": wanted}
        )
    legal = {
        "INITIALIZE_P0_FROM_APPROVED_GIT": {"EMPTY_HISTORY"},
        "CREATE_ASSIGNMENT": {"GENESIS", "ABORTED"},
        "BIND_PACKAGE": {"ASSIGNED"},
        "START_ATTEMPT": {"BOUND"},
        "CONFIRM_DELIVERY": {"STARTED"},
        "INGEST_EVIDENCE": {"DELIVERED"},
        "ACCEPT_RESULT": {"EVIDENCE_ACCEPTED"},
        "ABORT_ATTEMPT": {
            "ASSIGNED",
            "BOUND",
            "STARTED",
            "DELIVERED",
            "EVIDENCE_ACCEPTED",
        },
    }
    assert set(legal) == {o["name"] for o in corpus.descriptor["operations"]}
    states = [
        "EMPTY_HISTORY",
        "GENESIS",
        "ASSIGNED",
        "BOUND",
        "STARTED",
        "DELIVERED",
        "EVIDENCE_ACCEPTED",
        "ABORTED",
        "RESULT_ACCEPTED",
    ]
    branches = [
        {
            "operation": op,
            "input_state": state,
            "state_precondition_allows": state in allowed,
            "all_other_predicates": "REQUIRED_NOT_ESTABLISHED_BY_THIS_VECTOR",
            "required_objects": next(
                o["objects"] for o in corpus.descriptor["operations"] if o["name"] == op
            ),
        }
        for op, allowed in legal.items()
        for state in states
    ]
    return {
        "dag_status": "LOCAL_ORDERING_PROBES_NOT_HISTORY_ACCEPTANCE",
        "dag_vectors": dags,
        "state_status": "ALL_FINITE_STATE_BRANCHES_REQUIRE_AUTHORIZED_EXECUTION",
        "state_branches": branches,
    }


def generate(output):
    from bdb_audit.core.canonical_json import canonical_bytes
    from bdb_audit.core.hashing import object_digest, raw_digest
    from bdb_audit.history.limited_model import LimitedCorpus, MANIFEST_SHA, GRAPH_SHA

    manifest_raw = (ROOT / BASE / "CANDIDATE_MANIFEST.json").read_bytes()
    manifest = json.loads(manifest_raw)
    names = sorted(
        {e["file"] for g in ("normative", "machine") for e in manifest[g + "_files"]}
    )
    files = {n: (ROOT / n).read_bytes() for n in names}
    files[BASE + "CANDIDATE_MANIFEST.json"] = manifest_raw
    corpus = LimitedCorpus(files)
    definitions = {}
    for name, definition in corpus.descriptor["canonical_contracts"].items():
        schema = corpus.schemas.documents["canonical/" + name.replace("/", "__")]
        assert definition["body"] == {
            k: v for k, v in schema.items() if k not in {"$schema", "$id"}
        }
        definitions[name] = {
            "definition": definition,
            "schema_id": schema["$id"],
            "body_fields_equal": True,
        }
    vectors, unsatisfiable = Vectors(corpus.schemas.documents).cases()
    # COMMON intentionally has no public body; every $def is tested separately.
    allowed_unsatisfiable = {("wire/COMMON__1", "")}
    unexpected = [
        v
        for v in unsatisfiable
        if (v["schema"], v["pointer"]) not in allowed_unsatisfiable
    ]
    if unexpected:
        raise AssertionError(unexpected[:20])
    primitive = []
    for value in (
        {},
        {
            "controls": "".join(chr(i) for i in range(32)) + '\\"/🪲zażółć',
            "a": [None, True, False, -(2**53 - 1), 2**53 - 1],
        },
        {"object_id": "SHAPE_ONLY", "ordered": [3, 1, 2]},
    ):
        a, b = reference_a(value), reference_b(value)
        assert a == b == canonical_bytes(value)
        row = {
            "value": value,
            "cjson_base64": base64.b64encode(a).decode(),
            "raw_sha256": sha(a),
            "object_digests": {},
        }
        assert raw_digest(a).value == sha(a)
        for kind, version in corpus.versions.items():
            expected = sha(("BDB2/" + kind + "/" + version).encode() + b"\0" + a)
            assert (
                object_digest(
                    kind, version, value, registry_kind=kind, registry=corpus.registry
                ).value
                == expected
            )
            row["object_digests"][kind + "/" + version] = expected
        primitive.append(row)
    canonical_goldens = []
    for name, schema in sorted(corpus.schemas.documents.items()):
        if not name.startswith("canonical/"):
            continue
        value = Vectors(corpus.schemas.documents).sample(schema)
        kind, version = name.split("/")[1].split("__")
        a, b = reference_a(value), reference_b(value)
        assert a == b == canonical_bytes(value)
        expected = sha(("BDB2/" + kind + "/" + version).encode("ascii") + b"\0" + a)
        assert (
            object_digest(
                kind, version, value, registry_kind=kind, registry=corpus.registry
            ).value
            == expected
        )
        canonical_goldens.append(
            {
                "kind": kind,
                "version": version,
                "body": value,
                "object_digest": expected,
                "cjson_base64": base64.b64encode(a).decode(),
                "raw_sha256": sha(a),
            }
        )
    matrix = json.loads(files[BASE + "QUALIFICATION_MATRIX.json"])
    from bdb_audit.history.limited_protocol import LimitedProtocol
    ref_context = LimitedProtocol.__new__(LimitedProtocol)
    ref_context.schemas, ref_context.corpus = corpus.schemas, corpus
    ref_vectors = []
    for kind, version in corpus.versions.items():
        valid = {
            "kind": kind,
            "version": version,
            "logical_id": kind + "_00000000-0000-4000-8000-000000000000",
            "revision_digest": ZERO,
            "digest_profile": "BDB-OBJECT-DIGEST-1",
            "schema_revision_ref": corpus.schema_ref(kind),
        }
        variants = [
            ("EXACT_PIN_GRAMMAR_ONLY", valid, True, True),
            ("WRONG_VERSION", {**valid, "version": "999"}, False, False),
            ("UNKNOWN_KIND", {**valid, "kind": "generic_import"}, False, False),
            (
                "WRONG_LOGICAL_PREFIX",
                {**valid, "logical_id": "other_00000000-0000-4000-8000-000000000000"},
                False,
                False,
            ),
            (
                "CALLER_REF_CLASS",
                {**valid, "ref_class": "CONTENT_OR_PRIOR"},
                False,
                False,
            ),
            (
                "WRONG_SCHEMA_RAW_DIGEST",
                {
                    **valid,
                    "schema_revision_ref": {
                        **valid["schema_revision_ref"],
                        "raw_digest": ZERO,
                    },
                },
                True,
                False,
            ),
        ]
        for other in corpus.versions:
            if other != kind:
                variants.append(
                    (
                        "SCHEMA_OF_" + other,
                        {**valid, "schema_revision_ref": corpus.schema_ref(other)},
                        False,
                        False,
                    )
                )
        for label, value, grammar, pin in variants:
            schema = {"$ref": "urn:bdb:p0:wire:COMMON/1#/$defs/TypedRef"}
            assert Vectors(corpus.schemas.documents).valid(schema, value) == grammar
            from bdb_audit.core.errors import ValidationError

            try:
                LimitedProtocol.ref(ref_context, value)
                actual_pin = True
            except ValidationError:
                actual_pin = False
            assert actual_pin == pin
            ref_vectors.append(
                {
                    "kind": kind,
                    "case": label,
                    "value": value,
                    "expected_schema": grammar,
                    "expected_exact_pin": pin,
                    "prior_resolution": "NOT_ESTABLISHED_BY_THIS_VECTOR",
                }
            )
    finite = finite_inputs(corpus)
    output.mkdir(parents=True, exist_ok=True)
    values = {
        "SCHEMA_VECTORS.json": {
            "status": "SHAPE_ONLY_LOCAL_CHECKS_NOT_QUALIFICATION",
            "vector_count": len(vectors),
            "shards": [],
            "intentional_uninhabited": unsatisfiable,
        },
        "PRIMITIVE_VECTORS.json": {
            "status": "TWO_LOCAL_REFERENCE_PROCEDURES_NOT_INDEPENDENT_APPROVAL",
            "vectors": primitive,
            "canonical_shape_goldens": canonical_goldens,
        },
        "REF_VECTORS.json": {
            "status": "GRAMMAR_AND_EXACT_SCHEMA_PINS_NOT_AUTHORITY",
            "vectors": ref_vectors,
        },
        "DAG_AND_STATE_VECTORS.json": finite,
        "QUALIFICATION_WORKLIST.json": {
            "status": "REQUIRES_AUTHORIZED_REVIEW_AND_REAL_RUNTIME",
            "requirements": matrix["cases"],
            "contracts": definitions,
            "profiles": corpus.descriptor["profiles"],
            "schema_names": sorted(corpus.schemas.documents),
            "finite_operation_branches": corpus.descriptor["operations"],
            "required_material_target_mutations": [
                {
                    "contract": key,
                    **ref,
                    "mutations": [
                        "ABSENT",
                        "WRONG_KIND",
                        "WRONG_VERSION",
                        "WRONG_SCHEMA_RAW_DIGEST",
                        "WRONG_LOGICAL_ID",
                        "WRONG_REVISION",
                        "SAME_COMMIT_PRIOR",
                        "FUTURE",
                        "WRONG_CAMPAIGN",
                        "WRONG_ATTEMPT",
                        "WRONG_SOURCE",
                        "WRONG_SLOT",
                        "WRONG_CUT",
                    ],
                }
                for key, definition in corpus.descriptor["canonical_contracts"].items()
                for ref in definition["material_refs"]
            ],
            "entry_points": [
                "TransactionalHistoryStore.accept",
                "Coordinator.accept",
                "LimitedIntake.accept",
                "E1ResultInbox.accept_p0_evidence",
                "E1ResultInbox.accept_p0_result",
                "product p0",
                "p0_service.execute",
                "installed standalone",
            ],
        },
    }
    # Qualification inputs keep the approved JSON quota; never enlarge M06.
    chunks: list[list[dict[str, Any]]] = []
    chunk: list[dict[str, Any]] = []
    size = 0
    for vector in vectors:
        amount = len(reference_a(vector)) + 1
        if chunk and size + amount > 1024 * 1024:
            chunks.append(chunk)
            chunk, size = [], 0
        chunk.append(vector)
        size += amount
    if chunk:
        chunks.append(chunk)
    offset = 0
    for i, chunk in enumerate(chunks, 1):
        name = f"SCHEMA_VECTORS_PART_{i:02}.json"
        shard_body = {
            "status": "SHAPE_ONLY_LOCAL_CHECKS_NOT_QUALIFICATION",
            "vectors": chunk,
        }
        raw = reference_a(shard_body) + b"\n"
        assert len(raw) <= 2 * 1024 * 1024
        values[name] = shard_body
        values["SCHEMA_VECTORS.json"]["shards"].append(
            {
                "file": name,
                "sha256": sha(raw),
                "bytes": len(raw),
                "first_vector_index": offset,
                "vector_count": len(chunk),
            }
        )
        offset += len(chunk)
    assert offset == len(vectors)
    for name, value in values.items():
        raw = reference_a(value) + b"\n"
        assert len(raw) <= 2 * 1024 * 1024
        (output / name).write_bytes(raw)
    report = {
        "status": "LOCAL_Q1_INPUT_CHECKS_COMPLETE_NOT_Q1_PASS",
        "candidate_manifest_sha256": MANIFEST_SHA,
        "dependency_graph_sha256": GRAPH_SHA,
        "normative_set_sha256": manifest["normative_set_sha256"],
        "machine_set_sha256": manifest["machine_set_sha256"],
        "counts": {
            "canonical": len(corpus.versions),
            "profiles": 7,
            "schemas": len(corpus.schemas.documents),
            "schema_vectors": len(vectors),
            "exact_ref_vectors": len(ref_vectors),
            "dag_vectors": len(finite["dag_vectors"]),
            "state_branches_to_qualify": len(finite["state_branches"]),
        },
        "readback_files": [
            {"file": n, "sha256": sha(files[n]), "bytes": len(files[n])} for n in names
        ],
        "materials": [
            {
                "file": n,
                "sha256": sha((output / n).read_bytes()),
                "bytes": (output / n).stat().st_size,
            }
            for n in sorted(values)
        ],
        "author_record_issued": False,
        "independent_qualification": False,
        "production_import": "BLOCKED",
    }
    report["reference_procedures"] = [
        {
            "file": "tools/nf02_p0_q1.py",
            "sha256": sha(Path(__file__).read_bytes()),
            "bytes": Path(__file__).stat().st_size,
        }
    ]
    (output / "LOCAL_Q1_INPUT_CHECKS.json").write_bytes(reference_a(report) + b"\n")
    print(
        json.dumps(
            {
                "status": report["status"],
                "counts": report["counts"],
                "output": str(output),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    generate(parser.parse_args().output_dir)
