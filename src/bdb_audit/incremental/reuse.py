"""Evidence-bound incremental reuse qualification for RU16.

Reuse is derived from the evidence capture binding plus old/new source manifests.
Caller-declared booleans cannot override policy/runtime/dependency drift or an
incomplete impact map.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

from .change_map import SourceManifest, build_change_map


def _is_sha256(value: str) -> bool:
    if len(value) != 64:
        return False
    try:
        int(value, 16)
    except ValueError:
        return False
    return True


@dataclass(frozen=True)
class EvidenceReuseBinding:
    evidence_id: str
    evidence_digest: str
    source_identity: str
    dependency_lock_digest: str
    policy_digest: str
    runtime_profile_digest: str
    dependency_nodes: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.evidence_id.strip():
            raise ValueError("evidence_id required")
        if not _is_sha256(self.evidence_digest):
            raise ValueError("evidence_digest must be SHA-256")
        if not self.source_identity.strip():
            raise ValueError("source_identity required")
        if any(not node.strip() for node in self.dependency_nodes):
            raise ValueError("dependency nodes must be non-empty")
        if len(set(self.dependency_nodes)) != len(self.dependency_nodes):
            raise ValueError("dependency nodes must be unique")


def qualify_reuse(
    *,
    binding: EvidenceReuseBinding,
    old_manifest: SourceManifest,
    new_manifest: SourceManifest,
    impact: Mapping[str, Sequence[str]],
    challenger_evidence: bool = False,
    material_candidate_changed: bool = False,
) -> dict[str, object]:
    reasons: list[str] = []

    if binding.source_identity != old_manifest.source_identity:
        reasons.append("OLD_EVIDENCE_SOURCE_BINDING_MISMATCH")
    if binding.dependency_lock_digest != old_manifest.dependency_lock_digest:
        reasons.append("OLD_EVIDENCE_DEPENDENCY_BINDING_MISMATCH")
    if binding.policy_digest != old_manifest.policy_digest:
        reasons.append("OLD_EVIDENCE_POLICY_BINDING_MISMATCH")
    if binding.runtime_profile_digest != old_manifest.runtime_profile_digest:
        reasons.append("OLD_EVIDENCE_RUNTIME_BINDING_MISMATCH")

    change = build_change_map(old_manifest, new_manifest)
    changed_paths = set(str(value) for value in change["changed_paths"])
    declared_changed = set(str(value) for value in impact.get("changed", ()))
    if not changed_paths.issubset(declared_changed):
        reasons.append("IMPACT_MAP_INCOMPLETE")

    external_changes = set(str(value) for value in change["external_input_changes"])
    if "DEPENDENCY_LOCK" in external_changes:
        reasons.append("DEPENDENCY_LOCK_CHANGED")
    if "POLICY" in external_changes:
        reasons.append("POLICY_CHANGED")
    if "RUNTIME_PROFILE" in external_changes:
        reasons.append("RUNTIME_CHANGED")

    dependency_nodes = set(binding.dependency_nodes)
    if dependency_nodes.intersection(str(value) for value in impact.get("impacted", ())):
        reasons.append("DEPENDENCY_IMPACTED")
    if dependency_nodes.intersection(str(value) for value in impact.get("uncertain_impacts", ())):
        reasons.append("DEPENDENCY_UNCERTAIN")

    if old_manifest.source_identity == new_manifest.source_identity and (changed_paths or external_changes):
        reasons.append("SOURCE_IDENTITY_NOT_ADVANCED")
    if challenger_evidence and material_candidate_changed:
        reasons.append("BASELINE_CHALLENGER_RERUN_REQUIRED")

    return {
        "evidence_id": binding.evidence_id,
        "evidence_digest": binding.evidence_digest,
        "old_source_identity": old_manifest.source_identity,
        "new_source_identity": new_manifest.source_identity,
        "status": "REUSE_QUALIFIED" if not reasons else "REQUALIFICATION_REQUIRED",
        "reason_codes": sorted(set(reasons)),
    }


__all__ = ["EvidenceReuseBinding", "qualify_reuse"]
