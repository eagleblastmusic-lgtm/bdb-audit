from __future__ import annotations

from typing import Any

from ..history.store import TransactionalHistoryStore


def inspect_evidence(store: TransactionalHistoryStore, ref: dict[str, Any], cut: dict[str, Any]) -> dict:
    record = store.resolve_accepted(ref, cut)
    return {
        "projection_kind": "EVIDENCE_INSPECTION",
        "history_cut": cut,
        "ref": record["ref"],
        "accepted_seq": record["accepted_seq"],
        "body": record["body"],
    }
