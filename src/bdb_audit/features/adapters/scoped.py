"""Fail-closed adapters for environment-dependent functional verification."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from ...runner.specs import OperationalToolSpec
from ..models import BehaviorCase, TestabilityAssessment, VerificationPlan


@dataclass(frozen=True)
class ScopedCommandAdapter:
    adapter_kind: str
    required_capability: str
    require_no_network: bool

    def assess(self, behavior: BehaviorCase, capabilities: Iterable[str]) -> TestabilityAssessment:
        available = set(capabilities)
        if self.required_capability not in available:
            return TestabilityAssessment(
                behavior.behavior_id,
                "BLOCKED",
                self.adapter_kind,
                (self.required_capability,),
                (f"CAPABILITY_UNAVAILABLE:{self.required_capability}",),
            )
        return TestabilityAssessment(behavior.behavior_id, "TESTABLE", self.adapter_kind, (), ())

    def to_tool_spec(self, plan: VerificationPlan, capabilities: Iterable[str]) -> OperationalToolSpec:
        if self.required_capability not in set(capabilities):
            raise ValueError(f"required capability unavailable: {self.required_capability}")
        return OperationalToolSpec(
            tool_id=f"functional-{self.adapter_kind.lower()}",
            action_class="FUNCTIONAL_VERIFICATION",
            argv=plan.argv,
            source_identity=plan.source_identity,
            scope_identity=plan.behavior_id,
            ruleset_ref=f"functional-{self.adapter_kind.lower()}-v1",
            fixture_refs=plan.fixture_refs,
            cwd=plan.cwd,
            require_no_network=self.require_no_network,
        )


BROWSER_ADAPTER = ScopedCommandAdapter("BROWSER", "BROWSER_SANDBOX", False)
WORKER_ADAPTER = ScopedCommandAdapter("WORKER", "WORKER_SANDBOX", True)
DATABASE_ADAPTER = ScopedCommandAdapter("DATABASE", "DISPOSABLE_DATABASE", False)
DESKTOP_ADAPTER = ScopedCommandAdapter("DESKTOP", "DESKTOP_UI_HARNESS", True)
MANUAL_ADAPTER = ScopedCommandAdapter("MANUAL", "MANUAL_PROVENANCE_CAPTURE", True)

__all__ = [
    "ScopedCommandAdapter", "BROWSER_ADAPTER", "WORKER_ADAPTER", "DATABASE_ADAPTER",
    "DESKTOP_ADAPTER", "MANUAL_ADAPTER",
]
