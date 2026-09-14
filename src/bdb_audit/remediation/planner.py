"""Evidence-linked remediation plan construction and validation."""
from __future__ import annotations

import re
from typing import Any, Mapping

from ..core.errors import ValidationError
from ..report.models import ReportSnapshot
from .models import RemediationPlan, RepairUnit

_ACTIONABLE = {"OPEN", "CONFIRMED_CURRENT", "REMEDIATION_PENDING", "REOPENED", "PARTIALLY_FIXED"}


def _unit_id(index: int, finding: Mapping[str, Any]) -> str:
    claim_id = str(finding.get("claim_id") or "finding")
    token = re.sub(r"[^A-Za-z0-9_.-]+", "-", claim_id).strip("-") or "finding"
    return f"RU-{index:04d}-{token[:48]}"


def validate_remediation_plan(plan: RemediationPlan | Mapping[str, Any]) -> dict[str, Any]:
    body = plan.as_dict() if isinstance(plan, RemediationPlan) else dict(plan)
    units = body.get("repair_units", [])
    if not isinstance(units, list):
        raise ValidationError("REMEDIATION_UNITS_INVALID")
    ids = [u.get("unit_id") for u in units if isinstance(u, Mapping)]
    if len(ids) != len(units) or any(not isinstance(v, str) or not v for v in ids):
        raise ValidationError("REMEDIATION_UNIT_ID_INVALID")
    if len(ids) != len(set(ids)):
        raise ValidationError("REMEDIATION_UNIT_ID_DUPLICATE")
    id_set = set(ids)
    graph: dict[str, tuple[str, ...]] = {}
    for unit in units:
        deps = unit.get("dependency_unit_ids", [])
        if not isinstance(deps, list) or any(dep not in id_set for dep in deps):
            raise ValidationError("REMEDIATION_DEPENDENCY_INVALID", str(unit.get("unit_id")))
        if unit.get("unit_id") in deps:
            raise ValidationError("REMEDIATION_CYCLE", str(unit.get("unit_id")))
        graph[str(unit["unit_id"])] = tuple(str(dep) for dep in deps)
        if not isinstance(unit.get("finding_ref"), Mapping):
            raise ValidationError("REMEDIATION_FINDING_REF_REQUIRED", str(unit.get("unit_id")))
        if not unit.get("statement"):
            raise ValidationError("REMEDIATION_STATEMENT_REQUIRED", str(unit.get("unit_id")))

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node: str) -> None:
        if node in visiting:
            raise ValidationError("REMEDIATION_CYCLE", node)
        if node in visited:
            return
        visiting.add(node)
        for dep in graph[node]:
            visit(dep)
        visiting.remove(node)
        visited.add(node)

    for node in sorted(graph):
        visit(node)
    return {"status": "PASS", "unit_count": len(units), "acyclic": True}


class RemediationPlanner:
    """Create proposals only for current actionable accepted finding claims."""

    def __init__(self, snapshot: ReportSnapshot | Mapping[str, Any]):
        self.snapshot = snapshot.as_dict() if isinstance(snapshot, ReportSnapshot) else dict(snapshot)

    def build(self) -> RemediationPlan:
        units: list[RepairUnit] = []
        unresolved: list[dict[str, Any]] = []
        for finding in self.snapshot.get("findings", []):
            if not isinstance(finding, Mapping):
                continue
            lifecycle = str(finding.get("lifecycle_status", "UNADJUDICATED"))
            if lifecycle == "UNADJUDICATED":
                unresolved.append({
                    "type": "FINDING_NOT_READY_FOR_REMEDIATION",
                    "finding_ref": dict(finding.get("finding_ref") or {}),
                    "reason": "UNADJUDICATED",
                })
                continue
            if lifecycle not in _ACTIONABLE:
                continue
            index = len(units) + 1
            evidence = finding.get("evidence_qualification_refs", [])
            scopes = finding.get("scope_refs", [])
            unit = RepairUnit(
                unit_id=_unit_id(index, finding),
                finding_ref=dict(finding.get("finding_ref") or {}),
                statement=str(finding.get("statement", "")),
                lifecycle_status=lifecycle,
                affected_scope_refs=tuple(dict(v) for v in scopes if isinstance(v, Mapping)),
                evidence_refs=tuple(dict(v) for v in evidence if isinstance(v, Mapping)),
                expected_fixed_property=(
                    "The exact finding claim is no longer CONFIRMED_CURRENT after qualified re-adjudication "
                    "on the successor source; prior accepted evidence remains immutable."
                ),
                acceptance_protocol=(
                    "Reproduce the accepted finding mechanism on the exact predecessor source using its evidence refs.",
                    "Implement the repair on a successor source generation without rewriting predecessor history.",
                    "Run the finding-specific regression plus relevant negative/sibling controls on the successor source.",
                    "Re-adjudicate mechanism, reachability, impact and severity using current qualified evidence.",
                ),
            )
            units.append(unit)

        plan = RemediationPlan(
            campaign_id=str(self.snapshot.get("campaign_id", "")),
            history_cut=dict(self.snapshot.get("history_cut") or {}),
            repair_units=tuple(units),
            unresolved_inputs=tuple(unresolved),
        )
        validate_remediation_plan(plan)
        return plan


__all__ = ["RemediationPlanner", "validate_remediation_plan"]
