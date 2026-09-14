from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True)
class DependencyEdge:
    source: str
    dependent: str
    confidence: str = "CONFIRMED"


def propagate_impact(changed_nodes: Sequence[str], edges: Sequence[DependencyEdge]) -> dict:
    impacted = set(changed_nodes)
    uncertain = set()
    queue = list(changed_nodes)
    while queue:
        node = queue.pop(0)
        for edge in edges:
            if edge.source != node:
                continue
            if edge.confidence != "CONFIRMED":
                uncertain.add(edge.dependent)
            if edge.dependent not in impacted:
                impacted.add(edge.dependent)
                queue.append(edge.dependent)
    return {"changed": sorted(set(changed_nodes)), "impacted": sorted(impacted), "uncertain_impacts": sorted(uncertain)}
