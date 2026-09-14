from __future__ import annotations

from .models import BehaviorCase, TestabilityAssessment


def assess_testability(behavior: BehaviorCase, available_adapters: tuple[str, ...]) -> TestabilityAssessment:
    preferred = "CLI" if "CLI" in available_adapters else (available_adapters[0] if available_adapters else None)
    if preferred is None:
        return TestabilityAssessment(behavior.behavior_id, "BLOCKED", None, (), ("NO_ADAPTER_AVAILABLE",))
    return TestabilityAssessment(behavior.behavior_id, "TESTABLE", preferred, (), ())
