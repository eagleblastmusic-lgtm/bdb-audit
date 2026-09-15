from __future__ import annotations

from dataclasses import replace

from bdb_audit.qualification.receipts import ActualRunReceipt
from bdb_audit.strategy.metrics import StrategyRunMetrics, compare_adaptive_to_baseline


SOURCE = "source@abc"
CORPUS = "c" * 64


def _receipt(
    run_id: str,
    profile: str,
    roots: tuple[str, ...],
    cost: float,
    *,
    receipt_id: str | None = None,
    source: str = SOURCE,
    corpus: str = CORPUS,
    evaluated_cases: int = 10,
    details_override: dict[str, object] | None = None,
) -> ActualRunReceipt:
    details: dict[str, object] = {
        "strategy_run_id": run_id,
        "strategy_profile_id": profile,
        "source_identity": source,
        "frozen_corpus_digest": corpus,
        "evaluated_cases": evaluated_cases,
        "cost_units": cost,
        "qualified_root_cause_ids": list(roots),
    }
    if details_override:
        details.update(details_override)
    return ActualRunReceipt(
        receipt_id=receipt_id or f"receipt-{run_id}",
        benchmark_id=f"strategy:{profile}",
        target_id=run_id,
        checker_id=f"strategy-runner:{profile}",
        execution_timestamp="2026-09-15T00:00:00Z",
        exit_code=0,
        status="PASS",
        raw_output_digest="a" * 64,
        evaluated_cases_count=1,
        passed_cases_count=1,
        failed_cases_count=0,
        execution_duration_ms=5,
        details=details,
    )


def _run(
    run_id: str,
    profile: str,
    roots: tuple[str, ...],
    cost: float,
    *,
    source: str = SOURCE,
    corpus: str = CORPUS,
    evaluated_cases: int = 10,
    receipts: tuple[ActualRunReceipt, ...] | None = None,
    execution_receipt_ids: tuple[str, ...] | None = None,
) -> StrategyRunMetrics:
    actual = receipts
    if actual is None:
        actual = (_receipt(run_id, profile, roots, cost, source=source, corpus=corpus, evaluated_cases=evaluated_cases),)
    ids = execution_receipt_ids
    if ids is None:
        ids = tuple(receipt.receipt_id for receipt in actual)
    return StrategyRunMetrics(
        run_id=run_id,
        strategy_profile_id=profile,
        source_identity=source,
        frozen_corpus_digest=corpus,
        qualified_root_cause_ids=roots,
        execution_receipt_ids=ids,
        cost_units=cost,
        evaluated_cases=evaluated_cases,
        actual_receipts=actual,
    )


def test_ru14_benchmark_reports_unique_yield_and_measured_marginal_cost():
    baseline = _run("baseline", "fixed", ("rc1",), 5)
    adaptive = _run("adaptive", "adaptive", ("rc1", "rc2", "rc3"), 9)
    result = compare_adaptive_to_baseline(baseline, adaptive, required_baseline_root_causes=("rc1",))
    assert result.status == "BENEFIT_DEMONSTRATED"
    assert result.incremental_unique_qualified_root_causes == 2
    assert result.incremental_cost_units == 4
    assert result.marginal_unique_root_causes_per_cost_unit == 0.5
    assert len(result.verified_execution_receipt_digests) == 2


def test_ru14_benchmark_cannot_claim_benefit_without_actual_receipts():
    baseline = _run(
        "baseline",
        "fixed",
        ("rc1",),
        5,
        receipts=(),
        execution_receipt_ids=("receipt-baseline",),
    )
    adaptive = _run("adaptive", "adaptive", ("rc1", "rc2"), 7)
    result = compare_adaptive_to_baseline(baseline, adaptive)
    assert result.status == "INCOMPARABLE_OR_INSUFFICIENT"
    assert "BASELINE_ACTUAL_EXECUTION_RECEIPTS_REQUIRED" in result.reason_codes
    assert result.verified_execution_receipt_digests == ()


def test_ru14_benchmark_rejects_baseline_loss_by_default():
    baseline = _run("baseline", "fixed", ("rc1", "rc2"), 5)
    adaptive = _run("adaptive", "adaptive", ("rc2", "rc3"), 8)
    result = compare_adaptive_to_baseline(baseline, adaptive)
    assert result.status == "REJECTED_ASSURANCE_WEAKENING"
    assert "BASELINE_ASSURANCE_WEAKENED" in result.reason_codes


def test_ru14_benchmark_refuses_cross_corpus_comparison():
    baseline = _run("baseline", "fixed", ("rc1",), 5)
    adaptive = _run("adaptive", "adaptive", ("rc1", "rc2"), 7, corpus="d" * 64)
    result = compare_adaptive_to_baseline(baseline, adaptive)
    assert result.status == "INCOMPARABLE_OR_INSUFFICIENT"
    assert "CORPUS_MISMATCH" in result.reason_codes


def test_ru14_benchmark_refuses_partial_corpus_comparison():
    baseline = _run("baseline", "fixed", ("rc1",), 5, evaluated_cases=10)
    adaptive = _run("adaptive", "adaptive", ("rc1", "rc2"), 7, evaluated_cases=9)
    result = compare_adaptive_to_baseline(baseline, adaptive)
    assert result.status == "INCOMPARABLE_OR_INSUFFICIENT"
    assert "EVALUATED_CASE_COUNT_MISMATCH" in result.reason_codes


