"""RU13-C continuous methodology qualification helpers.

The legacy ``evaluate_holdout`` scorer remains available for raw frozen-holdout
metrics. ``evaluate_continuous_holdout`` is the strict qualification gate: it
requires a non-empty anti-bypass regression set and refuses qualification when
any mandatory control is missing or failing.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import Mapping, Sequence

from .methodology_metrics import MethodologyMetrics
from .receipts import BenchmarkManifest
from .runner import MethodologyQualifier


@dataclass(frozen=True)
class FrozenHoldout:
    manifests: tuple[BenchmarkManifest, ...]
    commitment_sha256: str

    @classmethod
    def freeze(cls, manifests: Sequence[BenchmarkManifest]) -> "FrozenHoldout":
        holdout = tuple(sorted((m for m in manifests if m.split_membership == "HOLDOUT"), key=lambda m: m.benchmark_id))
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


def _score(holdout: FrozenHoldout, observed: Mapping[str, str]) -> tuple[MethodologyMetrics, bool]:
    metrics = MethodologyQualifier.score_benchmark_corpus(holdout.manifests, observed)
    qualified = (
        metrics.total_targets > 0
        and metrics.evaluated_targets == metrics.total_targets
        and metrics.false_negatives == 0
        and metrics.false_positives == 0
        and metrics.unknown_cases == 0
    )
    return metrics, qualified


def evaluate_holdout(holdout: FrozenHoldout, observed: Mapping[str, str]) -> ContinuousQualificationResult:
    """Score frozen holdout truth without claiming anti-bypass qualification."""
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


def evaluate_continuous_holdout(
    holdout: FrozenHoldout,
    observed: Mapping[str, str],
    anti_bypass_results: Mapping[str, bool],
    *,
    required_anti_bypass_ids: Sequence[str] = (),
) -> ContinuousQualificationResult:
    """Strict release-methodology gate over holdout and anti-bypass controls.

    ``required_anti_bypass_ids`` lets a release profile pin the mandatory control
    set. Missing controls and false controls both block qualification. When no
    explicit required set is supplied, at least one executed anti-bypass control
    is still mandatory.
    """
    metrics, holdout_ok = _score(holdout, observed)
    required = tuple(sorted(set(required_anti_bypass_ids)))
    missing = tuple(name for name in required if name not in anti_bypass_results)
    failed = tuple(sorted(name for name, passed in anti_bypass_results.items() if passed is not True))
    total_controls = len(anti_bypass_results)
    passed_controls = sum(1 for passed in anti_bypass_results.values() if passed is True)
    reason_codes: list[str] = []
    if total_controls == 0:
        reason_codes.append("ANTI_BYPASS_SET_EMPTY")
    reason_codes.extend(f"ANTI_BYPASS_MISSING:{name}" for name in missing)
    reason_codes.extend(f"ANTI_BYPASS_FAILED:{name}" for name in failed)
    anti_failures = tuple(sorted(reason_codes))
    qualified = (
        holdout_ok
        and total_controls > 0
        and not anti_failures
        and passed_controls == total_controls
    )
    return ContinuousQualificationResult(
        holdout.commitment_sha256,
        metrics.total_targets,
        metrics.evaluated_targets,
        metrics.false_negatives,
        metrics.false_positives,
        metrics.unknown_cases,
        qualified,
        total_controls,
        passed_controls,
        anti_failures,
    )


__all__ = [
    "FrozenHoldout", "ContinuousQualificationResult", "evaluate_holdout",
    "evaluate_continuous_holdout",
]
