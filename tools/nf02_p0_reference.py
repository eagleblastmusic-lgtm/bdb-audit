"""Independent author reference checks from frozen schemas and retained SQL.

No production validator, identity/transport/authority predicate is imported.
This is a finite reference procedure, not a new runtime or schema service.
"""
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import struct
import zlib
from typing import Any

from tools.nf02_p0_q1 import reference_a, reference_b


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def equal(a, b):
    if type(a) is not type(b):
        return False
    if isinstance(a, dict):
        return set(a) == set(b) and all(equal(a[k], b[k]) for k in a)
    if isinstance(a, list):
        return len(a) == len(b) and all(equal(x, y) for x, y in zip(a, b))
    return a == b


def pointer(document, fragment):
    for segment in fragment.removeprefix("/").split("/") if fragment else []:
        segment = segment.replace("~1", "/").replace("~0", "~")
        document = document[int(segment)] if isinstance(document, list) else document[segment]
    return document


def valid(schema, value, documents):
    """Every keyword present in this frozen 43-schema corpus; no backend oracle."""
    if isinstance(schema, bool):
        return schema
    supported = {"$id", "$schema", "$defs", "title", "description", "$ref", "type", "properties", "required",
                 "additionalProperties", "const", "enum", "pattern", "minimum", "maximum", "minLength", "maxLength",
                 "minItems", "maxItems", "uniqueItems", "items", "allOf", "anyOf", "oneOf", "not", "if", "then", "else"}
    if set(schema) - supported:
        raise ValueError("Unsupported reference keywords: " + str(set(schema) - supported))
    if "$ref" in schema:
        uri, _, fragment = schema["$ref"].partition("#")
        if not uri or uri not in documents:
            raise ValueError("Reference not in approved offline corpus")
        if not valid(pointer(documents[uri], fragment), value, documents):
            return False
    if "const" in schema and not equal(schema["const"], value):
        return False
    if "enum" in schema and not any(equal(item, value) for item in schema["enum"]):
        return False
    types = {"null": type(value) is type(None), "boolean": type(value) is bool, "integer": type(value) is int,
             "string": type(value) is str, "array": type(value) is list, "object": type(value) is dict}
    if "type" in schema:
        declared = schema["type"] if isinstance(schema["type"], list) else [schema["type"]]
        if not any(types[t] for t in declared):
            return False
    if isinstance(value, dict):
        if not set(schema.get("required", [])) <= set(value):
            return False
        properties = schema.get("properties", {})
        if schema.get("additionalProperties") is False and not set(value) <= set(properties):
            return False
        if not all(valid(properties[k], v, documents) for k, v in value.items() if k in properties):
            return False
    if type(value) is list:
        if len(value) < schema.get("minItems", 0) or len(value) > schema.get("maxItems", len(value)):
            return False
        if schema.get("uniqueItems") and any(equal(a, b) for i, a in enumerate(value) for b in value[:i]):
            return False
        if "items" in schema and not all(valid(schema["items"], item, documents) for item in value):
            return False
    if type(value) is str:
        if len(value) < schema.get("minLength", 0) or len(value) > schema.get("maxLength", len(value)):
            return False
        if "pattern" in schema and re.search(schema["pattern"], value) is None:
            return False
    if type(value) is int:
        if value < schema.get("minimum", value) or value > schema.get("maximum", value):
            return False
    for keyword in ("allOf", "anyOf", "oneOf"):
        if keyword in schema:
            decisions = [valid(child, value, documents) for child in schema[keyword]]
            if (keyword == "allOf" and not all(decisions) or keyword == "anyOf" and not any(decisions)
                    or keyword == "oneOf" and sum(decisions) != 1):
                return False
    if "not" in schema and valid(schema["not"], value, documents):
        return False
    if "if" in schema:
        selected = "then" if valid(schema["if"], value, documents) else "else"
        if selected in schema and not valid(schema[selected], value, documents):
            return False
    return True


def fixed_zip(members):
    """ZIP_STORED reference encoder using struct/CRC, never zipfile/SUT."""
    local, central = bytearray(), bytearray()
    for name, raw in sorted(members.items()):
        filename = name.encode("ascii")
        crc, size, offset = zlib.crc32(raw), len(raw), len(local)
        local.extend(struct.pack("<4s5H3L2H", b"PK\x03\x04", 20, 0, 0, 0, 33, crc, size, size, len(filename), 0))
        local.extend(filename + raw)
        central.extend(struct.pack("<4s6H3L5H2L", b"PK\x01\x02", 3 * 256 + 20, 20, 0, 0, 0, 33,
                                   crc, size, size, len(filename), 0, 0, 0, 0, 0o100644 << 16, offset))
        central.extend(filename)
    return bytes(local + central + struct.pack("<4s4H2LH", b"PK\x05\x06", 0, 0, len(members), len(members), len(central), len(local), 0))


def typed_refs(value):
    if isinstance(value, dict):
        if {"kind", "version", "revision_digest", "logical_id", "schema_revision_ref", "digest_profile"} <= set(value):
            yield value
        else:
            for child in value.values():
                yield from typed_refs(child)
    elif isinstance(value, list):
        for child in value:
            yield from typed_refs(child)


