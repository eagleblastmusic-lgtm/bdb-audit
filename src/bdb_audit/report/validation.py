from __future__ import annotations

from typing import Mapping, Sequence

from ..core.errors import ValidationError

_REQUIRED_TOP_LEVEL = (
    "report_version", "campaign_id", "history_cut", "source_identity", "report_status",
    "termination_state", "campaign_completed", "findings", "coverage", "evidence_index",
    "contradictions", "stop_evaluations", "unknowns",
)


def validate_report(report: Mapping[str, object]) -> dict:
    missing = [key for key in _REQUIRED_TOP_LEVEL if key not in report]
    if missing:
        raise ValidationError("REPORT_REQUIRED_FIELD_MISSING", ",".join(missing))
    if report.get("report_status") not in {"FINAL", "PARTIAL_BOUNDED", "PARTIAL/BOUNDED"}:
        raise ValidationError("REPORT_STATUS_INVALID")
    if report.get("report_status") == "FINAL" and not report.get("campaign_completed"):
        raise ValidationError("FINAL_REPORT_REQUIRES_CONCLUDED_CAMPAIGN")
    cut = report.get("history_cut")
    if not isinstance(cut, Mapping) or cut.get("variant") != "ACCEPTED_HISTORY_CUT":
        raise ValidationError("REPORT_ACCEPTED_CUT_REQUIRED")
    source = report.get("source_identity")
    if not isinstance(source, Mapping) or not source:
        raise ValidationError("REPORT_SOURCE_IDENTITY_REQUIRED")

    for key in ("findings", "coverage", "evidence_index", "contradictions", "stop_evaluations", "unknowns"):
        if not isinstance(report.get(key), (list, tuple)):
            raise ValidationError("REPORT_SECTION_INVALID", key)

    material_without_evidence: list[str] = []
    for finding in report.get("findings", ()):  # type: ignore[union-attr]
        if not isinstance(finding, Mapping):
            raise ValidationError("REPORT_FINDING_INVALID")
        statement = str(finding.get("statement", "")).strip()
        if not statement:
            raise ValidationError("REPORT_FINDING_STATEMENT_REQUIRED")
        lifecycle = str(finding.get("lifecycle_status", "UNADJUDICATED"))
        evidence = finding.get("evidence_qualification_refs")
        if lifecycle in {"CONFIRMED_CURRENT", "OPEN", "REMEDIATION_PENDING", "REOPENED", "PARTIALLY_FIXED"} and not evidence:
            ref = finding.get("finding_ref")
            token = ref.get("revision_digest") if isinstance(ref, Mapping) else "unknown"
            material_without_evidence.append(str(token))
    if material_without_evidence:
        raise ValidationError("REPORT_MATERIAL_CLAIM_EVIDENCE_REQUIRED", ",".join(sorted(material_without_evidence)))
    return {"status": "PASS", "report_status": report.get("report_status"), "finding_count": len(report.get("findings", ())), "unknown_count": len(report.get("unknowns", ())) }


def section_completeness(report: Mapping[str, object], feature_matrix: Mapping[str, object] | None = None, remediation_plan: Mapping[str, object] | None = None) -> tuple[dict, ...]:
    sections = [
        ("SOURCE_IDENTITY", bool(report.get("source_identity"))),
        ("FINDINGS", bool(report.get("findings"))),
        ("COVERAGE_MATRIX", bool(report.get("coverage"))),
        ("EVIDENCE_INDEX", bool(report.get("evidence_index"))),
        ("CONTRADICTIONS", bool(report.get("contradictions"))),
        ("STOP_EVALUATIONS", bool(report.get("stop_evaluations"))),
        ("KNOWN_UNKNOWNS", bool(report.get("unknowns"))),
        ("FUNCTIONAL_MATRIX", bool(feature_matrix and feature_matrix.get("features"))),
        ("REMEDIATION_PLAN", bool(remediation_plan and remediation_plan.get("repair_units"))),
    ]
    return tuple({"section": name, "status": "PRESENT" if present else "NOT_ASSESSED"} for name, present in sections)


__all__ = ["section_completeness", "validate_report"]
