"""Local report projection; model findings remain unverified interpretations."""
from __future__ import annotations

from collections import defaultdict
import html
from pathlib import Path
from typing import Any

from ..core.canonical_json import canonical_bytes
from ..core.errors import ValidationError
from ..report.models import ReportItem, ReportModel
from ..report.render_markdown import render_markdown
from .profile import MODE, NOTICE
from .store import sha
from .workflow import LocalWorkflow

SEVERITY_ORDER = {value: index for index, value in enumerate(("CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"))}


def build_report(workflow: LocalWorkflow) -> dict[str, Any]:
    # Never export a stale view while a different process appends decisions.
    workflow = LocalWorkflow(workflow.store.root)
    facts: list[ReportItem] = [ReportItem("FACT", "local_source_snapshot", None, 1, workflow.source)]
    interpretations: list[ReportItem] = []
    proposals: list[ReportItem] = []
    unknowns: list[ReportItem] = [ReportItem("UNKNOWN", "local_assurance_limits", None, None, {"notice": NOTICE})]
    findings: list[dict[str, Any]] = []
    responses: list[dict[str, Any]] = []
    contradictions: list[dict[str, Any]] = []
    recommendations: list[dict[str, Any]] = []
    declared_models: list[dict[str, Any]] = []
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    contains_fixtures = False
    for task, rid in workflow.accepted.items():
        result = workflow.results[rid]
        response = result["response"]
        ref = {"namespace": "LOCAL", "result_id": rid, "raw_sha256": result["raw"]["raw_digest"]}
        producer = response["producer"]
        contains_fixtures |= producer["kind"] == "TEST_FIXTURE"
        declared_models.append({"task_id": task, "declared_producer": producer, "identity_verified": False})
        responses.append({"task_id": task, "result_id": rid, "state": "USER_ACCEPTED_LOCAL",
                          "raw": result["raw"], "response": response, "actor_label": result["actor_label"]})
        facts.append(ReportItem("FACT", "local_manual_acceptance", ref, result["accepted_seq"], {
            "task_id": task, "actor_label": result["actor_label"], "meaning": "Permission to use locally; not attestation of truth or identity"}))
        interpretations.append(ReportItem("INTERPRETATION", "local_declared_stage_outputs", ref, None, {
            "task_id": task, "outputs": response["outputs"], "producer": producer, "truth_verified": False}))
        for finding in response["findings"]:
            item = {**finding, "task_id": task, "result_id": rid, "producer": producer, "truth_verified": False,
                    "raw_sha256": result["raw"]["raw_digest"]}
            findings.append(item)
            groups[finding["id"]].append(item)
            interpretations.append(ReportItem("INTERPRETATION", "local_finding_claim", ref, None, item))
        for text in response["contradictions"]:
            contradictions.append({"classification": "DECLARED_DISPUTE", "task_id": task, "result_id": rid, "text": text})
        for text in response["recommendations"]:
            item = {"task_id": task, "result_id": rid, "text": text}
            recommendations.append(item)
            proposals.append(ReportItem("PROPOSAL", "local_remediation", ref, None, item))
        for text in response["limitations"]:
            unknowns.append(ReportItem("UNKNOWN", "local_declared_limitation", ref, None, {"task_id": task, "text": text}))
    for identifier, claims in groups.items():
        if len({(claim["severity"], claim["disposition"]) for claim in claims}) > 1:
            contradictions.append({"classification": "POTENTIAL_DISAGREEMENT_REQUIRES_REVIEW", "finding_id": identifier,
                                   "claims": [{"task_id": c["task_id"], "result_id": c["result_id"],
                                               "severity": c["severity"], "disposition": c["disposition"]} for c in claims]})
    for run in workflow.runs:
        facts.append(ReportItem("FACT", "local_tool_execution", {"namespace": "LOCAL", "run_id": run["run_id"]}, None, run))
    for run in workflow.abandoned_runs:
        unknowns.append(ReportItem("UNKNOWN", "local_abandoned_check", None, None, run))
    for run in workflow.pending_runs.values():
        unknowns.append(ReportItem("UNKNOWN", "local_pending_check", None, None, run))
    model = ReportModel(workflow.campaign_id, {"namespace": "LOCAL", "event_hash": workflow.head,
                        "seq": len(workflow.events)}, workflow.source,
                        "FULL" if workflow.stage == "COMPLETE" else "PARTIAL",
                        tuple(facts), tuple(interpretations), tuple(proposals), tuple(unknowns),
                        schema_version="BDB-LOCAL-REPORT-1")
    evidence = [{"event_seq": e["seq"], "event_hash": e["event_hash"], "kind": e["kind"]} for e in workflow.events]
    raw_refs: dict[str, dict[str, Any]] = {}
    def collect(value: Any) -> None:
        if isinstance(value, dict):
            if "raw_digest" in value and "byte_length" in value:
                raw_refs[value["raw_digest"]] = value
            for child in value.values():
                collect(child)
        elif isinstance(value, list):
            for child in value:
                collect(child)
    collect(workflow.events)
    status = workflow.status()
    return {"format": "BDB_LOCAL_AUDIT_REPORT_1", "mode": MODE, "notice": NOTICE,
            "status": status["status"], "campaign_id": workflow.campaign_id,
            "input_history_head": workflow.head, "source": workflow.source,
            "stage_progress": {"current": workflow.stage, "completed": workflow.completed,
                               "missing_results": status["missing_results"]},
            "contains_test_fixtures": contains_fixtures, "declared_producers": declared_models,
            "findings": sorted(findings, key=lambda f: (SEVERITY_ORDER[f["severity"]], f["id"], f["task_id"])),
            "accepted_responses": responses, "contradictions": contradictions, "recommendations": recommendations,
            "local_checks": workflow.runs, "pending_checks": list(workflow.pending_runs.values()),
            "abandoned_checks": workflow.abandoned_runs, "evidence_events": evidence,
            "raw_evidence": [{**raw_refs[key], "relative_blob_path": f"vault/sha256/{key[:2]}/{key[2:]}"} for key in sorted(raw_refs)],
            "unverified_claims": "All producer identities, stage assessments and findings; execution receipts establish only captured local execution",
            "limitations": [NOTICE, "Unsigned local journal cannot resist complete rewriting by an administrator of this host",
                            "Source scope is fixed; no submodules, symlinks or unresolved LFS content",
                            "Local subprocesses do not enforce host filesystem or network isolation"],
            "derived_report_model": model.as_dict()}


