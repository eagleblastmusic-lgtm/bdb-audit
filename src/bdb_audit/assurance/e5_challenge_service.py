"""Operational E5A/E5B assurance lifecycle over accepted history.

R5.3 requires an acyclic temporal sequence:
CandidateAssuranceCase -> challenger assignments -> challenger results -> E5 StageCompletion.
This service materializes the first three steps as separate accepted commits. It does
not synthesize a positive challenger outcome and it does not complete E5.
"""
from __future__ import annotations

import hashlib
import json
import time
from typing import Any, Mapping, Sequence

from .candidate_case import CandidateAssuranceCase, CandidateAssuranceCaseBuilder
from .candidate_projection import current_finding_adjudication_pairs
from .challenger import ChallengerAssignment, ChallengerResult, REQUIRED_BASELINE_CHALLENGER_TYPES
from .challenger_evidence import validate_positive_challenger_evidence
from ..coordinator import Coordinator
from ..core.errors import ValidationError
from ..core.ids import new_id
from ..history.objects import CanonicalObject, CommandEnvelope
from ..history.selection import chronological_accepted_records, latest_accepted_record
from ..history.store import TransactionalHistoryStore


def _digest(ref: object) -> str | None:
    if not isinstance(ref, Mapping):
        return None
    value = ref.get("revision_digest")
    return value if isinstance(value, str) and value else None


def _candidate_from_body(body: Mapping[str, Any]) -> CandidateAssuranceCase:
    return CandidateAssuranceCase(
        candidate_assurance_case_id=str(body["candidate_assurance_case_id"]),
        campaign_ref=dict(body["campaign_ref"]),
        source_generation_ref=dict(body["source_generation_ref"]),
        candidate_input_history_cut=dict(body["candidate_input_history_cut"]),
        scope_inventory_ref=dict(body["scope_inventory_ref"]),
        coverage_obligation_refs=tuple(dict(r) for r in body.get("coverage_obligation_refs", ())),
        coverage_obligation_qualification_refs=tuple(
            dict(r) for r in body.get("coverage_obligation_qualification_refs", ())
        ),
        finding_claim_revision_refs=tuple(dict(r) for r in body.get("finding_claim_revision_refs", ())),
        finding_adjudication_refs=tuple(dict(r) for r in body.get("finding_adjudication_refs", ())),
        contradiction_refs=tuple(dict(r) for r in body.get("contradiction_refs", ())),
        evidence_qualification_refs=tuple(dict(r) for r in body.get("evidence_qualification_refs", ())),
        residual_risk_refs=tuple(dict(r) for r in body.get("residual_risk_refs", ())),
        assurance_claim_set_ref=dict(body["assurance_claim_set_ref"]),
        coverage_obligation_summary_ref=(
            dict(body["coverage_obligation_summary_ref"])
            if isinstance(body.get("coverage_obligation_summary_ref"), Mapping)
            else None
        ),
    )


def _assignment_from_body(body: Mapping[str, Any]) -> ChallengerAssignment:
    return ChallengerAssignment(
        challenge_assignment_id=str(body["challenge_assignment_id"]),
        candidate_assurance_case_ref=dict(body["candidate_assurance_case_ref"]),
        challenger_type=str(body["challenger_type"]),
        challenge_scope=str(body["challenge_scope"]),
        challenge_policy_ref=dict(body["challenge_policy_ref"]),
        executor_profile_ref=dict(body["executor_profile_ref"]),
        assignment_input_history_cut=dict(body["assignment_input_history_cut"]),
        forbidden_prior_result_refs=tuple(dict(r) for r in body.get("forbidden_prior_result_refs", ())),
    )


