"""RU16 dependency-bound incremental audit and evidence reuse."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence


@dataclass(frozen=True)
class ChangeImpactMap:
    changed_nodes: tuple[str, ...]
    impacted_nodes: tuple[str, ...]


@dataclass(frozen=True)
class EvidenceReuseAssessment:
    evidence_id: str
    reusable: bool
    reason_codes: tuple[str, ...]


class IncrementalAuditPlanner:
    @staticmethod
    def impact(changed_nodes: Sequence[str], reverse_dependencies: Mapping[str, Sequence[str]]) -> ChangeImpactMap:
        changed = set(changed_nodes)
        impacted = set(changed)
        queue = list(changed)
        while queue:
            node = queue.pop(0)
            for dependent in reverse_dependencies.get(node, ()):
                if dependent not in impacted:
                    impacted.add(dependent)
                    queue.append(dependent)
        return ChangeImpactMap(tuple(sorted(changed)), tuple(sorted(impacted)))

    @staticmethod
    def assess_reuse(evidence_id: str, evidence_dependency_nodes: Sequence[str], impact_map: ChangeImpactMap, source_same: bool, policy_same: bool, environment_same: bool) -> EvidenceReuseAssessment:
        reasons: list[str] = []
        if not source_same:
            reasons.append("SOURCE_IDENTITY_CHANGED")
        if not policy_same:
            reasons.append("POLICY_CHANGED")
        if not environment_same:
            reasons.append("ENVIRONMENT_CHANGED")
        if set(evidence_dependency_nodes).intersection(impact_map.impacted_nodes):
            reasons.append("DEPENDENCY_IMPACTED")
        return EvidenceReuseAssessment(evidence_id, not reasons, tuple(reasons))
