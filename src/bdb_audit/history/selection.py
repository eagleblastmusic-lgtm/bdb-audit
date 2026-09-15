"""Explicit chronological selectors over accepted-history membership.

TransactionalHistoryStore.accepted_records() proves membership at an exact cut,
but its collection order is not a chronology contract. Callers that need
"latest accepted" must order by the accepted sequence carried by each resolved
record rather than by object digest or incidental container order.
"""
from __future__ import annotations

from typing import Any

from .store import TransactionalHistoryStore


def chronological_accepted_records(
    store: TransactionalHistoryStore,
    kind: str,
    cut: dict[str, Any],
) -> tuple[dict[str, Any], ...]:
    records = list(store.accepted_records(kind, cut))
    records.sort(
        key=lambda row: (
            int(row.get("accepted_seq", 0)),
            str(row.get("ref", {}).get("revision_digest", "")),
        )
    )
    return tuple(records)


def latest_accepted_record(
    store: TransactionalHistoryStore,
    kind: str,
    cut: dict[str, Any],
) -> dict[str, Any] | None:
    records = chronological_accepted_records(store, kind, cut)
    return records[-1] if records else None


__all__ = ["chronological_accepted_records", "latest_accepted_record"]
