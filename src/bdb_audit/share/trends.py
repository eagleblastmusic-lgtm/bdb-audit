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

    def __post_init__(self) -> None:
        if not self.source_identity.strip():
            raise ValueError("source_identity required")
        if not self.scope_digest.strip():
            raise ValueError("scope_digest required")
        if not self.policy_digest.strip():
            raise ValueError("policy_digest required")
        if self.denominator < 0:
            raise ValueError("denominator must be non-negative")
        if self.qualified < 0 or self.qualified > self.denominator:
            raise ValueError("qualified must be within denominator")

    @property
    def rate(self) -> float | None:
        if self.denominator <= 0:
            return None
        return self.qualified / self.denominator


def compare_trend(snapshots: Sequence[TrendSnapshot]) -> dict[str, object]:
    if not snapshots:
        return {"status": "NO_DATA", "rows": []}
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
    if len(snapshots) < 2:
        return {"status": "INSUFFICIENT_HISTORY", "rows": rows}
    source_ids = [item.source_identity for item in snapshots]
    if len(set(source_ids)) != len(source_ids):
        return {"status": "INCOMPARABLE_DUPLICATE_SOURCE", "rows": rows}
    scope_keys = {(item.scope_digest, item.policy_digest) for item in snapshots}
    if len(scope_keys) != 1:
        return {"status": "INCOMPARABLE_SCOPE", "rows": rows}
    if any(item.denominator <= 0 for item in snapshots):
        return {"status": "INSUFFICIENT_DENOMINATOR", "rows": rows}
    return {"status": "COMPARABLE", "rows": rows}


__all__ = ["TrendSnapshot", "compare_trend"]
