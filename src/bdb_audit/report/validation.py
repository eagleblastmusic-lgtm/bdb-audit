from __future__ import annotations

from typing import Mapping

from ..core.errors import ValidationError

_REQUIRED_TOP_LEVEL = (
    "report_version", "campaign_id", "history_cut", "source_identity", "report_status",
    "termination_state", "campaign_completed", "findings", "coverage", "evidence_index",
    "contradictions", "stop_evaluations", "unknowns",
)


def _items(value: object) -> tuple[object, ...]:
    if isinstance(value, (list, tuple)):
        return tuple(value)
    return ()


def validate_report(report: Mapping[str, object]) -> dict:
    missing = [key for key in _REQUIRED_TOP_LEVEL if key not in report]
    if missing:
        raise ValidationError("REPORT_REQUIRED_FIELD_MISSING", ",".join(missing))
    version = str(report.get("report_version", "1"))
    if version >= "2" and "root_causes" not in report:
        raise ValidationError("REPORT_REQUIRED_FIELD_MISSING", "root_causes")
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

    section_keys = ["findings", "coverage", "evidence_index", "contradictions", "stop_evaluations", "unknowns"]
    if version >= "2":
        section_keys.append("root_causes")
    for key in section_keys:
        if not isinstance(report.get(key), (list, tuple)):
            raise ValidationError("REPORT_SECTION_INVALID", key)

    findings = _items(report.get("findings"))
    material_without_evidence: list[str] = []
    for finding in findings:
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
    root_causes = _items(report.get("root_causes"))
    unknowns = _items(report.get("unknowns"))
    return {
        "status": "PASS",
        "report_status": report.get("report_status"),
        "report_version": version,
        "finding_count": len(findings),
        "root_cause_count": len(root_causes),
        "unknown_count": len(unknowns),
    }


def section_completeness(report: Mapping[str, object], feature_matrix: Mapping[str, object] | None = None, remediation_plan: Mapping[str, object] | None = None) -> tuple[dict, ...]:
    sections = [
        ("SOURCE_IDENTITY", bool(report.get("source_identity"))),
        ("FINDINGS", bool(report.get("findings"))),
        ("ROOT_CAUSES", bool(report.get("root_causes"))),
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
