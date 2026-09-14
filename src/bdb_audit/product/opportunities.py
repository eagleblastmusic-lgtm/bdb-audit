"""RU15 product/UX opportunity review with explicit skeptic assessment."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True)
class TaskTrace:
    trace_id: str
    task: str
    steps: tuple[str, ...]
    friction_refs: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()


@dataclass(frozen=True)
class OpportunityCandidate:
    opportunity_id: str
    title: str
    problem: str
    target_users: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    expected_value: str
    implementation_cost: str
    risk: str
    control_or_measurement: str


@dataclass(frozen=True)
class OpportunityReview:
    candidate: OpportunityCandidate
    status: str
    reason_codes: tuple[str, ...]


class ProductOpportunityReviewer:
    REQUIRED_TEXT_FIELDS = ("title", "problem", "expected_value", "implementation_cost", "risk", "control_or_measurement")

    @classmethod
    def skeptic_review(cls, candidate: OpportunityCandidate) -> OpportunityReview:
        reasons: list[str] = []
        for field in cls.REQUIRED_TEXT_FIELDS:
            if not str(getattr(candidate, field)).strip():
                reasons.append(f"MISSING_{field.upper()}")
        if not candidate.target_users:
            reasons.append("TARGET_USERS_MISSING")
        if not candidate.evidence_refs:
            reasons.append("EVIDENCE_MISSING")
        status = "ACCEPTED_CANDIDATE" if not reasons else "REJECTED_UNSUPPORTED"
        return OpportunityReview(candidate, status, tuple(reasons))

    @classmethod
    def review_all(cls, candidates: Sequence[OpportunityCandidate]) -> tuple[OpportunityReview, ...]:
        return tuple(cls.skeptic_review(candidate) for candidate in candidates)
