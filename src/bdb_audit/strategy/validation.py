from __future__ import annotations

from .models import AuditStrategyProfile, StrategyPlan


def _acyclic(plan: StrategyPlan) -> bool:
    deps = {lane.lane_id: set(lane.predecessor_lane_ids) for lane in plan.lanes}
    if any(dep not in deps for values in deps.values() for dep in values):
        return False
    temporary: set[str] = set()
    permanent: set[str] = set()

    def visit(node: str) -> bool:
        if node in permanent:
            return True
        if node in temporary:
            return False
        temporary.add(node)
        for dep in deps[node]:
            if not visit(dep):
                return False
        temporary.remove(node)
        permanent.add(node)
        return True

    return all(visit(node) for node in deps)


def validate_plan(plan: StrategyPlan, profile: AuditStrategyProfile) -> dict:
    reasons: list[str] = []
    role_ids = {lane.role_id for lane in plan.lanes}
    if not set(profile.mandatory_role_ids).issubset(role_ids):
        reasons.append("MANDATORY_BASELINE_REMOVED")
    if plan.budget_units > profile.max_budget_units:
        reasons.append("BUDGET_EXCEEDED")
    if len({lane.lane_id for lane in plan.lanes}) != len(plan.lanes):
        reasons.append("DUPLICATE_LANE_ID")
    if len({lane.session_id for lane in plan.lanes}) != len(plan.lanes):
        reasons.append("SESSION_REUSE_WEAKENS_INDEPENDENCE")
    if not _acyclic(plan):
        reasons.append("LANE_DEPENDENCY_DAG_INVALID")
    for lane in plan.lanes:
        if lane.method not in profile.allowed_methods:
            reasons.append(f"METHOD_NOT_ALLOWED:{lane.lane_id}")
        if not lane.scope_ids or not lane.consumer:
            reasons.append(f"SCOPE_OR_CONSUMER_MISSING:{lane.lane_id}")
        if not lane.mandatory and not lane.obligation_ids:
            reasons.append(f"OPTIONAL_LANE_WITHOUT_OBLIGATION:{lane.lane_id}")
        if lane.exposure.source_identity != plan.source_identity or lane.exposure.history_cut_digest != plan.history_cut_digest:
            reasons.append(f"EXPOSURE_BINDING_MISMATCH:{lane.lane_id}")
        if not set(lane.exposure.exposure_classes).issubset(profile.allowed_exposure_classes):
            reasons.append(f"EXPOSURE_WIDENING_FORBIDDEN:{lane.lane_id}")
        if set(lane.exposure.allowed_refs).intersection(lane.exposure.forbidden_refs):
            reasons.append(f"EXPOSURE_ALLOW_DENY_CONFLICT:{lane.lane_id}")
    return {"status": "VALIDATED" if not reasons else "REJECTED", "reason_codes": sorted(set(reasons)), "budget_used": plan.budget_units, "budget_limit": profile.max_budget_units}
