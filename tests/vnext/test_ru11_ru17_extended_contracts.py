from __future__ import annotations

from dataclasses import replace

import pytest

from bdb_audit.features import BehaviorCase
from bdb_audit.features.adapters import BROWSER_ADAPTER, DATABASE_ADAPTER
from bdb_audit.qualification.continuous import FrozenHoldout
from bdb_audit.qualification.holdout import BlindTarget, run_blind_holdout
from bdb_audit.qualification.mutation import MutationManifest, score_mutations
from bdb_audit.qualification.receipts import BenchmarkManifest
from bdb_audit.share import TrendSnapshot, build_recipient_bundle, compare_trend, verify_recipient_bundle
from bdb_audit.strategy import AuditStrategyProfile, ExposureManifest, LaneProposal, StrategyDispatcher, propose_plan


def test_ru11_environment_dependent_adapters_fail_closed_until_capability_exists():
    behavior = BehaviorCase("f:browser", "f", "render page", ("req:1",))
    blocked = BROWSER_ADAPTER.assess(behavior, ())
    assert blocked.status == "BLOCKED"
    assert "CAPABILITY_UNAVAILABLE:BROWSER_SANDBOX" in blocked.reason_codes
    assert DATABASE_ADAPTER.assess(behavior, ("DISPOSABLE_DATABASE",)).status == "TESTABLE"


def test_ru13_blind_holdout_executor_never_receives_truth_label_and_mutations_have_denominator():
    holdout = FrozenHoldout.freeze((
        BenchmarkManifest("b1", "clean", "a" * 40, "CLEAN", split_membership="HOLDOUT"),
        BenchmarkManifest("b2", "bad", "b" * 40, "DEFECTIVE", split_membership="HOLDOUT"),
    ))
    seen: list[BlindTarget] = []

    def executor(target: BlindTarget) -> str:
        seen.append(target)
        return "CLEAN" if target.target_id == "clean" else "DEFECTIVE"

    result, observed = run_blind_holdout(holdout, executor)
    assert result.qualified
    assert observed == {"clean": "CLEAN", "bad": "DEFECTIVE"}
    assert not hasattr(seen[0], "expected_label")

    metrics = score_mutations((MutationManifest("m1", "bad", "b" * 40, "flip", "AUTH"),), {"m1": "SURVIVED"})
    assert metrics.total == 1 and metrics.survived == 1 and not metrics.qualified


def test_ru14_dispatch_honors_dag_and_positive_exposure_allowlist():
    profile = AuditStrategyProfile("p", ("BASE",), ("STATIC", "DYNAMIC"), ("SOURCE",), 10)
    exposure = ExposureManifest("src", "cut", ("source:a",), ("SOURCE",), ("secret:x",))
    lanes = (
        LaneProposal("l1", "BASE", "STATIC", ("scope",), ("o1",), "E5", 2, exposure, "g1", "s1", mandatory=True),
        LaneProposal("l2", "EXTRA", "DYNAMIC", ("scope2",), ("o2",), "REPORT", 2, exposure, "g2", "s2", predecessor_lane_ids=("l1",)),
    )
    plan = propose_plan(profile=profile, source_identity="src", history_cut_digest="cut", lanes=lanes)
    dispatcher = StrategyDispatcher(plan, profile)
    assert dispatcher.ready_lane_ids() == ("l1",)
    payload = dispatcher.dispatch("l1", {"source:a": {"value": 1}, "secret:x": {"value": 2}})
    assert payload["exposure"] == {"source:a": {"value": 1}}
    dispatcher.mark_completed("l1")
    assert dispatcher.ready_lane_ids() == ("l2",)


def test_ru17_trends_refuse_incomparable_scope_and_bundle_is_privacy_filtered():
    trend = compare_trend((TrendSnapshot("s1", "scope-A", "policy", 8, 10), TrendSnapshot("s2", "scope-B", "policy", 9, 10)))
    assert trend["status"] == "INCOMPARABLE_SCOPE"

    bundle = build_recipient_bundle(
        {"result": "PASS", "token": "must-not-leak", "nested": {"password": "no"}},
        signing_key=b"shared-secret",
        key_id="k1",
        source_identity="src@1",
        history_cut_digest="cut1",
    )
    assert b"must-not-leak" not in bundle.payload
    assert b"password" not in bundle.payload
    assert verify_recipient_bundle(bundle, signing_key=b"shared-secret", expected_key_id="k1")["status"] == "PASS"
    assert verify_recipient_bundle(replace(bundle, payload=bundle.payload + b"x"), signing_key=b"shared-secret")["status"] == "FAIL"
