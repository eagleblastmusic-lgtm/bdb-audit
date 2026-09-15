from __future__ import annotations

import pytest

from bdb_audit.assurance.challenger_evidence import validate_positive_challenger_evidence
from bdb_audit.core.errors import ValidationError


def _ref(kind: str, digit: str) -> dict[str, str]:
    return {
        "kind": kind,
        "revision_digest": digit * 64,
        "digest_profile": "BDB-OBJECT-DIGEST-1",
        "schema_revision_ref": f"BDB_SCHEMA_REGISTRY::{kind}/1",
        "ref_class": "CONTENT_OR_PRIOR",
    }


class _Store:
    def __init__(self, records: dict[str, dict], execution_results=()):
        self.records = records
        self.execution_results = tuple(execution_results)

    def resolve_accepted(self, ref, cut):
        del cut
        return self.records[ref["revision_digest"]]

    def accepted_records(self, kind, cut):
        del cut
        return self.execution_results if kind == "execution_result" else ()


def _supporting_store(
    *,
    result_status: str = "SUCCESS",
    exit_code: int = 0,
    bind_observation: bool = True,
    result_count: int = 1,
    cleanup_body: dict | None = None,
):
    qualification_ref = _ref("evidence_qualification_assessment", "a")
    observation_ref = _ref("observation", "b")
    execution_ref = _ref("execution_descriptor", "c")
    raw_ref = _ref("raw_artifact_ref", "d")
    cleanup_ref = _ref("cleanup_result", "e")
    records = {
        "a" * 64: {
            "body": {
                "result": "SUPPORTS",
                "observation_refs": [observation_ref],
            }
        },
        "b" * 64: {
            "body": {
                "execution_descriptor_ref": execution_ref,
                "raw_observation_ref": raw_ref,
            }
        },
        "c" * 64: {"body": {"execution_id": "exec-1"}},
    }
    if cleanup_body is not None:
        records["e" * 64] = {"body": cleanup_body}
    result_body = {
        "execution_descriptor_ref": execution_ref,
        "exit_code": exit_code,
        "status": result_status,
        "observation_refs": [observation_ref] if bind_observation else [],
    }
    if cleanup_body is not None:
        result_body["cleanup_result_ref"] = cleanup_ref
    execution_results = tuple({"body": dict(result_body)} for _ in range(result_count))
    return _Store(records, execution_results), qualification_ref


def test_positive_challenger_requires_evidence() -> None:
    with pytest.raises(ValidationError, match="E5_POSITIVE_CHALLENGER_EVIDENCE_REQUIRED"):
        validate_positive_challenger_evidence(
            _Store({}),
            {"variant": "ACCEPTED_HISTORY_CUT"},
            status="NO_MATERIAL_COUNTEREVIDENCE",
            evidence_qualification_refs=(),
        )


def test_nonpositive_challenger_can_record_without_positive_evidence() -> None:
    validate_positive_challenger_evidence(
        _Store({}),
        {"variant": "ACCEPTED_HISTORY_CUT"},
        status="INCONCLUSIVE",
        evidence_qualification_refs=(),
    )


def test_positive_challenger_accepts_supporting_completed_execution_chain() -> None:
    store, qualification_ref = _supporting_store()
    validate_positive_challenger_evidence(
        store,
        {"variant": "ACCEPTED_HISTORY_CUT"},
        status="NO_MATERIAL_COUNTEREVIDENCE",
        evidence_qualification_refs=(qualification_ref,),
    )


def test_positive_challenger_rejects_nonsupporting_qualification() -> None:
    qualification_ref = _ref("evidence_qualification_assessment", "a")
    with pytest.raises(ValidationError, match="E5_POSITIVE_CHALLENGER_EVIDENCE_NOT_SUPPORTING"):
        validate_positive_challenger_evidence(
            _Store({"a" * 64: {"body": {"result": "INCONCLUSIVE", "observation_refs": []}}}),
            {"variant": "ACCEPTED_HISTORY_CUT"},
            status="NO_MATERIAL_COUNTEREVIDENCE",
            evidence_qualification_refs=(qualification_ref,),
        )


