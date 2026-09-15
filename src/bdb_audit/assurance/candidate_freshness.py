"""Fail-closed freshness guard for the frozen E5 CandidateAssuranceCase."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from ..core.errors import ValidationError
from ..history.selection import chronological_accepted_records
from ..history.store import TransactionalHistoryStore

_MATERIAL_KINDS = (
    "source_identity",
    "source_generation",
    "inventory_revision",
    "coverage_obligation",
    "obligation_qualification",
    "finding_claim_revision",
    "finding_adjudication_decision",
    "contradiction",
    "residual_risk",
    "evidence_qualification_assessment",
)


def _seq(row: Mapping[str, Any], label: str) -> int:
    value = row.get("accepted_seq")
    if type(value) is not int or value < 1:
        raise ValidationError("E5_FRESHNESS_ACCEPTED_SEQ_INVALID", label)
    return value


def _digest(ref: object) -> str | None:
    if not isinstance(ref, Mapping):
        return None
    value = ref.get("revision_digest")
    return value if isinstance(value, str) and value else None


def validate_e5_candidate_freshness(
    store: TransactionalHistoryStore,
    candidate_row: Mapping[str, Any],
    result_rows: Sequence[Mapping[str, Any]],
    cut: dict[str, Any],
) -> None:
    """Reject material accepted-state changes after candidate freeze.

    Challenger-produced evidence qualifications are the only allowed post-freeze
    material records, and only when their exact digests are referenced by the
    accepted challenger results being evaluated.
    """
    candidate_seq = _seq(candidate_row, "candidate")
    allowed_challenger_evidence: set[str] = set()
    for row in result_rows:
        result_seq = _seq(row, "challenger_result")
        if result_seq <= candidate_seq:
            raise ValidationError("E5_CHALLENGER_RESULT_PRECEDES_CANDIDATE")
        body = row.get("body")
        if not isinstance(body, Mapping):
            raise ValidationError("E5_CHALLENGER_RESULT_BODY_INVALID")
        refs = body.get("evidence_qualification_refs", ())
        if not isinstance(refs, (list, tuple)):
            raise ValidationError("E5_CHALLENGER_EVIDENCE_REFS_INVALID")
        for ref in refs:
            digest = _digest(ref)
            if digest is None:
                raise ValidationError("E5_CHALLENGER_EVIDENCE_REF_INVALID")
            allowed_challenger_evidence.add(digest)

    for kind in _MATERIAL_KINDS:
        for row in chronological_accepted_records(store, kind, cut):
            accepted_seq = _seq(row, kind)
            if accepted_seq <= candidate_seq:
                continue
            digest = _digest(row.get("ref"))
            if kind == "evidence_qualification_assessment" and digest in allowed_challenger_evidence:
                continue
            raise ValidationError(
                "E5_CANDIDATE_STALE_AFTER_FREEZE",
                f"{kind}:{digest or 'unknown'}",
            )


__all__ = ["validate_e5_candidate_freshness"]
