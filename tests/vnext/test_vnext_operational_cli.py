from __future__ import annotations

import json

from bdb_audit.qualification.continuous import FrozenHoldout
from bdb_audit.qualification.receipts import BenchmarkManifest
from bdb_audit.vnext_cli import create_parser, run_cli


def _write(tmp_path, name: str, value: object) -> str:
    path = tmp_path / name
    path.write_text(json.dumps(value), encoding="utf-8")
    return str(path)


def _receipt(
    benchmark_id: str,
    target_id: str,
    observed_label: str | None = None,
    *,
    receipt_id: str | None = None,
    status: str = "PASS",
    exit_code: int = 0,
    passed: int = 1,
    failed: int = 0,
) -> dict[str, object]:
    details: dict[str, str] = {}
    if observed_label is not None:
        details["observed_label"] = observed_label
    return {
        "receipt_id": receipt_id or f"receipt-{target_id}",
        "benchmark_id": benchmark_id,
        "target_id": target_id,
        "checker_id": "cli-contract-checker",
        "execution_timestamp": "2026-09-15T00:00:00Z",
        "exit_code": exit_code,
        "status": status,
        "raw_output_digest": "d" * 64,
        "evaluated_cases_count": 1,
        "passed_cases_count": passed,
        "failed_cases_count": failed,
        "unsupported_cases_count": 0,
        "unknown_cases_count": 0,
        "execution_duration_ms": 1,
        "details": details,
    }


def _strategy_receipt(
    run_id: str,
    profile: str,
    roots: list[str],
    cost_units: float,
    *,
    receipt_id: str,
) -> dict[str, object]:
    return {
        "receipt_id": receipt_id,
        "benchmark_id": f"strategy:{profile}",
        "target_id": run_id,
        "checker_id": f"strategy-runner:{profile}",
        "execution_timestamp": "2026-09-15T00:00:00Z",
        "exit_code": 0,
        "status": "PASS",
        "raw_output_digest": "e" * 64,
        "evaluated_cases_count": 1,
        "passed_cases_count": 1,
        "failed_cases_count": 0,
        "unsupported_cases_count": 0,
        "unknown_cases_count": 0,
        "execution_duration_ms": 1,
        "details": {
            "strategy_run_id": run_id,
            "strategy_profile_id": profile,
            "source_identity": "src",
            "frozen_corpus_digest": "c" * 64,
            "evaluated_cases": 10,
            "cost_units": cost_units,
            "qualified_root_cause_ids": roots,
        },
    }


def test_vnext_cli_exposes_operational_vnext_surfaces():
    parser = create_parser()
    assert parser.parse_args(["features", "matrix", "--file", "x"]).command == "features"
    assert parser.parse_args(["features", "verify", "--file", "x"]).command == "features"
    assert parser.parse_args(["qualification", "continuous", "--file", "x"]).command == "qualification"
    assert parser.parse_args(["strategy", "validate", "--file", "x"]).command == "strategy"
    assert parser.parse_args(["strategy", "benchmark", "--file", "x"]).command == "strategy"
    assert parser.parse_args(["opportunities", "review", "--file", "x"]).command == "opportunities"
    assert parser.parse_args(["incremental", "successor-validate", "--file", "x"]).command == "incremental"
    assert parser.parse_args(["share", "trends", "--file", "x"]).command == "share"
    assert parser.parse_args(["share", "verify", "--file", "x", "--key-hex", "00"]).command == "share"


