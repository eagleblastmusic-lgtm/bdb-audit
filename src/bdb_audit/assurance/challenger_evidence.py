"""Fail-closed evidence requirements for positive E5 challenger outcomes."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from ..core.errors import ValidationError
from ..history.store import TransactionalHistoryStore

_POSITIVE_STATUS = "NO_MATERIAL_COUNTEREVIDENCE"


def _ref_digest(ref: object, *, kind: str | None = None) -> str | None:
    if not isinstance(ref, Mapping):
        return None
    if kind is not None and ref.get("kind") != kind:
        return None
    digest = ref.get("revision_digest")
    return digest if isinstance(digest, str) and digest else None


def _require_terminal_execution_result(
    store: TransactionalHistoryStore,
    cut: dict[str, Any],
    *,
    execution_ref: Mapping[str, Any],
    observation_ref: Mapping[str, Any],
) -> None:
    """Bind an accepted observation to one successful terminal execution result."""
    execution_digest = _ref_digest(execution_ref, kind="execution_descriptor")
    if execution_digest is None:
        raise ValidationError("E5_POSITIVE_CHALLENGER_EXECUTION_DESCRIPTOR_REQUIRED")
    observation_digest = _ref_digest(observation_ref, kind="observation")
    if observation_digest is None:
        raise ValidationError("E5_POSITIVE_CHALLENGER_OBSERVATION_REF_INVALID")

    matches: list[Mapping[str, Any]] = []
    for row in store.accepted_records("execution_result", cut):
        body = row.get("body")
        if not isinstance(body, Mapping):
            raise ValidationError("E5_POSITIVE_CHALLENGER_EXECUTION_RESULT_INVALID")
        if _ref_digest(body.get("execution_descriptor_ref"), kind="execution_descriptor") == execution_digest:
            matches.append(row)

    if not matches:
        raise ValidationError("E5_POSITIVE_CHALLENGER_EXECUTION_RESULT_REQUIRED")
    if len(matches) != 1:
        raise ValidationError("E5_POSITIVE_CHALLENGER_EXECUTION_RESULT_AMBIGUOUS")

    result_body = matches[0].get("body")
    if not isinstance(result_body, Mapping):
        raise ValidationError("E5_POSITIVE_CHALLENGER_EXECUTION_RESULT_INVALID")
    if result_body.get("status") != "SUCCESS" or result_body.get("exit_code") != 0:
        raise ValidationError("E5_POSITIVE_CHALLENGER_EXECUTION_RESULT_NOT_SUCCESSFUL")

    result_observations = result_body.get("observation_refs")
    if not isinstance(result_observations, list):
        raise ValidationError("E5_POSITIVE_CHALLENGER_EXECUTION_OBSERVATIONS_INVALID")
    bound_observations = {
        digest
        for ref in result_observations
        if (digest := _ref_digest(ref, kind="observation")) is not None
    }
    if observation_digest not in bound_observations:
        raise ValidationError("E5_POSITIVE_CHALLENGER_OBSERVATION_NOT_BOUND_TO_EXECUTION_RESULT")

    cleanup_ref = result_body.get("cleanup_result_ref")
    if cleanup_ref is not None:
        cleanup_digest = _ref_digest(cleanup_ref, kind="cleanup_result")
        if cleanup_digest is None:
            raise ValidationError("E5_POSITIVE_CHALLENGER_CLEANUP_REF_INVALID")
        cleanup = store.resolve_accepted(dict(cleanup_ref), cut)
        cleanup_body = cleanup.get("body")
        if (
            not isinstance(cleanup_body, Mapping)
            or cleanup_body.get("cleanup_status") != "CLEAN"
            or cleanup_body.get("residual_artifacts_cleared") is not True
        ):
            raise ValidationError("E5_POSITIVE_CHALLENGER_CLEANUP_NOT_CLEAN")


def validate_positive_challenger_evidence(
    store: TransactionalHistoryStore,
    cut: dict[str, Any],
    *,
    status: str,
    evidence_qualification_refs: Sequence[dict[str, Any]],
) -> None:
    """Require prior accepted qualified evidence from actual successful execution."""
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

            raw_observation_ref = observation_body.get("raw_observation_ref")
            if _ref_digest(raw_observation_ref) is None:
                raise ValidationError("E5_POSITIVE_CHALLENGER_RAW_OBSERVATION_REQUIRED")

            _require_terminal_execution_result(
                store,
                cut,
                execution_ref=execution_ref,
                observation_ref=observation_ref,
            )


__all__ = ["validate_positive_challenger_evidence"]
