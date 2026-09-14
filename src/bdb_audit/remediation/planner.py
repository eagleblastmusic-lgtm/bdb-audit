"""Evidence-linked remediation plan construction and validation."""
from __future__ import annotations

import re
from typing import Any, Mapping

from ..core.errors import ValidationError
from ..report.models import ReportSnapshot
from .models import RemediationPlan, RepairUnit

_ACTIONABLE = {"OPEN", "CONFIRMED_CURRENT", "REMEDIATION_PENDING", "REOPENED", "PARTIALLY_FIXED"}
_REQUIRED_V2_SEQUENCE_FIELDS = (
    "reproduction_steps", "fix_alternatives", "regression_tests", "negative_tests",
    "sibling_tests", "holdout_tests", "acceptance_protocol",
)


def _unit_id(index: int, finding: Mapping[str, Any]) -> str:
    claim_id = str(finding.get("claim_id") or "finding")
    token = re.sub(r"[^A-Za-z0-9_.-]+", "-", claim_id).strip("-") or "finding"
    return f"RU-{index:04d}-{token[:48]}"


def _affected_modules(finding: Mapping[str, Any]) -> tuple[str, ...]:
    modules: set[str] = set()
    descriptors = finding.get("scope_descriptors", [])
    if isinstance(descriptors, (list, tuple)):
        for descriptor in descriptors:
            if not isinstance(descriptor, Mapping):
                continue
            for key in ("path", "module", "component", "package", "target_path"):
                value = descriptor.get(key)
                if isinstance(value, str) and value.strip():
                    modules.add(value.strip())
    return tuple(sorted(modules))


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
    v2 = str(body.get("plan_version", "1")) >= "2"
    if v2:
        source = body.get("source_identity")
        if not isinstance(source, Mapping) or not source:
            raise ValidationError("REMEDIATION_SOURCE_IDENTITY_REQUIRED")
        cut = body.get("history_cut")
        if not isinstance(cut, Mapping) or cut.get("variant") != "ACCEPTED_HISTORY_CUT":
            raise ValidationError("REMEDIATION_ACCEPTED_CUT_REQUIRED")

    for unit in units:
        if not isinstance(unit, Mapping):
            raise ValidationError("REMEDIATION_UNIT_INVALID")
        deps = unit.get("dependency_unit_ids", [])
        if not isinstance(deps, list) or any(dep not in id_set for dep in deps):
            raise ValidationError("REMEDIATION_DEPENDENCY_INVALID", str(unit.get("unit_id")))
        if unit.get("unit_id") in deps:
            raise ValidationError("REMEDIATION_CYCLE", str(unit.get("unit_id")))
        graph[str(unit["unit_id"])] = tuple(str(dep) for dep in deps)
        if not isinstance(unit.get("finding_ref"), Mapping):
            raise ValidationError("REMEDIATION_FINDING_REF_REQUIRED", str(unit.get("unit_id")))
        if not str(unit.get("statement", "")).strip():
            raise ValidationError("REMEDIATION_STATEMENT_REQUIRED", str(unit.get("unit_id")))
        if v2:
            if not str(unit.get("expected_fixed_property", "")).strip():
                raise ValidationError("REMEDIATION_FIXED_PROPERTY_REQUIRED", str(unit.get("unit_id")))
            if not str(unit.get("migration_strategy", "")).strip():
                raise ValidationError("REMEDIATION_MIGRATION_STRATEGY_REQUIRED", str(unit.get("unit_id")))
            for field in _REQUIRED_V2_SEQUENCE_FIELDS:
                value = unit.get(field)
                if not isinstance(value, list) or not value or any(not isinstance(item, str) or not item.strip() for item in value):
                    raise ValidationError("REMEDIATION_PROTOCOL_FIELD_REQUIRED", f"{unit.get('unit_id')}:{field}")

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
    return {"status": "PASS", "unit_count": len(units), "acyclic": True, "plan_version": str(body.get("plan_version", "1"))}


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
            root_causes = finding.get("root_cause_refs", [])
            modules = _affected_modules(finding)
            claim_id = str(finding.get("claim_id") or finding.get("finding_ref", {}).get("revision_digest") or "finding")
            if not modules:
                unresolved.append({
                    "type": "AFFECTED_MODULE_MAPPING_NOT_AVAILABLE",
                    "finding_ref": dict(finding.get("finding_ref") or {}),
                    "reason": "Accepted scope refs did not expose a path/module/component descriptor at this cut.",
                })
            if not root_causes:
                unresolved.append({
                    "type": "ROOT_CAUSE_NOT_ASSESSED",
                    "finding_ref": dict(finding.get("finding_ref") or {}),
                })
            if not evidence:
                unresolved.append({
                    "type": "REMEDIATION_EVIDENCE_LINK_MISSING",
                    "finding_ref": dict(finding.get("finding_ref") or {}),
                })

            status = "PROPOSED" if modules and root_causes and evidence else "PROPOSED_WITH_UNRESOLVED_INPUTS"
            unit = RepairUnit(
                unit_id=_unit_id(index, finding),
                finding_ref=dict(finding.get("finding_ref") or {}),
                statement=str(finding.get("statement", "")),
                lifecycle_status=lifecycle,
                affected_scope_refs=tuple(dict(v) for v in scopes if isinstance(v, Mapping)),
                root_cause_refs=tuple(dict(v) for v in root_causes if isinstance(v, Mapping)),
                evidence_refs=tuple(dict(v) for v in evidence if isinstance(v, Mapping)),
                affected_modules=modules,
                expected_fixed_property=(
                    "The exact finding claim is no longer CONFIRMED_CURRENT after qualified re-adjudication "
                    "on the successor source; predecessor accepted history and evidence remain immutable."
                ),
                reproduction_steps=(
                    f"Pin the predecessor source and accepted history cut from remediation plan for {claim_id}.",
                    "Resolve the finding_ref and all evidence_refs from canonical accepted history; do not substitute a mutable export.",
                    "Re-run the accepted mechanism/reachability path using the same qualified environment or record a new applicability assessment if the environment changed.",
                    "Record a measured reproduction receipt; an unavailable or inconclusive reproduction remains explicit and cannot be treated as fixed.",
                ),
                fix_alternatives=(
                    "Minimal successor repair: change only the affected implementation surface necessary to restore the expected fixed property.",
                    "Structural successor repair: redesign the root-cause boundary only when the minimal repair cannot satisfy sibling/negative controls; preserve a traceable migration from predecessor behavior.",
                ),
                regression_tests=(
                    f"Add or bind an exact regression for finding {claim_id} that fails on the predecessor and passes on the successor.",
                ),
                negative_tests=(
                    "Exercise malformed, forbidden, stale or unauthorized variants relevant to the violated invariant; PASS requires fail-closed behavior.",
                ),
                sibling_tests=(
                    "Run tests for adjacent features/invariants sharing the affected scope or root-cause dependency to detect repair-induced regressions.",
                ),
                holdout_tests=(
                    "Run an applicable blind holdout or mutation control for the same defect/invariant class; if no qualified case exists, record the holdout gap explicitly instead of claiming broad effectiveness.",
                ),
                migration_strategy=(
                    "Create a successor source generation; preserve predecessor accepted history; invalidate or requalify evidence whose source, dependency, policy or runtime applicability changed; then re-run affected STOP/release gates."
                ),
                acceptance_protocol=(
                    "Reproduce or explicitly bound the accepted predecessor finding using its exact evidence refs.",
                    "Implement the repair only on a successor source generation and bind the new source identity.",
                    "Run finding-specific regression, negative, sibling and applicable holdout/mutation controls with actual execution receipts.",
                    "Re-adjudicate mechanism, reachability, impact and severity using current qualified evidence and resolve material contradictions.",
                    "Recompute affected coverage obligations and STOP/release decisions; unknown, unsupported or stale inputs remain blocking/limited as required by policy.",
                ),
                status=status,
            )
            units.append(unit)

        plan = RemediationPlan(
            campaign_id=str(self.snapshot.get("campaign_id", "")),
            history_cut=dict(self.snapshot.get("history_cut") or {}),
            source_identity=dict(self.snapshot.get("source_identity") or {}),
            repair_units=tuple(units),
            unresolved_inputs=tuple(unresolved),
        )
        validate_remediation_plan(plan)
        return plan


__all__ = ["RemediationPlanner", "validate_remediation_plan"]
