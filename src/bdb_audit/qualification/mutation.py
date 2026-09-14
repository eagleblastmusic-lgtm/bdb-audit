"""Mutation-control scoring with explicit denominator and unknown partition."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence


@dataclass(frozen=True)
class MutationManifest:
    mutation_id: str
    target_id: str
    target_sha: str
    operator_ref: str
    defect_class: str


@dataclass(frozen=True)
class MutationMetrics:
    total: int
    evaluated: int
    killed: int
    survived: int
    unknown: int

    @property
    def kill_rate(self) -> float | None:
        return self.killed / self.total if self.total else None

    @property
    def qualified(self) -> bool:
        return self.total > 0 and self.evaluated == self.total and self.survived == 0 and self.unknown == 0


def score_mutations(manifests: Sequence[MutationManifest], observed: Mapping[str, str]) -> MutationMetrics:
    killed = survived = unknown = evaluated = 0
    for manifest in manifests:
        result = observed.get(manifest.mutation_id)
        if result is None:
            continue
        evaluated += 1
        if result == "KILLED":
            killed += 1
        elif result == "SURVIVED":
            survived += 1
        else:
            unknown += 1
    return MutationMetrics(len(manifests), evaluated, killed, survived, unknown)


__all__ = ["MutationManifest", "MutationMetrics", "score_mutations"]
