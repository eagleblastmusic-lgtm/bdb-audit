from __future__ import annotations

from bdb_audit.opportunities.models import OpportunityProposal, ProductContext
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


def test_ru15_reference_target_rejects_feature_creep():
    proposal = _proposal("opp-existing", "Saved filters")
    decision = qualify_opportunity_for_report(
        proposal, _context(), existing_feature_titles=("Saved filters", "Export report")
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
    )
    assert decision.status == "REVISE"
    assert decision.simpler_alternative
    assert "NO_STEP_REDUCTION" in decision.reason_codes
    assert "IMPLEMENTATION_COST_UNKNOWN" in decision.reason_codes
    assert decision.technical_stop_effect == "NONE"


def test_ru15_reference_target_accepts_measured_low_risk_quick_win():
    proposal = _proposal("opp-quick", "One-step result reopen")
    decision = qualify_opportunity_for_report(proposal, _context())
    assert decision.status == "ACCEPT_FOR_REPORT"
    assert decision.priority == "QUICK_WIN"
    assert decision.reason_codes == ()
    assert decision.technical_stop_effect == "NONE"
