from __future__ import annotations

from bdb_audit.qualification.continuous import FrozenHoldout, evaluate_continuous_holdout
from bdb_audit.qualification.corpus import BenchmarkRun
from bdb_audit.qualification.receipts import ActualRunReceipt, BenchmarkManifest


def test_ru13_receipt_identity_cannot_be_reused_across_holdout_and_antibypass():
    manifest = BenchmarkManifest(
        "b-clean",
        "clean-target",
        "a" * 40,
        "CLEAN",
        split_membership="HOLDOUT",
    )
    holdout = FrozenHoldout.freeze((manifest,))
    holdout_receipt = ActualRunReceipt(
        "shared-receipt-id",
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
    anti_receipt = ActualRunReceipt(
        "shared-receipt-id",
        "anti-bypass:validator-disabled",
        "validator-disabled",
        "anti-bypass-checker",
        "2026-09-15T00:00:00Z",
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
        (anti_receipt,),
        expected_commitment_sha256=holdout.commitment_sha256,
        required_anti_bypass_ids=("validator-disabled",),
    )
    assert not result.qualified
    assert "RUN_RECEIPT_ID_REUSED_ACROSS_GATE:shared-receipt-id" in result.qualification_failures