def test_ru14_receipt_id_list_must_match_actual_receipts():
    baseline = _run(
        "baseline",
        "fixed",
        ("rc1",),
        5,
        execution_receipt_ids=("declared-but-not-executed",),
    )
    adaptive = _run("adaptive", "adaptive", ("rc1", "rc2"), 7)
    result = compare_adaptive_to_baseline(baseline, adaptive)
    assert result.status == "INCOMPARABLE_OR_INSUFFICIENT"
    assert "BASELINE_EXECUTION_RECEIPT_ID_SET_MISMATCH" in result.reason_codes


def test_ru14_measured_cost_must_reconcile_to_receipts():
    bad_receipt = _receipt("adaptive", "adaptive", ("rc1", "rc2"), 99)
    baseline = _run("baseline", "fixed", ("rc1",), 5)
    adaptive = _run("adaptive", "adaptive", ("rc1", "rc2"), 7, receipts=(bad_receipt,))
    result = compare_adaptive_to_baseline(baseline, adaptive)
    assert result.status == "INCOMPARABLE_OR_INSUFFICIENT"
    assert "ADAPTIVE_MEASURED_COST_MISMATCH" in result.reason_codes


def test_ru14_root_cause_yield_must_be_evidenced_by_receipts():
    receipt = _receipt(
        "adaptive",
        "adaptive",
        ("rc1", "rc2"),
        7,
        details_override={"qualified_root_cause_ids": ["rc1"]},
    )
    baseline = _run("baseline", "fixed", ("rc1",), 5)
    adaptive = _run("adaptive", "adaptive", ("rc1", "rc2"), 7, receipts=(receipt,))
    result = compare_adaptive_to_baseline(baseline, adaptive)
    assert result.status == "INCOMPARABLE_OR_INSUFFICIENT"
    assert "ADAPTIVE_QUALIFIED_ROOT_CAUSE_EVIDENCE_MISMATCH" in result.reason_codes


def test_ru14_receipt_source_and_corpus_binding_are_fail_closed():
    receipt = _receipt(
        "adaptive",
        "adaptive",
        ("rc1", "rc2"),
        7,
        details_override={"source_identity": "stale-source", "frozen_corpus_digest": "d" * 64},
    )
    baseline = _run("baseline", "fixed", ("rc1",), 5)
    adaptive = _run("adaptive", "adaptive", ("rc1", "rc2"), 7, receipts=(receipt,))
    result = compare_adaptive_to_baseline(baseline, adaptive)
    assert result.status == "INCOMPARABLE_OR_INSUFFICIENT"
    assert any(code.startswith("ADAPTIVE_RECEIPT_SOURCE_MISMATCH") for code in result.reason_codes)
    assert any(code.startswith("ADAPTIVE_RECEIPT_CORPUS_MISMATCH") for code in result.reason_codes)


def test_ru14_same_receipt_identity_cannot_prove_both_runs():
    baseline_receipt = _receipt("baseline", "fixed", ("rc1",), 5, receipt_id="shared")
    adaptive_receipt = _receipt("adaptive", "adaptive", ("rc1", "rc2"), 7, receipt_id="shared")
    baseline = _run("baseline", "fixed", ("rc1",), 5, receipts=(baseline_receipt,))
    adaptive = _run("adaptive", "adaptive", ("rc1", "rc2"), 7, receipts=(adaptive_receipt,))
    result = compare_adaptive_to_baseline(baseline, adaptive)
    assert result.status == "INCOMPARABLE_OR_INSUFFICIENT"
    assert "EXECUTION_RECEIPT_REUSED_ACROSS_RUNS:shared" in result.reason_codes


def test_ru14_same_run_or_profile_is_not_an_adaptive_comparison():
    baseline = _run("baseline", "fixed", ("rc1",), 5)
    adaptive_same_profile = _run("adaptive", "fixed", ("rc1", "rc2"), 7)
    result = compare_adaptive_to_baseline(baseline, adaptive_same_profile)
    assert result.status == "INCOMPARABLE_OR_INSUFFICIENT"
    assert "STRATEGY_PROFILE_NOT_DISTINCT" in result.reason_codes

    adaptive_same_run = _run("baseline", "adaptive", ("rc1", "rc2"), 7)
    result = compare_adaptive_to_baseline(baseline, adaptive_same_run)
    assert result.status == "INCOMPARABLE_OR_INSUFFICIENT"
    assert "RUN_ID_NOT_DISTINCT" in result.reason_codes


def test_ru14_nonqualified_receipt_cannot_support_benefit():
    receipt = _receipt("adaptive", "adaptive", ("rc1", "rc2"), 7)
    failed = replace(receipt, status="FAIL", exit_code=1, passed_cases_count=0, failed_cases_count=1)
    baseline = _run("baseline", "fixed", ("rc1",), 5)
    adaptive = _run("adaptive", "adaptive", ("rc1", "rc2"), 7, receipts=(failed,))
    result = compare_adaptive_to_baseline(baseline, adaptive)
    assert result.status == "INCOMPARABLE_OR_INSUFFICIENT"
    assert any(code.startswith("ADAPTIVE_EXECUTION_RECEIPT_NOT_QUALIFIED") for code in result.reason_codes)
