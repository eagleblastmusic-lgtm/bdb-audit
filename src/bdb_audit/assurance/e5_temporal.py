"""Strict accepted-sequence checks for the E5A/E5B assurance DAG."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from ..core.errors import ValidationError


def _accepted_seq(row: Mapping[str, Any], label: str) -> int:
    value = row.get("accepted_seq")
    if type(value) is not int or value < 1:
        raise ValidationError("E5_TEMPORAL_ACCEPTED_SEQ_INVALID", label)
    return value


def validate_e5_challenge_temporal_order(
    candidate_row: Mapping[str, Any],
    assignment_rows: Sequence[Mapping[str, Any]],
    result_rows: Sequence[Mapping[str, Any]],
) -> None:
    """Require candidate < every assignment < every result in accepted history."""
    if len(assignment_rows) != 2:
        raise ValidationError("E5_TEMPORAL_ASSIGNMENT_CARDINALITY", str(len(assignment_rows)))
    if len(result_rows) != 2:
        raise ValidationError("E5_TEMPORAL_RESULT_CARDINALITY", str(len(result_rows)))

    candidate_seq = _accepted_seq(candidate_row, "candidate")
    assignment_seqs = tuple(_accepted_seq(row, "assignment") for row in assignment_rows)
    result_seqs = tuple(_accepted_seq(row, "result") for row in result_rows)

    if min(assignment_seqs) <= candidate_seq:
        raise ValidationError(
            "E5_CHALLENGE_TEMPORAL_ORDER_VIOLATION",
            "CandidateAssuranceCase must be accepted before challenger assignments",
        )
    if min(result_seqs) <= max(assignment_seqs):
        raise ValidationError(
            "E5_CHALLENGE_TEMPORAL_ORDER_VIOLATION",
            "Challenger assignments must be accepted before challenger results",
        )


__all__ = ["validate_e5_challenge_temporal_order"]
