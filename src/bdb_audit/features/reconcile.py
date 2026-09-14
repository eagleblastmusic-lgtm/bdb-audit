from __future__ import annotations

from dataclasses import replace
from typing import Mapping, Sequence

from .models import FeatureRevision


def reconcile_features(
    discovered: Sequence[FeatureRevision],
    declared_tasks: Mapping[str, tuple[str, ...]],
) -> tuple[FeatureRevision, ...]:
    result: list[FeatureRevision] = []
    for feature in discovered:
        matched_refs: tuple[str, ...] = ()
        for phrase, refs in declared_tasks.items():
            if phrase.lower() in feature.user_task.lower() or any(phrase.lower() in ep.lower() for ep in feature.entrypoints):
                matched_refs = tuple(sorted(set(matched_refs).union(refs)))
        result.append(replace(feature, requirement_refs=matched_refs))
    return tuple(result)
