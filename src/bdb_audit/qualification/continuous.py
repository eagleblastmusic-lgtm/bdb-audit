"""RU13-C continuous methodology qualification helpers."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import Mapping, Sequence

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


def evaluate_holdout(holdout: FrozenHoldout, observed: Mapping[str, str]) -> ContinuousQualificationResult:
    metrics = MethodologyQualifier.score_benchmark_corpus(holdout.manifests, observed)
    qualified = metrics.total_targets > 0 and metrics.evaluated_targets == metrics.total_targets and metrics.false_negatives == 0 and metrics.false_positives == 0 and metrics.unknown_cases == 0
    return ContinuousQualificationResult(holdout.commitment_sha256, metrics.total_targets, metrics.evaluated_targets, metrics.false_negatives, metrics.false_positives, metrics.unknown_cases, qualified)
