from __future__ import annotations

from typing import Any

from ..history.store import TransactionalHistoryStore
from ..workflow.read_models import current_accepted_cut


def coverage_matrix(store: TransactionalHistoryStore, cut: dict[str, Any] | None = None) -> dict:
    selected_cut = cut or current_accepted_cut(store)
    obligations = store.accepted_records("coverage_obligation", selected_cut)
    qualifications = store.accepted_records("coverage_obligation_qualification", selected_cut)
    latest: dict[str, dict] = {}
    for row in qualifications:
        ref = row["body"].get("obligation_revision_ref")
        digest = ref.get("revision_digest") if isinstance(ref, dict) else None
        if digest and (digest not in latest or row["accepted_seq"] > latest[digest]["accepted_seq"]):
            latest[digest] = row
    rows = []
    for row in obligations:
        ref = row["ref"]
        q = latest.get(ref["revision_digest"])
        body = q["body"] if q else {}
        status = body.get("qualification_status", "UNASSESSED")
        rows.append({
            "obligation_ref": ref,
            "status": status,
            "reason_codes": list(body.get("reason_codes", [])),
            "evidence_refs": list(body.get("evidence_qualification_refs", [])),
        })
    return {
        "projection_kind": "COVERAGE_MATRIX",
        "history_cut": selected_cut,
        "rows": rows,
        "denominator": len(rows),
        "unknown_or_unqualified": sum(1 for row in rows if row["status"] != "QUALIFIED"),
    }
