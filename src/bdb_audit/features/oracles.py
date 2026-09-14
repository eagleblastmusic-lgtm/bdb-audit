from __future__ import annotations

from .models import OracleAssessment


def qualify_oracle(oracle_id: str, source_kind: str, source_refs: tuple[str, ...]) -> OracleAssessment:
    if source_kind == "IMPLEMENTATION":
        return OracleAssessment(oracle_id, source_kind, source_refs, "INSUFFICIENT", ("IMPLEMENTATION_DERIVED_ORACLE",))
    if source_kind not in {"REQUIREMENT", "USER_TASK", "EXTERNAL_CONTRACT", "REFERENCE_FIXTURE"}:
        return OracleAssessment(oracle_id, source_kind, source_refs, "UNKNOWN", ("ORACLE_SOURCE_UNKNOWN",))
    if not source_refs:
        return OracleAssessment(oracle_id, source_kind, source_refs, "INSUFFICIENT", ("ORACLE_SOURCE_REFS_MISSING",))
    return OracleAssessment(oracle_id, source_kind, source_refs, "QUALIFIED", ())
