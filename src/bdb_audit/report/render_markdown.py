from __future__ import annotations

import json
from typing import Mapping


def _escape(value: object) -> str:
    text = str(value)
    for char in ("\\", "`", "*", "_", "[", "]", "<", ">"):
        text = text.replace(char, "\\" + char)
    return text.replace("\r", " ").replace("\n", " ")


def render_markdown(report: Mapping[str, object]) -> str:
    source = report.get("source_identity") if isinstance(report.get("source_identity"), Mapping) else {}
    cut = report.get("history_cut") if isinstance(report.get("history_cut"), Mapping) else {}
    lines = [
        "# BDB Audit — exact-cut report",
        "",
        f"- Campaign: `{_escape(report.get('campaign_id', 'UNKNOWN'))}`",
        f"- Status: **{_escape(report.get('report_status', 'UNKNOWN'))}**",
        f"- Termination: **{_escape(report.get('termination_state', 'UNKNOWN'))}**",
        f"- Source commit: `{_escape(source.get('git_commit_object_id', 'UNKNOWN'))}`",
        f"- Accepted head seq: `{_escape(cut.get('accepted_head_seq', 'UNKNOWN'))}`",
        "",
        "## Findings",
    ]
    findings = report.get("findings") if isinstance(report.get("findings"), (list, tuple)) else ()
    if not findings:
        lines.append("NOT_ASSESSED / no accepted finding claim is present at this cut. This is not a defect-free assertion.")
    else:
        for finding in findings:
            if not isinstance(finding, Mapping):
                continue
            lines.extend([
                "",
                f"### {_escape(finding.get('claim_id', 'finding'))}",
                _escape(finding.get("statement", "")),
                f"Lifecycle: `{_escape(finding.get('lifecycle_status', 'UNADJUDICATED'))}`",
            ])
            evidence = finding.get("evidence_qualification_refs")
            if isinstance(evidence, (list, tuple)) and evidence:
                lines.append("Evidence refs:")
                for ref in evidence:
                    if isinstance(ref, Mapping):
                        lines.append(f"- `{_escape(ref.get('kind', 'unknown'))}:{_escape(ref.get('revision_digest', 'missing'))}`")
            else:
                lines.append("Evidence: `INSUFFICIENT / NOT_LINKED`")

    sections = (
        ("Coverage", "coverage"),
        ("Evidence index", "evidence_index"),
        ("Contradictions", "contradictions"),
        ("STOP evaluations", "stop_evaluations"),
        ("Known unknowns / blockers", "unknowns"),
    )
    for title, key in sections:
        lines.extend(["", f"## {title}"])
        value = report.get(key)
        if not isinstance(value, (list, tuple)) or not value:
            lines.append("NOT_ASSESSED / no represented rows at this exact cut.")
        else:
            for item in value:
                lines.append("- " + _escape(json.dumps(item, ensure_ascii=False, sort_keys=True)))

    lines.extend([
        "",
        "## Authority note",
        "This document is a derived read model. Canonical accepted history at the exact cut remains authoritative. Missing, blocked, unknown, stale or unsupported evidence never implies PASS.",
        "",
    ])
    return "\n".join(lines)


__all__ = ["render_markdown"]
