from __future__ import annotations

from typing import Sequence


def qualify_reuse(
    *, evidence_id: str, dependency_nodes: Sequence[str], impact: dict,
    source_semantics_same: bool, policy_same: bool, runtime_same: bool,
    evidence_present: bool, challenger_evidence: bool = False,
    material_candidate_changed: bool = False,
) -> dict:
    reasons: list[str] = []
    if not evidence_present:
        reasons.append("OLD_EVIDENCE_MISSING")
    if not source_semantics_same:
        reasons.append("SOURCE_SEMANTICS_CHANGED")
    if not policy_same:
        reasons.append("POLICY_CHANGED")
    if not runtime_same:
        reasons.append("RUNTIME_CHANGED")
    if set(dependency_nodes).intersection(impact.get("impacted", ())):
        reasons.append("DEPENDENCY_IMPACTED")
    if set(dependency_nodes).intersection(impact.get("uncertain_impacts", ())):
        reasons.append("DEPENDENCY_UNCERTAIN")
    if challenger_evidence and material_candidate_changed:
        reasons.append("BASELINE_CHALLENGER_RERUN_REQUIRED")
    return {"evidence_id": evidence_id, "status": "REUSE_QUALIFIED" if not reasons else "REQUALIFICATION_REQUIRED", "reason_codes": sorted(set(reasons))}
