from __future__ import annotations

from dataclasses import dataclass


FEATURE_STATES = (
    "DISCOVERED", "RECONCILED", "EXPECTATION_QUALIFIED", "TESTABILITY_ASSESSED",
    "PLANNED", "RUNNING", "ASSESSED",
)


@dataclass(frozen=True)
class FeatureRevision:
    feature_id: str
    revision: str
    source_identity: str
    user_task: str
    entrypoints: tuple[str, ...]
    requirement_refs: tuple[str, ...]
    roles: tuple[str, ...] = ()
    environment_classes: tuple[str, ...] = ()
    input_classes: tuple[str, ...] = ()
    criticality: str = "NORMAL"
    discovery_confidence: str = "CONFIRMED"


@dataclass(frozen=True)
class BehaviorCase:
    behavior_id: str
    feature_id: str
    description: str
    requirement_refs: tuple[str, ...]
    negative_or_recovery: bool = False


@dataclass(frozen=True)
class OracleAssessment:
    oracle_id: str
    source_kind: str
    source_refs: tuple[str, ...]
    status: str
    reason_codes: tuple[str, ...] = ()


@dataclass(frozen=True)
class TestabilityAssessment:
    behavior_id: str
    status: str
    adapter_kind: str | None
    prerequisites: tuple[str, ...] = ()
    reason_codes: tuple[str, ...] = ()


@dataclass(frozen=True)
class VerificationPlan:
    plan_id: str
    source_identity: str
    behavior_id: str
    oracle: OracleAssessment
    testability: TestabilityAssessment
    argv: tuple[str, ...]
    cwd: str | None
    fixture_refs: tuple[str, ...] = ()
    environment_identity: str = "LOCAL_DECLARED"


@dataclass(frozen=True)
class BehaviorAssessment:
    behavior_id: str
    source_identity: str
    status: str
    executed: bool
    oracle_status: str
    run_receipt_digest: str | None
    reason_codes: tuple[str, ...] = ()
