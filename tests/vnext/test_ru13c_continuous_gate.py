from __future__ import annotations

from bdb_audit.qualification.continuous import FrozenHoldout, evaluate_continuous_holdout
from bdb_audit.qualification.receipts import BenchmarkManifest


def _holdout() -> FrozenHoldout:
    return FrozenHoldout.freeze((
        BenchmarkManifest("b-defect", "t-defect", "a" * 40, "DEFECTIVE", split_membership="HOLDOUT"),
        BenchmarkManifest("b-clean", "t-clean", "b" * 40, "CLEAN", split_membership="HOLDOUT"),
    ))


def test_ru13_continuous_gate_requires_antibypass_execution():
    result = evaluate_continuous_holdout(
        _holdout(), {"t-defect": "DEFECTIVE", "t-clean": "CLEAN"}, {}
    )
    assert result.qualified is False
    assert result.anti_bypass_failures == ("ANTI_BYPASS_SET_EMPTY",)


def test_ru13_continuous_gate_rejects_missing_pinned_control():
    result = evaluate_continuous_holdout(
        _holdout(),
        {"t-defect": "DEFECTIVE", "t-clean": "CLEAN"},
        {"disabled_validator": True},
        required_anti_bypass_ids=("disabled_validator", "zero_cases_false_pass"),
    )
    assert result.qualified is False
    assert "ANTI_BYPASS_MISSING:zero_cases_false_pass" in result.anti_bypass_failures


def test_ru13_continuous_gate_rejects_intentional_validator_bypass():
    result = evaluate_continuous_holdout(
        _holdout(),
        {"t-defect": "DEFECTIVE", "t-clean": "CLEAN"},
        {"disabled_validator": False, "zero_cases_false_pass": True, "lost_evidence": True},
        required_anti_bypass_ids=("disabled_validator", "zero_cases_false_pass", "lost_evidence"),
    )
    assert result.qualified is False
    assert result.false_negatives == 0
    assert result.false_positives == 0
    assert "ANTI_BYPASS_FAILED:disabled_validator" in result.anti_bypass_failures


def test_ru13_continuous_gate_passes_only_with_holdout_and_all_controls():
    result = evaluate_continuous_holdout(
        _holdout(),
        {"t-defect": "DEFECTIVE", "t-clean": "CLEAN"},
        {"disabled_validator": True, "zero_cases_false_pass": True, "lost_evidence": True},
        required_anti_bypass_ids=("disabled_validator", "zero_cases_false_pass", "lost_evidence"),
    )
    assert result.qualified is True
    assert result.anti_bypass_total == 3
    assert result.anti_bypass_passed == 3
