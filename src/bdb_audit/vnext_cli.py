"""Read-mostly vNext operational CLI.

The command surface exposes projections, reporting and controlled execution
without granting canonical authority to exported files or tool output.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
from typing import Any, Mapping

from .features import (
    BehaviorAssessment,
    BehaviorCase,
    FeatureRevision,
    assess_testability,
    discover_python_features,
    feature_status_matrix,
    plan_verification,
    qualify_behavior,
    qualify_oracle,
)
from .features.adapters.cli import CliBehaviorAdapter
from .history.store import TransactionalHistoryStore
from .incremental import SuccessorCampaignSpec, validate_successor_selection
from .opportunities import OpportunityProposal, ProductContext, qualify_opportunity_for_report
from .projections.coverage import coverage_matrix
from .projections.workbench import CoverageEvidenceWorkbench
from .qualification import BenchmarkManifest, FrozenHoldout, evaluate_continuous_holdout
from .remediation import RemediationPlanner, validate_remediation_plan
from .report import ReportBuilder, export_report_bundle, verify_report_bundle
from .report.render_html import render_html
from .report.render_markdown import render_markdown
from .report.validation import section_completeness, validate_report
from .runner import ActionAuthorization, OperationalToolSpec, OperationalToolSupervisor
from .share import RecipientBundle, TrendSnapshot, compare_trend, verify_recipient_bundle
from .share.privacy import ExportPrivacyPolicy, sanitize_document
from .strategy import (
    AuditStrategyProfile,
    ExposureManifest,
    LaneProposal,
    StrategyPlan,
    StrategyRunMetrics,
    compare_adaptive_to_baseline,
    validate_plan,
)


def _json(value: object) -> None:
    print(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2))


def _object(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object")
    return {str(key): item for key, item in value.items()}


def _load_object(path: str) -> dict[str, Any]:
    return _object(json.loads(Path(path).read_text(encoding="utf-8")), path)


def _str_tuple(value: object) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        return ()
    return tuple(str(item) for item in value)


def _feature_revision(value: object) -> FeatureRevision:
    raw = _object(value, "feature")
    return FeatureRevision(
        str(raw["feature_id"]),
        str(raw["revision"]),
        str(raw["source_identity"]),
        str(raw["user_task"]),
        _str_tuple(raw.get("entrypoints")),
        _str_tuple(raw.get("requirement_refs")),
        _str_tuple(raw.get("roles")),
        _str_tuple(raw.get("environment_classes")),
        _str_tuple(raw.get("input_classes")),
        str(raw.get("criticality", "NORMAL")),
        str(raw.get("discovery_confidence", "CONFIRMED")),
    )


def _behavior_assessment(value: object) -> BehaviorAssessment:
    raw = _object(value, "assessment")
    digest = raw.get("run_receipt_digest")
    return BehaviorAssessment(
        str(raw["behavior_id"]),
        str(raw["source_identity"]),
        str(raw["status"]),
        bool(raw.get("executed", False)),
        str(raw.get("oracle_status", "UNKNOWN")),
        str(digest) if digest is not None else None,
        _str_tuple(raw.get("reason_codes")),
    )


def _benchmark(value: object) -> BenchmarkManifest:
    raw = _object(value, "benchmark")
    metadata = raw.get("metadata")
    return BenchmarkManifest(
        benchmark_id=str(raw["benchmark_id"]),
        target_id=str(raw["target_id"]),
        target_sha=str(raw["target_sha"]),
        expected_label=str(raw.get("expected_label", "CLEAN")),
        defect_id=str(raw["defect_id"]) if raw.get("defect_id") is not None else None,
        allowed_exposures=_str_tuple(raw.get("allowed_exposures")),
        split_membership=str(raw.get("split_membership", "HOLDOUT")),
        domain_tags=_str_tuple(raw.get("domain_tags")),
        metadata=_object(metadata, "benchmark.metadata") if isinstance(metadata, dict) else {},
    )


def _strategy_run(value: object) -> StrategyRunMetrics:
    raw = _object(value, "strategy run")
    return StrategyRunMetrics(
        str(raw["run_id"]),
        str(raw["strategy_profile_id"]),
        str(raw["source_identity"]),
        str(raw["frozen_corpus_digest"]),
        _str_tuple(raw.get("qualified_root_cause_ids")),
        _str_tuple(raw.get("execution_receipt_ids")),
        float(raw.get("cost_units", 0)),
        int(raw.get("evaluated_cases", 0)),
    )


def _exposure(value: object) -> ExposureManifest:
    raw = _object(value, "exposure")
    return ExposureManifest(
        str(raw["source_identity"]),
        str(raw["history_cut_digest"]),
        _str_tuple(raw.get("allowed_refs")),
        _str_tuple(raw.get("exposure_classes")),
        _str_tuple(raw.get("forbidden_refs")),
    )


def _lane(value: object) -> LaneProposal:
    raw = _object(value, "lane")
    return LaneProposal(
        str(raw["lane_id"]),
        str(raw["role_id"]),
        str(raw["method"]),
        _str_tuple(raw.get("scope_ids")),
        _str_tuple(raw.get("obligation_ids")),
        str(raw.get("consumer", "")),
        int(raw.get("cost_units", 0)),
        _exposure(raw.get("exposure")),
        str(raw.get("independence_group", "")),
        str(raw.get("session_id", "")),
        _str_tuple(raw.get("predecessor_lane_ids")),
        bool(raw.get("mandatory", False)),
    )


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
    feature_matrix = features_sub.add_parser("matrix")
    feature_matrix.add_argument("--file", required=True)
    feature_verify = features_sub.add_parser("verify")
    feature_verify.add_argument("--file", required=True)

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

    qualification = sub.add_parser("qualification")
    qualification_sub = qualification.add_subparsers(dest="action", required=True)
    qualification_continuous = qualification_sub.add_parser("continuous")
    qualification_continuous.add_argument("--file", required=True)

    strategy = sub.add_parser("strategy")
    strategy_sub = strategy.add_subparsers(dest="action", required=True)
    strategy_validate = strategy_sub.add_parser("validate")
    strategy_validate.add_argument("--file", required=True)
    strategy_benchmark = strategy_sub.add_parser("benchmark")
    strategy_benchmark.add_argument("--file", required=True)

    opportunities = sub.add_parser("opportunities")
    opportunities_sub = opportunities.add_subparsers(dest="action", required=True)
    opportunities_review = opportunities_sub.add_parser("review")
    opportunities_review.add_argument("--file", required=True)

    incremental = sub.add_parser("incremental")
    incremental_sub = incremental.add_subparsers(dest="action", required=True)
    successor_validate = incremental_sub.add_parser("successor-validate")
    successor_validate.add_argument("--file", required=True)

    share = sub.add_parser("share")
    share_sub = share.add_subparsers(dest="action", required=True)
    share_trends = share_sub.add_parser("trends")
    share_trends.add_argument("--file", required=True)
    share_verify = share_sub.add_parser("verify")
    share_verify.add_argument("--file", required=True)
    share_verify.add_argument("--key-hex", required=True)
    share_verify.add_argument("--expected-key-id")

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


def _run_feature_verification(data: Mapping[str, Any]) -> tuple[dict[str, object], int]:
    behavior_raw = _object(data.get("behavior"), "behavior")
    oracle_raw = _object(data.get("oracle"), "oracle")
    behavior = BehaviorCase(
        str(behavior_raw["behavior_id"]),
        str(behavior_raw["feature_id"]),
        str(behavior_raw["description"]),
        _str_tuple(behavior_raw.get("requirement_refs")),
        bool(behavior_raw.get("negative_or_recovery", False)),
    )
    oracle = qualify_oracle(
        str(oracle_raw["oracle_id"]),
        str(oracle_raw["source_kind"]),
        _str_tuple(oracle_raw.get("source_refs")),
    )
    testability = assess_testability(behavior, _str_tuple(data.get("available_adapters")))
    verification_plan = plan_verification(
        source_identity=str(data["source_identity"]),
        behavior=behavior,
        oracle=oracle,
        testability=testability,
        argv=_str_tuple(data.get("argv")),
        cwd=str(data["cwd"]) if data.get("cwd") is not None else None,
        fixture_refs=_str_tuple(data.get("fixture_refs")),
        environment_identity=str(data.get("environment_identity", "LOCAL_DECLARED")),
    )
    tool_spec = CliBehaviorAdapter.to_tool_spec(
        verification_plan,
        ruleset_ref=str(data.get("ruleset_ref", "functional-cli-v1")),
        require_no_network=bool(data.get("require_no_network", True)),
    )
    allowed_executables = _str_tuple(data.get("authorized_executables")) or (tool_spec.argv[0],)
    authorization = ActionAuthorization(
        ("FUNCTIONAL_VERIFICATION",),
        allowed_executables,
        _str_tuple(data.get("allowed_work_roots")),
    )
    run_result = OperationalToolSupervisor(authorization).run(tool_spec)
    assessment = qualify_behavior(verification_plan, run_result)
    output: dict[str, object] = {
        "plan": asdict(verification_plan),
        "run": asdict(run_result),
        "assessment": asdict(assessment),
    }
    return output, 0 if assessment.status == "PASS" else 3


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
            report_remediation_plan = RemediationPlanner(snapshot).build().as_dict()
            validate_remediation_plan(report_remediation_plan)
            if args.format == "bundle":
                export_result = export_report_bundle(snapshot, report_remediation_plan, args.out)
                export_result["section_completeness"] = section_completeness(report, remediation_plan=report_remediation_plan)
                _json(export_result)
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
            remediation_plan = RemediationPlanner(snapshot).build().as_dict()
            validate_remediation_plan(remediation_plan)
            out = Path(args.out)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(remediation_plan, ensure_ascii=False, sort_keys=True, indent=2), encoding="utf-8")
            _json({"status": "PASS", "path": str(out), "repair_unit_count": len(remediation_plan["repair_units"])})
            return 0
        if args.command == "remediation" and args.action == "validate":
            remediation_payload = json.loads(Path(args.file).read_text(encoding="utf-8"))
            _json(validate_remediation_plan(remediation_payload))
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
        if args.command == "features" and args.action == "matrix":
            data = _load_object(args.file)
            feature_values = data.get("features")
            assessment_values = data.get("assessments")
            if not isinstance(feature_values, list) or not isinstance(assessment_values, list):
                raise ValueError("features and assessments must be arrays")
            feature_matrix_result = feature_status_matrix(
                tuple(_feature_revision(item) for item in feature_values),
                tuple(_behavior_assessment(item) for item in assessment_values),
            )
            _json(feature_matrix_result)
            return 0
        if args.command == "features" and args.action == "verify":
            feature_verify_result, code = _run_feature_verification(_load_object(args.file))
            _json(feature_verify_result)
            return code
        if args.command == "tools":
            explicit_tool_spec = _tool_spec(args)
            auth = ActionAuthorization(
                ("OPERATOR_EXPLICIT_TOOL",),
                (explicit_tool_spec.argv[0],),
                (args.cwd,) if args.cwd else (),
            )
            supervisor = OperationalToolSupervisor(auth)
            tool_result = (
                supervisor.inspect(explicit_tool_spec)
                if args.action == "inspect"
                else supervisor.run(explicit_tool_spec).__dict__
            )
            _json(tool_result)
            return 0
        if args.command == "qualification" and args.action == "continuous":
            data = _load_object(args.file)
            holdout_values = data.get("holdout")
            if not isinstance(holdout_values, list):
                raise ValueError("holdout must be an array")
            holdout = FrozenHoldout.freeze(tuple(_benchmark(item) for item in holdout_values))
            observed_raw = _object(data.get("observed"), "observed")
            bypass_raw = _object(data.get("anti_bypass_results"), "anti_bypass_results")
            qualification_result = evaluate_continuous_holdout(
                holdout,
                {str(key): str(value) for key, value in observed_raw.items()},
                {str(key): value is True for key, value in bypass_raw.items()},
                required_anti_bypass_ids=_str_tuple(data.get("required_anti_bypass_ids")),
            )
            _json(asdict(qualification_result))
            return 0 if qualification_result.qualified else 3
        if args.command == "strategy" and args.action == "validate":
            data = _load_object(args.file)
            profile_raw = _object(data.get("profile"), "profile")
            plan_raw = _object(data.get("plan"), "plan")
            lane_values = plan_raw.get("lanes")
            if not isinstance(lane_values, list):
                raise ValueError("plan.lanes must be an array")
            profile = AuditStrategyProfile(
                str(profile_raw["profile_id"]),
                _str_tuple(profile_raw.get("mandatory_role_ids")),
                _str_tuple(profile_raw.get("allowed_methods")),
                _str_tuple(profile_raw.get("allowed_exposure_classes")),
                int(profile_raw.get("max_budget_units", 0)),
            )
            lanes = tuple(_lane(item) for item in lane_values)
            strategy_plan = StrategyPlan(
                str(plan_raw.get("revision", "1")),
                str(plan_raw["source_identity"]),
                str(plan_raw["history_cut_digest"]),
                lanes,
                int(plan_raw.get("budget_units", sum(lane.cost_units for lane in lanes))),
                str(plan_raw.get("state", "PLAN_PROPOSED")),
            )
            strategy_validation_result = validate_plan(strategy_plan, profile)
            _json(strategy_validation_result)
            return 0 if strategy_validation_result.get("status") == "VALIDATED" else 3
        if args.command == "strategy" and args.action == "benchmark":
            data = _load_object(args.file)
            strategy_benchmark_result = compare_adaptive_to_baseline(
                _strategy_run(data.get("baseline")),
                _strategy_run(data.get("adaptive")),
                required_baseline_root_causes=_str_tuple(data.get("required_baseline_root_causes")),
            )
            _json(asdict(strategy_benchmark_result))
            return 0 if strategy_benchmark_result.benefit_demonstrated else 3
        if args.command == "opportunities" and args.action == "review":
            data = _load_object(args.file)
            context_raw = _object(data.get("context"), "context")
            proposal_raw = _object(data.get("proposal"), "proposal")
            context = ProductContext(
                str(context_raw["target_source_identity"]),
                str(context_raw["product_name"]),
                _str_tuple(context_raw.get("user_groups")),
                _str_tuple(context_raw.get("platform_classes")),
                _str_tuple(context_raw.get("context_refs")),
            )
            proposal = OpportunityProposal(
                str(proposal_raw["opportunity_id"]),
                str(proposal_raw["target_source_identity"]),
                str(proposal_raw["category"]),
                str(proposal_raw["title"]),
                str(proposal_raw["user_problem"]),
                _str_tuple(proposal_raw.get("target_users")),
                _str_tuple(proposal_raw.get("evidence_refs")),
                int(proposal_raw["current_steps"]) if proposal_raw.get("current_steps") is not None else None,
                int(proposal_raw["proposed_steps"]) if proposal_raw.get("proposed_steps") is not None else None,
                str(proposal_raw["expected_value"]),
                str(proposal_raw["implementation_cost"]),
                str(proposal_raw["risk"]),
                _str_tuple(proposal_raw.get("alternatives")),
                str(proposal_raw["controls_and_measurement"]),
                str(proposal_raw["confidence_basis"]),
                str(proposal_raw.get("consumer_report_section", "PRODUCT_AND_UX_OPPORTUNITIES")),
            )
            simpler = data.get("simpler_alternative")
            opportunity_decision = qualify_opportunity_for_report(
                proposal,
                context,
                existing_feature_titles=_str_tuple(data.get("existing_feature_titles")),
                simpler_alternative=str(simpler) if simpler is not None else None,
            )
            _json(asdict(opportunity_decision))
            return 0 if opportunity_decision.status == "ACCEPT_FOR_REPORT" else 3
        if args.command == "incremental" and args.action == "successor-validate":
            data = _load_object(args.file)
            spec_raw = _object(data.get("spec"), "spec")
            successor_spec = SuccessorCampaignSpec(
                str(spec_raw["predecessor_campaign_id"]),
                str(spec_raw["predecessor_conclusion_digest"]),
                str(spec_raw["predecessor_source_identity"]),
                str(spec_raw["successor_campaign_id"]),
                str(spec_raw["successor_source_identity"]),
            )
            successor_result = validate_successor_selection(
                successor_spec,
                predecessor_is_concluded=bool(data.get("predecessor_is_concluded", False)),
                predecessor_source_after=str(data.get("predecessor_source_after", "")),
                predecessor_state_after=str(data.get("predecessor_state_after", "")),
                competing_successor_refs=_str_tuple(data.get("competing_successor_refs")),
                selected_successor_ref=str(data["selected_successor_ref"])
                if data.get("selected_successor_ref") is not None
                else None,
            )
            _json(successor_result)
            return 0 if successor_result.get("status") == "PASS" else 3
        if args.command == "share" and args.action == "trends":
            data = _load_object(args.file)
            snapshot_values = data.get("snapshots")
            if not isinstance(snapshot_values, list):
                raise ValueError("snapshots must be an array")
            snapshots = []
            for item in snapshot_values:
                raw = _object(item, "snapshot")
                snapshots.append(TrendSnapshot(
                    str(raw["source_identity"]),
                    str(raw["scope_digest"]),
                    str(raw["policy_digest"]),
                    int(raw["qualified"]),
                    int(raw["denominator"]),
                ))
            trend_result = compare_trend(tuple(snapshots))
            _json(trend_result)
            return 0 if trend_result.get("status") == "COMPARABLE" else 3
        if args.command == "share" and args.action == "verify":
            data = _load_object(args.file)
            bundle = RecipientBundle(
                str(data["payload"]).encode("utf-8"),
                str(data["payload_sha256"]),
                str(data["signature_hex"]),
                str(data["key_id"]),
                str(data["source_identity"]),
                str(data["history_cut_digest"]),
                _str_tuple(data.get("removed_private_fields")),
                str(data.get("signature_profile", "HMAC-SHA256-SHARED-SECRET")),
            )
            share_verification_result = verify_recipient_bundle(
                bundle,
                signing_key=bytes.fromhex(args.key_hex),
                expected_key_id=args.expected_key_id,
            )
            _json(share_verification_result)
            return 0 if share_verification_result.get("status") == "PASS" else 3
        return 2
    except Exception as exc:
        _json({"status": "ERROR", "error": type(exc).__name__, "detail": str(exc)})
        return 1


def main() -> None:
    raise SystemExit(run_cli())


if __name__ == "__main__":
    main()
