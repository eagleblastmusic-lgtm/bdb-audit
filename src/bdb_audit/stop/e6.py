"""Adaptive E6 Generator (WP-E5-11 / M45 / §104 / Data Contracts §78).

Generates adaptive E6 StageSpec exclusively from an accepted StopEvaluation with E6_REQUIRED.

Normative requirements:
- Strictly inherits governing source, policy, unresolved obligations, and materiality.
- CANNOT reduce or drop requirements that caused FAIL/BLOCKED (no denominator manipulation).
- CANNOT weaken or rewrite isolation after seeing failure results.
- CANNOT launder unresolved contradictions.
- CAN add new surfaces, invariants, and obligations (preserves or strengthens).
- After E6 execution, execution must return to global STOP on the new accepted head.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
from typing import Any, Mapping, Sequence, Set

from ..core.errors import ValidationError
from ..orchestration.stages import StageSpec
from .models import StopInput, StopEvaluation


@dataclass(frozen=True)
class AdaptiveE6Spec:
    """Adaptive E6 planning context with a schema-valid canonical StageSpec projection."""

    e6_stage_spec_id: str
    source_stop_evaluation_ref: dict[str, Any]
    source_generation_ref: dict[str, Any]
    governing_policy_ref: dict[str, Any]
    trust_profile_ref: dict[str, Any]
    isolation_profile_ref: dict[str, Any]
    inherited_unresolved_obligations: tuple[dict[str, Any], ...]
    added_surfaces: tuple[dict[str, Any], ...] = ()
    added_invariants: tuple[dict[str, Any], ...] = ()
    added_obligations: tuple[dict[str, Any], ...] = ()
    unresolved_contradictions: tuple[dict[str, Any], ...] = ()
    e6_input_history_cut: dict[str, Any] = field(default_factory=dict)

    def to_stage_spec(self) -> StageSpec:
        stop_digest = str(self.source_stop_evaluation_ref.get("revision_digest", ""))
        policy_digest = str(self.governing_policy_ref.get("revision_digest", ""))
        if len(stop_digest) != 64:
            raise ValidationError("E6_SOURCE_STOP_REF_INVALID")
        if not policy_digest:
            raise ValidationError("E6_GOVERNING_POLICY_REF_INVALID")
        return StageSpec(
            stage_key="E6",
            stage_spec_revision=self.e6_stage_spec_id,
            stage_role="E6",
            stage_ordinal=6,
            purpose="Adaptive E6 work derived from an accepted E6_REQUIRED STOP result",
            predecessor_requirements=("E5",),
            required_lane_slots=("E6_PRIMARY",),
            optional_lane_slots=(),
            blind_reveal_phase_model="CONTROLLED",
            allowed_corpus_roles=(),
            forbidden_corpus_roles=(),
            coverage_obligation_policy_ref=f"POLICY_DIGEST:{policy_digest}",
            required_stage_completion_outputs=("STAGE_COMPLETED",),
            transition_policy_ref="TRANSITION_PROFILE_V1",
            stop_e6_relationship=f"SOURCE_STOP_EVALUATION:{stop_digest}",
        )

    def body(self) -> dict[str, Any]:
        """Return the executable canonical ``stage_spec`` body, not a side-channel schema."""
        return self.to_stage_spec().body()

    def digest(self) -> str:
        return self.to_stage_spec().revision_digest

    @property
    def ref(self) -> dict[str, Any]:
        return self.to_stage_spec().ref


class AdaptiveE6Generator:
    """Generates Adaptive E6 StageSpec from a StopEvaluation."""

    @staticmethod
    def generate_e6_spec(
        spec_id: str,
        stop_evaluation: StopEvaluation,
        stop_input: StopInput,
        trust_profile_ref: dict[str, Any],
        isolation_profile_ref: dict[str, Any],
        proposed_isolation_profile_ref: dict[str, Any] | None = None,
        added_surfaces: Sequence[dict[str, Any]] = (),
        added_invariants: Sequence[dict[str, Any]] = (),
        added_obligations: Sequence[dict[str, Any]] = (),
        attempted_dropped_obligation_digests: Set[str] | None = None,
        e6_input_history_cut: dict[str, Any] | None = None,
    ) -> AdaptiveE6Spec:
        # Invariant 1: E6 can ONLY be generated from explicit continuation_decision == "E6_REQUIRED"
        if stop_evaluation.continuation_decision != "E6_REQUIRED":
            raise ValidationError(
                "E6_ONLY_FROM_E6_REQUIRED",
                f"Cannot generate E6 from STOP decision '{stop_evaluation.continuation_decision}'; requires E6_REQUIRED",
            )
        if stop_evaluation.stop_input_ref.get("revision_digest") != stop_input.ref.get("revision_digest"):
            raise ValidationError(
                "E6_STOP_INPUT_BINDING_MISMATCH",
                "Accepted STOP evaluation does not bind the supplied StopInput revision",
            )

        # Invariant 2: Denominator manipulation forbidden: cannot drop unresolved obligations
        mandatory_digests = {
            r.get("revision_digest") for r in stop_input.mandatory_obligation_refs if r.get("revision_digest")
        }
        if attempted_dropped_obligation_digests and (attempted_dropped_obligation_digests & mandatory_digests):
            raise ValidationError(
                "DENOMINATOR_MANIPULATION_FORBIDDEN",
                "E6 cannot drop mandatory unresolved obligations to manipulate the denominator",
            )

        # Invariant 3: Isolation rewrite forbidden: cannot weaken isolation
        if proposed_isolation_profile_ref is not None:
            baseline_level = isolation_profile_ref.get("isolation_level", "STRICT")
            proposed_level = proposed_isolation_profile_ref.get("isolation_level", "STRICT")
            if baseline_level == "STRICT" and proposed_level != "STRICT":
                raise ValidationError(
                    "ISOLATION_REWRITE_FORBIDDEN",
                    "E6 cannot weaken baseline isolation profile after failure observation",
                )

        # Invariant 4: Contradiction laundering forbidden: unresolved contradictions must be carried forward
        unresolved_contradictions = tuple(stop_input.contradiction_refs)

        hcut = e6_input_history_cut or stop_input.input_history_cut

        return AdaptiveE6Spec(
            e6_stage_spec_id=spec_id,
            source_stop_evaluation_ref=dict(stop_evaluation.ref),
            source_generation_ref=dict(stop_input.source_generation_ref),
            governing_policy_ref=dict(stop_input.governing_policy_ref),
            trust_profile_ref=dict(trust_profile_ref),
            isolation_profile_ref=dict(isolation_profile_ref),
            inherited_unresolved_obligations=tuple(stop_input.mandatory_obligation_refs),
            added_surfaces=tuple(added_surfaces),
            added_invariants=tuple(added_invariants),
            added_obligations=tuple(added_obligations),
            unresolved_contradictions=unresolved_contradictions,
            e6_input_history_cut=dict(hcut),
        )

    @staticmethod
    def verify_post_e6_return_to_stop(new_head_cut: Mapping[str, Any], previous_cut: Mapping[str, Any]) -> None:
        """Verify that after E6 completion, control flow returns to global STOP on a newer accepted cut."""
        new_seq = new_head_cut.get("accepted_head_seq", new_head_cut.get("commit_seq", 0))
        prev_seq = previous_cut.get("accepted_head_seq", previous_cut.get("commit_seq", 0))
        if type(new_seq) is not int or type(prev_seq) is not int or new_seq <= prev_seq:
            raise ValidationError(
                "POST_E6_MUST_ADVANCE_HEAD",
                f"Post-E6 evaluation requires advanced head cut (new {new_seq} <= prev {prev_seq})",
            )


def reconstruct_stop_input(body: Mapping[str, Any]) -> StopInput:
    """Rehydrate an accepted StopInput body without inventing authority fields."""
    return StopInput(**dict(body))


def reconstruct_stop_evaluation(body: Mapping[str, Any]) -> StopEvaluation:
    """Rehydrate an accepted StopEvaluation body for exact binding checks."""
    return StopEvaluation(**dict(body))


__all__ = [
    "AdaptiveE6Generator",
    "AdaptiveE6Spec",
    "reconstruct_stop_evaluation",
    "reconstruct_stop_input",
]
