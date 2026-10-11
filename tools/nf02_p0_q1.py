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
    kind, amount = recipe["type"], recipe["amount"]
    return (
        [None] * amount
        if kind == "array"
        else "x" * amount
        if kind == "string"
        else amount
    )


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
    output.mkdir(parents=True, exist_ok=True)
    values = {
        "SCHEMA_VECTORS.json": {
            "status": "SHAPE_ONLY_LOCAL_CHECKS_NOT_QUALIFICATION",
            "vectors": vectors,
            "intentional_uninhabited": unsatisfiable,
        },
        "PRIMITIVE_VECTORS.json": {
            "status": "TWO_LOCAL_REFERENCE_PROCEDURES_NOT_INDEPENDENT_APPROVAL",
            "vectors": primitive,
            "canonical_shape_goldens": canonical_goldens,
        },
        "QUALIFICATION_WORKLIST.json": {
            "status": "REQUIRES_AUTHORIZED_REVIEW_AND_REAL_RUNTIME",
            "requirements": matrix["cases"],
            "contracts": definitions,
            "profiles": corpus.descriptor["profiles"],
            "schema_names": sorted(corpus.schemas.documents),
        },
    }
    for name, value in values.items():
        (output / name).write_bytes(reference_a(value) + b"\n")
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
