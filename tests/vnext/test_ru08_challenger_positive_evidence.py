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
    def __init__(self, records: dict[str, dict]):
        self.records = records

    def resolve_accepted(self, ref, cut):
        del cut
        return self.records[ref["revision_digest"]]


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


def test_positive_challenger_accepts_supporting_observed_execution_chain() -> None:
    qualification_ref = _ref("evidence_qualification_assessment", "a")
    observation_ref = _ref("observation", "b")
    execution_ref = _ref("execution_descriptor", "c")
    store = _Store(
        {
            "a" * 64: {
                "body": {
                    "result": "SUPPORTS",
                    "observation_refs": [observation_ref],
                }
            },
            "b" * 64: {
                "body": {
                    "execution_descriptor_ref": execution_ref,
                    "raw_observation_ref": "raw:challenger-output",
                }
            },
            "c" * 64: {"body": {"execution_id": "exec-1"}},
        }
    )
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
            "b" * 64: {"body": {"raw_observation_ref": "raw:challenger-output"}},
        }
    )
    with pytest.raises(ValidationError, match="E5_POSITIVE_CHALLENGER_EXECUTION_DESCRIPTOR_REQUIRED"):
        validate_positive_challenger_evidence(
            store,
            {"variant": "ACCEPTED_HISTORY_CUT"},
            status="NO_MATERIAL_COUNTEREVIDENCE",
            evidence_qualification_refs=(qualification_ref,),
        )
