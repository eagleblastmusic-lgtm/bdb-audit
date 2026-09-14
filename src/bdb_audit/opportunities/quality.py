"""Publication quality gate for RU15 product/UX opportunities.

This layer is intentionally separate from technical STOP. It turns evidence-backed
proposals into ACCEPT/REVISE/REJECT publication decisions and makes feature-creep
rejection explicit.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from .models import OpportunityProposal, ProductContext
from .skeptic import skeptic_review


@dataclass(frozen=True)
class OpportunityQualityDecision:
    opportunity_id: str
    status: str
    priority: str
    reason_codes: tuple[str, ...]
    simpler_alternative: str | None
    technical_stop_effect: str = "NONE"


def _normalize(value: str) -> str:
    return " ".join(value.lower().split())


def qualify_opportunity_for_report(
    proposal: OpportunityProposal,
    context: ProductContext,
    *,
    existing_feature_titles: Sequence[str] = (),
    simpler_alternative: str | None = None,
) -> OpportunityQualityDecision:
    reasons: set[str] = set()
    normalized_existing = {_normalize(value) for value in existing_feature_titles}
    if _normalize(proposal.title) in normalized_existing:
        reasons.add("FEATURE_ALREADY_PRESENT")

    skeptic = skeptic_review(proposal, context)
    reasons.update(skeptic.reason_codes)

    if proposal.current_steps is not None and proposal.proposed_steps is not None:
        if proposal.proposed_steps >= proposal.current_steps:
            reasons.add("NO_STEP_REDUCTION")

    if proposal.implementation_cost.upper() == "UNKNOWN":
        reasons.add("IMPLEMENTATION_COST_UNKNOWN")
    if proposal.risk.upper() == "UNKNOWN":
        reasons.add("RISK_UNKNOWN")

    reject_reasons = {
        "FEATURE_ALREADY_PRESENT",
        "TARGET_SOURCE_MISMATCH",
        "FRICTION_EVIDENCE_MISSING",
        "PERSONA_UNKNOWN",
        "MEASURED_CLAIM_WITHOUT_METRIC",
        "REQUIRED_FIELD_MISSING",
    }
    revise_reasons = {
        "AUTOMATION_CONTROL_MISSING",
        "INVALID_STEP_ACCOUNTING",
        "NO_STEP_REDUCTION",
        "IMPLEMENTATION_COST_UNKNOWN",
        "RISK_UNKNOWN",
        "CONFIDENCE_BASIS_UNKNOWN",
    }

    if reasons.intersection(reject_reasons):
        status = "REJECT"
    elif reasons.intersection(revise_reasons):
        status = "REVISE"
    else:
        status = "ACCEPT_FOR_REPORT"

    reduction = None
    if proposal.current_steps is not None and proposal.proposed_steps is not None:
        reduction = proposal.current_steps - proposal.proposed_steps
    priority = "STANDARD"
    if (
        status == "ACCEPT_FOR_REPORT"
        and reduction is not None
        and reduction > 0
        and proposal.implementation_cost.upper() == "LOW"
        and proposal.risk.upper() == "LOW"
    ):
        priority = "QUICK_WIN"

    alternative = simpler_alternative if status == "REVISE" else None
    return OpportunityQualityDecision(
        proposal.opportunity_id,
        status,
        priority,
        tuple(sorted(reasons)),
        alternative,
    )


__all__ = ["OpportunityQualityDecision", "qualify_opportunity_for_report"]