def markdown(report: dict[str, Any]) -> str:
    def esc(text: Any) -> str:
        return html.escape(str(text)).replace("`", "&#96;")
    rows = ["# BDB Audit — LOCAL PRODUCT MODE", "", report["notice"], "",
            "Status użytkowego workflow: **" + report["status"] + "**. Nie jest to kwalifikacja NF02.", "",
            f"Kampania: {esc(report['campaign_id'])}", f"Repozytorium: {esc(report['source']['location'])}",
            f"Exact commit: {esc(report['source']['commit'])}", f"Exact tree: {esc(report['source']['tree'])}", "",
            "Zakres źródła: " + esc(report["source"]["scope"]) + "; plików: " + str(len(report["source"]["paths"])), "",
            "Etapy ukończone lokalnie: " + ", ".join(report["stage_progress"]["completed"]), "",
            "Brakujące zadania: " + (", ".join(report["stage_progress"]["missing_results"]) or "brak"), ""]
    if report["contains_test_fixtures"]:
        rows.extend(["**Zawiera jawne TEST_FIXTURE. Nie przedstawia rzeczywistych odpowiedzi modeli AI.**", ""])
    rows.extend(["## Deklarowani producenci", ""])
    for item in report["declared_producers"]:
        producer = item["declared_producer"]
        rows.append(f"- {esc(item['task_id'])}: {esc(producer['kind'])}, {esc(producer['declared_name'])}; tożsamość niezweryfikowana")
    rows.extend(["", "## Ustalenia — niezweryfikowane twierdzenia", ""])
    for item in report["findings"]:
        rows.extend([f"### {esc(item['id'])} [{item['severity']}] {esc(item['title'])}", "",
                     esc(item["statement"]), "", "Uzasadnienie deklarowane: " + esc(item["rationale"]), "",
                     "Zadanie: " + esc(item["task_id"]) + "; deklarowany status: " + item["disposition"], "",
                     "Źródła: " + ", ".join(esc(ref["path"]) + ":" + str(ref["line"]) for ref in item["source_refs"]), "",
                     "Raw SHA-256 wyniku: " + item["raw_sha256"], ""])
    rows.extend(["## Rzeczywiście uruchomione lokalne kontrole", ""])
    for run in report["local_checks"]:
        result = run["result"]
        rows.extend([f"- {esc(run['run_id'])}: {result['supervisor_status']}; exit={result['target_exit_code']}",
                     "  Ograniczenia: " + esc(", ".join(result["limitations"]))])
    rows.extend(["", "## Spory i rozbieżności wymagające oceny", ""])
    for dispute in report["contradictions"]:
        rows.append("- " + esc(dispute))
    rows.extend(["", "## Zalecenia i działania naprawcze", ""])
    for item in report["recommendations"]:
        rows.append("- " + esc(item["task_id"]) + ": " + esc(item["text"]))
    rows.extend(["", "## Ograniczenia i nieukończone kontrole", ""])
    for text in report["limitations"]:
        rows.append("- " + esc(text))
    for item in report["derived_report_model"]["unknowns"]:
        rows.append("- " + esc(item["payload"]))
    rows.extend(["", "## Szczegółowa projekcja historii", ""])
    # Reuse the product renderer, while local classification and schema above
    # explicitly restrict its 'facts' to local decisions and run observations.
    raw_model = report["derived_report_model"]
    def items(key: str) -> tuple[ReportItem, ...]:
        return tuple(ReportItem(**item) for item in raw_model[key])
    model = ReportModel(raw_model["campaign_id"], raw_model["input_history_cut"], raw_model["source_identity"],
                        raw_model["report_scope"], items("facts"), items("interpretations"), items("proposals"),
                        items("unknowns"), raw_model["schema_version"])
    rows.append(render_markdown(model))
    return "\n".join(rows) + "\n"


