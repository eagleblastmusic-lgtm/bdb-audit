from __future__ import annotations

import sys

from bdb_audit.features import (
    BehaviorCase, assess_testability, plan_verification, qualify_behavior, qualify_oracle,
)
from bdb_audit.features.adapters.api import LocalApiTestAdapter
from bdb_audit.incremental import DependencyEdge, SourceManifest, build_change_map, build_requalification_plan, propagate_impact, qualify_reuse
from bdb_audit.opportunities import OpportunityProposal, ProductContext, skeptic_review
from bdb_audit.runner import ActionAuthorization, OperationalToolSupervisor
from bdb_audit.strategy import AuditStrategyProfile, ExposureManifest, LaneProposal, propose_plan, validate_plan


def test_ru10_operational_receipt_binds_source_environment_and_raw_output():
    plan = plan_verification(
        source_identity="source@abc",
        behavior=BehaviorCase("feature_x:happy", "feature_x", "prints ready", ("req:1",)),
        oracle=qualify_oracle("oracle", "REQUIREMENT", ("req:1",)),
        testability=assess_testability(BehaviorCase("feature_x:happy", "feature_x", "prints ready", ("req:1",)), ("CLI",)),
        argv=(sys.executable, "-c", "print('READY')"),
        cwd=None,
    )
    spec = LocalApiTestAdapter.to_tool_spec(plan)
    supervisor = OperationalToolSupervisor(ActionAuthorization(("FUNCTIONAL_VERIFICATION",), (sys.executable,)))
    result = supervisor.run(spec)
    assert result.status == "PASS"
    assert result.qualified_runtime_receipt
    assert result.source_identity == "source@abc"
    assert len(result.environment_digest) == 64
    assert len(result.stdout_raw_digest) == 64
    assessment = qualify_behavior(plan, result)
    assert assessment.status == "PASS"


def test_ru10_offline_claim_fails_closed_without_os_network_sandbox():
    behavior = BehaviorCase("feature_x:offline", "feature_x", "offline", ("req:2",))
    plan = plan_verification(
        source_identity="source@abc", behavior=behavior,
        oracle=qualify_oracle("oracle", "REQUIREMENT", ("req:2",)),
        testability=assess_testability(behavior, ("CLI",)),
        argv=(sys.executable, "-c", "print('READY')"), cwd=None,
    )
    from bdb_audit.features.adapters.cli import CliBehaviorAdapter
    result = OperationalToolSupervisor(ActionAuthorization(("FUNCTIONAL_VERIFICATION",), (sys.executable,))).run(CliBehaviorAdapter.to_tool_spec(plan, require_no_network=True))
    assert result.status == "BLOCKED"
    assert "NETWORK_ISOLATION_NOT_ENFORCED" in result.reason_codes
    assert qualify_behavior(plan, result).status == "BLOCKED"


def test_ru14_strategy_rejects_baseline_removal_exposure_widening_and_session_reuse():
    profile = AuditStrategyProfile("p", ("BASE",), ("STATIC", "DYNAMIC"), ("SOURCE",), 10)
    exposure = ExposureManifest("src", "cut", ("ref:a",), ("SOURCE", "ANSWER_KEY"))
    lanes = (
        LaneProposal("l1", "BASE", "STATIC", ("scope",), ("o1",), "E5", 2, exposure, "g1", "session" , mandatory=True),
        LaneProposal("l2", "EXTRA", "DYNAMIC", ("scope2",), ("o2",), "REPORT", 2, exposure, "g2", "session"),
    )
    plan = propose_plan(profile=profile, source_identity="src", history_cut_digest="cut", lanes=lanes)
    result = validate_plan(plan, profile)
    assert result["status"] == "REJECTED"
    assert "SESSION_REUSE_WEAKENS_INDEPENDENCE" in result["reason_codes"]
    assert any(code.startswith("EXPOSURE_WIDENING_FORBIDDEN") for code in result["reason_codes"])


def test_ru15_opportunity_cannot_fake_measured_or_cross_target_context():
    context = ProductContext("src-A", "Target", ("operator",), ("web",), ("ctx:1",))
    proposal = OpportunityProposal(
        "opp1", "src-B", "AUTOMATION", "One click", "Too many steps", ("operator",),
        ("trace:1",), 8, 2, "faster", "MEDIUM", "MEDIUM", ("keep manual",),
        "success rate", "MEASURED",
    )
    result = skeptic_review(proposal, context)
    assert result.status == "REVISE_OR_REJECT"
    assert "TARGET_SOURCE_MISMATCH" in result.reason_codes
    assert "MEASURED_CLAIM_WITHOUT_METRIC" in result.reason_codes
    assert "AUTOMATION_CONTROL_MISSING" in result.reason_codes


def test_ru16_dependency_and_environment_changes_force_requalification():
    old = SourceManifest("old", {"db.py": "1", "api.py": "2"}, "lock1", "policy", "runtime")
    new = SourceManifest("new", {"db.py": "9", "api.py": "2"}, "lock2", "policy", "runtime")
    change = build_change_map(old, new)
    assert change["changed_paths"] == ["db.py"]
    assert change["external_input_changes"] == ["DEPENDENCY_LOCK"]
    impact = propagate_impact(("db.py",), (DependencyEdge("db.py", "service"), DependencyEdge("service", "api.py", "UNCERTAIN")))
    assessment = qualify_reuse(evidence_id="ev", dependency_nodes=("api.py",), impact=impact, source_semantics_same=True, policy_same=True, runtime_same=True, evidence_present=True)
    assert assessment["status"] == "REQUALIFICATION_REQUIRED"
    assert "DEPENDENCY_IMPACTED" in assessment["reason_codes"]
    plan = build_requalification_plan((assessment,), control_sample_nodes=("unrelated.py",))
    assert plan["status"] == "TARGETED_AUDIT_REQUIRED"
    assert plan["control_sample_nodes"] == ["unrelated.py"]
