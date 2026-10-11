"""One raw-to-proposal transform for Inbox and canonical admission checks.

This proves byte provenance, not auditor truth or the original package's
assignment-time authority. Those remain separate admission requirements.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from ..assurance.zip_safety import Limits as ZipLimits, read_bytes as read_zip_bytes
from ..core.canonical_json import canonical_bytes, parse
from ..core.errors import ValidationError

RESULT_ZIP_LIMITS = ZipLimits(
    input_bytes=64 * 1024 * 1024,
    central_bytes=4 * 1024 * 1024,
    members=512,
    member_bytes=32 * 1024 * 1024,
    expanded_bytes=50 * 1024 * 1024,
    ratio=500,
)


def media_type(name: str) -> str:
    lower = name.lower()
    if lower.endswith(".json"):
        return "application/json"
    if lower.endswith((".md", ".txt", ".log")):
        return "text/plain"
    if lower.endswith(".xml"):
        return "application/xml"
    return "application/octet-stream"


def member_evidence(members: dict[str, bytes]) -> list[dict[str, Any]]:
    return [
        {"path": name, "raw_digest": hashlib.sha256(raw).hexdigest(),
         "byte_length": len(raw), "media_type": media_type(name)}
        for name, raw in sorted(members.items(), key=lambda item: item[0].encode("utf-8"))
    ]


def derive_result_proposal(
    raw: bytes, members: dict[str, bytes], *, history_cut: dict[str, Any],
    assignment_ref: dict[str, Any], attempt_ref: dict[str, Any],
) -> dict[str, Any]:
    if "MANIFEST.json" not in members:
        raise ValidationError("MISSING_MANIFEST")
    manifest = parse(members["MANIFEST.json"])
    if not isinstance(manifest, dict):
        raise ValidationError("MALFORMED_MANIFEST")
    if manifest.get("kind") != "bdb_audit_lane_result":
        raise ValidationError("INVALID_CONTRACT_KIND")
    if str(manifest.get("version", "")) != "1":
        raise ValidationError("INVALID_CONTRACT_VERSION")
    if manifest.get("campaign_id") != history_cut.get("campaign_id"):
        raise ValidationError("CAMPAIGN_BINDING_MISMATCH")
    result_cut = manifest.get("history_cut")
    if not isinstance(result_cut, dict):
        raise ValidationError("MISSING_MANDATORY_FIELD", "history_cut")
    required = ("campaign_id", "accepted_head_seq", "accepted_head_hash")
    if any(result_cut.get(key) != history_cut.get(key) for key in required):
        raise ValidationError("STALE_CUT")
    if any(value != history_cut.get(key) for key, value in result_cut.items()):
        raise ValidationError("STALE_CUT", "conflicting history context")
    if "admission_evidence_ref" in manifest:
        raise ValidationError("UNAUTHORIZED_PRODUCER_AUTHORITY", "External manifest supplies admission authority")
    from ..history.authority_hooks import _typed_ref_identity
    for field, expected in (("assignment_ref", assignment_ref), ("attempt_ref", attempt_ref)):
        if field in manifest and _typed_ref_identity(manifest[field]) != _typed_ref_identity(expected):
            raise ValidationError("RESULT_CONTEXT_CLAIM_MISMATCH", field)

    if manifest.get("stage_id") == "E1":
        if "findings" in manifest:
            findings = manifest["findings"]
        elif "FINDINGS.json" in members:
            findings = parse(members["FINDINGS.json"])
        else:
            raise ValidationError("MISSING_MANDATORY_FIELD", "findings")
        if not isinstance(findings, list):
            raise ValidationError("INVALID_FINDING_STRUCTURE")
        if "findings_count" in manifest and manifest["findings_count"] != len(findings):
            raise ValidationError("FINDINGS_COUNT_MISMATCH")
        if any(not isinstance(f, dict) or not f.get("statement") or not (f.get("finding_id") or f.get("title")) for f in findings):
            raise ValidationError("INVALID_FINDING_STRUCTURE")
    else:
        findings = manifest.get("findings", [])
        if not isinstance(findings, list) or any(not isinstance(f, dict) for f in findings):
            raise ValidationError("INVALID_FINDING_STRUCTURE")
        if not isinstance(manifest.get("outputs", {}), dict):
            raise ValidationError("INVALID_OUTPUT_STRUCTURE")

    proposal = dict(manifest)
    proposal.update(
        history_cut=dict(history_cut), assignment_ref=dict(assignment_ref),
        attempt_ref=dict(attempt_ref), findings=findings,
        raw_result_digest=hashlib.sha256(raw).hexdigest(),
        raw_result_byte_length=len(raw), evidence_files=member_evidence(members),
    )
    if manifest.get("stage_id") == "E1":
        proposal["findings_count"] = len(findings)
    else:
        proposal["outputs"] = manifest.get("outputs", {})
    return proposal


def verify_admission_bytes(body: dict[str, Any], *, vault, assignment: dict[str, Any]) -> dict[str, Any]:
    """Check the claimed proposal/members against raw bytes and accepted cut."""
    raw = vault.read_bytes(body["raw_result_digest"])
    if len(raw) != body.get("raw_result_byte_length"):
        raise ValidationError("RAW_RESULT_BYTE_LENGTH_MISMATCH")
    members = read_zip_bytes(raw, limits=RESULT_ZIP_LIMITS)
    proposal = derive_result_proposal(
        raw, members, history_cut=assignment["assignment_input_history_cut"],
        assignment_ref=body["assignment_ref"], attempt_ref=body["attempt_ref"],
    )
    if hashlib.sha256(canonical_bytes(proposal)).hexdigest() != body.get("result_proposal_digest"):
        raise ValidationError("RESULT_PROPOSAL_DIGEST_MISMATCH")
    if body.get("evidence_files") != proposal["evidence_files"]:
        raise ValidationError("RESULT_MEMBER_EVIDENCE_MISMATCH")
    if body.get("phase_id") != assignment.get("phase_id") or proposal.get("phase_id") != assignment.get("phase_id"):
        raise ValidationError("PHASE_BINDING_MISMATCH")

    # Raw identity and context are necessary but do not establish the original
    # assignment-time package identity; see the unresolved R2 contract gate.
    package_raw = vault.read_bytes(body.get("package_zip_sha256", ""))
    package_members = read_zip_bytes(package_raw)
    package = parse(package_members.get("MANIFEST.json", b"null"))
    if not isinstance(package, dict):
        raise ValidationError("PACKAGE_MANIFEST_INVALID")
    for package_field, evidence_field in (
        ("campaign_id", "campaign_id"), ("stage_id", "stage_id"),
        ("phase_id", "phase_id"), ("lane_slot", "lane_slot"),
        ("package_digest", "input_package_digest"), ("execution_mode", "executor_profile"),
        ("model", "executor_model"), ("input_history_cut", "history_cut"),
    ):
        if package.get(package_field) != body.get(evidence_field):
            raise ValidationError("PACKAGE_CONTEXT_MISMATCH", package_field)
    from ..history.authority_hooks import _typed_ref_identity
    for field in ("assignment_ref", "attempt_ref"):
        if _typed_ref_identity(package.get(field)) != _typed_ref_identity(body.get(field)):
            raise ValidationError("PACKAGE_CONTEXT_MISMATCH", field)
    source = package.get("source_target")
    if not isinstance(source, dict) or str(source.get("exact_commit_sha", "")).lower() != str(body.get("source_commit_sha", "")).lower():
        raise ValidationError("PACKAGE_SOURCE_COMMIT_MISMATCH")
    return proposal


def inspect_result_zip(store, batch, path: str | Path) -> dict[str, Any]:
    """Inspect transport/context without issuing authority, retaining raw or writing history.

    A successful inspection is explicitly untrusted. The package hash is the
    current product's local receipt, not an accepted assignment-time binding.
    Stage-specific output semantics and isolation enforcement remain unproved.
    """
    from .read_models import current_accepted_cut
    from ..history.authority_hooks import _typed_ref_identity

    path = Path(path).resolve()
    with path.open("rb") as handle:
        raw = handle.read(RESULT_ZIP_LIMITS.input_bytes + 1)
    members = read_zip_bytes(raw, limits=RESULT_ZIP_LIMITS)
    manifest = parse(members.get("MANIFEST.json", b"null"))
    if not isinstance(manifest, dict):
        raise ValidationError("MISSING_MANIFEST")
    slot = manifest.get("lane_slot")
    if not isinstance(slot, str) or slot not in batch.jobs:
        raise ValidationError("UNKNOWN_LANE")
    job = batch.get_job(slot)
    for field, expected in (
        ("campaign_id", batch.campaign_id), ("stage_id", batch.stage_id),
        ("phase_id", getattr(batch, "phase_id", None)),
        ("input_package_digest", job.package_digest),
        ("executor_profile", job.executor_profile), ("executor_model", job.model),
        ("source_commit_sha", job.source_commit_sha),
    ):
        if manifest.get(field) != expected:
            raise ValidationError("RESULT_CONTEXT_CLAIM_MISMATCH", field)
    cut = current_accepted_cut(store)
    assignment = store.resolve_accepted(job.assignment_ref, cut)["body"]
    store.resolve_accepted(job.attempt_ref, cut)
    if _typed_ref_identity(assignment.get("attempt_ref")) != _typed_ref_identity(job.attempt_ref):
        raise ValidationError("ASSIGNMENT_ATTEMPT_BINDING_MISMATCH")
    if assignment.get("assignment_input_history_cut") != batch.frozen_history_cut:
        raise ValidationError("ASSIGNMENT_CUT_MISMATCH")
    # These references come from accepted history, never from the result ZIP.
    for field in ("source_generation_ref", "stage_spec_ref", "lane_spec_ref"):
        store.resolve_accepted(assignment[field], cut)
    lane_spec = store.resolve_accepted(assignment["lane_spec_ref"], cut)["body"]
    proposal = derive_result_proposal(
        raw, members, history_cut=assignment["assignment_input_history_cut"],
        assignment_ref=job.assignment_ref, attempt_ref=job.attempt_ref,
    )
    with job.package_zip_path.open("rb") as handle:
        package_raw = handle.read(RESULT_ZIP_LIMITS.input_bytes + 1)
    if hashlib.sha256(package_raw).hexdigest() != job.package_zip_sha256:
        raise ValidationError("ASSIGNED_PACKAGE_TAMPERED")
    digest = proposal["raw_result_digest"]
    snapshots = {digest: raw, job.package_zip_sha256: package_raw}
    evidence = {
        **proposal, "package_zip_sha256": job.package_zip_sha256,
        "result_proposal_digest": hashlib.sha256(canonical_bytes(proposal)).hexdigest(),
    }
    verify_admission_bytes(evidence, vault=SimpleNamespace(read_bytes=snapshots.__getitem__), assignment=assignment)
    return {
        "status": "INSPECTED_UNTRUSTED", "path": str(path),
        "accepted": False, "producer_authorization": "NOT_ESTABLISHED",
        "campaign_id": batch.campaign_id, "stage_id": batch.stage_id,
        "phase_id": getattr(batch, "phase_id", None), "lane_slot": slot,
        "assignment_ref": job.assignment_ref, "attempt_ref": job.attempt_ref,
        "accepted_history_cut": cut, "assignment_input_history_cut": batch.frozen_history_cut,
        "raw_result_digest": digest, "raw_result_byte_length": len(raw),
        "package_zip_sha256": job.package_zip_sha256,
        "package_binding": "LOCAL_RECEIPT_ONLY; NO_ACCEPTED_ASSIGNMENT_TIME_BINDING",
        "result_proposal_digest": evidence["result_proposal_digest"],
        "byte_context_checks": "MATCH", "output_semantics": "NOT_QUALIFIED",
        "required_isolation_assurance": lane_spec.get("required_isolation_assurance"),
        "isolation_enforcement": "NOT_ESTABLISHED",
        "findings": proposal["findings"], "outputs": proposal.get("outputs", {}),
        "evidence_files": proposal["evidence_files"],
    }
