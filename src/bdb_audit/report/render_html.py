from __future__ import annotations

import html
import json
from typing import Mapping


def render_html(report: Mapping[str, object]) -> str:
    def esc(value: object) -> str:
        return html.escape(str(value), quote=True)

    source = report.get("source_identity") if isinstance(report.get("source_identity"), Mapping) else {}
    cut = report.get("history_cut") if isinstance(report.get("history_cut"), Mapping) else {}
    findings = report.get("findings") if isinstance(report.get("findings"), (list, tuple)) else ()
    unknowns = report.get("unknowns") if isinstance(report.get("unknowns"), (list, tuple)) else ()
    chunks = [
        "<!doctype html><html><head><meta charset=\"utf-8\"><title>BDB Audit report</title></head><body>",
        "<h1>BDB Audit — exact-cut report</h1>",
        "<dl>",
        f"<dt>Campaign</dt><dd><code>{esc(report.get('campaign_id', 'UNKNOWN'))}</code></dd>",
        f"<dt>Status</dt><dd>{esc(report.get('report_status', 'UNKNOWN'))}</dd>",
        f"<dt>Source commit</dt><dd><code>{esc(source.get('git_commit_object_id', 'UNKNOWN'))}</code></dd>",
        f"<dt>Accepted head seq</dt><dd><code>{esc(cut.get('accepted_head_seq', 'UNKNOWN'))}</code></dd>",
        "</dl><h2>Findings</h2>",
    ]
    if not findings:
        chunks.append("<p>NOT_ASSESSED / no accepted finding claim is present at this cut. This is not a defect-free assertion.</p>")
    for finding in findings:
        if not isinstance(finding, Mapping):
            continue
        chunks.append(f"<article><h3>{esc(finding.get('claim_id', 'finding'))}</h3><p>{esc(finding.get('statement', ''))}</p>")
        chunks.append(f"<p>Lifecycle: <code>{esc(finding.get('lifecycle_status', 'UNADJUDICATED'))}</code></p></article>")
    chunks.append("<h2>Known unknowns / blockers</h2>")
    if not unknowns:
        chunks.append("<p>No unresolved item is represented in this projection.</p>")
    else:
        chunks.append("<ul>")
        for item in unknowns:
            chunks.append(f"<li><code>{esc(json.dumps(item, ensure_ascii=False, sort_keys=True))}</code></li>")
        chunks.append("</ul>")
    chunks.append("<h2>Authority note</h2><p>This is a derived exact-cut read model. Missing or unknown evidence never implies PASS.</p></body></html>")
    return "".join(chunks)


__all__ = ["render_html"]
