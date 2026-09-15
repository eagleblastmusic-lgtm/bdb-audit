"""Deterministic StopInput Builder from Verified Accepted History (B02 / §103).

Constructs an immutable StopInput derived strictly from accepted history records,
never from unadmitted proposals or in-memory caches.
"""
from __future__ import annotations

from typing import Any, Sequence

from ..core.errors import ValidationError
from ..history.selection import chronological_accepted_records, latest_accepted_record
from ..history.store import TransactionalHistoryStore
from .models import StopInput


_REQUIRED_BASELINE_CHALLENGER_TYPES = (
    "FALSE_POSITIVE_SKEPTIC",
    "FALSE_NEGATIVE_HUNTER",
)


def _ref(kind: str, digest: str, ref_class: str = "CONTENT_OR_PRIOR") -> dict[str, Any]:
    return {
        "kind": kind,
        "revision_digest": digest,
        "digest_profile": "BDB-OBJECT-DIGEST-1",
        "schema_revision_ref": f"BDB_SCHEMA_REGISTRY::{kind}/1",
        "ref_class": ref_class,
    }


def _revision_digest(ref: object) -> str | None:
    if not isinstance(ref, dict):
        return None
    digest = ref.get("revision_digest")
    return digest if isinstance(digest, str) and digest else None


def _accepted_cut_key(value: object) -> tuple[str, int, str] | None:
    if not isinstance(value, dict):
        return None
    campaign_id = value.get("campaign_id")
    seq = value.get("accepted_head_seq")
    accepted_hash = value.get("accepted_head_hash")
    if not isinstance(campaign_id, str) or not campaign_id:
        return None
    if type(seq) is not int or seq < 0:
        return None
    if not isinstance(accepted_hash, str) or not accepted_hash:
        return None
    return campaign_id, seq, accepted_hash


def select_current_baseline_challenger_refs(
    candidate_record: dict[str, Any] | None,
    assignment_records: Sequence[dict[str, Any]],
    result_records: Sequence[dict[str, Any]],
) -> tuple[dict[str, Any], ...]:
    """Return one fresh accepted result for each required baseline challenger role."""
    if candidate_record is None:
        return ()
    candidate_ref = candidate_record.get("ref")
    candidate_body = candidate_record.get("body")
    if not isinstance(candidate_body, dict):
        return ()
    candidate_digest = _revision_digest(candidate_ref)
    candidate_cut = _accepted_cut_key(candidate_body.get("candidate_input_history_cut"))
    if candidate_digest is None or candidate_cut is None:
        return ()
    candidate_campaign, candidate_seq, _ = candidate_cut

    assignments: dict[str, tuple[str, int, dict[str, Any]]] = {}
    for row in assignment_records:
        body = row.get("body")
        ref = row.get("ref")
        if not isinstance(body, dict) or not isinstance(ref, dict):
            continue
        if _revision_digest(body.get("candidate_assurance_case_ref")) != candidate_digest:
            continue
        role = body.get("challenger_type")
        if role not in _REQUIRED_BASELINE_CHALLENGER_TYPES:
            continue
        cut = _accepted_cut_key(body.get("assignment_input_history_cut"))
        digest = _revision_digest(ref)
        if cut is None or digest is None:
            continue
        campaign_id, seq, _ = cut
        if campaign_id != candidate_campaign or seq < candidate_seq:
            continue
        assignments[digest] = (str(role), seq, ref)

    eligible_by_role: dict[str, list[tuple[str, str, dict[str, Any]]]] = {
        role: [] for role in _REQUIRED_BASELINE_CHALLENGER_TYPES
    }
    for row in result_records:
        body = row.get("body")
        ref = row.get("ref")
        if not isinstance(body, dict) or not isinstance(ref, dict):
            continue
        if body.get("status") != "NO_MATERIAL_COUNTEREVIDENCE":
            continue
        if _revision_digest(body.get("candidate_assurance_case_ref")) != candidate_digest:
            continue
        assignment_digest = _revision_digest(body.get("challenge_assignment_ref"))
        if assignment_digest is None or assignment_digest not in assignments:
            continue
        role, assignment_seq, _ = assignments[assignment_digest]
        result_cut = _accepted_cut_key(body.get("result_input_history_cut"))
        result_digest = _revision_digest(ref)
        if result_cut is None or result_digest is None:
            continue
        campaign_id, result_seq, _ = result_cut
        if campaign_id != candidate_campaign or result_seq < assignment_seq:
            continue
        eligible_by_role[role].append((assignment_digest, result_digest, ref))

    selected: list[dict[str, Any]] = []
    selected_assignments: set[str] = set()
    selected_results: set[str] = set()
    for role in _REQUIRED_BASELINE_CHALLENGER_TYPES:
        candidates = eligible_by_role[role]
        if len(candidates) != 1:
            return ()
        assignment_digest, result_digest, ref = candidates[0]
        if assignment_digest in selected_assignments or result_digest in selected_results:
            return ()
        selected_assignments.add(assignment_digest)
        selected_results.add(result_digest)
        selected.append(dict(ref))
    return tuple(selected)


