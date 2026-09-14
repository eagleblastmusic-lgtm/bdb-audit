from __future__ import annotations

import json

from bdb_audit.vnext_cli import create_parser, run_cli


def _write(tmp_path, name: str, value: object) -> str:
    path = tmp_path / name
    path.write_text(json.dumps(value), encoding="utf-8")
    return str(path)


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


def test_cli_continuous_qualification_is_fail_closed_and_machine_readable(tmp_path, capsys):
    base = {
        "holdout": [
            {"benchmark_id": "b1", "target_id": "clean", "target_sha": "a" * 40, "expected_label": "CLEAN", "split_membership": "HOLDOUT"},
            {"benchmark_id": "b2", "target_id": "bad", "target_sha": "b" * 40, "expected_label": "DEFECTIVE", "split_membership": "HOLDOUT"},
        ],
        "observed": {"clean": "CLEAN", "bad": "DEFECTIVE"},
        "required_anti_bypass_ids": ["validator_disabled"],
        "anti_bypass_results": {"validator_disabled": True},
    }
    path = _write(tmp_path, "qualification.json", base)
    assert run_cli(["qualification", "continuous", "--file", path]) == 0
    assert '"qualified": true' in capsys.readouterr().out

    base["anti_bypass_results"] = {"validator_disabled": False}
    path = _write(tmp_path, "qualification-fail.json", base)
    assert run_cli(["qualification", "continuous", "--file", path]) == 3
    assert "ANTI_BYPASS_FAILED" in capsys.readouterr().out


def test_cli_strategy_benchmark_requires_measured_unique_gain(tmp_path, capsys):
    data = {
        "baseline": {
            "run_id": "base", "strategy_profile_id": "fixed", "source_identity": "src",
            "frozen_corpus_digest": "c" * 64, "qualified_root_cause_ids": ["r1"],
            "execution_receipt_ids": ["receipt-base"], "cost_units": 5, "evaluated_cases": 10,
        },
        "adaptive": {
            "run_id": "adaptive", "strategy_profile_id": "adaptive", "source_identity": "src",
            "frozen_corpus_digest": "c" * 64, "qualified_root_cause_ids": ["r1", "r2"],
            "execution_receipt_ids": ["receipt-adaptive"], "cost_units": 7, "evaluated_cases": 10,
        },
    }
    path = _write(tmp_path, "benchmark.json", data)
    assert run_cli(["strategy", "benchmark", "--file", path]) == 0
    assert "BENEFIT_DEMONSTRATED" in capsys.readouterr().out

    data["adaptive"]["qualified_root_cause_ids"] = ["r2"]
    path = _write(tmp_path, "benchmark-weakened.json", data)
    assert run_cli(["strategy", "benchmark", "--file", path]) == 3
    assert "BASELINE_ASSURANCE_WEAKENED" in capsys.readouterr().out


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
    }
    path = _write(tmp_path, "opportunity.json", opportunity)
    assert run_cli(["opportunities", "review", "--file", path]) == 0
    assert "QUICK_WIN" in capsys.readouterr().out

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
            "oracle_status": "QUALIFIED", "run_receipt_digest": "r" * 64,
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
