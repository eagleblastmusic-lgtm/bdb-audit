from __future__ import annotations

import sys

from bdb_audit.functional import BehaviorCase, ExpectedOracle, FeatureRevision, FunctionalVerifier
from bdb_audit.planning import AdaptiveLanePlanner, LaneCandidate
from bdb_audit.product import OpportunityCandidate, ProductOpportunityReviewer
from bdb_audit.projections.verified_matrix import VerifiedMatrixProjection
from bdb_audit.qualification.continuous import FrozenHoldout, evaluate_holdout
from bdb_audit.qualification.receipts import BenchmarkManifest
from bdb_audit.share import HistoricalTrendNormalizer, ShareBundleBuilder
from bdb_audit.successor import IncrementalAuditPlanner
from bdb_audit.tooling import CapabilityPolicy, ToolRunSpec, ToolRunner


def _runner() -> ToolRunner:
    return ToolRunner(CapabilityPolicy(allowed_executables=(sys.executable,), network_isolation="EXTERNAL_ENFORCED", external_network_guard=True, max_seconds=2))


def test_ru10_runner_pass_timeout_and_fail_closed_network():
    runner = _runner()
    ok = runner.run(ToolRunSpec((sys.executable, "-c", "print('ok')")))
    assert ok.qualified_success
    assert ok.stdout.strip() == "ok"
    blocked = ToolRunner(CapabilityPolicy((sys.executable,))).run(ToolRunSpec((sys.executable, "-c", "print('x')"), require_no_network=True))
    assert blocked.status == "BLOCKED"
    assert "NETWORK_ISOLATION_NOT_ENFORCED" in blocked.reason_codes
    timeout = runner.run(ToolRunSpec((sys.executable, "-c", "import time; time.sleep(1)"), timeout_seconds=0.05))
    assert timeout.status == "TIMEOUT"
    assert timeout.timed_out


def test_ru11_pass_requires_real_execution_and_independent_oracle():
    verifier = FunctionalVerifier(_runner())
    oracle = ExpectedOracle("o1", "CONTRACT", stdout_contains="READY")
    passed = verifier.verify(BehaviorCase("c1", "f1", (sys.executable, "-c", "print('READY')"), oracle))
    assert passed.status == "PASS" and passed.executed and passed.oracle_qualified
    mock = verifier.verify(BehaviorCase("c2", "f1", (sys.executable, "-c", "print('READY')"), oracle, mock_only=True))
    assert mock.status == "INSUFFICIENT"
    copied = verifier.verify(BehaviorCase("c3", "f1", (sys.executable, "-c", "print('READY')"), ExpectedOracle("o2", "IMPLEMENTATION", stdout_contains="READY")))
    assert copied.status == "INSUFFICIENT"
    matrix = verifier.matrix((FeatureRevision("f1", "1", "task", ("cli",)),), (passed, mock))
    assert matrix["features"][0]["status"] == "INSUFFICIENT"


def test_ru12b_projection_drills_to_evidence_and_blockers():
    assessment = FunctionalVerifier(_runner()).verify(BehaviorCase("case", "feature", (sys.executable, "-c", "print('wrong')"), ExpectedOracle("oracle", "USER_TASK", stdout_contains="expected")))
    projection = VerifiedMatrixProjection("source@abc", "cut123", (assessment,), ("contradiction-1",))
    row = projection.explain("case")
    assert row["source_identity"] == "source@abc"
    assert row["evidence_digest"]
    assert len(projection.blockers()) == 2


def test_ru13c_frozen_holdout_detects_false_negative():
    manifests = (BenchmarkManifest("b1", "t1", "a" * 40, "DEFECTIVE", split_membership="HOLDOUT"), BenchmarkManifest("b2", "t2", "b" * 40, "CLEAN", split_membership="HOLDOUT"))
    holdout = FrozenHoldout.freeze(manifests)
    result = evaluate_holdout(holdout, {"t1": "CLEAN", "t2": "CLEAN"})
    assert result.false_negatives == 1
    assert not result.qualified


def test_ru14_planner_never_hides_uncovered_required_obligation():
    plan = AdaptiveLanePlanner().plan((LaneCandidate("a", "static", ("O1",), 2.0, 1, "g1", required=True), LaneCandidate("b", "dynamic", ("O2",), 4.0, 2, "g2")), ("O1", "O2"), budget_units=1)
    assert plan.decision == "INSUFFICIENT_COVERAGE"
    assert plan.uncovered_required_obligations == ("O2",)


def test_ru15_skeptic_rejects_unsupported_opportunity():
    candidate = OpportunityCandidate("opp", "Better UX", "Too many steps", ("operator",), (), "faster", "MEDIUM", "LOW", "task completion time")
    review = ProductOpportunityReviewer.skeptic_review(candidate)
    assert review.status == "REJECTED_UNSUPPORTED"
    assert "EVIDENCE_MISSING" in review.reason_codes


def test_ru16_out_of_diff_dependency_invalidates_reuse():
    impact = IncrementalAuditPlanner.impact(("db",), {"db": ("service",), "service": ("api",)})
    assessment = IncrementalAuditPlanner.assess_reuse("ev1", ("api",), impact, source_same=True, policy_same=True, environment_same=True)
    assert not assessment.reusable
    assert "DEPENDENCY_IMPACTED" in assessment.reason_codes


def test_ru17_normalized_trend_and_bundle_verification():
    rows = HistoricalTrendNormalizer.compare(({"qualified": 8, "denominator": 10}, {"qualified": 90, "denominator": 100}))
    assert rows[0]["rate"] == 0.8
    assert rows[1]["rate"] == 0.9
    bundle = ShareBundleBuilder.build({"scope": "exact", "rows": rows}, b"test-key")
    assert ShareBundleBuilder.verify(bundle, b"test-key")
    tampered = type(bundle)(bundle.payload + b"x", bundle.payload_sha256, bundle.signature_hex)
    assert not ShareBundleBuilder.verify(tampered, b"test-key")
