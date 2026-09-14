from __future__ import annotations

from bdb_audit.report.render_html import render_html
from bdb_audit.report.render_markdown import render_markdown
from bdb_audit.report.validation import section_completeness, validate_report
from bdb_audit.share.privacy import ExportPrivacyPolicy, sanitize_document
from bdb_audit.vnext_cli import create_parser


def _report():
    return {
        "report_version": "1",
        "campaign_id": "campaign_1",
        "history_cut": {"variant": "ACCEPTED_HISTORY_CUT", "accepted_head_seq": 2, "accepted_head_hash": "a" * 64},
        "source_identity": {"git_commit_object_id": "b" * 40},
        "report_status": "PARTIAL_BOUNDED",
        "termination_state": "RUNNING",
        "campaign_completed": False,
        "findings": [],
        "coverage": [],
        "evidence_index": [],
        "contradictions": [],
        "stop_evaluations": [],
        "unknowns": [{"type": "NOT_DONE"}],
    }


def test_report_validation_and_completeness_never_turn_empty_into_pass():
    report = _report()
    assert validate_report(report)["status"] == "PASS"
    sections = section_completeness(report)
    statuses = {row["section"]: row["status"] for row in sections}
    assert statuses["FINDINGS"] == "NOT_ASSESSED"
    assert statuses["KNOWN_UNKNOWNS"] == "PRESENT"


def test_renderers_escape_active_markup_and_script_content():
    report = _report()
    report["findings"] = [{"claim_id": "x", "statement": "<script>alert(1)</script> [link](javascript:x)", "lifecycle_status": "UNADJUDICATED", "evidence_qualification_refs": []}]
    html = render_html(report)
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html
    markdown = render_markdown(report)
    assert "\\<script\\>" in markdown
    assert "\\[link\\]" in markdown


def test_privacy_sanitizer_removes_secret_named_fields_recursively():
    clean, removed = sanitize_document({"ok": 1, "nested": {"token": "abc", "value": 2}}, ExportPrivacyPolicy())
    assert clean == {"ok": 1, "nested": {"value": 2}}
    assert "nested.token" in removed


def test_vnext_cli_has_report_remediation_coverage_features_and_tools_surfaces():
    parser = create_parser()
    assert parser.parse_args(["report", "verify", "--bundle", "x"]).command == "report"
    assert parser.parse_args(["remediation", "validate", "--file", "x"]).command == "remediation"
    assert parser.parse_args(["coverage", "matrix", "--store", "x"]).command == "coverage"
    assert parser.parse_args(["features", "discover", "--path", ".", "--source", "s"]).command == "features"
    args = parser.parse_args(["tools", "inspect", "--source", "s", "--scope", "x", "--ruleset", "r", "python", "-V"])
    assert args.command == "tools"
