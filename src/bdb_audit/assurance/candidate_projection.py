"""Fail-closed projection of current finding/adjudication pairs for E5A."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from ..core.errors import ValidationError


def _digest(ref: object) -> str | None:
    if not isinstance(ref, Mapping):
        return None
    value = ref.get("revision_digest")
    return value if isinstance(value, str) and value else None


def _seq(row: Mapping[str, Any]) -> int:
    value = row.get("accepted_seq")
    if type(value) is not int or value < 1:
        raise ValidationError("E5_CANDIDATE_ACCEPTED_SEQ_INVALID")
    return value


def current_finding_adjudication_pairs(
    claim_rows: Sequence[Mapping[str, Any]],
    adjudication_rows: Sequence[Mapping[str, Any]],
) -> tuple[tuple[dict[str, Any], dict[str, Any]], ...]:
    """Return exact current claim/adjudication refs, failing closed on missing/ambiguous truth."""
    latest_claim_by_id: dict[str, Mapping[str, Any]] = {}
    for row in claim_rows:
        body = row.get("body")
        ref = row.get("ref")
        if not isinstance(body, Mapping) or not isinstance(ref, Mapping):
            raise ValidationError("E5_CANDIDATE_FINDING_ROW_INVALID")
        claim_id = body.get("claim_id")
        if not isinstance(claim_id, str) or not claim_id:
            raise ValidationError("E5_CANDIDATE_CLAIM_ID_INVALID")
        previous = latest_claim_by_id.get(claim_id)
        if previous is None or _seq(row) > _seq(previous):
            latest_claim_by_id[claim_id] = row
        elif _seq(row) == _seq(previous) and _digest(ref) != _digest(previous.get("ref")):
            raise ValidationError("E5_CANDIDATE_CLAIM_REVISION_AMBIGUOUS", claim_id)

    adjudications_by_claim_digest: dict[str, list[Mapping[str, Any]]] = {}
    for row in adjudication_rows:
        body = row.get("body")
        ref = row.get("ref")
        if not isinstance(body, Mapping) or not isinstance(ref, Mapping):
            raise ValidationError("E5_CANDIDATE_ADJUDICATION_ROW_INVALID")
        claim_digest = _digest(body.get("claim_revision_ref"))
        if claim_digest is None:
            raise ValidationError("E5_CANDIDATE_ADJUDICATION_CLAIM_REF_INVALID")
        adjudications_by_claim_digest.setdefault(claim_digest, []).append(row)

    pairs: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for claim_id, claim_row in sorted(latest_claim_by_id.items()):
        claim_ref = claim_row.get("ref")
        claim_digest = _digest(claim_ref)
        if claim_digest is None or not isinstance(claim_ref, Mapping):
            raise ValidationError("E5_CANDIDATE_CLAIM_REF_INVALID", claim_id)
        candidates = adjudications_by_claim_digest.get(claim_digest, [])
        if not candidates:
            raise ValidationError("E5_CANDIDATE_FINDING_ADJUDICATION_MISSING", claim_id)
        max_seq = max(_seq(row) for row in candidates)
        latest = [row for row in candidates if _seq(row) == max_seq]
        unique_digests = {_digest(row.get("ref")) for row in latest}
        if len(latest) != 1 or None in unique_digests or len(unique_digests) != 1:
            raise ValidationError("E5_CANDIDATE_ADJUDICATION_AMBIGUOUS", claim_id)
        adjudication_ref = latest[0].get("ref")
        if not isinstance(adjudication_ref, Mapping):
            raise ValidationError("E5_CANDIDATE_ADJUDICATION_REF_INVALID", claim_id)
        pairs.append((dict(claim_ref), dict(adjudication_ref)))
    return tuple(pairs)


__all__ = ["current_finding_adjudication_pairs"]