def test_positive_challenger_rejects_observation_without_execution_descriptor() -> None:
    qualification_ref = _ref("evidence_qualification_assessment", "a")
    observation_ref = _ref("observation", "b")
    store = _Store(
        {
            "a" * 64: {"body": {"result": "SUPPORTS", "observation_refs": [observation_ref]}},
            "b" * 64: {"body": {"raw_observation_ref": _ref("raw_artifact_ref", "d")}},
        }
    )
    with pytest.raises(ValidationError, match="E5_POSITIVE_CHALLENGER_EXECUTION_DESCRIPTOR_REQUIRED"):
        validate_positive_challenger_evidence(
            store,
            {"variant": "ACCEPTED_HISTORY_CUT"},
            status="NO_MATERIAL_COUNTEREVIDENCE",
            evidence_qualification_refs=(qualification_ref,),
        )


def test_positive_challenger_rejects_descriptor_without_terminal_result() -> None:
    store, qualification_ref = _supporting_store(result_count=0)
    with pytest.raises(ValidationError, match="E5_POSITIVE_CHALLENGER_EXECUTION_RESULT_REQUIRED"):
        validate_positive_challenger_evidence(
            store,
            {"variant": "ACCEPTED_HISTORY_CUT"},
            status="NO_MATERIAL_COUNTEREVIDENCE",
            evidence_qualification_refs=(qualification_ref,),
        )


def test_positive_challenger_rejects_failed_terminal_result() -> None:
    store, qualification_ref = _supporting_store(result_status="FAILED", exit_code=1)
    with pytest.raises(ValidationError, match="E5_POSITIVE_CHALLENGER_EXECUTION_RESULT_NOT_SUCCESSFUL"):
        validate_positive_challenger_evidence(
            store,
            {"variant": "ACCEPTED_HISTORY_CUT"},
            status="NO_MATERIAL_COUNTEREVIDENCE",
            evidence_qualification_refs=(qualification_ref,),
        )


def test_positive_challenger_rejects_result_not_binding_observation() -> None:
    store, qualification_ref = _supporting_store(bind_observation=False)
    with pytest.raises(
        ValidationError,
        match="E5_POSITIVE_CHALLENGER_OBSERVATION_NOT_BOUND_TO_EXECUTION_RESULT",
    ):
        validate_positive_challenger_evidence(
            store,
            {"variant": "ACCEPTED_HISTORY_CUT"},
            status="NO_MATERIAL_COUNTEREVIDENCE",
            evidence_qualification_refs=(qualification_ref,),
        )


def test_positive_challenger_rejects_ambiguous_terminal_results() -> None:
    store, qualification_ref = _supporting_store(result_count=2)
    with pytest.raises(ValidationError, match="E5_POSITIVE_CHALLENGER_EXECUTION_RESULT_AMBIGUOUS"):
        validate_positive_challenger_evidence(
            store,
            {"variant": "ACCEPTED_HISTORY_CUT"},
            status="NO_MATERIAL_COUNTEREVIDENCE",
            evidence_qualification_refs=(qualification_ref,),
        )


def test_positive_challenger_rejects_dirty_cleanup_when_cleanup_is_declared() -> None:
    store, qualification_ref = _supporting_store(
        cleanup_body={"cleanup_status": "DIRTY", "residual_artifacts_cleared": False}
    )
    with pytest.raises(ValidationError, match="E5_POSITIVE_CHALLENGER_CLEANUP_NOT_CLEAN"):
        validate_positive_challenger_evidence(
            store,
            {"variant": "ACCEPTED_HISTORY_CUT"},
            status="NO_MATERIAL_COUNTEREVIDENCE",
            evidence_qualification_refs=(qualification_ref,),
        )
