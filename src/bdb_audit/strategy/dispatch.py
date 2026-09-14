"""Dependency-aware dispatch for validated adaptive lane plans."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

from .models import AuditStrategyProfile, ExposureManifest, LaneProposal, StrategyPlan
from .validation import validate_plan


def materialize_exposure(manifest: ExposureManifest, available_refs: Mapping[str, object]) -> dict[str, object]:
    allowed = set(manifest.allowed_refs)
    forbidden = set(manifest.forbidden_refs)
    if allowed.intersection(forbidden):
        raise ValueError("exposure allow/deny conflict")
    missing = allowed.difference(available_refs)
    if missing:
        raise ValueError("allowed exposure ref missing: " + ",".join(sorted(missing)))
    return {key: available_refs[key] for key in sorted(allowed)}


@dataclass
class StrategyDispatcher:
    plan: StrategyPlan
    profile: AuditStrategyProfile
    lane_states: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validation = validate_plan(self.plan, self.profile)
        if validation["status"] != "VALIDATED":
            raise ValueError("strategy plan must validate before dispatch")
        self.lane_states = {lane.lane_id: "PENDING" for lane in self.plan.lanes}

    def _lane(self, lane_id: str) -> LaneProposal:
        for lane in self.plan.lanes:
            if lane.lane_id == lane_id:
                return lane
        raise KeyError(lane_id)

    def ready_lane_ids(self) -> tuple[str, ...]:
        ready = []
        for lane in self.plan.lanes:
            if self.lane_states[lane.lane_id] != "PENDING":
                continue
            if all(self.lane_states.get(dep) == "COMPLETED" for dep in lane.predecessor_lane_ids):
                ready.append(lane.lane_id)
        return tuple(sorted(ready))

    def dispatch(self, lane_id: str, available_refs: Mapping[str, object]) -> dict:
        lane = self._lane(lane_id)
        if lane_id not in self.ready_lane_ids():
            raise ValueError("lane dependencies are not complete")
        exposed = materialize_exposure(lane.exposure, available_refs)
        self.lane_states[lane_id] = "DISPATCHED"
        return {
            "lane_id": lane.lane_id,
            "role_id": lane.role_id,
            "method": lane.method,
            "scope_ids": list(lane.scope_ids),
            "obligation_ids": list(lane.obligation_ids),
            "consumer": lane.consumer,
            "source_identity": self.plan.source_identity,
            "history_cut_digest": self.plan.history_cut_digest,
            "exposure": exposed,
            "session_id": lane.session_id,
        }

    def mark_running(self, lane_id: str) -> None:
        if self.lane_states.get(lane_id) != "DISPATCHED":
            raise ValueError("lane must be dispatched before running")
        self.lane_states[lane_id] = "RUNNING"

    def mark_completed(self, lane_id: str) -> None:
        if self.lane_states.get(lane_id) not in {"DISPATCHED", "RUNNING"}:
            raise ValueError("lane must be dispatched before completion")
        self.lane_states[lane_id] = "COMPLETED"


__all__ = ["StrategyDispatcher", "materialize_exposure"]
