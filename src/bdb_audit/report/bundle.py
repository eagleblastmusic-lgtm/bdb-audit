"""Deterministic report bundle renderer and verifier."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from ..core.canonical_json import canonical_bytes
from ..core.errors import ValidationError
from .models import ReportSnapshot

_REQUIRED = (
    "REPORT.md",
    "REPORT.json",
    "FEATURE_STATUS_MATRIX.json",
    "COVERAGE_MATRIX.json",
    "REMEDIATION_PLAN.json",
    "EVIDENCE_INDEX.json",
)


def _json_bytes(value: Any) -> bytes:
    return canonical_bytes(value)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _markdown(snapshot: Mapping[str, Any]) -> str:
    source = snapshot.get("source_identity", {})
    findings = snapshot.get("findings", [])
    unknowns = snapshot.get("unknowns", [])
    coverage = snapshot.get("coverage", [])
    lines = [
        "# BDB Audit Report",
        "",
        f"- Campaign: `{snapshot.get('campaign_id', '')}`",
        f"- Report status: **{snapshot.get('report_status', 'UNKNOWN')}**",
        f"- Termination: **{snapshot.get('termination_state', 'UNKNOWN')}**",
        f"- Source commit: `{source.get('git_commit_object_id', 'UNKNOWN')}`",
        f"- Accepted head: `{snapshot.get('history_cut', {}).get('accepted_head_seq', 'UNKNOWN')}`",
        "",
        "## Findings",
        "",
    ]
    if not findings:
        lines.append("No accepted finding claims are present at this cut. This is not evidence that the target is defect-free.")
    for index, finding in enumerate(findings, 1):
        lines.extend([
            f"### F{index} — {finding.get('lifecycle_status', 'UNADJUDICATED')}",
            "",
            str(finding.get("statement", "")),
            "",
            f"Claim ref: `{(finding.get('finding_ref') or {}).get('revision_digest', '')}`",
            "",
        ])
    lines.extend(["## Coverage", ""])
    if not coverage:
        lines.append("No accepted coverage obligations are present at this cut; coverage is NOT_ASSESSED.")
    else:
        for item in coverage:
            lines.append(
                f"- `{item.get('obligation_id') or (item.get('obligation_ref') or {}).get('revision_digest')}`: "
                f"**{item.get('qualification_status', 'UNASSESSED')}** / "
                f"{item.get('substantive_outcome') or 'NO_SUBSTANTIVE_OUTCOME'}"
            )
    lines.extend(["", "## Known unknowns / blockers", ""])
    if not unknowns:
        lines.append("No unresolved item is represented in this projection.")
    else:
        for item in unknowns:
            lines.append(f"- `{item.get('type', 'UNKNOWN')}` — {json.dumps(item, ensure_ascii=False, sort_keys=True)}")
    lines.extend([
        "",
        "## Integrity note",
        "",
        "This report is a derived exact-cut projection. The accepted history remains the authority. "
        "Missing evidence, unassessed coverage, or an open campaign must not be interpreted as PASS.",
        "",
    ])
    return "\n".join(lines)


def export_report_bundle(
    snapshot: ReportSnapshot | Mapping[str, Any],
    remediation_plan: Mapping[str, Any],
    output_dir: str | Path,
    feature_status_matrix: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    report = snapshot.as_dict() if isinstance(snapshot, ReportSnapshot) else dict(snapshot)
    feature_matrix = dict(feature_status_matrix or {
        "status": "NOT_ASSESSED",
        "reason_codes": ["FUNCTIONAL_VERIFICATION_NOT_AVAILABLE_AT_THIS_REPORT_CUT"],
        "features": [],
        "history_cut": report.get("history_cut"),
    })
    payloads: dict[str, bytes] = {
        "REPORT.md": _markdown(report).encode("utf-8"),
        "REPORT.json": _json_bytes(report),
        "FEATURE_STATUS_MATRIX.json": _json_bytes(feature_matrix),
        "COVERAGE_MATRIX.json": _json_bytes({
            "history_cut": report.get("history_cut"),
            "coverage": report.get("coverage", []),
        }),
        "REMEDIATION_PLAN.json": _json_bytes(dict(remediation_plan)),
        "EVIDENCE_INDEX.json": _json_bytes({
            "history_cut": report.get("history_cut"),
            "evidence": report.get("evidence_index", []),
        }),
    }
    entries = []
    for name in sorted(payloads):
        data = payloads[name]
        (root / name).write_bytes(data)
        entries.append({"path": name, "sha256": _sha(data), "size": len(data)})
    manifest = {
        "bundle_version": "1",
        "campaign_id": report.get("campaign_id"),
        "history_cut": report.get("history_cut"),
        "report_status": report.get("report_status"),
        "files": entries,
    }
    manifest_bytes = _json_bytes(manifest)
    (root / "MANIFEST.json").write_bytes(manifest_bytes)
    return {**manifest, "manifest_sha256": _sha(manifest_bytes), "output_dir": str(root)}


def verify_report_bundle(output_dir: str | Path) -> dict[str, Any]:
    root = Path(output_dir)
    manifest_path = root / "MANIFEST.json"
    if not manifest_path.is_file():
        raise ValidationError("REPORT_BUNDLE_MANIFEST_MISSING")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ValidationError("REPORT_BUNDLE_MANIFEST_INVALID", str(exc)) from exc
    entries = manifest.get("files")
    if not isinstance(entries, list):
        raise ValidationError("REPORT_BUNDLE_MANIFEST_INVALID")
    by_path = {e.get("path"): e for e in entries if isinstance(e, dict)}
    missing_manifest_entries = set(_REQUIRED) - set(by_path)
    if missing_manifest_entries:
        raise ValidationError("REPORT_BUNDLE_INCOMPLETE", ",".join(sorted(missing_manifest_entries)))
    for name, entry in sorted(by_path.items()):
        if not isinstance(name, str) or Path(name).name != name:
            raise ValidationError("REPORT_BUNDLE_PATH_INVALID", str(name))
        path = root / name
        if not path.is_file():
            raise ValidationError("REPORT_BUNDLE_FILE_MISSING", name)
        data = path.read_bytes()
        if len(data) != entry.get("size") or _sha(data) != entry.get("sha256"):
            raise ValidationError("REPORT_BUNDLE_TAMPERED", name)
    return {
        "status": "PASS",
        "campaign_id": manifest.get("campaign_id"),
        "history_cut": manifest.get("history_cut"),
        "file_count": len(entries),
        "manifest_sha256": _sha(manifest_path.read_bytes()),
    }


__all__ = ["export_report_bundle", "verify_report_bundle"]
