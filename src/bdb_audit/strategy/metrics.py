"""Measured baseline-vs-adaptive strategy benchmark for RU14.

The benchmark consumes actual run summaries. It never infers improved audit
quality from a larger lane count: benefit requires more *unique qualified*
root causes on the same frozen target corpus, with explicit measured cost.
Adaptive execution is baseline-preserving by default: a previously qualified
root cause may not disappear from the comparison and still count as benefit.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence


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

    def __post_init__(self) -> None:
        if not self.run_id or not self.strategy_profile_id or not self.source_identity:
            raise ValueError("strategy run identity required")
        if not self.frozen_corpus_digest:
            raise ValueError("frozen corpus digest required")
        if self.cost_units < 0:
            raise ValueError("cost_units must be non-negative")
        if self.evaluated_cases < 0:
            raise ValueError("evaluated_cases must be non-negative")
        if len(set(self.qualified_root_cause_ids)) != len(self.qualified_root_cause_ids):
            raise ValueError("qualified root causes must be unique")
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

    @property
    def benefit_demonstrated(self) -> bool:
        return self.status == "BENEFIT_DEMONSTRATED"


def compare_adaptive_to_baseline(
    baseline: StrategyRunMetrics,
    adaptive: StrategyRunMetrics,
    *,
    required_baseline_root_causes: Sequence[str] = (),
) -> StrategyBenchmarkResult:
    reasons: list[str] = []
    if baseline.source_identity != adaptive.source_identity:
        reasons.append("SOURCE_IDENTITY_MISMATCH")
    if baseline.frozen_corpus_digest != adaptive.frozen_corpus_digest:
        reasons.append("CORPUS_MISMATCH")
    if baseline.evaluated_cases <= 0 or adaptive.evaluated_cases <= 0:
        reasons.append("ZERO_EVALUATED_CASES")
    elif baseline.evaluated_cases != adaptive.evaluated_cases:
        reasons.append("EVALUATED_CASE_COUNT_MISMATCH")
    if not baseline.execution_receipt_ids or not adaptive.execution_receipt_ids:
        reasons.append("ACTUAL_EXECUTION_RECEIPTS_REQUIRED")

    baseline_roots = set(baseline.qualified_root_cause_ids)
    adaptive_roots = set(adaptive.qualified_root_cause_ids)
    required = baseline_roots.union(required_baseline_root_causes)
    if not required.issubset(adaptive_roots):
        reasons.append("BASELINE_ASSURANCE_WEAKENED")

    baseline_count = len(baseline_roots)
    adaptive_count = len(adaptive_roots)
    incremental_count = len(adaptive_roots - baseline_roots)
    incremental_cost = adaptive.cost_units - baseline.cost_units
    marginal = None
    if incremental_cost > 0:
        marginal = incremental_count / incremental_cost

    if any(code in reasons for code in (
        "SOURCE_IDENTITY_MISMATCH", "CORPUS_MISMATCH", "ZERO_EVALUATED_CASES",
        "EVALUATED_CASE_COUNT_MISMATCH", "ACTUAL_EXECUTION_RECEIPTS_REQUIRED",
    )):
        status = "INCOMPARABLE_OR_INSUFFICIENT"
    elif "BASELINE_ASSURANCE_WEAKENED" in reasons:
        status = "REJECTED_ASSURANCE_WEAKENING"
    elif incremental_count > 0:
        status = "BENEFIT_DEMONSTRATED"
    else:
        status = "NO_MEASURED_UNIQUE_YIELD_GAIN"
        reasons.append("NO_ADDITIONAL_QUALIFIED_ROOT_CAUSE")

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
    )


__all__ = ["StrategyRunMetrics", "StrategyBenchmarkResult", "compare_adaptive_to_baseline"]
