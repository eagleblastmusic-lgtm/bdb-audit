"""Fail-closed evidence requirements for positive E5 challenger outcomes."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from ..core.errors import ValidationError
from ..history.store import TransactionalHistoryStore

_POSITIVE_STATUS = "NO_MATERIAL_COUNTEREVIDENCE"


def validate_positive_challenger_evidence(
    store: TransactionalHistoryStore,
    cut: dict[str, Any],
    *,
    status: str,
    evidence_qualification_refs: Sequence[dict[str, Any]],
) -> None:
    """Require prior accepted qualified execution evidence for a positive result."""
    if status != _POSITIVE_STATUS:
        return
    if not evidence_qualification_refs:
        raise ValidationError("E5_POSITIVE_CHALLENGER_EVIDENCE_REQUIRED")

    seen: set[str] = set()
    for ref in evidence_qualification_refs:
        if not isinstance(ref, Mapping) or ref.get("kind") != "evidence_qualification_assessment":
            raise ValidationError("E5_POSITIVE_CHALLENGER_EVIDENCE_KIND_INVALID")
        digest = ref.get("revision_digest")
        if not isinstance(digest, str) or not digest or digest in seen:
            raise ValidationError("E5_POSITIVE_CHALLENGER_EVIDENCE_IDENTITY_INVALID")
        seen.add(digest)

        qualification = store.resolve_accepted(dict(ref), cut)
        body = qualification.get("body")
        if not isinstance(body, Mapping) or body.get("result") != "SUPPORTS":
            raise ValidationError("E5_POSITIVE_CHALLENGER_EVIDENCE_NOT_SUPPORTING")
        observation_refs = body.get("observation_refs")
        if not isinstance(observation_refs, list) or not observation_refs:
            raise ValidationError("E5_POSITIVE_CHALLENGER_OBSERVATION_REQUIRED")

        for observation_ref in observation_refs:
            if not isinstance(observation_ref, Mapping) or observation_ref.get("kind") != "observation":
                raise ValidationError("E5_POSITIVE_CHALLENGER_OBSERVATION_REF_INVALID")
            observation = store.resolve_accepted(dict(observation_ref), cut)
            observation_body = observation.get("body")
            if not isinstance(observation_body, Mapping):
                raise ValidationError("E5_POSITIVE_CHALLENGER_OBSERVATION_INVALID")
            execution_ref = observation_body.get("execution_descriptor_ref")
            if not isinstance(execution_ref, Mapping):
                raise ValidationError("E5_POSITIVE_CHALLENGER_EXECUTION_DESCRIPTOR_REQUIRED")
            store.resolve_accepted(dict(execution_ref), cut)
            if observation_body.get("raw_observation_ref") in (None, ""):
                raise ValidationError("E5_POSITIVE_CHALLENGER_RAW_OBSERVATION_REQUIRED")


__all__ = ["validate_positive_challenger_evidence"]
