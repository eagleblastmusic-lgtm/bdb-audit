"""Measured, evidence-bound baseline-vs-adaptive strategy benchmark for RU14.

Benefit may be claimed only when baseline and adaptive executions are comparable
on the same frozen corpus and their measured cost/root-cause summaries are
reconciled against actual execution receipts.  Receipt identifiers alone never
constitute execution evidence.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Sequence

from ..qualification.receipts import ActualRunReceipt


def _is_sha256(value: str) -> bool:
    if len(value) != 64:
        return False
    try:
        int(value, 16)
    except ValueError:
        return False
    return True


def _detail_string_tuple(value: object) -> tuple[str, ...] | None:
    if not isinstance(value, (list, tuple)):
        return None
    values: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            return None
        values.append(item)
    return tuple(values)


@dataclass(frozen=True)
class StrategyRunMetrics:
    run_id: str
    strategy_profile_id: str
    source_identity: str
    frozen_corpus_digest: str
    qualified_root_cause_ids: tuple[str, ...]
    execution_receipt_ids: tuple[str, ...]
    cost_units: float
    evaluated_cases: int
    actual_receipts: tuple[ActualRunReceipt, ...] = ()

    def __post_init__(self) -> None:
        if not self.run_id or not self.strategy_profile_id or not self.source_identity:
            raise ValueError("strategy run identity required")
        if not _is_sha256(self.frozen_corpus_digest):
            raise ValueError("frozen_corpus_digest must be a SHA-256 hex digest")
        if not math.isfinite(self.cost_units) or self.cost_units < 0:
            raise ValueError("cost_units must be finite and non-negative")
        if self.evaluated_cases < 0:
            raise ValueError("evaluated_cases must be non-negative")
        if any(not root.strip() for root in self.qualified_root_cause_ids):
            raise ValueError("qualified root cause ids must be non-empty")
        if len(set(self.qualified_root_cause_ids)) != len(self.qualified_root_cause_ids):
            raise ValueError("qualified root causes must be unique")
        if any(not receipt_id.strip() for receipt_id in self.execution_receipt_ids):
            raise ValueError("execution receipt ids must be non-empty")
        if len(set(self.execution_receipt_ids)) != len(self.execution_receipt_ids):
            raise ValueError("execution receipts must be unique")


@dataclass(frozen=True)
class StrategyBenchmarkResult:
    status: str
    baseline_unique_qualified_root_causes: int
    adaptive_unique_qualified_root_causes: int
    incremental_unique_qualified_root_causes: int
    baseline_cost_units: float
    adaptive_cost_units: float
    incremental_cost_units: float
    marginal_unique_root_causes_per_cost_unit: float | None
    reason_codes: tuple[str, ...]
    verified_execution_receipt_digests: tuple[str, ...] = ()

    @property
    def benefit_demonstrated(self) -> bool:
        return self.status == "BENEFIT_DEMONSTRATED"


def _receipt_failures(
    run: StrategyRunMetrics,
    receipt: ActualRunReceipt,
    role: str,
) -> tuple[list[str], float | None, tuple[str, ...] | None]:
    prefix = role.upper()
    receipt_id = receipt.receipt_id
    reasons: list[str] = []

    if receipt.target_id != run.run_id:
        reasons.append(f"{prefix}_RECEIPT_RUN_TARGET_MISMATCH:{receipt_id}")
    if receipt.details.get("strategy_run_id") != run.run_id:
        reasons.append(f"{prefix}_RECEIPT_RUN_BINDING_MISMATCH:{receipt_id}")
    if receipt.details.get("strategy_profile_id") != run.strategy_profile_id:
        reasons.append(f"{prefix}_RECEIPT_PROFILE_MISMATCH:{receipt_id}")
    if receipt.details.get("source_identity") != run.source_identity:
        reasons.append(f"{prefix}_RECEIPT_SOURCE_MISMATCH:{receipt_id}")
    if receipt.details.get("frozen_corpus_digest") != run.frozen_corpus_digest:
        reasons.append(f"{prefix}_RECEIPT_CORPUS_MISMATCH:{receipt_id}")

    measured_cases = receipt.details.get("evaluated_cases")
    if isinstance(measured_cases, bool) or not isinstance(measured_cases, int):
        reasons.append(f"{prefix}_RECEIPT_CASE_DENOMINATOR_MISSING:{receipt_id}")
    elif measured_cases != run.evaluated_cases:
        reasons.append(f"{prefix}_RECEIPT_CASE_DENOMINATOR_MISMATCH:{receipt_id}")

    if (
        receipt.status != "PASS"
        or receipt.exit_code != 0
        or receipt.evaluated_cases_count <= 0
        or receipt.passed_cases_count != receipt.evaluated_cases_count
        or receipt.failed_cases_count != 0
        or receipt.unsupported_cases_count != 0
        or receipt.unknown_cases_count != 0
    ):
        reasons.append(f"{prefix}_EXECUTION_RECEIPT_NOT_QUALIFIED:{receipt_id}")
    if not _is_sha256(receipt.raw_output_digest):
        reasons.append(f"{prefix}_RECEIPT_RAW_DIGEST_INVALID:{receipt_id}")
    if not receipt.execution_timestamp.strip():
        reasons.append(f"{prefix}_RECEIPT_TIMESTAMP_MISSING:{receipt_id}")
    if receipt.execution_duration_ms <= 0:
        reasons.append(f"{prefix}_RECEIPT_DURATION_MISSING:{receipt_id}")

    measured_cost_raw = receipt.details.get("cost_units")
    measured_cost: float | None = None
    if isinstance(measured_cost_raw, bool) or not isinstance(measured_cost_raw, (int, float)):
        reasons.append(f"{prefix}_RECEIPT_COST_MISSING:{receipt_id}")
    else:
        measured_cost = float(measured_cost_raw)
        if not math.isfinite(measured_cost) or measured_cost < 0:
            reasons.append(f"{prefix}_RECEIPT_COST_INVALID:{receipt_id}")
            measured_cost = None

    evidence_roots = _detail_string_tuple(receipt.details.get("qualified_root_cause_ids"))
    if evidence_roots is None:
        reasons.append(f"{prefix}_RECEIPT_ROOT_CAUSE_EVIDENCE_MISSING:{receipt_id}")

    return reasons, measured_cost, evidence_roots


def _validate_execution_evidence(
    run: StrategyRunMetrics,
    role: str,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    prefix = role.upper()
    reasons: list[str] = []
    receipts = run.actual_receipts
    if not receipts:
        return (f"{prefix}_ACTUAL_EXECUTION_RECEIPTS_REQUIRED",), ()

    actual_ids = tuple(receipt.receipt_id for receipt in receipts)
    if len(set(actual_ids)) != len(actual_ids):
        reasons.append(f"{prefix}_ACTUAL_RECEIPT_ID_DUPLICATE")
    if set(actual_ids) != set(run.execution_receipt_ids) or len(actual_ids) != len(run.execution_receipt_ids):
        reasons.append(f"{prefix}_EXECUTION_RECEIPT_ID_SET_MISMATCH")

    measured_cost_total = 0.0
    all_costs_present = True
    evidenced_roots: set[str] = set()
    all_roots_present = True
    for receipt in receipts:
        receipt_reasons, measured_cost, receipt_roots = _receipt_failures(run, receipt, role)
        reasons.extend(receipt_reasons)
        if measured_cost is None:
            all_costs_present = False
        else:
            measured_cost_total += measured_cost
        if receipt_roots is None:
            all_roots_present = False
        else:
            evidenced_roots.update(receipt_roots)

    if all_costs_present and not math.isclose(measured_cost_total, run.cost_units, rel_tol=0.0, abs_tol=1e-9):
        reasons.append(f"{prefix}_MEASURED_COST_MISMATCH")
    if all_roots_present and evidenced_roots != set(run.qualified_root_cause_ids):
        reasons.append(f"{prefix}_QUALIFIED_ROOT_CAUSE_EVIDENCE_MISMATCH")

    verified_digests: tuple[str, ...] = ()
    if not reasons:
        verified_digests = tuple(sorted(receipt.receipt_digest() for receipt in receipts))
    return tuple(sorted(set(reasons))), verified_digests


def compare_adaptive_to_baseline(
    baseline: StrategyRunMetrics,
    adaptive: StrategyRunMetrics,
    *,
    required_baseline_root_causes: Sequence[str] = (),
) -> StrategyBenchmarkResult:
    comparison_failures: list[str] = []
    if baseline.run_id == adaptive.run_id:
        comparison_failures.append("RUN_ID_NOT_DISTINCT")
    if baseline.strategy_profile_id == adaptive.strategy_profile_id:
        comparison_failures.append("STRATEGY_PROFILE_NOT_DISTINCT")
    if baseline.source_identity != adaptive.source_identity:
        comparison_failures.append("SOURCE_IDENTITY_MISMATCH")
    if baseline.frozen_corpus_digest != adaptive.frozen_corpus_digest:
        comparison_failures.append("CORPUS_MISMATCH")
    if baseline.evaluated_cases <= 0 or adaptive.evaluated_cases <= 0:
        comparison_failures.append("ZERO_EVALUATED_CASES")
    elif baseline.evaluated_cases != adaptive.evaluated_cases:
        comparison_failures.append("EVALUATED_CASE_COUNT_MISMATCH")

    baseline_evidence_failures, baseline_receipt_digests = _validate_execution_evidence(baseline, "baseline")
    adaptive_evidence_failures, adaptive_receipt_digests = _validate_execution_evidence(adaptive, "adaptive")
    comparison_failures.extend(baseline_evidence_failures)
    comparison_failures.extend(adaptive_evidence_failures)

    baseline_receipt_ids = {receipt.receipt_id for receipt in baseline.actual_receipts}
    adaptive_receipt_ids = {receipt.receipt_id for receipt in adaptive.actual_receipts}
    reused_ids = sorted(baseline_receipt_ids.intersection(adaptive_receipt_ids))
    for receipt_id in reused_ids:
        comparison_failures.append(f"EXECUTION_RECEIPT_REUSED_ACROSS_RUNS:{receipt_id}")

    baseline_roots = set(baseline.qualified_root_cause_ids)
    adaptive_roots = set(adaptive.qualified_root_cause_ids)
    required = baseline_roots.union(required_baseline_root_causes)
    assurance_weakened = not required.issubset(adaptive_roots)

    baseline_count = len(baseline_roots)
    adaptive_count = len(adaptive_roots)
    incremental_count = len(adaptive_roots - baseline_roots)
    incremental_cost = adaptive.cost_units - baseline.cost_units
    marginal = None
    if incremental_cost > 0:
        marginal = incremental_count / incremental_cost

    reasons = list(comparison_failures)
    if comparison_failures:
        status = "INCOMPARABLE_OR_INSUFFICIENT"
    elif assurance_weakened:
        status = "REJECTED_ASSURANCE_WEAKENING"
        reasons.append("BASELINE_ASSURANCE_WEAKENED")
    elif incremental_count > 0:
        status = "BENEFIT_DEMONSTRATED"
    else:
        status = "NO_MEASURED_UNIQUE_YIELD_GAIN"
        reasons.append("NO_ADDITIONAL_QUALIFIED_ROOT_CAUSE")

    verified_receipt_digests: tuple[str, ...] = ()
    if status in {"BENEFIT_DEMONSTRATED", "NO_MEASURED_UNIQUE_YIELD_GAIN", "REJECTED_ASSURANCE_WEAKENING"}:
        verified_receipt_digests = tuple(sorted(baseline_receipt_digests + adaptive_receipt_digests))

    return StrategyBenchmarkResult(
        status=status,
        baseline_unique_qualified_root_causes=baseline_count,
        adaptive_unique_qualified_root_causes=adaptive_count,
        incremental_unique_qualified_root_causes=incremental_count,
        baseline_cost_units=baseline.cost_units,
        adaptive_cost_units=adaptive.cost_units,
        incremental_cost_units=incremental_cost,
        marginal_unique_root_causes_per_cost_unit=marginal,
        reason_codes=tuple(sorted(set(reasons))),
        verified_execution_receipt_digests=verified_receipt_digests,
    )


__all__ = ["StrategyRunMetrics", "StrategyBenchmarkResult", "compare_adaptive_to_baseline"]
