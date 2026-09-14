"""Read-mostly vNext operational CLI.

The command surface exposes projections, reporting and controlled execution
without granting canonical authority to exported files or tool output.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .features import discover_python_features
from .history.store import TransactionalHistoryStore
from .projections.coverage import coverage_matrix
from .projections.workbench import CoverageEvidenceWorkbench
from .remediation import RemediationPlanner, validate_remediation_plan
from .report import ReportBuilder, export_report_bundle, verify_report_bundle
from .report.render_html import render_html
from .report.render_markdown import render_markdown
from .report.validation import section_completeness, validate_report
from .runner import ActionAuthorization, OperationalToolSpec, OperationalToolSupervisor
from .share.privacy import ExportPrivacyPolicy, sanitize_document
from .workflow.read_models import current_accepted_cut


def _json(value: object) -> None:
    print(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2))


def create_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="bdb-audit-vnext", description="BDB Audit vNext verified projections and operational tools")
    sub = p.add_subparsers(dest="command", required=True)

    report = sub.add_parser("report")
    report_sub = report.add_subparsers(dest="action", required=True)
    export = report_sub.add_parser("export")
    export.add_argument("--store", required=True)
    export.add_argument("--out", required=True)
    export.add_argument("--format", choices=("bundle", "json", "markdown", "html"), default="bundle")
    verify = report_sub.add_parser("verify")
    verify.add_argument("--bundle", required=True)

    remediation = sub.add_parser("remediation")
    remediation_sub = remediation.add_subparsers(dest="action", required=True)
    rem_export = remediation_sub.add_parser("export")
    rem_export.add_argument("--store", required=True)
    rem_export.add_argument("--out", required=True)
    rem_validate = remediation_sub.add_parser("validate")
    rem_validate.add_argument("--file", required=True)

    coverage = sub.add_parser("coverage")
    coverage_sub = coverage.add_subparsers(dest="action", required=True)
    cov_matrix = coverage_sub.add_parser("matrix")
    cov_matrix.add_argument("--store", required=True)
    cov_blockers = coverage_sub.add_parser("blockers")
    cov_blockers.add_argument("--store", required=True)

    features = sub.add_parser("features")
    features_sub = features.add_subparsers(dest="action", required=True)
    discover = features_sub.add_parser("discover")
    discover.add_argument("--path", required=True)
    discover.add_argument("--source", required=True)

    tools = sub.add_parser("tools")
    tools_sub = tools.add_subparsers(dest="action", required=True)
    inspect = tools_sub.add_parser("inspect")
    inspect.add_argument("--source", required=True)
    inspect.add_argument("--scope", required=True)
    inspect.add_argument("--ruleset", required=True)
    inspect.add_argument("--cwd")
    inspect.add_argument("--allow-network", action="store_true")
    inspect.add_argument("argv", nargs=argparse.REMAINDER)
    run = tools_sub.add_parser("run")
    run.add_argument("--source", required=True)
    run.add_argument("--scope", required=True)
    run.add_argument("--ruleset", required=True)
    run.add_argument("--cwd")
    run.add_argument("--allow-network", action="store_true")
    run.add_argument("argv", nargs=argparse.REMAINDER)

    return p


def _tool_spec(args: argparse.Namespace) -> OperationalToolSpec:
    argv = tuple(args.argv)
    if not argv:
        raise ValueError("explicit argv is required")
    return OperationalToolSpec(
        tool_id=Path(argv[0]).name,
        action_class="OPERATOR_EXPLICIT_TOOL",
        argv=argv,
        source_identity=args.source,
        scope_identity=args.scope,
        ruleset_ref=args.ruleset,
        cwd=args.cwd,
        require_no_network=not args.allow_network,
    )


def run_cli(argv: list[str] | None = None) -> int:
    args = create_parser().parse_args(argv)
    try:
        if args.command == "report" and args.action == "verify":
            _json(verify_report_bundle(args.bundle))
            return 0
        if args.command == "report" and args.action == "export":
            snapshot = ReportBuilder.from_path(args.store).build()
            report = snapshot.as_dict()
            validate_report(report)
            plan = RemediationPlanner(snapshot).build().as_dict()
            validate_remediation_plan(plan)
            if args.format == "bundle":
                result = export_report_bundle(snapshot, plan, args.out)
                result["section_completeness"] = section_completeness(report, remediation_plan=plan)
                _json(result)
            else:
                root = Path(args.out)
                root.parent.mkdir(parents=True, exist_ok=True)
                sanitized, removed = sanitize_document(report, ExportPrivacyPolicy())
                if args.format == "json":
                    root.write_text(json.dumps(sanitized, ensure_ascii=False, sort_keys=True, indent=2), encoding="utf-8")
                elif args.format == "markdown":
                    root.write_text(render_markdown(sanitized), encoding="utf-8")
                else:
                    root.write_text(render_html(sanitized), encoding="utf-8")
                _json({"status": "PASS", "path": str(root), "removed_private_fields": removed})
            return 0
        if args.command == "remediation" and args.action == "export":
            snapshot = ReportBuilder.from_path(args.store).build()
            plan = RemediationPlanner(snapshot).build().as_dict()
            validate_remediation_plan(plan)
            out = Path(args.out)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(plan, ensure_ascii=False, sort_keys=True, indent=2), encoding="utf-8")
            _json({"status": "PASS", "path": str(out), "repair_unit_count": len(plan["repair_units"])})
            return 0
        if args.command == "remediation" and args.action == "validate":
            plan = json.loads(Path(args.file).read_text(encoding="utf-8"))
            _json(validate_remediation_plan(plan))
            return 0
        if args.command == "coverage":
            store = TransactionalHistoryStore(args.store)
            if args.action == "matrix":
                _json(coverage_matrix(store))
            else:
                _json(CoverageEvidenceWorkbench(store).blockers())
            return 0
        if args.command == "features" and args.action == "discover":
            features = discover_python_features(args.path, args.source)
            _json({"source_identity": args.source, "feature_denominator": len(features), "features": [feature.__dict__ for feature in features]})
            return 0
        if args.command == "tools":
            spec = _tool_spec(args)
            auth = ActionAuthorization(("OPERATOR_EXPLICIT_TOOL",), (spec.argv[0],), (args.cwd,) if args.cwd else ())
            supervisor = OperationalToolSupervisor(auth)
            result = supervisor.inspect(spec) if args.action == "inspect" else supervisor.run(spec).__dict__
            _json(result)
            return 0
        return 2
    except Exception as exc:
        _json({"status": "ERROR", "error": type(exc).__name__, "detail": str(exc)})
        return 1


def main() -> None:
    raise SystemExit(run_cli())


if __name__ == "__main__":
    main()
