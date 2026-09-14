"""RU12-B verified cross-domain status projection."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from ..functional.verification import FunctionalAssessment


@dataclass(frozen=True)
class VerifiedMatrixProjection:
    source_identity: str
    history_cut_digest: str
    functional_assessments: tuple[FunctionalAssessment, ...]
    contradiction_ids: tuple[str, ...] = ()

    def rows(self) -> list[dict]:
        return [{"case_id": item.case_id, "feature_id": item.feature_id, "status": item.status, "executed": item.executed, "oracle_qualified": item.oracle_qualified, "evidence_digest": item.evidence_digest, "reason_codes": list(item.reason_codes), "source_identity": self.source_identity, "history_cut_digest": self.history_cut_digest} for item in self.functional_assessments]

    def blockers(self) -> list[dict]:
        result = []
        for item in self.functional_assessments:
            if item.status != "PASS":
                result.append({"type": "FUNCTIONAL_VERIFICATION", "id": item.case_id, "status": item.status})
        result.extend({"type": "CONTRADICTION", "id": cid, "status": "UNRESOLVED"} for cid in self.contradiction_ids)
        return result

    def explain(self, case_id: str) -> Mapping[str, object]:
        for row in self.rows():
            if row["case_id"] == case_id:
                return row
        return {"case_id": case_id, "status": "UNKNOWN", "reason_codes": ["CASE_NOT_IN_PROJECTION"]}
