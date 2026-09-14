from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProductContext:
    target_source_identity: str
    product_name: str
    user_groups: tuple[str, ...]
    platform_classes: tuple[str, ...]
    context_refs: tuple[str, ...]


@dataclass(frozen=True)
class UserTaskTrace:
    trace_id: str
    target_source_identity: str
    task: str
    user_group: str
    steps: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    observation_basis: str = "OBSERVED"


@dataclass(frozen=True)
class FrictionCandidate:
    friction_id: str
    trace_id: str
    statement: str
    evidence_refs: tuple[str, ...]
    basis: str


@dataclass(frozen=True)
class OpportunityProposal:
    opportunity_id: str
    target_source_identity: str
    category: str
    title: str
    user_problem: str
    target_users: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    current_steps: int | None
    proposed_steps: int | None
    expected_value: str
    implementation_cost: str
    risk: str
    alternatives: tuple[str, ...]
    controls_and_measurement: str
    confidence_basis: str
    consumer_report_section: str = "PRODUCT_AND_UX_OPPORTUNITIES"


@dataclass(frozen=True)
class OpportunityAssessment:
    opportunity_id: str
    status: str
    reason_codes: tuple[str, ...]