def _result_from_body(body: Mapping[str, Any]) -> ChallengerResult:
    return ChallengerResult(
        challenger_result_id=str(body["challenger_result_id"]),
        challenge_assignment_ref=dict(body["challenge_assignment_ref"]),
        candidate_assurance_case_ref=dict(body["candidate_assurance_case_ref"]),
        result_input_history_cut=dict(body["result_input_history_cut"]),
        status=str(body["status"]),
        challenged_claim_or_scope_refs=tuple(dict(r) for r in body.get("challenged_claim_or_scope_refs", ())),
        counterclaim_refs=tuple(dict(r) for r in body.get("counterclaim_refs", ())),
        evidence_qualification_refs=tuple(dict(r) for r in body.get("evidence_qualification_refs", ())),
        reason_codes=tuple(str(v) for v in body.get("reason_codes", ())),
    )


class E5ChallengeService:
    """Materialize E5A candidate and E5B challenge artifacts without temporal collapse."""

    def __init__(self, store: TransactionalHistoryStore):
        self.store = store
        self.coordinator = Coordinator(store)

    def _cut(self) -> dict[str, Any]:
        from ..workflow.read_models import current_accepted_cut

        return current_accepted_cut(self.store)

    def _status(self) -> dict[str, Any]:
        from ..workflow.read_models import campaign_status

        return campaign_status(self.store, lambda value: str(value).upper())

    def _accept(self, scope: str, objects: Sequence[CanonicalObject]) -> dict[str, Any]:
        head = self.store.head()
        if head is None:
            raise ValidationError("EMPTY_STORE")
        conn = self.store._connect()
        try:
            row = conn.execute("SELECT body FROM commits WHERE commit_hash=?", (head.commit_hash,)).fetchone()
            prior_commit = json.loads(row[0]) if row else {}
        finally:
            conn.close()
        token = hashlib.sha256(
            f"{head.campaign_id}:{scope}:{head.commit_seq + 1}:{int(time.time())}".encode("utf-8")
        ).hexdigest()
        command_id = f"command_{token[:8]}-{token[8:12]}-4{token[13:16]}-8{token[17:20]}-{token[20:32]}"
        command = CommandEnvelope(
            command_id=command_id,
            command_kind="RECORD_ASSURANCE_DECISION",
            actor_ref=prior_commit.get("actor_ref", "installation-owner"),
            expected_parent_head={"tag": "ACCEPTED_HEAD_REF", **head.as_dict()},
            governing_policy_ref=prior_commit.get("governing_policy_ref", "pin:initial_governing_policy_ref"),
            governing_spec_refs=tuple(
                prior_commit.get("governing_spec_refs", ("pin:initial_transition_profile_ref",))
            ),
            idempotency_scope=f"{scope}:{':'.join(obj.digest[:12] for obj in objects)}",
            campaign_ref=head.campaign_id,
        )
        result = self.coordinator.accept(command, immutable_objects=list(objects))
        return {
            "commit_seq": result.head.commit_seq,
            "commit_hash": result.head.commit_hash,
        }

    def freeze_candidate(self) -> dict[str, Any]:
        """Accept one frozen CandidateAssuranceCase after E1-E4 and prepared E5."""
        head = self.store.head()
        if head is None:
            raise ValidationError("EMPTY_STORE")
        status = self._status()
        if "E4" not in status["stages_completed"]:
            raise ValidationError("E5_CANDIDATE_REQUIRES_E4_COMPLETION")
        if "E5" not in status["stages_prepared"]:
            raise ValidationError("E5_CANDIDATE_REQUIRES_PREPARED_E5")
        if "E5" in status["stages_completed"]:
            raise ValidationError("E5_ALREADY_COMPLETED")

        cut = self._cut()
        sg = latest_accepted_record(self.store, "source_generation", cut)
        inventory = latest_accepted_record(self.store, "inventory_revision", cut)
        if sg is None:
            raise ValidationError("E5_CANDIDATE_SOURCE_GENERATION_REQUIRED")
        if inventory is None:
            raise ValidationError("E5_CANDIDATE_INVENTORY_REQUIRED")

        campaign_ref = {
            "kind": "campaign_ref",
            "revision_digest": hashlib.sha256(head.campaign_id.encode("utf-8")).hexdigest(),
            "digest_profile": "BDB-OBJECT-DIGEST-1",
            "schema_revision_ref": "BDB_TARGET/campaign_ref",
            "ref_class": "PRIOR_ACCEPTED_ONLY",
        }
        claim_set_ref = {
            "kind": "assurance_claim_set_ref",
            "revision_digest": "0" * 64,
            "digest_profile": "BDB-OBJECT-DIGEST-1",
            "schema_revision_ref": "BDB_TARGET/assurance_claim_set_ref",
            "ref_class": "CONTENT_OR_PRIOR",
        }
        builder = CandidateAssuranceCaseBuilder(
            case_id=new_id("candidate_assurance_case"),
            campaign_ref=campaign_ref,
            source_generation_ref=dict(sg["ref"]),
            candidate_input_history_cut=cut,
            scope_inventory_ref=dict(inventory["ref"]),
            assurance_claim_set_ref=claim_set_ref,
        )
        obligations = chronological_accepted_records(self.store, "coverage_obligation", cut)
        qualifications = chronological_accepted_records(self.store, "obligation_qualification", cut)
        qual_by_obligation = {
            _digest(row["body"].get("coverage_obligation_ref")): row["ref"]
            for row in qualifications
            if _digest(row["body"].get("coverage_obligation_ref")) is not None
        }
        for row in obligations:
            builder.add_coverage_obligation(
                dict(row["ref"]),
                dict(qual_by_obligation[_digest(row["ref"])]) if _digest(row["ref"]) in qual_by_obligation else None,
            )
        finding_rows = chronological_accepted_records(self.store, "finding_claim_revision", cut)
        adjudication_rows = chronological_accepted_records(self.store, "finding_adjudication_decision", cut)
        for claim_ref, adjudication_ref in current_finding_adjudication_pairs(
            finding_rows,
            adjudication_rows,
        ):
            builder.add_finding(claim_ref, adjudication_ref)
        for row in chronological_accepted_records(self.store, "contradiction", cut):
            builder.add_contradiction(dict(row["ref"]))
        for row in chronological_accepted_records(self.store, "evidence_qualification_assessment", cut):
            builder.add_evidence_qualification(dict(row["ref"]))
        for row in chronological_accepted_records(self.store, "residual_risk", cut):
            builder.add_residual_risk(dict(row["ref"]))

        candidate = builder.build()
        obj = CanonicalObject(
            "candidate_assurance_case",
            candidate.body(),
            logical_id=candidate.candidate_assurance_case_id,
        )
        accepted = self._accept("e5_candidate", [obj])
        return {
            "status": "SUCCESS",
            "candidate_assurance_case_digest": obj.digest,
            **accepted,
        }

    def assign_required_challengers(self) -> dict[str, Any]:
        """Accept the skeptic+hunter assignments on a cut after the frozen candidate."""
        cut = self._cut()
        candidate_row = latest_accepted_record(self.store, "candidate_assurance_case", cut)
        if candidate_row is None:
            raise ValidationError("E5_CHALLENGER_CANDIDATE_REQUIRED")
        candidate_digest = _digest(candidate_row["ref"])
        existing = [
            row
            for row in chronological_accepted_records(self.store, "challenger_assignment", cut)
            if _digest(row["body"].get("candidate_assurance_case_ref")) == candidate_digest
        ]
        if existing:
            raise ValidationError("E5_CHALLENGERS_ALREADY_ASSIGNED")

        candidate_ref = dict(candidate_row["ref"], ref_class="PRIOR_ACCEPTED_ONLY")
        policy_ref = {
            "kind": "policy_revision",
            "revision_digest": "1" * 64,
            "digest_profile": "BDB-OBJECT-DIGEST-1",
            "schema_revision_ref": "BDB_TARGET/policy_revision",
            "ref_class": "HISTORY_CONTEXT_BINDING",
        }
        executor_ref = {
            "kind": "executor_spec",
            "revision_digest": "2" * 64,
            "digest_profile": "BDB-OBJECT-DIGEST-1",
            "schema_revision_ref": "BDB_TARGET/executor_spec",
            "ref_class": "HISTORY_CONTEXT_BINDING",
        }
        objects: list[CanonicalObject] = []
        digests: dict[str, str] = {}
        for role in ("FALSE_POSITIVE_SKEPTIC", "FALSE_NEGATIVE_HUNTER"):
            assignment = ChallengerAssignment(
                challenge_assignment_id=new_id("challenger_assignment"),
                candidate_assurance_case_ref=candidate_ref,
                challenger_type=role,
                challenge_scope="ALL",
                challenge_policy_ref=policy_ref,
                executor_profile_ref=executor_ref,
                assignment_input_history_cut=cut,
            )
            obj = CanonicalObject(
                "challenger_assignment",
                assignment.body(),
                logical_id=assignment.challenge_assignment_id,
            )
            objects.append(obj)
            digests[role] = obj.digest
        accepted = self._accept("e5_challenger_assignments", objects)
        return {"status": "SUCCESS", "assignment_digests": digests, **accepted}

    def record_required_challenger_results(
        self,
        *,
        skeptic_status: str,
        hunter_status: str,
        skeptic_evidence_qualification_refs: Sequence[dict[str, Any]] = (),
        hunter_evidence_qualification_refs: Sequence[dict[str, Any]] = (),
    ) -> dict[str, Any]:
        """Accept explicit challenger outcomes on a cut after their assignments.

        Statuses are mandatory caller inputs; this service never defaults them to a positive
        outcome. Evidence refs, when supplied, must already resolve on the assigned cut.
        """
        cut = self._cut()
        candidate_row = latest_accepted_record(self.store, "candidate_assurance_case", cut)
        if candidate_row is None:
            raise ValidationError("E5_CHALLENGER_CANDIDATE_REQUIRED")
        candidate_digest = _digest(candidate_row["ref"])
        assignments = [
            row
            for row in chronological_accepted_records(self.store, "challenger_assignment", cut)
            if _digest(row["body"].get("candidate_assurance_case_ref")) == candidate_digest
        ]
        by_role: dict[str, dict[str, Any]] = {}
        for row in assignments:
            role = row["body"].get("challenger_type")
            if role in REQUIRED_BASELINE_CHALLENGER_TYPES:
                if role in by_role:
                    raise ValidationError("E5_CHALLENGER_ASSIGNMENT_AMBIGUOUS", str(role))
                by_role[str(role)] = row
        if set(by_role) != REQUIRED_BASELINE_CHALLENGER_TYPES:
            raise ValidationError("E5_REQUIRED_CHALLENGER_ASSIGNMENTS_MISSING")

        prior_results = [
            row
            for row in chronological_accepted_records(self.store, "challenger_result", cut)
            if _digest(row["body"].get("candidate_assurance_case_ref")) == candidate_digest
        ]
        if prior_results:
            raise ValidationError("E5_CHALLENGER_RESULTS_ALREADY_RECORDED")

        for ref in (*skeptic_evidence_qualification_refs, *hunter_evidence_qualification_refs):
            self.store.resolve_accepted(ref, cut)
        validate_positive_challenger_evidence(
            self.store,
            cut,
            status=skeptic_status,
            evidence_qualification_refs=skeptic_evidence_qualification_refs,
        )
        validate_positive_challenger_evidence(
            self.store,
            cut,
            status=hunter_status,
            evidence_qualification_refs=hunter_evidence_qualification_refs,
        )

        candidate_ref = dict(candidate_row["ref"], ref_class="PRIOR_ACCEPTED_ONLY")
        inputs = (
            ("FALSE_POSITIVE_SKEPTIC", skeptic_status, skeptic_evidence_qualification_refs),
            ("FALSE_NEGATIVE_HUNTER", hunter_status, hunter_evidence_qualification_refs),
        )
        objects: list[CanonicalObject] = []
        digests: dict[str, str] = {}
        for role, result_status, evidence_refs in inputs:
            assignment_row = by_role[role]
            assignment_ref = dict(assignment_row["ref"], ref_class="PRIOR_ACCEPTED_ONLY")
            result = ChallengerResult(
                challenger_result_id=new_id("challenger_result"),
                challenge_assignment_ref=assignment_ref,
                candidate_assurance_case_ref=candidate_ref,
                result_input_history_cut=cut,
                status=result_status,
                evidence_qualification_refs=tuple(dict(ref) for ref in evidence_refs),
            )
            obj = CanonicalObject(
                "challenger_result",
                result.body(),
                logical_id=result.challenger_result_id,
            )
            objects.append(obj)
            digests[role] = obj.digest
        accepted = self._accept("e5_challenger_results", objects)
        return {"status": "SUCCESS", "result_digests": digests, **accepted}

    def current_pair(self) -> tuple[
        CandidateAssuranceCase,
        ChallengerAssignment,
        ChallengerAssignment,
        ChallengerResult,
        ChallengerResult,
    ]:
        """Resolve the exact latest candidate and unique baseline assignment/result pair."""
        cut = self._cut()
        candidate_row = latest_accepted_record(self.store, "candidate_assurance_case", cut)
        if candidate_row is None:
            raise ValidationError("E5_CHALLENGER_CANDIDATE_REQUIRED")
        candidate_digest = _digest(candidate_row["ref"])
        assignments = [
            row
            for row in chronological_accepted_records(self.store, "challenger_assignment", cut)
            if _digest(row["body"].get("candidate_assurance_case_ref")) == candidate_digest
        ]
        results = [
            row
            for row in chronological_accepted_records(self.store, "challenger_result", cut)
            if _digest(row["body"].get("candidate_assurance_case_ref")) == candidate_digest
        ]
        asgn_by_role: dict[str, dict[str, Any]] = {}
        for row in assignments:
            role = str(row["body"].get("challenger_type"))
            if role in REQUIRED_BASELINE_CHALLENGER_TYPES:
                if role in asgn_by_role:
                    raise ValidationError("E5_CHALLENGER_ASSIGNMENT_AMBIGUOUS", role)
                asgn_by_role[role] = row
        if set(asgn_by_role) != REQUIRED_BASELINE_CHALLENGER_TYPES:
            raise ValidationError("E5_REQUIRED_CHALLENGER_ASSIGNMENTS_MISSING")

        result_by_role: dict[str, dict[str, Any]] = {}
        assignment_role_by_digest = {
            _digest(row["ref"]): role for role, row in asgn_by_role.items()
        }
        for row in results:
            role = assignment_role_by_digest.get(_digest(row["body"].get("challenge_assignment_ref")))
            if role is None:
                continue
            if role in result_by_role:
                raise ValidationError("E5_CHALLENGER_RESULT_AMBIGUOUS", role)
            result_by_role[role] = row
        if set(result_by_role) != REQUIRED_BASELINE_CHALLENGER_TYPES:
            raise ValidationError("E5_REQUIRED_CHALLENGER_RESULTS_MISSING")

        return (
            _candidate_from_body(candidate_row["body"]),
            _assignment_from_body(asgn_by_role["FALSE_POSITIVE_SKEPTIC"]["body"]),
            _assignment_from_body(asgn_by_role["FALSE_NEGATIVE_HUNTER"]["body"]),
            _result_from_body(result_by_role["FALSE_POSITIVE_SKEPTIC"]["body"]),
            _result_from_body(result_by_role["FALSE_NEGATIVE_HUNTER"]["body"]),
        )


__all__ = ["E5ChallengeService"]
