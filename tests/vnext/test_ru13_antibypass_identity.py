from __future__ import annotations

from bdb_audit.qualification.continuous import FrozenHoldout, evaluate_continuous_holdout
from bdb_audit.qualification.corpus import BenchmarkRun
from bdb_audit.qualification.receipts import ActualRunReceipt, BenchmarkManifest


def test_ru13_antibypass_cannot_create_a_denominator_from_blank_identity_fields():
    manifest = BenchmarkManifest(
        "b-clean",
        "clean-target",
        "a" * 40,
        "CLEAN",
        split_membership="HOLDOUT",
    )
    holdout = FrozenHoldout.freeze((manifest,))
    holdout_receipt = ActualRunReceipt(
        "holdout-receipt",
        "b-clean",
        "clean-target",
        "holdout-checker",
        "2026-09-15T00:00:00Z",
        0,
        "PASS",
        "d" * 64,
        1,
        1,
        0,
        0,
        0,
        1,
        {"observed_label": "CLEAN"},
    )
    blank_control = ActualRunReceipt(
        "blank-control-receipt",
        " ",
        " ",
        "anti-bypass-checker",
        " ",
        0,
        "PASS",
        "e" * 64,
        1,
        1,
        0,
        0,
        0,
        1,
        {},
    )
    result = evaluate_continuous_holdout(
        holdout,
        (BenchmarkRun(manifest, "CLEAN", holdout_receipt),),
        (blank_control,),
        expected_commitment_sha256=holdout.commitment_sha256,
    )
    assert not result.qualified
    assert "ANTI_BYPASS_CONTROL_ID_MISSING" in result.anti_bypass_failures
    assert "ANTI_BYPASS_SET_EMPTY" in result.anti_bypass_failures
    assert any(code.startswith("ANTI_BYPASS_BENCHMARK_ID_MISSING:") for code in result.anti_bypass_failures)
    assert any(code.startswith("ANTI_BYPASS_TIMESTAMP_MISSING:") for code in result.anti_bypass_failures)
