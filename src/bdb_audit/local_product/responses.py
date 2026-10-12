"""Bounded, non-executing parsing of explicitly untrusted local responses."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from ..assurance.zip_safety import Limits, read_bytes, snapshot, canonical_path
from ..core.canonical_json import parse
from ..core.errors import ValidationError
from .profile import MODE, RESPONSE
from .store import sha

RESULT_LIMITS = Limits(input_bytes=64 * 1024 * 1024, central_bytes=4 * 1024 * 1024,
                      members=512, member_bytes=32 * 1024 * 1024, expanded_bytes=50 * 1024 * 1024, ratio=500)
JSON_LIMIT = 2 * 1024 * 1024


def decode(raw: bytes) -> tuple[dict[str, Any], dict[str, bytes]]:
    members: dict[str, bytes] = {}
    if raw.startswith(b"PK"):
        members = read_bytes(raw, limits=RESULT_LIMITS)
        if "LOCAL_RESULT.json" not in members:
            raise ValidationError("LOCAL_RESULT_MANIFEST_MISSING", "Expected root LOCAL_RESULT.json")
        body = parse(members["LOCAL_RESULT.json"], max_bytes=JSON_LIMIT)
    else:
        body = parse(raw, max_bytes=JSON_LIMIT)
    if not isinstance(body, dict):
        raise ValidationError("LOCAL_RESPONSE_OBJECT_REQUIRED")
    return body, members


def read_file(path: str | Path) -> bytes:
    raw = snapshot(path, limits=RESULT_LIMITS).raw
    decode(raw)  # Unsafe or malformed bytes are refused before journal/vault mutation.
    return raw


def _text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip()) and len(value) <= 100_000


def issues(body: dict[str, Any], members: dict[str, bytes], context: dict[str, Any],
           required_outputs: list[str], source_paths: set[str]) -> list[str]:
    errors: list[str] = []
    if body.get("format") != RESPONSE or body.get("mode") != MODE:
        errors.append("LOCAL_RESPONSE_FORMAT_OR_MODE_MISMATCH")
    for key, expected in context.items():
        if body.get(key) != expected:
            errors.append("LOCAL_CONTEXT_MISMATCH:" + key)
    producer = body.get("producer")
    if (not isinstance(producer, dict) or producer.get("kind") not in (
            "EXTERNAL_AI", "HUMAN", "LOCAL_CONTROL", "TEST_FIXTURE")
            or not _text(producer.get("declared_name"))):
        errors.append("LOCAL_DECLARED_PRODUCER_REQUIRED")
    if body.get("completion") not in ("COMPLETE", "NEEDS_WORK", "BLOCKED"):
        errors.append("LOCAL_COMPLETION_INVALID")
    outputs = body.get("outputs")
    if not isinstance(outputs, dict):
        errors.append("LOCAL_OUTPUTS_REQUIRED")
    elif body.get("completion") == "COMPLETE":
        for key in required_outputs:
            if not _text(outputs.get(key)):
                errors.append("LOCAL_REQUIRED_OUTPUT_MISSING:" + key)
    for field in ("limitations", "recommendations", "contradictions"):
        value = body.get(field)
        if not isinstance(value, list) or len(value) > 2000 or any(not _text(v) for v in value):
            errors.append("LOCAL_TEXT_LIST_REQUIRED:" + field)
    findings = body.get("findings")
    if not isinstance(findings, list) or len(findings) > 2000:
        errors.append("LOCAL_FINDINGS_REQUIRED")
    else:
        ids: set[str] = set()
        for finding in findings:
            if not isinstance(finding, dict):
                errors.append("LOCAL_FINDING_OBJECT_REQUIRED")
                continue
            identifier = finding.get("id")
            if not isinstance(identifier, str) or not _text(identifier) or identifier in ids:
                errors.append("LOCAL_FINDING_ID_INVALID_OR_DUPLICATE")
            else:
                ids.add(identifier)
            for key in ("title", "statement", "rationale"):
                if not _text(finding.get(key)):
                    errors.append("LOCAL_FINDING_FIELD_REQUIRED:" + key)
            if finding.get("severity") not in ("CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"):
                errors.append("LOCAL_FINDING_SEVERITY_INVALID")
            if finding.get("disposition") not in ("CLAIM", "SUPPORTED", "DISPUTED", "WITHDRAWN"):
                errors.append("LOCAL_FINDING_DISPOSITION_INVALID")
            refs = finding.get("source_refs")
            if not isinstance(refs, list):
                errors.append("LOCAL_FINDING_SOURCE_REFS_REQUIRED")
            else:
                for ref in refs:
                    if (not isinstance(ref, dict) or not isinstance(ref.get("path"), str) or ref["path"] not in source_paths
                            or type(ref.get("line")) is not int or ref["line"] < 1):
                        errors.append("LOCAL_FINDING_SOURCE_REF_INVALID")
    evidence = body.get("evidence_files")
    declared: set[str] = set()
    if not isinstance(evidence, list):
        errors.append("LOCAL_EVIDENCE_LIST_REQUIRED")
    else:
        for item in evidence:
            if not isinstance(item, dict):
                errors.append("LOCAL_EVIDENCE_OBJECT_REQUIRED")
                continue
            name = item.get("path")
            try:
                if canonical_path(name) != name or name == "LOCAL_RESULT.json" or name in declared:
                    raise ValidationError("LOCAL_EVIDENCE_PATH_INVALID")
            except ValidationError:
                errors.append("LOCAL_EVIDENCE_PATH_INVALID")
                continue
            declared.add(name)
            member = members.get(name)
            if member is None or sha(member) != item.get("sha256") or len(member) != item.get("byte_length"):
                errors.append("LOCAL_EVIDENCE_EXACT_BYTES_MISMATCH:" + name)
    if set(members) - {"LOCAL_RESULT.json"} != declared:
        errors.append("LOCAL_UNDECLARED_OR_MISSING_MEMBERS")
    # Qualified record envelopes cannot be smuggled in as an alternate root.
    allowed = {"format", "mode", *context, "producer", "completion", "outputs", "findings",
               "evidence_files", "limitations", "recommendations", "contradictions"}
    if set(body) - allowed:
        errors.append("LOCAL_UNKNOWN_RESPONSE_FIELDS:" + ",".join(sorted(set(body) - allowed)))
    return sorted(set(errors))
