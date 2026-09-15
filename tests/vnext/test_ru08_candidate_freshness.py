from __future__ import annotations

import pytest

from bdb_audit.assurance.candidate_freshness import validate_e5_candidate_freshness
from bdb_audit.core.errors import ValidationError


def _ref(kind: str, digit: str) -> dict[str, str]:
    return {
        "kind": kind,
        "revision_digest": digit * 64,
        "digest_profile": "BDB-OBJECT-DIGEST-1",
        "schema_revision_ref": f"BDB_SCHEMA_REGISTRY::{kind}/1",
        "ref_class": "CONTENT_OR_PRIOR",
    }


def _row(kind: str, digit: str, seq: int, body: dict | None = None) -> dict:
    return {
        "accepted_seq": seq,
        "ref": _ref(kind, digit),
        "body": body or {},
    }


class _Store:
    def __init__(self, rows: dict[str, list[dict]]):
        self.rows = rows

    def accepted_records(self, kind, cut):
        del cut
        return tuple(self.rows.get(kind, ()))


def _candidate() -> dict:
    return _row("candidate_assurance_case", "a", 10)


def _result(seq: int = 20, evidence=()) -> dict:
    return _row(
        "challenger_result",
        "b" if seq == 20 else "c",
        seq,
        {"evidence_qualification_refs": list(evidence)},
    )


def test_unchanged_candidate_remains_fresh() -> None:
    validate_e5_candidate_freshness(
        _Store({}),
        _candidate(),
        (_result(), _result(21)),
        {"variant": "ACCEPTED_HISTORY_CUT"},
    )


def test_new_finding_after_freeze_invalidates_candidate() -> None:
    store = _Store({"finding_claim_revision": [_row("finding_claim_revision", "d", 11)]})
    with pytest.raises(ValidationError, match="E5_CANDIDATE_STALE_AFTER_FREEZE"):
        validate_e5_candidate_freshness(
            store,
            _candidate(),
            (_result(), _result(21)),
            {"variant": "ACCEPTED_HISTORY_CUT"},
        )


def test_new_source_generation_after_freeze_invalidates_candidate() -> None:
    store = _Store({"source_generation": [_row("source_generation", "d", 11)]})
    with pytest.raises(ValidationError, match="E5_CANDIDATE_STALE_AFTER_FREEZE"):
        validate_e5_candidate_freshness(
            store,
            _candidate(),
            (_result(), _result(21)),
            {"variant": "ACCEPTED_HISTORY_CUT"},
        )


def test_exact_challenger_evidence_is_allowed_after_freeze() -> None:
    evidence_ref = _ref("evidence_qualification_assessment", "d")
    store = _Store(
        {"evidence_qualification_assessment": [_row("evidence_qualification_assessment", "d", 15)]}
    )
    validate_e5_candidate_freshness(
        store,
        _candidate(),
        (_result(evidence=(evidence_ref,)), _result(21)),
        {"variant": "ACCEPTED_HISTORY_CUT"},
    )


def test_unreferenced_post_freeze_evidence_invalidates_candidate() -> None:
    evidence_ref = _ref("evidence_qualification_assessment", "d")
    store = _Store(
        {
            "evidence_qualification_assessment": [
                _row("evidence_qualification_assessment", "d", 15),
                _row("evidence_qualification_assessment", "e", 16),
            ]
        }
    )
    with pytest.raises(ValidationError, match="E5_CANDIDATE_STALE_AFTER_FREEZE"):
        validate_e5_candidate_freshness(
            store,
            _candidate(),
            (_result(evidence=(evidence_ref,)), _result(21)),
            {"variant": "ACCEPTED_HISTORY_CUT"},
        )
