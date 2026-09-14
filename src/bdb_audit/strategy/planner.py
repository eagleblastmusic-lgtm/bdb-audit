from __future__ import annotations

from typing import Sequence

from .models import AuditStrategyProfile, LaneProposal, StrategyPlan


def propose_plan(*, profile: AuditStrategyProfile, source_identity: str, history_cut_digest: str, lanes: Sequence[LaneProposal], revision: str = "1") -> StrategyPlan:
    mandatory_roles = set(profile.mandatory_role_ids)
    selected = list(lanes)
    missing = mandatory_roles.difference(lane.role_id for lane in selected)
    if missing:
        raise ValueError("mandatory baseline roles missing: " + ",".join(sorted(missing)))
    return StrategyPlan(revision, source_identity, history_cut_digest, tuple(selected), sum(lane.cost_units for lane in selected))
