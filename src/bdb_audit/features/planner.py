from __future__ import annotations

import hashlib

from .models import BehaviorCase, OracleAssessment, TestabilityAssessment, VerificationPlan


def plan_verification(
    *, source_identity: str, behavior: BehaviorCase, oracle: OracleAssessment,
    testability: TestabilityAssessment, argv: tuple[str, ...], cwd: str | None,
    fixture_refs: tuple[str, ...] = (), environment_identity: str = "LOCAL_DECLARED",
) -> VerificationPlan:
    if oracle.status != "QUALIFIED":
        raise ValueError("qualified oracle required before planning")
    if testability.status != "TESTABLE" or not testability.adapter_kind:
        raise ValueError("testable behavior required before planning")
    if not argv:
        raise ValueError("execution argv required")
    material = f"{source_identity}|{behavior.behavior_id}|{oracle.oracle_id}|{environment_identity}|{argv!r}"
    plan_id = "verification_plan_" + hashlib.sha256(material.encode()).hexdigest()[:20]
    return VerificationPlan(plan_id, source_identity, behavior.behavior_id, oracle, testability, argv, cwd, fixture_refs, environment_identity)
