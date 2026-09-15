"""Publication quality gate for RU15 product/UX opportunities.

The gate separates product-opportunity publication from technical STOP and
requires target-bound evidence.  A caller cannot obtain ACCEPT/QUICK_WIN merely
by naming a ``metric:*`` reference or declaring ``confidence_basis=MEASURED``.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Mapping, Sequence

from .models import OpportunityEvidence, OpportunityProposal, ProductContext
from .skeptic import skeptic_review

_ALLOWED_EVIDENCE_KINDS = {"TRACE", "METRIC", "SOURCE"}
_EXPECTED_REPORT_SECTION = "PRODUCT_AND_UX_OPPORTUNITIES"


@dataclass(frozen=True)
class OpportunityQualityDecision:
    opportunity_id: str
    status: str
    priority: str
    reason_codes: tuple[str, ...]
    simpler_alternative: str | None
    technical_stop_effect: str = "NONE"
    verified_evidence_refs: tuple[str, ...] = ()


def _normalize(value: str) -> str:
    return " ".join(value.lower().split())


def _reason_matches(reasons: set[str], exact: set[str], prefixes: tuple[str, ...]) -> bool:
    if reasons.intersection(exact):
        return True
    return any(any(reason.startswith(prefix) for prefix in prefixes) for reason in reasons)


def _validate_evidence(
    proposal: OpportunityProposal,
    context: ProductContext,
    evidence_catalog: Mapping[str, OpportunityEvidence] | None,
) -> tuple[set[str], tuple[str, ...], bool]:
    reasons: set[str] = set()
    verified: list[str] = []
    valid_metric = False

    if len(set(proposal.evidence_refs)) != len(proposal.evidence_refs):
        reasons.add("EVIDENCE_REF_DUPLICATE")
    if proposal.evidence_refs and evidence_catalog is None:
        reasons.add("EVIDENCE_CATALOG_REQUIRED")

    catalog = evidence_catalog or {}
    for evidence_ref in proposal.evidence_refs:
        record = catalog.get(evidence_ref)
        if record is None:
            reasons.add(f"EVIDENCE_REF_UNRESOLVED:{evidence_ref}")
            continue
        record_valid = True
        if record.evidence_ref != evidence_ref:
            reasons.add(f"EVIDENCE_KEY_MISMATCH:{evidence_ref}")
            record_valid = False
        if record.target_source_identity != proposal.target_source_identity or record.target_source_identity != context.target_source_identity:
            reasons.add(f"EVIDENCE_SOURCE_MISMATCH:{evidence_ref}")
            record_valid = False
        if record.evidence_kind not in _ALLOWED_EVIDENCE_KINDS:
            reasons.add(f"EVIDENCE_KIND_INVALID:{evidence_ref}")
            record_valid = False
        if not record.provenance_ref.strip():
            reasons.add(f"EVIDENCE_PROVENANCE_MISSING:{evidence_ref}")
            record_valid = False

        if record.evidence_kind == "METRIC":
            value = record.measured_value
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
                reasons.add(f"METRIC_VALUE_INVALID:{evidence_ref}")
                record_valid = False
            if record.measurement_unit is None or not record.measurement_unit.strip():
                reasons.add(f"METRIC_UNIT_MISSING:{evidence_ref}")
                record_valid = False
            if record_valid:
                valid_metric = True
        elif proposal.confidence_basis == "OBSERVED" and record.evidence_kind == "TRACE" and not record.observed:
            reasons.add(f"TRACE_NOT_OBSERVED:{evidence_ref}")
            record_valid = False

        if record_valid:
            verified.append(evidence_ref)

    if proposal.confidence_basis == "MEASURED" and not valid_metric:
        reasons.add("MEASURED_EVIDENCE_UNRESOLVED")
    if proposal.confidence_basis == "OBSERVED":
        has_observed_trace = any(
            evidence_ref in verified
            and catalog[evidence_ref].evidence_kind == "TRACE"
            and catalog[evidence_ref].observed
            for evidence_ref in proposal.evidence_refs
            if evidence_ref in catalog
        )
        if not has_observed_trace:
            reasons.add("OBSERVED_EVIDENCE_UNRESOLVED")
    if proposal.confidence_basis == "SOURCE_INFERRED":
        has_source = any(
            evidence_ref in verified and catalog[evidence_ref].evidence_kind == "SOURCE"
            for evidence_ref in proposal.evidence_refs
            if evidence_ref in catalog
        )
        if not has_source:
            reasons.add("SOURCE_INFERRED_EVIDENCE_UNRESOLVED")

    return reasons, tuple(sorted(set(verified))), valid_metric


def qualify_opportunity_for_report(
    proposal: OpportunityProposal,
    context: ProductContext,
    *,
    existing_feature_titles: Sequence[str] = (),
    simpler_alternative: str | None = None,
    evidence_catalog: Mapping[str, OpportunityEvidence] | None = None,
) -> OpportunityQualityDecision:
    reasons: set[str] = set()
    normalized_existing = {_normalize(value) for value in existing_feature_titles}
    if _normalize(proposal.title) in normalized_existing:
        reasons.add("FEATURE_ALREADY_PRESENT")

    skeptic = skeptic_review(proposal, context)
    reasons.update(skeptic.reason_codes)

    evidence_reasons, verified_evidence, valid_metric = _validate_evidence(
        proposal,
        context,
        evidence_catalog,
    )
    reasons.update(evidence_reasons)

    if proposal.current_steps is not None and proposal.proposed_steps is not None:
        if proposal.proposed_steps >= proposal.current_steps:
            reasons.add("NO_STEP_REDUCTION")

    if proposal.implementation_cost.upper() == "UNKNOWN":
        reasons.add("IMPLEMENTATION_COST_UNKNOWN")
    if proposal.risk.upper() == "UNKNOWN":
        reasons.add("RISK_UNKNOWN")
    if not proposal.alternatives:
        reasons.add("ALTERNATIVES_MISSING")
    if proposal.consumer_report_section != _EXPECTED_REPORT_SECTION:
        reasons.add("REPORT_SECTION_INVALID")

    reject_exact = {
        "FEATURE_ALREADY_PRESENT",
        "TARGET_SOURCE_MISMATCH",
        "FRICTION_EVIDENCE_MISSING",
        "PERSONA_UNKNOWN",
        "MEASURED_CLAIM_WITHOUT_METRIC",
        "REQUIRED_FIELD_MISSING",
        "EVIDENCE_CATALOG_REQUIRED",
        "EVIDENCE_REF_DUPLICATE",
        "MEASURED_EVIDENCE_UNRESOLVED",
        "OBSERVED_EVIDENCE_UNRESOLVED",
        "SOURCE_INFERRED_EVIDENCE_UNRESOLVED",
        "REPORT_SECTION_INVALID",
    }
    reject_prefixes = (
        "EVIDENCE_REF_UNRESOLVED:",
        "EVIDENCE_KEY_MISMATCH:",
        "EVIDENCE_SOURCE_MISMATCH:",
        "EVIDENCE_KIND_INVALID:",
        "EVIDENCE_PROVENANCE_MISSING:",
        "METRIC_VALUE_INVALID:",
        "METRIC_UNIT_MISSING:",
        "TRACE_NOT_OBSERVED:",
    )
    revise_exact = {
        "AUTOMATION_CONTROL_MISSING",
        "INVALID_STEP_ACCOUNTING",
        "NO_STEP_REDUCTION",
        "IMPLEMENTATION_COST_UNKNOWN",
        "RISK_UNKNOWN",
        "CONFIDENCE_BASIS_UNKNOWN",
        "ALTERNATIVES_MISSING",
    }

    if _reason_matches(reasons, reject_exact, reject_prefixes):
        status = "REJECT"
    elif reasons.intersection(revise_exact):
        status = "REVISE"
    else:
        status = "ACCEPT_FOR_REPORT"

    if status == "REVISE" and (simpler_alternative is None or not simpler_alternative.strip()):
        reasons.add("SIMPLER_ALTERNATIVE_MISSING")

    reduction = None
    if proposal.current_steps is not None and proposal.proposed_steps is not None:
        reduction = proposal.current_steps - proposal.proposed_steps
    priority = "STANDARD"
    if (
        status == "ACCEPT_FOR_REPORT"
        and proposal.confidence_basis == "MEASURED"
        and valid_metric
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
        verified_evidence_refs=verified_evidence,
    )


__all__ = ["OpportunityQualityDecision", "qualify_opportunity_for_report"]
