"""Remediation plan DTOs. These are proposals, never accepted audit authority."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence


@dataclass(frozen=True)
class RepairUnit:
    unit_id: str
    finding_ref: Mapping[str, Any]
    statement: str
    priority: str = "UNPRIORITIZED"
    lifecycle_status: str = "OPEN"
    affected_scope_refs: Sequence[Mapping[str, Any]] = field(default_factory=tuple)
    evidence_refs: Sequence[Mapping[str, Any]] = field(default_factory=tuple)
    expected_fixed_property: str = ""
    acceptance_protocol: Sequence[str] = field(default_factory=tuple)
    dependency_unit_ids: Sequence[str] = field(default_factory=tuple)
    status: str = "PROPOSED"

    def as_dict(self) -> dict[str, Any]:
        return {
            "unit_id": self.unit_id,
            "status": self.status,
            "priority": self.priority,
            "finding_ref": dict(self.finding_ref),
            "statement": self.statement,
            "lifecycle_status": self.lifecycle_status,
            "affected_scope_refs": [dict(v) for v in self.affected_scope_refs],
            "evidence_refs": [dict(v) for v in self.evidence_refs],
            "expected_fixed_property": self.expected_fixed_property,
            "acceptance_protocol": list(self.acceptance_protocol),
            "dependency_unit_ids": list(self.dependency_unit_ids),
        }


@dataclass(frozen=True)
class RemediationPlan:
    campaign_id: str
    history_cut: Mapping[str, Any]
    repair_units: Sequence[RepairUnit] = field(default_factory=tuple)
    unresolved_inputs: Sequence[Mapping[str, Any]] = field(default_factory=tuple)
    plan_version: str = "1"
    status: str = "PROPOSED"

    def as_dict(self) -> dict[str, Any]:
        return {
            "plan_version": self.plan_version,
            "status": self.status,
            "campaign_id": self.campaign_id,
            "history_cut": dict(self.history_cut),
            "repair_units": [u.as_dict() for u in self.repair_units],
            "unresolved_inputs": [dict(v) for v in self.unresolved_inputs],
        }


__all__ = ["RepairUnit", "RemediationPlan"]
