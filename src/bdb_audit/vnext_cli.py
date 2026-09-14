"""vNext CLI with strict RU13 continuous-qualification evidence binding.

All non-RU13 commands delegate to the previously qualified CLI implementation
bit-for-bit.  Only ``qualification continuous`` is intercepted here so the
release-methodology path cannot qualify from caller-declared labels/booleans.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
from typing import Any

from . import vnext_cli_legacy as _legacy
from .qualification import ActualRunReceipt, FrozenHoldout, evaluate_continuous_holdout
from .qualification.corpus import BenchmarkRun


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


def run_cli(argv: list[str] | None = None) -> int:
    args = create_parser().parse_args(argv)
    if args.command == "qualification" and args.action == "continuous":
        try:
            return _run_strict_continuous(args)
        except Exception as exc:
            _legacy._json({"status": "ERROR", "error": type(exc).__name__, "detail": str(exc)})
            return 1
    return _legacy.run_cli(argv)


def main() -> None:
    raise SystemExit(run_cli())


if __name__ == "__main__":
    main()
