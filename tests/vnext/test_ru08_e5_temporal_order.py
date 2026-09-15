from __future__ import annotations

import pytest

from bdb_audit.assurance.e5_temporal import validate_e5_challenge_temporal_order
from bdb_audit.core.errors import ValidationError


def _row(seq: int) -> dict[str, int]:
    return {"accepted_seq": seq}


def test_e5_temporal_order_accepts_strict_candidate_assignment_result_chain() -> None:
    validate_e5_challenge_temporal_order(
        _row(10),
        (_row(11), _row(11)),
        (_row(12), _row(12)),
    )


def test_e5_temporal_order_rejects_same_commit_candidate_and_assignments() -> None:
    with pytest.raises(ValidationError, match="E5_CHALLENGE_TEMPORAL_ORDER_VIOLATION"):
        validate_e5_challenge_temporal_order(
            _row(10),
            (_row(10), _row(10)),
            (_row(11), _row(11)),
        )


def test_e5_temporal_order_rejects_same_commit_assignments_and_results() -> None:
    with pytest.raises(ValidationError, match="E5_CHALLENGE_TEMPORAL_ORDER_VIOLATION"):
        validate_e5_challenge_temporal_order(
            _row(10),
            (_row(11), _row(11)),
            (_row(11), _row(11)),
        )


def test_e5_temporal_order_rejects_wrong_cardinality() -> None:
    with pytest.raises(ValidationError, match="E5_TEMPORAL_ASSIGNMENT_CARDINALITY"):
        validate_e5_challenge_temporal_order(_row(10), (_row(11),), (_row(12), _row(12)))