def _same_ref_set(left: Sequence[dict[str, Any]], right: Sequence[dict[str, Any]]) -> bool:
    left_digests = sorted(d for d in (_revision_digest(ref) for ref in left) if d is not None)
    right_digests = sorted(d for d in (_revision_digest(ref) for ref in right) if d is not None)
    return len(left_digests) == len(left) and len(right_digests) == len(right) and left_digests == right_digests


class StopInputBuilder:
    """Extracts and builds an exact reproducible StopInput from an accepted cut."""

    @classmethod
    def build_from_store(
        cls,
        store: TransactionalHistoryStore,
        evaluation_context: str = "FINAL_POST_E5",
        candidate_assurance_case_ref: dict[str, Any] | None = None,
        challenger_refs: Sequence[dict[str, Any]] = (),
        unknown_blocked_summary: dict[str, Any] | None = None,
        e6_plan_approved: bool = False,
    ) -> StopInput:
        from ..workflow.read_models import current_accepted_cut

        head = store.head()
        if head is None:
            raise ValidationError("EMPTY_STORE", "Cannot build StopInput on empty store")
        cut = current_accepted_cut(store)

        sg_record = latest_accepted_record(store, "source_generation", cut)
        if sg_record is None:
            si_record = latest_accepted_record(store, "source_identity", cut)
            sg_ref = si_record["ref"] if si_record is not None else _ref("source_generation", "0" * 64)
        else:
            sg_ref = sg_record["ref"]

        stage_specs = store.accepted_records("stage_spec", cut)
        stage_completions = chronological_accepted_records(store, "stage_completion", cut)

        spec_digest_to_key = {
            row["ref"]["revision_digest"]: row["body"].get("stage_key")
            for row in stage_specs
            if row["body"].get("stage_key")
        }

        completed_stage_keys = set()
        for row in stage_completions:
            spec_ref = row["body"].get("stage_spec_ref")
            if isinstance(spec_ref, dict):
                sk = spec_digest_to_key.get(spec_ref.get("revision_digest"))
                if sk:
                    completed_stage_keys.add(sk)
            sk_direct = row["body"].get("stage_key", row["body"].get("stage_role"))
            if sk_direct:
                completed_stage_keys.add(sk_direct)

        completed_stage_refs = [row["ref"] for row in stage_completions]
        required_stage_spec_refs = [row["ref"] for row in stage_specs]
        pending_required_stage_refs = [
            row["ref"]
            for row in stage_specs
            if row["body"].get("stage_key") not in completed_stage_keys
        ]

        cac_records = chronological_accepted_records(store, "candidate_assurance_case", cut)
        current_candidate_record = cac_records[-1] if cac_records else None
        current_candidate_ref = current_candidate_record["ref"] if current_candidate_record is not None else None
        if candidate_assurance_case_ref is not None:
            if current_candidate_ref is None or _revision_digest(candidate_assurance_case_ref) != _revision_digest(current_candidate_ref):
                raise ValidationError(
                    "STOP_CANDIDATE_REF_NOT_CURRENT",
                    "Explicit candidate assurance case is not the latest accepted candidate revision",
                )
        candidate_assurance_case_ref = dict(current_candidate_ref) if isinstance(current_candidate_ref, dict) else None

        assignment_records = chronological_accepted_records(store, "challenger_assignment", cut)
        result_records = chronological_accepted_records(store, "challenger_result", cut)
        current_challenger_refs = select_current_baseline_challenger_refs(
            current_candidate_record,
            assignment_records,
            result_records,
        )
        if challenger_refs and not _same_ref_set(challenger_refs, current_challenger_refs):
            raise ValidationError(
                "STOP_CHALLENGER_REFS_NOT_CURRENT_BASELINE_PAIR",
                "Explicit challenger refs do not equal the current accepted baseline challenger pair",
            )
        challenger_refs = current_challenger_refs

        invalidation_records = store.accepted_records("evidence_invalidation", cut)
        contradiction_records = store.accepted_records("contradiction", cut)
        residual_risk_records = store.accepted_records("residual_risk", cut)
        obligation_records = store.accepted_records("coverage_obligation", cut)
        qualification_records = store.accepted_records("obligation_qualification", cut)

        inv_record = latest_accepted_record(store, "inventory_revision", cut)
        inv_ref = inv_record["ref"] if inv_record is not None else _ref(
            "inventory_revision", "0" * 64, ref_class="CONTENT_OR_PRIOR"
        )

        summary = unknown_blocked_summary or {
            "unknown_surfaces_count": 0,
            "is_blocked": False,
            "unresolved_obligations_count": len(pending_required_stage_refs),
        }

        pol_ref = _ref("policy_revision", "1" * 64, ref_class="HISTORY_CONTEXT_BINDING")
        spec_ref = _ref("spec_revision", "1" * 64, ref_class="HISTORY_CONTEXT_BINDING")
        prof_ref = _ref("external_profile_ref", "1" * 64, ref_class="HISTORY_CONTEXT_BINDING")

        req_specs = [dict(r, ref_class="HISTORY_CONTEXT_BINDING") for r in required_stage_spec_refs] if required_stage_spec_refs else [spec_ref]
        pend_specs = [dict(r, ref_class="HISTORY_CONTEXT_BINDING") for r in pending_required_stage_refs]

        from .models import Snapshot
        direct_refs = [
            sg_ref,
            inv_ref,
            *[r["ref"] for r in obligation_records],
            *[r["ref"] for r in qualification_records],
            *completed_stage_refs,
            *req_specs,
        ]
        snapshot = Snapshot(
            snapshot_type="STOP_INPUT_STATE_CAPTURE",
            as_of_head=cut,
            projection_code_revision="BDB_V2_SNAPSHOT_PROJECTION_1",
            projection_input_refs=direct_refs,
            snapshot_artifact_ref={
                "kind": "raw_artifact_ref",
                "revision_digest": "0" * 64,
                "digest_profile": "BDB-OBJECT-DIGEST-1",
                "schema_revision_ref": "BDB_TARGET/raw_artifact_ref",
                "ref_class": "CONTENT_OR_PRIOR",
            },
        )
        snapshot_obj = snapshot.as_object()

        effort_result = completed_stage_refs[-1] if completed_stage_refs else sg_ref

        stop_input = StopInput(
            campaign_id=head.campaign_id,
            source_generation_ref=sg_ref,
            input_history_cut=cut,
            evaluation_context=evaluation_context,
            governing_policy_ref=pol_ref,
            policy_spec_refs=[spec_ref],
            evaluator_revision_ref=spec_ref,
            required_stage_set_ref=prof_ref,
            required_stage_spec_refs=req_specs,
            completed_stage_refs=completed_stage_refs,
            pending_required_stage_refs=pend_specs,
            stop_input_snapshot_ref=snapshot.ref,
            inventory_revision_ref=inv_ref,
            mandatory_obligation_refs=[r["ref"] for r in obligation_records],
            current_obligation_qualification_refs=[r["ref"] for r in qualification_records],
            evidence_invalidation_refs=[r["ref"] for r in invalidation_records],
            contradiction_refs=[r["ref"] for r in contradiction_records],
            residual_risk_refs=[r["ref"] for r in residual_risk_records],
            evidence_invalidation_state={"invalidated_count": len(invalidation_records)},
            release_policy_ref=pol_ref,
            effort_profile_ref=prof_ref,
            effort_results_ref=effort_result,
            unknown_blocked_summary=summary,
            candidate_assurance_case_ref=candidate_assurance_case_ref,
            challenger_refs=challenger_refs,
        )
        object.__setattr__(stop_input, "_snapshot_obj", snapshot_obj)
        return stop_input


__all__ = ["StopInputBuilder", "select_current_baseline_challenger_refs"]