def export_report(workflow: LocalWorkflow, output: str | Path) -> dict[str, Any]:
    report = build_report(workflow)
    root = Path(output).resolve()
    protected = [workflow.store.root / name for name in ("vault", "checks", "work", "packages")]
    if root == workflow.store.root or any(root == path or root.is_relative_to(path) for path in protected):
        raise ValidationError("LOCAL_REPORT_PROTECTED_PATH")
    if root.exists():
        raise ValidationError("LOCAL_REPORT_OUTPUT_EXISTS", "Use a new export directory to preserve prior evidence")
    json_raw = canonical_bytes(report) + b"\n"
    md_raw = markdown(report).encode("utf-8")
    root.mkdir(parents=True)
    (root / "REPORT.json").write_bytes(json_raw)
    (root / "REPORT.md").write_bytes(md_raw)
    manifest = {"format": "BDB_LOCAL_REPORT_EVIDENCE_1", "mode": MODE,
                "campaign_id": report["campaign_id"], "history_head": report["input_history_head"],
                "reports": [{"path": "REPORT.json", "sha256": sha(json_raw), "byte_length": len(json_raw)},
                            {"path": "REPORT.md", "sha256": sha(md_raw), "byte_length": len(md_raw)}],
                "raw_evidence": report["raw_evidence"], "campaign_directory": str(workflow.store.root)}
    (root / "EVIDENCE_MANIFEST.json").write_bytes(canonical_bytes(manifest) + b"\n")
    return {"mode": MODE, "status": "EXPORTED_LOCAL", "workflow_status": report["status"],
            "output": str(root), "reports": manifest["reports"], "notice": NOTICE}
