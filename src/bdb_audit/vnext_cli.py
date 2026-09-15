"""vNext CLI with strict evidence binding for RU13, RU14 and RU15.

All commands outside the strict qualification/strategy/opportunity surfaces
delegate to the previously qualified CLI implementation.  Intercepted paths
cannot qualify from caller-declared labels, receipt ids, cost/root-cause
summaries, or unresolved product evidence.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
from typing import Any

from . import vnext_cli_legacy as _legacy
from .opportunities import (
    OpportunityEvidence,
    OpportunityProposal,
    ProductContext,
    qualify_opportunity_for_report,
)
from .qualification import ActualRunReceipt, FrozenHoldout, evaluate_continuous_holdout
from .qualification.corpus import BenchmarkRun
from .strategy import StrategyRunMetrics, compare_adaptive_to_baseline


create_parser = _legacy.create_parser


def _actual_run_receipt(value: object, label: str) -> ActualRunReceipt:
    raw = _legacy._object(value, label)
    details = raw.get("details")
    return ActualRunReceipt(
        receipt_id=str(raw["receipt_id"]),
        benchmark_id=str(raw["benchmark_id"]),
        target_id=str(raw["target_id"]),
        checker_id=str(raw["checker_id"]),
        execution_timestamp=str(raw["execution_timestamp"]),
        exit_code=int(raw["exit_code"]),
        status=str(raw["status"]),
        raw_output_digest=str(raw["raw_output_digest"]),
        evaluated_cases_count=int(raw["evaluated_cases_count"]),
        passed_cases_count=int(raw["passed_cases_count"]),
        failed_cases_count=int(raw["failed_cases_count"]),
        unsupported_cases_count=int(raw.get("unsupported_cases_count", 0)),
        unknown_cases_count=int(raw.get("unknown_cases_count", 0)),
        execution_duration_ms=int(raw.get("execution_duration_ms", 0)),
        details=_legacy._object(details, f"{label}.details") if isinstance(details, dict) else {},
    )


def _benchmark_run(value: object) -> BenchmarkRun:
    raw = _legacy._object(value, "holdout_run")
    return BenchmarkRun(
        _legacy._benchmark(raw.get("manifest")),
        str(raw["observed_label"]),
        _actual_run_receipt(raw.get("receipt"), "holdout_run.receipt"),
    )


def _run_strict_continuous(args: argparse.Namespace) -> int:
    data: dict[str, Any] = _legacy._load_object(args.file)
    holdout_values = data.get("holdout")
    run_values = data.get("holdout_runs")
    anti_values = data.get("anti_bypass_receipts")
    if not isinstance(holdout_values, list):
        raise ValueError("holdout must be an array")
    if not isinstance(run_values, list):
        raise ValueError("holdout_runs must be an array")
    if not isinstance(anti_values, list):
        raise ValueError("anti_bypass_receipts must be an array")
    if "expected_commitment_sha256" not in data:
        raise ValueError("expected_commitment_sha256 is required")

    holdout = FrozenHoldout.freeze(tuple(_legacy._benchmark(item) for item in holdout_values))
    result = evaluate_continuous_holdout(
        holdout,
        tuple(_benchmark_run(item) for item in run_values),
        tuple(_actual_run_receipt(item, "anti_bypass_receipt") for item in anti_values),
        expected_commitment_sha256=str(data["expected_commitment_sha256"]),
        required_anti_bypass_ids=_legacy._str_tuple(data.get("required_anti_bypass_ids")),
    )
    _legacy._json(asdict(result))
    return 0 if result.qualified else 3


def _strategy_run(value: object, label: str) -> StrategyRunMetrics:
    raw = _legacy._object(value, label)
    actual_values = raw.get("actual_receipts")
    if actual_values is None:
        actual_receipts: tuple[ActualRunReceipt, ...] = ()
    elif isinstance(actual_values, list):
        actual_receipts = tuple(
            _actual_run_receipt(item, f"{label}.actual_receipt") for item in actual_values
        )
    else:
        raise ValueError(f"{label}.actual_receipts must be an array")
    return StrategyRunMetrics(
        run_id=str(raw["run_id"]),
        strategy_profile_id=str(raw["strategy_profile_id"]),
        source_identity=str(raw["source_identity"]),
        frozen_corpus_digest=str(raw["frozen_corpus_digest"]),
        qualified_root_cause_ids=_legacy._str_tuple(raw.get("qualified_root_cause_ids")),
        execution_receipt_ids=_legacy._str_tuple(raw.get("execution_receipt_ids")),
        cost_units=float(raw.get("cost_units", 0)),
        evaluated_cases=int(raw.get("evaluated_cases", 0)),
        actual_receipts=actual_receipts,
    )


def _run_strict_strategy_benchmark(args: argparse.Namespace) -> int:
    data: dict[str, Any] = _legacy._load_object(args.file)
    result = compare_adaptive_to_baseline(
        _strategy_run(data.get("baseline"), "baseline"),
        _strategy_run(data.get("adaptive"), "adaptive"),
        required_baseline_root_causes=_legacy._str_tuple(data.get("required_baseline_root_causes")),
    )
    _legacy._json(asdict(result))
    return 0 if result.benefit_demonstrated else 3


def _opportunity_evidence(value: object) -> OpportunityEvidence:
    raw = _legacy._object(value, "opportunity evidence")
    measured_raw = raw.get("measured_value")
    measured: float | int | None
    if isinstance(measured_raw, bool) or not isinstance(measured_raw, (int, float)):
        measured = None
    else:
        measured = measured_raw
    observed_raw = raw.get("observed", True)
    if not isinstance(observed_raw, bool):
        raise ValueError("opportunity evidence observed must be boolean")
    unit_raw = raw.get("measurement_unit")
    return OpportunityEvidence(
        evidence_ref=str(raw["evidence_ref"]),
        target_source_identity=str(raw["target_source_identity"]),
        evidence_kind=str(raw["evidence_kind"]),
        provenance_ref=str(raw["provenance_ref"]),
        measured_value=measured,
        measurement_unit=str(unit_raw) if unit_raw is not None else None,
        observed=observed_raw,
    )


def _run_strict_opportunity_review(args: argparse.Namespace) -> int:
    data: dict[str, Any] = _legacy._load_object(args.file)
    context_raw = _legacy._object(data.get("context"), "context")
    proposal_raw = _legacy._object(data.get("proposal"), "proposal")
    context = ProductContext(
        str(context_raw["target_source_identity"]),
        str(context_raw["product_name"]),
        _legacy._str_tuple(context_raw.get("user_groups")),
        _legacy._str_tuple(context_raw.get("platform_classes")),
        _legacy._str_tuple(context_raw.get("context_refs")),
    )
    proposal = OpportunityProposal(
        str(proposal_raw["opportunity_id"]),
        str(proposal_raw["target_source_identity"]),
        str(proposal_raw["category"]),
        str(proposal_raw["title"]),
        str(proposal_raw["user_problem"]),
        _legacy._str_tuple(proposal_raw.get("target_users")),
        _legacy._str_tuple(proposal_raw.get("evidence_refs")),
        int(proposal_raw["current_steps"]) if proposal_raw.get("current_steps") is not None else None,
        int(proposal_raw["proposed_steps"]) if proposal_raw.get("proposed_steps") is not None else None,
        str(proposal_raw["expected_value"]),
        str(proposal_raw["implementation_cost"]),
        str(proposal_raw["risk"]),
        _legacy._str_tuple(proposal_raw.get("alternatives")),
        str(proposal_raw["controls_and_measurement"]),
        str(proposal_raw["confidence_basis"]),
        str(proposal_raw.get("consumer_report_section", "PRODUCT_AND_UX_OPPORTUNITIES")),
    )

    evidence_values = data.get("evidence")
    catalog: dict[str, OpportunityEvidence] | None
    if evidence_values is None:
        catalog = None
    elif isinstance(evidence_values, list):
        catalog = {}
        for item in evidence_values:
            record = _opportunity_evidence(item)
            if record.evidence_ref in catalog:
                raise ValueError(f"duplicate opportunity evidence ref: {record.evidence_ref}")
            catalog[record.evidence_ref] = record
    else:
        raise ValueError("evidence must be an array")

    simpler = data.get("simpler_alternative")
    result = qualify_opportunity_for_report(
        proposal,
        context,
        existing_feature_titles=_legacy._str_tuple(data.get("existing_feature_titles")),
        simpler_alternative=str(simpler) if simpler is not None else None,
        evidence_catalog=catalog,
    )
    _legacy._json(asdict(result))
    return 0 if result.status == "ACCEPT_FOR_REPORT" else 3


def run_cli(argv: list[str] | None = None) -> int:
    args = create_parser().parse_args(argv)
    if args.command == "qualification" and args.action == "continuous":
        try:
            return _run_strict_continuous(args)
        except Exception as exc:
            _legacy._json({"status": "ERROR", "error": type(exc).__name__, "detail": str(exc)})
            return 1
    if args.command == "strategy" and args.action == "benchmark":
        try:
            return _run_strict_strategy_benchmark(args)
        except Exception as exc:
            _legacy._json({"status": "ERROR", "error": type(exc).__name__, "detail": str(exc)})
            return 1
    if args.command == "opportunities" and args.action == "review":
        try:
            return _run_strict_opportunity_review(args)
        except Exception as exc:
            _legacy._json({"status": "ERROR", "error": type(exc).__name__, "detail": str(exc)})
            return 1
    return _legacy.run_cli(argv)


def main() -> None:
    raise SystemExit(run_cli())


if __name__ == "__main__":
    main()
