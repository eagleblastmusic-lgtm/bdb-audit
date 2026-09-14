from __future__ import annotations

from typing import Any

from ..history.store import TransactionalHistoryStore

_RESOLVED = {"RESOLVED", "RESOLVED_SCOPED", "RESOLVED_FULL"}


def contradiction_projection(store: TransactionalHistoryStore, cut: dict[str, Any]) -> dict:
    rows = []
    for record in store.accepted_records("contradiction_revision", cut):
        body = record["body"]
        status = body.get("status", body.get("contradiction_status", "UNRESOLVED"))
        rows.append({"ref": record["ref"], "status": status, "resolved": status in _RESOLVED, "claim_refs": list(body.get("claim_revision_refs", [])), "reason_codes": list(body.get("reason_codes", []))})
    return {"projection_kind": "CONTRADICTION_MATRIX", "history_cut": cut, "rows": rows, "unresolved_count": sum(1 for row in rows if not row["resolved"])}
