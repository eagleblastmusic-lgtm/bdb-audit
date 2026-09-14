"""Read-only coverage/evidence workbench backed only by verified accepted history."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from ..core.errors import ValidationError
from ..history.store import TransactionalHistoryStore
from ..report.builder import ReportBuilder
from ..workflow.read_models import current_accepted_cut


class CoverageEvidenceWorkbench:
    """Derived projection with explainability and explicit freshness."""

    def __init__(self, store: TransactionalHistoryStore):
        self.store = store
        self.cut = current_accepted_cut(store)
        self.snapshot = ReportBuilder(store).build().as_dict()

    @classmethod
    def from_path(cls, path: str | Path) -> "CoverageEvidenceWorkbench":
        return cls(TransactionalHistoryStore(path))

    def freshness(self) -> dict[str, Any]:
        current = current_accepted_cut(self.store)
        fresh = current == self.cut
        return {
            "status": "CURRENT" if fresh else "STALE",
            "projection_cut": dict(self.cut),
            "current_cut": dict(current),
        }

    def coverage_matrix(self) -> dict[str, Any]:
        return {
            "history_cut": dict(self.cut),
            "freshness": self.freshness()["status"],
            "coverage": list(self.snapshot.get("coverage", [])),
            "unknown_count": sum(
                1 for item in self.snapshot.get("unknowns", [])
                if item.get("type") == "COVERAGE_NOT_QUALIFIED"
            ),
        }

    def explain_obligation(self, obligation_digest: str) -> dict[str, Any]:
        for item in self.snapshot.get("coverage", []):
            ref = item.get("obligation_ref") or {}
            if ref.get("revision_digest") == obligation_digest:
                return {
                    "status": "FOUND",
                    "history_cut": dict(self.cut),
                    "obligation": dict(item),
                    "reason_tree": {
                        "qualification_status": item.get("qualification_status", "UNASSESSED"),
                        "substantive_outcome": item.get("substantive_outcome"),
                        "reason_codes": list(item.get("reason_codes", [])),
                        "evidence_qualification_refs": list(item.get("evidence_qualification_refs", [])),
                    },
                }
        raise ValidationError("COVERAGE_OBLIGATION_NOT_ACCEPTED_AT_CUT", obligation_digest)

    def inspect_evidence(self, evidence_ref: Mapping[str, Any]) -> dict[str, Any]:
        if evidence_ref.get("kind") != "evidence_qualification_assessment":
            raise ValidationError("EVIDENCE_REF_KIND_INVALID")
        record = self.store.resolve_accepted(dict(evidence_ref), self.cut)
        return {
            "status": "FOUND",
            "history_cut": dict(self.cut),
            "evidence_ref": dict(record["ref"]),
            "accepted_seq": record["accepted_seq"],
            "assessment": dict(record["body"]),
        }

    def blockers(self) -> dict[str, Any]:
        blockers = []
        for item in self.snapshot.get("unknowns", []):
            blockers.append(dict(item))
        for stop in self.snapshot.get("stop_evaluations", []):
            decision = stop.get("continuation_decision")
            if decision and decision != "PASS":
                blockers.append({
                    "type": "STOP_NON_PASS",
                    "stop_evaluation_ref": stop.get("stop_evaluation_ref"),
                    "continuation_decision": decision,
                    "reason_codes": list(stop.get("reason_codes", [])),
                })
        return {
            "history_cut": dict(self.cut),
            "freshness": self.freshness()["status"],
            "blocker_count": len(blockers),
            "blockers": blockers,
        }


__all__ = ["CoverageEvidenceWorkbench"]
