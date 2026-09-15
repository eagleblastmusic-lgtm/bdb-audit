"""Accepted-history adapter for operational Adaptive E6 rounds.

This module does not create a second state authority. It derives the next E6
StageSpec exclusively from the current accepted history cut and the latest
accepted STOP decision.
"""
from __future__ import annotations

import hashlib
from typing import Any, Mapping

from ..core.errors import ValidationError
from ..history.store import TransactionalHistoryStore
from ..orchestration.stages import StageSpec
from ..workflow.read_models import current_accepted_cut
from .e6 import AdaptiveE6Generator, reconstruct_stop_evaluation, reconstruct_stop_input


def _digest(ref: object) -> str | None:
    if not isinstance(ref, Mapping):
        return None
    value = ref.get("revision_digest")
    return value if isinstance(value, str) and value else None


def _completed_stage_spec_digests(store: TransactionalHistoryStore, cut: Mapping[str, Any]) -> set[str]:
    completed: set[str] = set()
    for row in store.accepted_records("stage_completion", dict(cut)):
        if row["body"].get("completion_predicate_result") != "STAGE_COMPLETED":
            continue
        digest = _digest(row["body"].get("stage_spec_ref"))
        if digest is not None:
            completed.add(digest)
    return completed


def build_next_adaptive_e6_stage_spec(store: TransactionalHistoryStore) -> StageSpec:
    """Derive the next immutable E6 StageSpec from the latest accepted E6_REQUIRED STOP."""
    cut = current_accepted_cut(store)
    head = store.head()
    if head is None:
        raise ValidationError("CAMPAIGN_NOT_FOUND")

    stop_rows = list(store.accepted_records("stop_evaluation", cut))
    if not stop_rows:
        raise ValidationError("E6_REQUIRES_ACCEPTED_STOP_EVALUATION")
    stop_row = stop_rows[-1]
    stop_body = stop_row["body"]
    if stop_body.get("continuation_decision") != "E6_REQUIRED":
        raise ValidationError(
            "E6_REQUIRES_ACCEPTED_E6_REQUIRED",
            f"Latest accepted STOP decision is {stop_body.get('continuation_decision')!r}",
        )
    stop_ref = stop_row["ref"]
    stop_digest = _digest(stop_ref)
    if stop_digest is None:
        raise ValidationError("E6_SOURCE_STOP_REF_INVALID")

    stop_input_ref = stop_body.get("stop_input_ref")
    if not isinstance(stop_input_ref, dict):
        raise ValidationError("E6_STOP_INPUT_REF_MISSING")
    stop_input_row = store.resolve_accepted(stop_input_ref, cut)
    stop_input = reconstruct_stop_input(stop_input_row["body"])
    stop_evaluation = reconstruct_stop_evaluation(stop_body)
    if stop_input.campaign_id != head.campaign_id:
        raise ValidationError("E6_CAMPAIGN_BINDING_MISMATCH")
    if stop_input.evaluation_context not in {"FINAL_POST_E5", "POST_E6"}:
        raise ValidationError("E6_STOP_CONTEXT_INVALID", stop_input.evaluation_context)

    genesis_rows = list(store.accepted_records("campaign_genesis", cut))
    if len(genesis_rows) != 1:
        raise ValidationError("E6_CAMPAIGN_GENESIS_INVALID")
    genesis = genesis_rows[0]["body"]
    current_source_ref = genesis.get("source_generation_ref")
    if _digest(current_source_ref) != _digest(stop_input.source_generation_ref):
        raise ValidationError("E6_SOURCE_GENERATION_DRIFT")
    trust_profile_ref = genesis.get("trust_profile_ref")
    if not isinstance(trust_profile_ref, dict):
        raise ValidationError("E6_TRUST_PROFILE_REF_MISSING")

    existing_e6 = [
        row for row in store.accepted_records("stage_spec", cut)
        if row["body"].get("stage_key") == "E6"
    ]
    source_relationship = f"SOURCE_STOP_EVALUATION:{stop_digest}"
    if any(row["body"].get("stop_e6_relationship") == source_relationship for row in existing_e6):
        raise ValidationError(
            "E6_STOP_ALREADY_MATERIALIZED",
            "An E6 StageSpec already exists for the latest accepted STOP decision",
        )

    completed_spec_digests = _completed_stage_spec_digests(store, cut)
    incomplete_prior = [
        row for row in existing_e6
        if _digest(row.get("ref")) not in completed_spec_digests
    ]
    if incomplete_prior:
        raise ValidationError(
            "PREVIOUS_E6_ROUND_NOT_COMPLETED",
            "Cannot materialize another E6 round while a prior E6 StageSpec is incomplete",
        )

    round_number = len(existing_e6) + 1
    spec_id = f"adaptive-{round_number}-{stop_digest[:12]}"
    isolation_profile_ref = {
        "kind": "isolation_profile",
        "revision_digest": hashlib.sha256(b"BDB_E6_ISOLATION_STRICT_V1").hexdigest(),
        "isolation_level": "STRICT",
    }
    adaptive = AdaptiveE6Generator.generate_e6_spec(
        spec_id=spec_id,
        stop_evaluation=stop_evaluation,
        stop_input=stop_input,
        trust_profile_ref=dict(trust_profile_ref),
        isolation_profile_ref=isolation_profile_ref,
        e6_input_history_cut=dict(cut),
    )
    spec = adaptive.to_stage_spec()
    if spec.stop_e6_relationship != source_relationship:
        raise ValidationError("E6_STOP_BINDING_INTERNAL_MISMATCH")
    return spec


__all__ = ["build_next_adaptive_e6_stage_spec"]
