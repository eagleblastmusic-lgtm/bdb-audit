"""RU13-C continuous methodology qualification helpers.

``evaluate_holdout`` remains a compatibility/raw scorer for a frozen truth set.
It is not the release-methodology authority.  ``evaluate_continuous_holdout``
is the strict gate: it binds the expected frozen-holdout commitment, requires
one executed ``BenchmarkRun`` per declared target, validates each execution
receipt, exact-matches every truth label (including non-binary outcomes), and
requires an exact executed anti-bypass denominator.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import Mapping, Sequence

from .corpus import BenchmarkRun
from .methodology_metrics import MethodologyMetrics
from .receipts import ActualRunReceipt, BenchmarkManifest
from .runner import MethodologyQualifier


@dataclass(frozen=True)
class FrozenHoldout:
    manifests: tuple[BenchmarkManifest, ...]
    commitment_sha256: str

    @classmethod
    def freeze(cls, manifests: Sequence[BenchmarkManifest]) -> "FrozenHoldout":
        holdout = tuple(
            sorted(
                (m for m in manifests if m.split_membership == "HOLDOUT"),
                key=lambda m: m.benchmark_id,
            )
        )
        material = "\n".join(m.manifest_digest() for m in holdout).encode("ascii")
        return cls(holdout, hashlib.sha256(material).hexdigest())


@dataclass(frozen=True)
class ContinuousQualificationResult:
    commitment_sha256: str
    total: int
    evaluated: int
    false_negatives: int
    false_positives: int
    unknown: int
    qualified: bool
    anti_bypass_total: int = 0
    anti_bypass_passed: int = 0
    anti_bypass_failures: tuple[str, ...] = ()
    verified_run_receipt_digests: tuple[str, ...] = ()
    qualification_failures: tuple[str, ...] = ()


def _is_sha256(value: str) -> bool:
    if len(value) != 64:
        return False
    try:
        int(value, 16)
    except ValueError:
        return False
    return True


def _score(
    holdout: FrozenHoldout,
    observed: Mapping[str, str],
) -> tuple[MethodologyMetrics, bool]:
    metrics = MethodologyQualifier.score_benchmark_corpus(holdout.manifests, observed)
    qualified = (
        metrics.total_targets > 0
        and metrics.evaluated_targets == metrics.total_targets
        and metrics.false_negatives == 0
        and metrics.false_positives == 0
        and metrics.unknown_cases == 0
    )
    return metrics, qualified


def evaluate_holdout(
    holdout: FrozenHoldout,
    observed: Mapping[str, str],
) -> ContinuousQualificationResult:
    """Compatibility/raw scorer; callers must not treat it as strict qualification."""
    metrics, qualified = _score(holdout, observed)
    return ContinuousQualificationResult(
        holdout.commitment_sha256,
        metrics.total_targets,
        metrics.evaluated_targets,
        metrics.false_negatives,
        metrics.false_positives,
        metrics.unknown_cases,
        qualified,
    )


def _receipt_shape_failures(
    target_id: str,
    expected_label: str,
    receipt: ActualRunReceipt,
) -> list[str]:
    reasons: list[str] = []
    if not _is_sha256(receipt.raw_output_digest):
        reasons.append(f"HOLDOUT_RECEIPT_RAW_DIGEST_INVALID:{target_id}")
    if not receipt.execution_timestamp:
        reasons.append(f"HOLDOUT_RECEIPT_TIMESTAMP_MISSING:{target_id}")
    if receipt.execution_duration_ms <= 0:
        reasons.append(f"HOLDOUT_RECEIPT_DURATION_MISSING:{target_id}")
    if receipt.evaluated_cases_count != 1:
        reasons.append(f"HOLDOUT_RECEIPT_DENOMINATOR_INVALID:{target_id}")

    if expected_label in {"CLEAN", "DEFECTIVE"}:
        if (
            receipt.status != "PASS"
            or receipt.exit_code != 0
            or receipt.passed_cases_count != 1
            or receipt.failed_cases_count != 0
            or receipt.unsupported_cases_count != 0
            or receipt.unknown_cases_count != 0
        ):
            reasons.append(f"HOLDOUT_EXECUTION_NOT_QUALIFIED:{target_id}")
    elif expected_label == "BLOCKED":
        if (
            receipt.status != "BLOCKED"
            or receipt.passed_cases_count != 0
            or receipt.failed_cases_count != 0
            or receipt.unsupported_cases_count != 0
            or receipt.unknown_cases_count != 0
        ):
            reasons.append(f"HOLDOUT_BLOCKED_RECEIPT_INVALID:{target_id}")
    elif expected_label == "UNSUPPORTED":
        if (
            receipt.status != "INSUFFICIENT"
            or receipt.passed_cases_count != 0
            or receipt.failed_cases_count != 0
            or receipt.unsupported_cases_count != 1
            or receipt.unknown_cases_count != 0
        ):
            reasons.append(f"HOLDOUT_UNSUPPORTED_RECEIPT_INVALID:{target_id}")
    elif expected_label == "AMBIGUOUS":
        if (
            receipt.status not in {"INSUFFICIENT", "UNKNOWN"}
            or receipt.passed_cases_count != 0
            or receipt.failed_cases_count != 0
            or receipt.unsupported_cases_count != 0
            or receipt.unknown_cases_count != 1
        ):
            reasons.append(f"HOLDOUT_AMBIGUOUS_RECEIPT_INVALID:{target_id}")
    return reasons


def _validate_holdout_runs(
    holdout: FrozenHoldout,
    runs: Sequence[BenchmarkRun],
) -> tuple[dict[str, str], tuple[str, ...]]:
    reasons: list[str] = []
    observed: dict[str, str] = {}

    benchmark_ids = [manifest.benchmark_id for manifest in holdout.manifests]
    target_ids = [manifest.target_id for manifest in holdout.manifests]
    for benchmark_id in sorted(set(benchmark_ids)):
        if benchmark_ids.count(benchmark_id) > 1:
            reasons.append(f"HOLDOUT_BENCHMARK_ID_DUPLICATE:{benchmark_id}")
    for target_id in sorted(set(target_ids)):
        if target_ids.count(target_id) > 1:
            reasons.append(f"HOLDOUT_TARGET_ID_DUPLICATE:{target_id}")

    expected_by_target = {manifest.target_id: manifest for manifest in holdout.manifests}
    supplied_targets: list[str] = []
    supplied_receipt_ids: list[str] = []

    for run in runs:
        target_id = run.manifest.target_id
        supplied_targets.append(target_id)
        supplied_receipt_ids.append(run.receipt.receipt_id)
        expected = expected_by_target.get(target_id)
        if expected is None:
            reasons.append(f"HOLDOUT_RUN_UNDECLARED:{target_id}")
            continue
        if supplied_targets.count(target_id) > 1:
            reasons.append(f"HOLDOUT_RUN_DUPLICATE:{target_id}")
            continue
        if run.manifest.manifest_digest() != expected.manifest_digest():
            reasons.append(f"HOLDOUT_MANIFEST_MISMATCH:{target_id}")
        receipt = run.receipt
        if receipt.benchmark_id != expected.benchmark_id:
            reasons.append(f"HOLDOUT_RECEIPT_BENCHMARK_MISMATCH:{target_id}")
        if receipt.target_id != target_id:
            reasons.append(f"HOLDOUT_RECEIPT_TARGET_MISMATCH:{target_id}")
        receipt_observed = receipt.details.get("observed_label")
        if receipt_observed != run.observed_label:
            reasons.append(f"HOLDOUT_OBSERVED_RECEIPT_MISMATCH:{target_id}")
        if expected.metadata.get("target_identity_profile") == "SHA256_SOURCE_BYTES":
            if receipt.details.get("target_source_sha256") != expected.target_sha:
                reasons.append(f"HOLDOUT_SOURCE_DIGEST_MISMATCH:{target_id}")
        if run.observed_label != expected.expected_label:
            reasons.append(f"HOLDOUT_LABEL_MISMATCH:{target_id}")
        reasons.extend(_receipt_shape_failures(target_id, expected.expected_label, receipt))
        observed[target_id] = run.observed_label

    for receipt_id in sorted(set(supplied_receipt_ids)):
        if supplied_receipt_ids.count(receipt_id) > 1:
            reasons.append(f"HOLDOUT_RECEIPT_ID_DUPLICATE:{receipt_id}")
    supplied_set = set(supplied_targets)
    for target_id in sorted(set(target_ids) - supplied_set):
        reasons.append(f"HOLDOUT_RUN_MISSING:{target_id}")

    return observed, tuple(sorted(set(reasons)))


def _anti_bypass_receipt_failures(
    control_id: str,
    receipt: ActualRunReceipt,
) -> list[str]:
    reasons: list[str] = []
    if receipt.target_id != control_id:
        reasons.append(f"ANTI_BYPASS_TARGET_MISMATCH:{control_id}")
    if not _is_sha256(receipt.raw_output_digest):
        reasons.append(f"ANTI_BYPASS_RAW_DIGEST_INVALID:{control_id}")
    if not receipt.execution_timestamp:
        reasons.append(f"ANTI_BYPASS_TIMESTAMP_MISSING:{control_id}")
    if receipt.execution_duration_ms <= 0:
        reasons.append(f"ANTI_BYPASS_DURATION_MISSING:{control_id}")
    if (
        receipt.status != "PASS"
        or receipt.exit_code != 0
        or receipt.evaluated_cases_count <= 0
        or receipt.passed_cases_count != receipt.evaluated_cases_count
        or receipt.failed_cases_count != 0
        or receipt.unsupported_cases_count != 0
        or receipt.unknown_cases_count != 0
    ):
        reasons.append(f"ANTI_BYPASS_FAILED:{control_id}")
    return reasons


def _validate_anti_bypass_receipts(
    receipts: Sequence[ActualRunReceipt],
    required_ids: Sequence[str],
) -> tuple[int, int, tuple[str, ...]]:
    reasons: list[str] = []
    supplied_targets = [receipt.target_id for receipt in receipts]
    supplied_receipt_ids = [receipt.receipt_id for receipt in receipts]
    required_list = list(required_ids)

    for control_id in sorted(set(required_list)):
        if required_list.count(control_id) > 1:
            reasons.append(f"ANTI_BYPASS_REQUIRED_ID_DUPLICATE:{control_id}")
    for control_id in sorted(set(supplied_targets)):
        if supplied_targets.count(control_id) > 1:
            reasons.append(f"ANTI_BYPASS_DUPLICATE:{control_id}")
    for receipt_id in sorted(set(supplied_receipt_ids)):
        if supplied_receipt_ids.count(receipt_id) > 1:
            reasons.append(f"ANTI_BYPASS_RECEIPT_ID_DUPLICATE:{receipt_id}")

    required = tuple(sorted(set(required_list)))
    denominator = required if required else tuple(sorted(set(supplied_targets)))
    denominator_set = set(denominator)
    supplied_set = set(supplied_targets)
    if not denominator:
        reasons.append("ANTI_BYPASS_SET_EMPTY")
    for control_id in sorted(denominator_set - supplied_set):
        reasons.append(f"ANTI_BYPASS_MISSING:{control_id}")
    if required:
        for control_id in sorted(supplied_set - denominator_set):
            reasons.append(f"ANTI_BYPASS_UNDECLARED:{control_id}")

    passed = 0
    for receipt in receipts:
        control_id = receipt.target_id
        receipt_reasons = _anti_bypass_receipt_failures(control_id, receipt)
        reasons.extend(receipt_reasons)
        if not receipt_reasons and control_id in denominator_set:
            passed += 1

    return len(denominator), passed, tuple(sorted(set(reasons)))


def evaluate_continuous_holdout(
    holdout: FrozenHoldout,
    holdout_runs: Sequence[BenchmarkRun],
    anti_bypass_receipts: Sequence[ActualRunReceipt],
    *,
    expected_commitment_sha256: str,
    required_anti_bypass_ids: Sequence[str] = (),
) -> ContinuousQualificationResult:
    """Strict release-methodology gate bound to executed holdout/control receipts."""
    qualification_reasons: list[str] = []
    if not _is_sha256(expected_commitment_sha256):
        qualification_reasons.append("HOLDOUT_COMMITMENT_INVALID")
    if expected_commitment_sha256 != holdout.commitment_sha256:
        qualification_reasons.append("HOLDOUT_COMMITMENT_MISMATCH")
    if not holdout.manifests:
        qualification_reasons.append("HOLDOUT_EMPTY")

    all_receipt_ids = [run.receipt.receipt_id for run in holdout_runs] + [
        receipt.receipt_id for receipt in anti_bypass_receipts
    ]
    for receipt_id in sorted(set(all_receipt_ids)):
        if all_receipt_ids.count(receipt_id) > 1:
            qualification_reasons.append(f"RUN_RECEIPT_ID_REUSED_ACROSS_GATE:{receipt_id}")

    observed, holdout_failures = _validate_holdout_runs(holdout, holdout_runs)
    qualification_reasons.extend(holdout_failures)
    metrics, metric_gate = _score(holdout, observed)

    anti_total, anti_passed, anti_failures = _validate_anti_bypass_receipts(
        anti_bypass_receipts,
        required_anti_bypass_ids,
    )
    qualified = (
        metric_gate
        and not qualification_reasons
        and anti_total > 0
        and anti_passed == anti_total
        and not anti_failures
    )
    verified_receipts = ()
    if qualified:
        verified_receipts = tuple(
            sorted(
                [run.receipt.receipt_digest() for run in holdout_runs]
                + [receipt.receipt_digest() for receipt in anti_bypass_receipts]
            )
        )

    return ContinuousQualificationResult(
        commitment_sha256=holdout.commitment_sha256,
        total=metrics.total_targets,
        evaluated=metrics.evaluated_targets,
        false_negatives=metrics.false_negatives,
        false_positives=metrics.false_positives,
        unknown=metrics.unknown_cases,
        qualified=qualified,
        anti_bypass_total=anti_total,
        anti_bypass_passed=anti_passed,
        anti_bypass_failures=anti_failures,
        verified_run_receipt_digests=verified_receipts,
        qualification_failures=tuple(sorted(set(qualification_reasons))),
    )


__all__ = [
    "FrozenHoldout",
    "ContinuousQualificationResult",
    "evaluate_holdout",
    "evaluate_continuous_holdout",
]
