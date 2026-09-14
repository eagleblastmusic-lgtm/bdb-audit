from __future__ import annotations

from .models import OpportunityAssessment, OpportunityProposal, ProductContext

_ALLOWED_BASIS = {"OBSERVED", "SOURCE_INFERRED", "MEASURED"}


def skeptic_review(proposal: OpportunityProposal, context: ProductContext) -> OpportunityAssessment:
    reasons: list[str] = []
    if proposal.target_source_identity != context.target_source_identity:
        reasons.append("TARGET_SOURCE_MISMATCH")
    if not proposal.evidence_refs:
        reasons.append("FRICTION_EVIDENCE_MISSING")
    if not proposal.target_users or not set(proposal.target_users).intersection(context.user_groups):
        reasons.append("PERSONA_UNKNOWN")
    if proposal.confidence_basis not in _ALLOWED_BASIS:
        reasons.append("CONFIDENCE_BASIS_UNKNOWN")
    if proposal.confidence_basis == "MEASURED" and not any(ref.startswith("metric:") for ref in proposal.evidence_refs):
        reasons.append("MEASURED_CLAIM_WITHOUT_METRIC")
    if proposal.current_steps is not None and proposal.proposed_steps is not None:
        if proposal.current_steps < 0 or proposal.proposed_steps < 0:
            reasons.append("INVALID_STEP_ACCOUNTING")
    if proposal.category == "AUTOMATION" and "consent" not in proposal.controls_and_measurement.lower() and "preview" not in proposal.controls_and_measurement.lower():
        reasons.append("AUTOMATION_CONTROL_MISSING")
    required_text = (proposal.title, proposal.user_problem, proposal.expected_value, proposal.implementation_cost, proposal.risk, proposal.controls_and_measurement)
    if any(not value.strip() for value in required_text):
        reasons.append("REQUIRED_FIELD_MISSING")
    return OpportunityAssessment(proposal.opportunity_id, "ACCEPT_FOR_REPORT" if not reasons else "REVISE_OR_REJECT", tuple(sorted(set(reasons))))