def test_cli_continuous_qualification_is_receipt_bound_fail_closed_and_machine_readable(tmp_path, capsys):
    holdout_rows = [
        {"benchmark_id": "b1", "target_id": "clean", "target_sha": "a" * 40, "expected_label": "CLEAN", "split_membership": "HOLDOUT"},
        {"benchmark_id": "b2", "target_id": "bad", "target_sha": "b" * 40, "expected_label": "DEFECTIVE", "split_membership": "HOLDOUT"},
    ]
    frozen = FrozenHoldout.freeze(tuple(
        BenchmarkManifest(
            str(row["benchmark_id"]),
            str(row["target_id"]),
            str(row["target_sha"]),
            str(row["expected_label"]),
            split_membership="HOLDOUT",
        )
        for row in holdout_rows
    ))
    base = {
        "holdout": holdout_rows,
        "expected_commitment_sha256": frozen.commitment_sha256,
        "holdout_runs": [
            {
                "manifest": holdout_rows[0],
                "observed_label": "CLEAN",
                "receipt": _receipt("b1", "clean", "CLEAN"),
            },
            {
                "manifest": holdout_rows[1],
                "observed_label": "DEFECTIVE",
                "receipt": _receipt("b2", "bad", "DEFECTIVE"),
            },
        ],
        "required_anti_bypass_ids": ["validator_disabled"],
        "anti_bypass_receipts": [
            _receipt("anti-bypass:validator_disabled", "validator_disabled", receipt_id="anti-validator-disabled")
        ],
    }
    path = _write(tmp_path, "qualification.json", base)
    assert run_cli(["qualification", "continuous", "--file", path]) == 0
    output = capsys.readouterr().out
    assert '"qualified": true' in output
    assert '"verified_run_receipt_digests"' in output

    base["anti_bypass_receipts"] = [
        _receipt(
            "anti-bypass:validator_disabled",
            "validator_disabled",
            receipt_id="anti-validator-disabled-fail",
            status="FAIL",
            exit_code=1,
            passed=0,
            failed=1,
        )
    ]
    path = _write(tmp_path, "qualification-fail.json", base)
    assert run_cli(["qualification", "continuous", "--file", path]) == 3
    assert "ANTI_BYPASS_FAILED:validator_disabled" in capsys.readouterr().out

    legacy = {
        "holdout": holdout_rows,
        "observed": {"clean": "CLEAN", "bad": "DEFECTIVE"},
        "required_anti_bypass_ids": ["validator_disabled"],
        "anti_bypass_results": {"validator_disabled": True},
    }
    path = _write(tmp_path, "qualification-legacy-declarative.json", legacy)
    assert run_cli(["qualification", "continuous", "--file", path]) == 1
    output = capsys.readouterr().out
    assert "holdout_runs must be an array" in output
    assert '"qualified": true' not in output


def test_cli_strategy_benchmark_requires_receipt_bound_measured_unique_gain(tmp_path, capsys):
    baseline_receipt = _strategy_receipt("base", "fixed", ["r1"], 5, receipt_id="receipt-base")
    adaptive_receipt = _strategy_receipt("adaptive", "adaptive", ["r1", "r2"], 7, receipt_id="receipt-adaptive")
    data = {
        "baseline": {
            "run_id": "base", "strategy_profile_id": "fixed", "source_identity": "src",
            "frozen_corpus_digest": "c" * 64, "qualified_root_cause_ids": ["r1"],
            "execution_receipt_ids": ["receipt-base"], "actual_receipts": [baseline_receipt],
            "cost_units": 5, "evaluated_cases": 10,
        },
        "adaptive": {
            "run_id": "adaptive", "strategy_profile_id": "adaptive", "source_identity": "src",
            "frozen_corpus_digest": "c" * 64, "qualified_root_cause_ids": ["r1", "r2"],
            "execution_receipt_ids": ["receipt-adaptive"], "actual_receipts": [adaptive_receipt],
            "cost_units": 7, "evaluated_cases": 10,
        },
    }
    path = _write(tmp_path, "benchmark.json", data)
    assert run_cli(["strategy", "benchmark", "--file", path]) == 0
    output = capsys.readouterr().out
    assert "BENEFIT_DEMONSTRATED" in output
    assert "verified_execution_receipt_digests" in output

    data["adaptive"]["qualified_root_cause_ids"] = ["r2"]
    adaptive_receipt["details"]["qualified_root_cause_ids"] = ["r2"]
    path = _write(tmp_path, "benchmark-weakened.json", data)
    assert run_cli(["strategy", "benchmark", "--file", path]) == 3
    assert "BASELINE_ASSURANCE_WEAKENED" in capsys.readouterr().out

    data["adaptive"]["qualified_root_cause_ids"] = ["r1", "r2"]
    adaptive_receipt["details"]["qualified_root_cause_ids"] = ["r1", "r2"]
    data["baseline"].pop("actual_receipts")
    path = _write(tmp_path, "benchmark-declarative-only.json", data)
    assert run_cli(["strategy", "benchmark", "--file", path]) == 3
    output = capsys.readouterr().out
    assert "BASELINE_ACTUAL_EXECUTION_RECEIPTS_REQUIRED" in output
    assert "BENEFIT_DEMONSTRATED" not in output


