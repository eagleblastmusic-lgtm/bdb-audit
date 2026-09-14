from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AuditStrategyProfile:
    profile_id: str
    mandatory_role_ids: tuple[str, ...]
    allowed_methods: tuple[str, ...]
    allowed_exposure_classes: tuple[str, ...]
    max_budget_units: int


@dataclass(frozen=True)
class ExposureManifest:
    source_identity: str
    history_cut_digest: str
    allowed_refs: tuple[str, ...]
    exposure_classes: tuple[str, ...]
    forbidden_refs: tuple[str, ...] = ()


@dataclass(frozen=True)
class LaneProposal:
    lane_id: str
    role_id: str
    method: str
    scope_ids: tuple[str, ...]
    obligation_ids: tuple[str, ...]
    consumer: str
    cost_units: int
    exposure: ExposureManifest
    independence_group: str
    session_id: str
    predecessor_lane_ids: tuple[str, ...] = ()
    mandatory: bool = False


@dataclass(frozen=True)
class StrategyPlan:
    revision: str
    source_identity: str
    history_cut_digest: str
    lanes: tuple[LaneProposal, ...]
    budget_units: int
    state: str = "PLAN_PROPOSED"
