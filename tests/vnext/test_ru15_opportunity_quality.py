from __future__ import annotations

from bdb_audit.opportunities.models import OpportunityEvidence, OpportunityProposal, ProductContext
from bdb_audit.opportunities.quality import qualify_opportunity_for_report


def _context() -> ProductContext:
    return ProductContext("src-A", "Reference Target", ("operator",), ("web",), ("ctx:1",))


def _proposal(opportunity_id: str, title: str, *, current_steps: int = 8, proposed_steps: int = 3, cost: str = "LOW", risk: str = "LOW") -> OpportunityProposal:
    return OpportunityProposal(
        opportunity_id,
        "src-A",
        "WORKFLOW",
        title,
        "Repeated navigation slows a recorded operator task",
        ("operator",),
        ("trace:1", "metric:task-steps"),
        current_steps,
        proposed_steps,
        "Reduce measured task friction",
        cost,
        risk,
        ("Keep current flow",),
        "Keep existing confirmation boundary; re-measure completion time and success rate",
        "MEASURED",
    )


def _evidence(*, source: str = "src-A", measured_value: float | int = 8) -> dict[str, OpportunityEvidence]:
    return {
        "trace:1": OpportunityEvidence(
            "trace:1",
            source,
            "TRACE",
            "accepted-history:trace-1",
            observed=True,
        ),
        "metric:task-steps": OpportunityEvidence(
            "metric:task-steps",
            source,
            "METRIC",
            "accepted-history:metric-task-steps",
            measured_value=measured_value,
            measurement_unit="steps",
        ),
    }


def test_ru15_reference_target_rejects_feature_creep():
    proposal = _proposal("opp-existing", "Saved filters")
    decision = qualify_opportunity_for_report(
        proposal,
        _context(),
        existing_feature_titles=("Saved filters", "Export report"),
        evidence_catalog=_evidence(),
    )
    assert decision.status == "REJECT"
    assert "FEATURE_ALREADY_PRESENT" in decision.reason_codes
    assert decision.technical_stop_effect == "NONE"


def test_ru15_reference_target_revises_to_simpler_alternative():
    proposal = _proposal("opp-overbuilt", "Guided audit", current_steps=5, proposed_steps=5, cost="UNKNOWN")
    decision = qualify_opportunity_for_report(
        proposal,
        _context(),
        simpler_alternative="Keep the current task and remove only the redundant navigation step.",
        evidence_catalog=_evidence(),
    )
    assert decision.status == "REVISE"
    assert decision.simpler_alternative
    assert "NO_STEP_REDUCTION" in decision.reason_codes
    assert "IMPLEMENTATION_COST_UNKNOWN" in decision.reason_codes
    assert decision.technical_stop_effect == "NONE"


def test_ru15_reference_target_accepts_only_evidence_bound_measured_quick_win():
    proposal = _proposal("opp-quick", "One-step result reopen")
    decision = qualify_opportunity_for_report(proposal, _context(), evidence_catalog=_evidence())
    assert decision.status == "ACCEPT_FOR_REPORT"
    assert decision.priority == "QUICK_WIN"
    assert decision.reason_codes == ()
    assert decision.verified_evidence_refs == ("metric:task-steps", "trace:1")
    assert decision.technical_stop_effect == "NONE"


def test_ru15_declared_metric_ref_without_catalog_cannot_publish():
    proposal = _proposal("opp-fake-metric", "One-step result reopen")
    decision = qualify_opportunity_for_report(proposal, _context())
    assert decision.status == "REJECT"
    assert "EVIDENCE_CATALOG_REQUIRED" in decision.reason_codes
    assert "MEASURED_EVIDENCE_UNRESOLVED" in decision.reason_codes
    assert decision.priority == "STANDARD"


def test_ru15_stale_source_evidence_is_rejected():
    proposal = _proposal("opp-stale", "One-step result reopen")
    decision = qualify_opportunity_for_report(
        proposal,
        _context(),
        evidence_catalog=_evidence(source="src-B"),
    )
    assert decision.status == "REJECT"
    assert any(reason.startswith("EVIDENCE_SOURCE_MISMATCH:") for reason in decision.reason_codes)
    assert decision.priority == "STANDARD"


def test_ru15_metric_requires_value_unit_and_provenance():
    proposal = _proposal("opp-bad-metric", "One-step result reopen")
    evidence = _evidence()
    evidence["metric:task-steps"] = OpportunityEvidence(
        "metric:task-steps",
        "src-A",
        "METRIC",
        "",
        measured_value=None,
        measurement_unit=None,
    )
    decision = qualify_opportunity_for_report(proposal, _context(), evidence_catalog=evidence)
    assert decision.status == "REJECT"
    assert "EVIDENCE_PROVENANCE_MISSING:metric:task-steps" in decision.reason_codes
    assert "METRIC_VALUE_INVALID:metric:task-steps" in decision.reason_codes
    assert "METRIC_UNIT_MISSING:metric:task-steps" in decision.reason_codes
    assert "MEASURED_EVIDENCE_UNRESOLVED" in decision.reason_codes


def test_ru15_report_section_and_alternatives_are_quality_gated():
    proposal = _proposal("opp-wrong-section", "One-step result reopen")
    proposal = OpportunityProposal(
        proposal.opportunity_id,
        proposal.target_source_identity,
        proposal.category,
        proposal.title,
        proposal.user_problem,
        proposal.target_users,
        proposal.evidence_refs,
        proposal.current_steps,
        proposal.proposed_steps,
        proposal.expected_value,
        proposal.implementation_cost,
        proposal.risk,
        (),
        proposal.controls_and_measurement,
        proposal.confidence_basis,
        "TECHNICAL_FINDINGS",
    )
    decision = qualify_opportunity_for_report(proposal, _context(), evidence_catalog=_evidence())
    assert decision.status == "REJECT"
    assert "REPORT_SECTION_INVALID" in decision.reason_codes
    assert "ALTERNATIVES_MISSING" in decision.reason_codes