def test_cli_opportunity_review_and_successor_validation(tmp_path, capsys):
    opportunity = {
        "context": {
            "target_source_identity": "src", "product_name": "Target", "user_groups": ["operator"],
            "platform_classes": ["web"], "context_refs": ["ctx:1"],
        },
        "proposal": {
            "opportunity_id": "opp", "target_source_identity": "src", "category": "WORKFLOW",
            "title": "Reduce repeated steps", "user_problem": "Task has repeated navigation", "target_users": ["operator"],
            "evidence_refs": ["metric:task_steps"], "current_steps": 6, "proposed_steps": 3,
            "expected_value": "fewer steps", "implementation_cost": "LOW", "risk": "LOW",
            "alternatives": ["keep current"], "controls_and_measurement": "measure completion rate",
            "confidence_basis": "MEASURED",
        },
        "evidence": [{
            "evidence_ref": "metric:task_steps",
            "target_source_identity": "src",
            "evidence_kind": "METRIC",
            "provenance_ref": "accepted-history:metric-task-steps",
            "measured_value": 6,
            "measurement_unit": "steps",
            "observed": True,
        }],
    }
    path = _write(tmp_path, "opportunity.json", opportunity)
    assert run_cli(["opportunities", "review", "--file", path]) == 0
    output = capsys.readouterr().out
    assert "QUICK_WIN" in output
    assert "verified_evidence_refs" in output

    missing_evidence = dict(opportunity)
    missing_evidence.pop("evidence")
    path = _write(tmp_path, "opportunity-no-evidence.json", missing_evidence)
    assert run_cli(["opportunities", "review", "--file", path]) == 3
    output = capsys.readouterr().out
    assert "EVIDENCE_CATALOG_REQUIRED" in output
    assert "QUICK_WIN" not in output

    successor = {
        "spec": {
            "predecessor_campaign_id": "c1", "predecessor_conclusion_digest": "d1",
            "predecessor_source_identity": "src1", "successor_campaign_id": "c2", "successor_source_identity": "src2",
        },
        "predecessor_is_concluded": True,
        "predecessor_source_after": "src1",
        "predecessor_state_after": "CONCLUDED",
    }
    path = _write(tmp_path, "successor.json", successor)
    assert run_cli(["incremental", "successor-validate", "--file", path]) == 0
    assert '"status": "PASS"' in capsys.readouterr().out


def test_cli_feature_matrix_requires_declared_denominator_and_trend_scope_is_explicit(tmp_path, capsys):
    matrix = {
        "features": [{
            "feature_id": "f", "revision": "1", "source_identity": "src", "user_task": "do thing",
            "entrypoints": ["cli"], "requirement_refs": ["req:1"],
        }],
        "assessments": [{
            "behavior_id": "f:happy", "source_identity": "src", "status": "PASS", "executed": True,
            "oracle_status": "QUALIFIED", "run_receipt_digest": "d" * 64,
        }],
        "required_behavior_ids": {"f": ["f:happy"]},
    }
    path = _write(tmp_path, "matrix.json", matrix)
    assert run_cli(["features", "matrix", "--file", path]) == 0
    output = capsys.readouterr().out
    assert "VERIFIED" in output
    assert '"denominator_declared": true' in output

    matrix.pop("required_behavior_ids")
    path = _write(tmp_path, "matrix-no-denominator.json", matrix)
    assert run_cli(["features", "matrix", "--file", path]) == 0
    output = capsys.readouterr().out
    assert "VERIFIED" not in output
    assert '"denominator_declared": false' in output

    trends = {"snapshots": [
        {"source_identity": "s1", "scope_digest": "scope", "policy_digest": "policy", "qualified": 8, "denominator": 10},
        {"source_identity": "s2", "scope_digest": "scope", "policy_digest": "policy", "qualified": 9, "denominator": 10},
    ]}
    path = _write(tmp_path, "trends.json", trends)
    assert run_cli(["share", "trends", "--file", path]) == 0
    assert "COMPARABLE" in capsys.readouterr().out

    trends["snapshots"][1]["scope_digest"] = "different"
    path = _write(tmp_path, "trends-incomparable.json", trends)
    assert run_cli(["share", "trends", "--file", path]) == 3
    assert "INCOMPARABLE_SCOPE" in capsys.readouterr().out
