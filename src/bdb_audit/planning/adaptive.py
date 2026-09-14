"""RU14 adaptive lane planner with obligation-preserving budget selection."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True)
class LaneCandidate:
    lane_id: str
    method: str
    obligation_ids: tuple[str, ...]
    expected_unique_yield: float
    cost_units: int
    independence_group: str
    required: bool = False


@dataclass(frozen=True)
class LanePlan:
    selected: tuple[LaneCandidate, ...]
    total_cost_units: int
    uncovered_required_obligations: tuple[str, ...]
    decision: str


class AdaptiveLanePlanner:
    def plan(self, candidates: Sequence[LaneCandidate], required_obligations: Sequence[str], budget_units: int) -> LanePlan:
        if budget_units < 0:
            raise ValueError("budget_units must be non-negative")
        required = set(required_obligations)
        selected: list[LaneCandidate] = []
        cost = 0
        mandatory = sorted((c for c in candidates if c.required), key=lambda c: c.lane_id)
        for lane in mandatory:
            if cost + lane.cost_units > budget_units:
                return LanePlan(tuple(selected), cost, tuple(sorted(required)), "BLOCKED_REQUIRED_BUDGET")
            selected.append(lane)
            cost += lane.cost_units
            required.difference_update(lane.obligation_ids)
        remaining = [c for c in candidates if c not in selected]
        remaining.sort(key=lambda c: (-(c.expected_unique_yield / max(1, c.cost_units)), c.independence_group, c.lane_id))
        seen_groups = {c.independence_group for c in selected}
        for lane in remaining:
            if cost + lane.cost_units > budget_units:
                continue
            adds_required = bool(required.intersection(lane.obligation_ids))
            adds_independence = lane.independence_group not in seen_groups
            if not adds_required and not adds_independence and lane.expected_unique_yield <= 0:
                continue
            selected.append(lane)
            cost += lane.cost_units
            seen_groups.add(lane.independence_group)
            required.difference_update(lane.obligation_ids)
        decision = "READY" if not required else "INSUFFICIENT_COVERAGE"
        return LanePlan(tuple(selected), cost, tuple(sorted(required)), decision)
