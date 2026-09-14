"""Blind holdout execution: the executor never receives expected labels."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .continuous import ContinuousQualificationResult, FrozenHoldout, evaluate_holdout


@dataclass(frozen=True)
class BlindTarget:
    benchmark_id: str
    target_id: str
    target_sha: str
    allowed_exposures: tuple[str, ...]
    domain_tags: tuple[str, ...]


def run_blind_holdout(
    holdout: FrozenHoldout,
    executor: Callable[[BlindTarget], str],
) -> tuple[ContinuousQualificationResult, dict[str, str]]:
    observed: dict[str, str] = {}
    for manifest in holdout.manifests:
        target = BlindTarget(
            manifest.benchmark_id,
            manifest.target_id,
            manifest.target_sha,
            manifest.allowed_exposures,
            manifest.domain_tags,
        )
        observed[target.target_id] = executor(target)
    return evaluate_holdout(holdout, observed), observed


__all__ = ["BlindTarget", "run_blind_holdout"]