def history(path):
    """Independent digest, content order, exact-ref, receipt and chronology proof.

    Simulated CMS remains simulated; this procedure does not validate signatures.
    """
    con = sqlite3.connect(Path(path).absolute().as_uri() + "?mode=ro", uri=True)
    try:
        objects, raw_objects = {}, []
        for digest, kind, version, schema, logical_id, raw in con.execute("SELECT digest,kind,version,schema_ref,logical_id,body FROM immutable_objects"):
            body = json.loads(raw)
            a, b = reference_a(body), reference_b(body)
            assert a == b == raw
            expected = sha(("BDB2/" + kind + "/" + version).encode("ascii") + b"\0" + b)
            assert expected == digest
            objects[digest] = {"body": body, "kind": kind, "version": version, "logical_id": logical_id,
                "ref": {"kind": kind, "version": version, "logical_id": logical_id, "revision_digest": expected,
                        "digest_profile": "BDB-OBJECT-DIGEST-1", "schema_revision_ref": json.loads(schema)}}
            raw_objects.append({"kind": kind, "version": version, "logical_id": logical_id, "expected_object_digest": expected,
                                "expected_cjson_sha256": sha(b), "actual_digest_matches": True})
        raw_rows = []
        for digest, size, raw in con.execute("SELECT digest,byte_length,body FROM immutable_raw_artifacts"):
            assert digest == sha(raw) and size == len(raw)
            raw_rows.append({"raw_digest": digest, "bytes": size, "actual_exact_bytes_match": True})
        previous: str | dict[str, Any] = "EMPTY_HISTORY"
        seen: set[str] = set()
        steps: list[dict[str, Any]] = []
        for seq, commit_digest, raw in con.execute("SELECT seq,commit_hash,body FROM commits ORDER BY seq"):
            body = json.loads(raw)
            assert reference_a(body) == reference_b(body) == raw
            assert commit_digest == sha(b"BDB2/commit_body/3\0" + reference_b(body))
            assert body["commit_seq"] == seq == len(steps) + 1 and body["previous_head"] == previous
            refs = body["immutable_object_refs"]
            content = {ref["revision_digest"] for ref in refs}
            assert len(content) == len(refs) and not content & seen
            remaining = set(content)
            ordered: list[str] = []
            while remaining:
                ready = [d for d in remaining if {r["revision_digest"] for r in typed_refs(objects[d]["body"])} & content <= set(ordered)]
                assert ready
                selected = min(ready, key=lambda d: (objects[d]["kind"], objects[d]["logical_id"], d))
                ordered.append(selected)
                remaining.remove(selected)
            assert [r["revision_digest"] for r in refs] == ordered
            for ref in refs:
                assert ref == objects[ref["revision_digest"]]["ref"]
            command = objects[body["command_ref"]["revision_digest"]]["body"]
            assert command["expected_parent"] == previous and command["events"] == body["events"]
            assert command["actor_ref"] == body["actor_ref"] and command["campaign_id"] == body["campaign_id"]
            for field in ("policy_ref", "spec_ref", "schema_registry_ref"):
                assert command[field] == body[field]
            domain = [objects[d] for d in content if objects[d]["kind"] != "command_envelope"]
            for obj in domain:
                for ref in typed_refs(obj["body"]):
                    assert ref == objects[ref["revision_digest"]]["ref"]
                    assert ref["revision_digest"] in seen | content
                for field, cut in obj["body"].items():
                    if field.endswith("_cut"):
                        assert cut["head"] == previous
            previous = {"campaign_id": body["campaign_id"], "commit_seq": seq, "commit_hash": commit_digest}
            receipt_digest, receipt_raw = con.execute("SELECT receipt_digest,body FROM receipts WHERE command_id=?", (command["command_id"],)).fetchone()
            receipt = json.loads(receipt_raw)
            assert reference_a(receipt) == reference_b(receipt) == receipt_raw
            assert receipt_digest == sha(b"BDB2/command_receipt/3\0" + reference_b(receipt))
            assert receipt["accepted_head"] == previous and receipt["command_ref"] == body["command_ref"]
            assert receipt["commit_ref"]["revision_digest"] == commit_digest
            assert receipt["result_object_refs"] == sorted([obj["ref"] for obj in domain], key=lambda r: (r["kind"], r["logical_id"], r["revision_digest"]))
            steps.append({"seq": seq, "operation": command["operation"], "commit_hash": commit_digest, "receipt_digest": receipt_digest,
                          "content_order": ordered, "chronology_checked": True})
            seen.update(content)
        assert [s["operation"] for s in steps] == ["INITIALIZE_P0_FROM_APPROVED_GIT", "CREATE_ASSIGNMENT", "BIND_PACKAGE", "START_ATTEMPT", "CONFIRM_DELIVERY", "INGEST_EVIDENCE", "ACCEPT_RESULT"]
        return {"authority": "EXPLICIT_SIMULATION_NOT_REAL_CMS_OR_RQ", "objects": raw_objects, "raw": raw_rows, "steps": steps,
                "counts_by_kind": dict(Counter(o["kind"] for o in objects.values())), "reference_status": "PASS_FOR_LISTED_PROPERTIES"}
    finally:
        con.close()
