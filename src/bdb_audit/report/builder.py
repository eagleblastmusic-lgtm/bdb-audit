"""Build a truthful report from one exact verified accepted-history cut."""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping

from ..core.errors import ValidationError
from ..history.store import TransactionalHistoryStore
from ..workflow.read_models import VerifiedCampaignReadModel, current_accepted_cut
from .models import ReportSnapshot


_AXES = ("MECHANISM", "REACHABILITY", "IMPACT", "SEVERITY")
_ACTIONABLE_FINDINGS = {"OPEN", "CONFIRMED_CURRENT", "REMEDIATION_PENDING", "REOPENED", "PARTIALLY_FIXED"}


def _digest(ref: Any) -> str | None:
    return ref.get("revision_digest") if isinstance(ref, Mapping) else None


def _safe_refs(values: Any) -> list[dict[str, Any]]:
    if not isinstance(values, (list, tuple)):
        return []
    return [dict(v) for v in values if isinstance(v, Mapping)]


class ReportBuilder:
    """Read-only report projection. Never writes accepted state."""

    def __init__(self, store: TransactionalHistoryStore):
        self.store = store
        self.cut = current_accepted_cut(store)
        self.read_model = VerifiedCampaignReadModel(store, cut=self.cut)

    @classmethod
    def from_path(cls, path: str | Path) -> "ReportBuilder":
        return cls(TransactionalHistoryStore(path))

    def _accepted(self, kind: str) -> tuple[dict[str, Any], ...]:
        return tuple(self.store.accepted_records(kind, self.cut))

    @staticmethod
    def _latest_by_subject(
        rows: Iterable[dict[str, Any]], ref_field: str
    ) -> dict[str, dict[str, Any]]:
        latest: dict[str, dict[str, Any]] = {}
        for row in rows:
            subject = _digest(row["body"].get(ref_field))
            if subject is None:
                continue
            if subject not in latest or row["accepted_seq"] > latest[subject]["accepted_seq"]:
                latest[subject] = row
        return latest

    def _scope_descriptors(self, refs: list[dict[str, Any]]) -> list[dict[str, Any]]:
        descriptors: list[dict[str, Any]] = []
        for ref in refs:
            descriptor: dict[str, Any] = {"ref": dict(ref)}
            try:
                record = self.store.resolve_accepted(ref, self.cut)
            except ValidationError:
                descriptor["status"] = "REF_NOT_RESOLVABLE_AT_CUT"
                descriptors.append(descriptor)
                continue
            body = record["body"]
            descriptor["status"] = "RESOLVED"
            for key in (
                "path", "module", "component", "name", "surface_id", "scope_id",
                "feature_id", "logical_name", "target_path", "package",
            ):
                value = body.get(key)
                if isinstance(value, (str, int, float, bool)):
                    descriptor[key] = value
            descriptors.append(descriptor)
        return descriptors

    def _findings(self) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        claims = self._accepted("finding_claim_revision")
        assessments = self._accepted("finding_axis_assessment")
        decisions = self._accepted("finding_adjudication_decision")

        assessments_by_claim: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
        for row in assessments:
            body = row["body"]
            claim_digest = _digest(body.get("claim_revision_ref"))
            axis = body.get("axis")
            if claim_digest is None or axis not in _AXES:
                continue
            previous = assessments_by_claim[claim_digest].get(axis)
            if previous is None or row["accepted_seq"] > previous["accepted_seq"]:
                assessments_by_claim[claim_digest][axis] = row

        decisions_by_claim = self._latest_by_subject(decisions, "claim_revision_ref")
        findings: list[dict[str, Any]] = []
        unknowns: list[dict[str, Any]] = []

        for claim in sorted(claims, key=lambda r: r["ref"]["revision_digest"]):
            ref = dict(claim["ref"])
            digest = ref["revision_digest"]
            body = claim["body"]
            decision_row = decisions_by_claim.get(digest)
            decision = decision_row["body"] if decision_row else {}
            axis_rows = assessments_by_claim.get(digest, {})
            axes: dict[str, Any] = {}
            evidence_refs: list[dict[str, Any]] = []
            for axis in _AXES:
                axis_row = axis_rows.get(axis)
                if axis_row is None:
                    axes[axis] = {"status": "NOT_ASSESSED"}
                    unknowns.append({
                        "type": "FINDING_AXIS_NOT_ASSESSED",
                        "finding_ref": ref,
                        "axis": axis,
                    })
                    continue
                axis_body = axis_row["body"]
                axes[axis] = {
                    "status": axis_body.get("epistemic_outcome", "UNKNOWN"),
                    "method": axis_body.get("method"),
                    "assessment_ref": dict(axis_row["ref"]),
                }
                evidence_refs.extend(_safe_refs(axis_body.get("evidence_qualification_refs")))
                if axis_body.get("epistemic_outcome") in {"INCONCLUSIVE", "BLOCKED"}:
                    unknowns.append({
                        "type": "FINDING_AXIS_UNRESOLVED",
                        "finding_ref": ref,
                        "axis": axis,
                        "outcome": axis_body.get("epistemic_outcome"),
                    })

            evidence_refs.extend(_safe_refs(decision.get("evidence_qualification_refs")))
            unique_evidence = {
                (r.get("kind"), r.get("revision_digest"), r.get("schema_revision_ref")): r
                for r in evidence_refs
            }
            lifecycle = decision.get("lifecycle_status", "UNADJUDICATED")
            if decision_row is None:
                unknowns.append({"type": "FINDING_UNADJUDICATED", "finding_ref": ref})

            scope_refs = _safe_refs(body.get("scope_refs"))
            findings.append({
                "finding_ref": ref,
                "claim_id": body.get("claim_id"),
                "claim_revision": body.get("claim_revision"),
                "statement": body.get("statement", ""),
                "source_generation_ref": body.get("source_generation_ref"),
                "scope_refs": scope_refs,
                "scope_descriptors": self._scope_descriptors(scope_refs),
                "violated_invariant_refs": _safe_refs(body.get("violated_invariant_refs")),
                "lifecycle_status": lifecycle,
                "adjudication_ref": dict(decision_row["ref"]) if decision_row else None,
                "axes": axes,
                "evidence_qualification_refs": [
                    unique_evidence[k] for k in sorted(unique_evidence, key=lambda x: tuple(str(v) for v in x))
                ],
                "root_cause_refs": [],
            })
        return findings, unknowns

    def _coverage(self) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        obligations = self._accepted("coverage_obligation")
        qualifications = self._accepted("coverage_obligation_qualification")
        latest = self._latest_by_subject(qualifications, "obligation_revision_ref")
        matrix: list[dict[str, Any]] = []
        unknowns: list[dict[str, Any]] = []
        for obligation in sorted(obligations, key=lambda r: r["ref"]["revision_digest"]):
            ref = dict(obligation["ref"])
            digest = ref["revision_digest"]
            body = obligation["body"]
            q_row = latest.get(digest)
            q = q_row["body"] if q_row else {}
            status = q.get("qualification_status", "UNASSESSED")
            item = {
                "obligation_ref": ref,
                "obligation_id": body.get("obligation_id"),
                "scenario_class": body.get("scenario_class"),
                "target_scope_or_surface_ref": body.get("target_scope_or_surface_ref"),
                "qualification_status": status,
                "substantive_outcome": q.get("substantive_outcome"),
                "qualification_ref": dict(q_row["ref"]) if q_row else None,
                "reason_codes": list(q.get("reason_codes", [])),
                "evidence_qualification_refs": _safe_refs(q.get("evidence_qualification_refs")),
            }
            matrix.append(item)
            if status != "QUALIFIED":
                unknowns.append({
                    "type": "COVERAGE_NOT_QUALIFIED",
                    "obligation_ref": ref,
                    "qualification_status": status,
                    "reason_codes": list(q.get("reason_codes", [])),
                })
        return matrix, unknowns

    def _evidence_index(self) -> list[dict[str, Any]]:
        rows = self._accepted("evidence_qualification_assessment")
        result: list[dict[str, Any]] = []
        for row in sorted(rows, key=lambda r: r["ref"]["revision_digest"]):
            body = row["body"]
            result.append({
                "evidence_ref": dict(row["ref"]),
                "accepted_seq": row["accepted_seq"],
                "qualification_status": body.get("qualification_status", body.get("result", "UNKNOWN")),
                "reason_codes": list(body.get("reason_codes", [])),
                "subject_ref": body.get("subject_ref", body.get("evidence_ref")),
            })
        return result

    def _contradictions(self) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        rows = self._accepted("contradiction_revision")
        result: list[dict[str, Any]] = []
        unknowns: list[dict[str, Any]] = []
        for row in sorted(rows, key=lambda r: r["ref"]["revision_digest"]):
            body = row["body"]
            status = body.get("status", body.get("contradiction_status", "UNRESOLVED"))
            claim_refs = _safe_refs(body.get("claim_revision_refs"))
            if not claim_refs and isinstance(body.get("claim_revision_ref"), Mapping):
                claim_refs = [dict(body["claim_revision_ref"])]
            item = {
                "contradiction_ref": dict(row["ref"]),
                "status": status,
                "claim_revision_refs": claim_refs,
                "reason_codes": list(body.get("reason_codes", [])),
            }
            result.append(item)
            if status not in {"RESOLVED", "RESOLVED_SCOPED", "RESOLVED_FULL"}:
                unknowns.append({
                    "type": "CONTRADICTION_UNRESOLVED",
                    "contradiction_ref": dict(row["ref"]),
                    "status": status,
                })
        return result, unknowns

    def _root_causes(self) -> list[dict[str, Any]]:
        rows = self._accepted("root_cause_revision")
        latest: dict[str, dict[str, Any]] = {}
        for row in rows:
            body = row["body"]
            logical_id = str(body.get("root_cause_id") or row["ref"]["revision_digest"])
            previous = latest.get(logical_id)
            if previous is None or row["accepted_seq"] > previous["accepted_seq"]:
                latest[logical_id] = row
        result: list[dict[str, Any]] = []
        for logical_id in sorted(latest):
            row = latest[logical_id]
            body = row["body"]
            edges = [dict(edge) for edge in body.get("membership_edges", []) if isinstance(edge, Mapping)]
            result.append({
                "root_cause_ref": dict(row["ref"]),
                "root_cause_id": body.get("root_cause_id"),
                "root_cause_revision": body.get("root_cause_revision"),
                "source_generation_ref": body.get("source_generation_ref"),
                "membership_edges": edges,
                "predecessor_root_cause_refs": _safe_refs(body.get("predecessor_root_cause_refs")),
            })
        return result

    @staticmethod
    def _link_root_causes(findings: list[dict[str, Any]], root_causes: list[dict[str, Any]]) -> list[dict[str, Any]]:
        by_finding: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for root in root_causes:
            root_ref = root.get("root_cause_ref")
            if not isinstance(root_ref, Mapping):
                continue
            for edge in root.get("membership_edges", []):
                if not isinstance(edge, Mapping):
                    continue
                finding_ref = edge.get("finding_claim_revision_ref")
                digest = _digest(finding_ref)
                if digest:
                    by_finding[digest].append(dict(root_ref))
        unknowns: list[dict[str, Any]] = []
        for finding in findings:
            finding_ref = finding.get("finding_ref")
            digest = _digest(finding_ref)
            refs = by_finding.get(digest or "", [])
            refs.sort(key=lambda ref: str(ref.get("revision_digest", "")))
            finding["root_cause_refs"] = refs
            if finding.get("lifecycle_status") in _ACTIONABLE_FINDINGS and not refs:
                unknowns.append({
                    "type": "ROOT_CAUSE_NOT_ASSESSED",
                    "finding_ref": dict(finding_ref) if isinstance(finding_ref, Mapping) else {},
                })
        return unknowns

    def build(self) -> ReportSnapshot:
        status = self.read_model.project_status()
        source = self.read_model.project_source_identity()
        findings, finding_unknowns = self._findings()
        coverage, coverage_unknowns = self._coverage()
        contradictions, contradiction_unknowns = self._contradictions()
        root_causes = self._root_causes()
        root_cause_unknowns = self._link_root_causes(findings, root_causes)
        evidence_index = self._evidence_index()
        stop_rows = self._accepted("stop_evaluation")
        stops = [
            {
                "stop_evaluation_ref": dict(row["ref"]),
                "accepted_seq": row["accepted_seq"],
                "continuation_decision": row["body"].get("continuation_decision"),
                "release_readiness": row["body"].get("release_readiness"),
                "reason_codes": list(row["body"].get("reason_codes", [])),
            }
            for row in stop_rows
        ]
        unknowns = [*finding_unknowns, *coverage_unknowns, *contradiction_unknowns, *root_cause_unknowns]
        if not status["campaign_completed"]:
            unknowns.append({
                "type": "CAMPAIGN_NOT_CONCLUDED",
                "termination_state": status["termination_state"],
            })
        report_status = "FINAL" if status["campaign_completed"] else "PARTIAL_BOUNDED"
        return ReportSnapshot(
            campaign_id=status["campaign_id"],
            history_cut=self.cut,
            source_identity=source,
            report_status=report_status,
            termination_state=status["termination_state"],
            campaign_completed=bool(status["campaign_completed"]),
            findings=tuple(findings),
            coverage=tuple(coverage),
            evidence_index=tuple(evidence_index),
            contradictions=tuple(contradictions),
            root_causes=tuple(root_causes),
            stop_evaluations=tuple(stops),
            unknowns=tuple(unknowns),
        )


__all__ = ["ReportBuilder"]
