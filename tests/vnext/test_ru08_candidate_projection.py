from __future__ import annotations

import pytest

from bdb_audit.assurance.candidate_projection import current_finding_adjudication_pairs
from bdb_audit.core.errors import ValidationError


def _ref(kind: str, digit: str) -> dict[str, str]:
    return {"kind": kind, "revision_digest": digit * 64}


def _claim(claim_id: str, seq: int, digit: str) -> dict:
    return {
        "accepted_seq": seq,
        "ref": _ref("finding_claim_revision", digit),
        "body": {"claim_id": claim_id},
    }


def _decision(claim_digit: str, seq: int, digit: str) -> dict:
    return {
        "accepted_seq": seq,
        "ref": _ref("finding_adjudication_decision", digit),
        "body": {"claim_revision_ref": _ref("finding_claim_revision", claim_digit)},
    }


def test_candidate_projection_selects_latest_claim_revision_and_matching_adjudication() -> None:
    pairs = current_finding_adjudication_pairs(
        (_claim("claim-a", 2, "a"), _claim("claim-a", 5, "b"), _claim("claim-b", 4, "c")),
        (
            _decision("a", 3, "d"),
            _decision("b", 6, "e"),
            _decision("c", 5, "f"),
        ),
    )
    assert [pair[0]["revision_digest"] for pair in pairs] == ["b" * 64, "c" * 64]
    assert [pair[1]["revision_digest"] for pair in pairs] == ["e" * 64, "f" * 64]


def test_candidate_projection_rejects_current_unadjudicated_finding() -> None:
    with pytest.raises(ValidationError, match="E5_CANDIDATE_FINDING_ADJUDICATION_MISSING"):
        current_finding_adjudication_pairs((_claim("claim-a", 2, "a"),), ())


def test_candidate_projection_rejects_same_cut_ambiguous_adjudication() -> None:
    with pytest.raises(ValidationError, match="E5_CANDIDATE_ADJUDICATION_AMBIGUOUS"):
        current_finding_adjudication_pairs(
            (_claim("claim-a", 2, "a"),),
            (_decision("a", 3, "b"), _decision("a", 3, "c")),
        )


def test_candidate_projection_allows_no_findings() -> None:
    assert current_finding_adjudication_pairs((), ()) == ()
