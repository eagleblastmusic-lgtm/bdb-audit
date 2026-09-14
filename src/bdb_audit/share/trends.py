"""Scope-normalized historical comparison for successor audit snapshots."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True)
class TrendSnapshot:
    source_identity: str
    scope_digest: str
    policy_digest: str
    qualified: int
    denominator: int

    @property
    def rate(self) -> float | None:
        if self.denominator <= 0:
            return None
        if self.qualified < 0 or self.qualified > self.denominator:
            raise ValueError("qualified must be within denominator")
        return self.qualified / self.denominator


def compare_trend(snapshots: Sequence[TrendSnapshot]) -> dict:
    if not snapshots:
        return {"status": "NO_DATA", "rows": []}
    scope_keys = {(item.scope_digest, item.policy_digest) for item in snapshots}
    rows = [
        {
            "source_identity": item.source_identity,
            "scope_digest": item.scope_digest,
            "policy_digest": item.policy_digest,
            "qualified": item.qualified,
            "denominator": item.denominator,
            "rate": item.rate,
        }
        for item in snapshots
    ]
    if len(scope_keys) != 1:
        return {"status": "INCOMPARABLE_SCOPE", "rows": rows}
    if any(item.denominator <= 0 for item in snapshots):
        return {"status": "INSUFFICIENT_DENOMINATOR", "rows": rows}
    return {"status": "COMPARABLE", "rows": rows}


__all__ = ["TrendSnapshot", "compare_trend"]
