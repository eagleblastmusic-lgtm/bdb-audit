from __future__ import annotations

from bdb_audit.strategy.metrics import StrategyRunMetrics, compare_adaptive_to_baseline


def _run(run_id: str, profile: str, roots: tuple[str, ...], cost: float, receipts: tuple[str, ...] = ("receipt",), evaluated_cases: int = 10) -> StrategyRunMetrics:
    return StrategyRunMetrics(
        run_id=run_id,
        strategy_profile_id=profile,
        source_identity="source@abc",
        frozen_corpus_digest="c" * 64,
        qualified_root_cause_ids=roots,
        execution_receipt_ids=receipts,
        cost_units=cost,
        evaluated_cases=evaluated_cases,
    )


def test_ru14_benchmark_reports_unique_yield_and_measured_marginal_cost():
    baseline = _run("baseline", "fixed", ("rc1",), 5)
    adaptive = _run("adaptive", "adaptive", ("rc1", "rc2", "rc3"), 9)
    result = compare_adaptive_to_baseline(baseline, adaptive, required_baseline_root_causes=("rc1",))
    assert result.status == "BENEFIT_DEMONSTRATED"
    assert result.incremental_unique_qualified_root_causes == 2
    assert result.incremental_cost_units == 4
    assert result.marginal_unique_root_causes_per_cost_unit == 0.5


def test_ru14_benchmark_cannot_claim_benefit_without_actual_receipts():
    baseline = _run("baseline", "fixed", ("rc1",), 5, receipts=())
    adaptive = _run("adaptive", "adaptive", ("rc1", "rc2"), 7)
    result = compare_adaptive_to_baseline(baseline, adaptive)
    assert result.status == "INCOMPARABLE_OR_INSUFFICIENT"
    assert "ACTUAL_EXECUTION_RECEIPTS_REQUIRED" in result.reason_codes


def test_ru14_benchmark_rejects_baseline_loss_by_default():
    baseline = _run("baseline", "fixed", ("rc1", "rc2"), 5)
    adaptive = _run("adaptive", "adaptive", ("rc2", "rc3"), 8)
    result = compare_adaptive_to_baseline(baseline, adaptive)
    assert result.status == "REJECTED_ASSURANCE_WEAKENING"
    assert "BASELINE_ASSURANCE_WEAKENED" in result.reason_codes


def test_ru14_benchmark_refuses_cross_corpus_comparison():
    baseline = _run("baseline", "fixed", ("rc1",), 5)
    adaptive = StrategyRunMetrics(
        "adaptive", "adaptive", "source@abc", "d" * 64, ("rc1", "rc2"), ("r2",), 7, 10
    )
    result = compare_adaptive_to_baseline(baseline, adaptive)
    assert result.status == "INCOMPARABLE_OR_INSUFFICIENT"
    assert "CORPUS_MISMATCH" in result.reason_codes


def test_ru14_benchmark_refuses_partial_corpus_comparison():
    baseline = _run("baseline", "fixed", ("rc1",), 5, evaluated_cases=10)
    adaptive = _run("adaptive", "adaptive", ("rc1", "rc2"), 7, evaluated_cases=9)
    result = compare_adaptive_to_baseline(baseline, adaptive)
    assert result.status == "INCOMPARABLE_OR_INSUFFICIENT"
    assert "EVALUATED_CASE_COUNT_MISMATCH" in result.reason_codes
