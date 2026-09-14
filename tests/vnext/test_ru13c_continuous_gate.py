from __future__ import annotations

from dataclasses import replace

from bdb_audit.qualification.continuous import FrozenHoldout, evaluate_continuous_holdout
from bdb_audit.qualification.corpus import BenchmarkRun
from bdb_audit.qualification.receipts import ActualRunReceipt, BenchmarkManifest


def _manifest(
    benchmark_id: str,
    target_id: str,
    target_sha: str,
    expected_label: str,
    *,
    source_bytes_profile: bool = False,
) -> BenchmarkManifest:
    metadata = {"target_identity_profile": "SHA256_SOURCE_BYTES"} if source_bytes_profile else {}
    return BenchmarkManifest(
        benchmark_id,
        target_id,
        target_sha,
        expected_label,
        split_membership="HOLDOUT",
        metadata=metadata,
    )


def _receipt(
    manifest: BenchmarkManifest,
    observed_label: str,
    *,
    receipt_id: str | None = None,
    status: str = "PASS",
    exit_code: int = 0,
    raw_output_digest: str = "d" * 64,
    passed: int = 1,
    failed: int = 0,
    unsupported: int = 0,
    unknown: int = 0,
    evaluated: int = 1,
    timestamp: str = "2026-09-15T00:00:00Z",
    duration_ms: int = 1,
    source_sha: str | None = None,
) -> ActualRunReceipt:
    details: dict[str, str] = {"observed_label": observed_label}
    if source_sha is not None:
        details["target_source_sha256"] = source_sha
    return ActualRunReceipt(
        receipt_id or f"run-{manifest.target_id}",
        manifest.benchmark_id,
        manifest.target_id,
        "strict-holdout-checker",
        timestamp,
        exit_code,
        status,
        raw_output_digest,
        evaluated,
        passed,
        failed,
        unsupported,
        unknown,
        duration_ms,
        details,
    )


def _run(manifest: BenchmarkManifest, observed_label: str | None = None, **receipt_overrides: object) -> BenchmarkRun:
    observed = observed_label or manifest.expected_label
    source_sha = manifest.target_sha if manifest.metadata.get("target_identity_profile") == "SHA256_SOURCE_BYTES" else None
    receipt = _receipt(manifest, observed, source_sha=source_sha, **receipt_overrides)
    return BenchmarkRun(manifest, observed, receipt)


def _anti(
    control_id: str,
    *,
    receipt_id: str | None = None,
    status: str = "PASS",
    exit_code: int = 0,
    raw_output_digest: str = "e" * 64,
    evaluated: int = 1,
    passed: int = 1,
    failed: int = 0,
    unsupported: int = 0,
    unknown: int = 0,
    timestamp: str = "2026-09-15T00:00:00Z",
    duration_ms: int = 1,
) -> ActualRunReceipt:
    return ActualRunReceipt(
        receipt_id or f"anti-{control_id}",
        f"anti-bypass:{control_id}",
        control_id,
        "anti-bypass-checker",
        timestamp,
        exit_code,
        status,
        raw_output_digest,
        evaluated,
        passed,
        failed,
        unsupported,
        unknown,
        duration_ms,
        {},
    )


def _holdout() -> FrozenHoldout:
    return FrozenHoldout.freeze((
        _manifest("b-defect", "t-defect", "a" * 40, "DEFECTIVE"),
        _manifest("b-clean", "t-clean", "b" * 40, "CLEAN"),
    ))


def _good_runs(holdout: FrozenHoldout) -> tuple[BenchmarkRun, ...]:
    return tuple(_run(manifest) for manifest in holdout.manifests)


def test_ru13_strict_gate_passes_only_receipt_bound_frozen_holdout_and_controls():
    holdout = _holdout()
    controls = ("disabled_validator", "zero_cases_false_pass", "lost_evidence")
    result = evaluate_continuous_holdout(
        holdout,
        _good_runs(holdout),
        tuple(_anti(control) for control in controls),
        expected_commitment_sha256=holdout.commitment_sha256,
        required_anti_bypass_ids=controls,
    )
    assert result.qualified is True
    assert result.anti_bypass_total == 3
    assert result.anti_bypass_passed == 3
    assert result.anti_bypass_failures == ()
    assert result.qualification_failures == ()
    assert len(result.verified_run_receipt_digests) == 5


def test_ru13_commitment_is_mandatory_and_exact():
    holdout = _holdout()
    result = evaluate_continuous_holdout(
        holdout,
        _good_runs(holdout),
        (_anti("control"),),
        expected_commitment_sha256="0" * 64,
        required_anti_bypass_ids=("control",),
    )
    assert not result.qualified
    assert "HOLDOUT_COMMITMENT_MISMATCH" in result.qualification_failures

    malformed = evaluate_continuous_holdout(
        holdout,
        _good_runs(holdout),
        (_anti("control"),),
        expected_commitment_sha256="not-a-sha",
        required_anti_bypass_ids=("control",),
    )
    assert not malformed.qualified
    assert "HOLDOUT_COMMITMENT_INVALID" in malformed.qualification_failures


def test_ru13_holdout_denominator_rejects_missing_duplicate_and_undeclared_runs():
    holdout = _holdout()
    runs = _good_runs(holdout)

    missing = evaluate_continuous_holdout(
        holdout,
        runs[:1],
        (_anti("control"),),
        expected_commitment_sha256=holdout.commitment_sha256,
        required_anti_bypass_ids=("control",),
    )
    assert not missing.qualified
    assert any(code.startswith("HOLDOUT_RUN_MISSING:") for code in missing.qualification_failures)

    duplicate = evaluate_continuous_holdout(
        holdout,
        (runs[0], runs[0], runs[1]),
        (_anti("control"),),
        expected_commitment_sha256=holdout.commitment_sha256,
        required_anti_bypass_ids=("control",),
    )
    assert not duplicate.qualified
    assert any(code.startswith("HOLDOUT_RUN_DUPLICATE:") for code in duplicate.qualification_failures)

    extra_manifest = _manifest("extra", "extra-target", "c" * 40, "CLEAN")
    extra = evaluate_continuous_holdout(
        holdout,
        runs + (_run(extra_manifest),),
        (_anti("control"),),
        expected_commitment_sha256=holdout.commitment_sha256,
        required_anti_bypass_ids=("control",),
    )
    assert not extra.qualified
    assert "HOLDOUT_RUN_UNDECLARED:extra-target" in extra.qualification_failures


def test_ru13_manifest_receipt_and_source_identity_are_bound():
    source_sha = "1" * 64
    manifest = _manifest("source-benchmark", "source-target", source_sha, "CLEAN", source_bytes_profile=True)
    holdout = FrozenHoldout.freeze((manifest,))
    good = _run(manifest)

    altered_manifest = replace(manifest, allowed_exposures=("UNDECLARED",))
    manifest_mismatch = evaluate_continuous_holdout(
        holdout,
        (BenchmarkRun(altered_manifest, good.observed_label, good.receipt),),
        (_anti("control"),),
        expected_commitment_sha256=holdout.commitment_sha256,
        required_anti_bypass_ids=("control",),
    )
    assert not manifest_mismatch.qualified
    assert "HOLDOUT_MANIFEST_MISMATCH:source-target" in manifest_mismatch.qualification_failures

    wrong_source_receipt = replace(good.receipt, details={"observed_label": "CLEAN", "target_source_sha256": "2" * 64})
    source_mismatch = evaluate_continuous_holdout(
        holdout,
        (BenchmarkRun(manifest, "CLEAN", wrong_source_receipt),),
        (_anti("control"),),
        expected_commitment_sha256=holdout.commitment_sha256,
        required_anti_bypass_ids=("control",),
    )
    assert not source_mismatch.qualified
    assert "HOLDOUT_SOURCE_DIGEST_MISMATCH:source-target" in source_mismatch.qualification_failures


def test_ru13_plain_declared_label_cannot_override_receipt_or_truth():
    holdout = _holdout()
    runs = list(_good_runs(holdout))
    defect = runs[0] if runs[0].manifest.target_id == "t-defect" else runs[1]
    fake_observed = BenchmarkRun(defect.manifest, "DEFECTIVE", replace(defect.receipt, details={"observed_label": "CLEAN"}))
    runs = [fake_observed if run.manifest.target_id == "t-defect" else run for run in runs]
    result = evaluate_continuous_holdout(
        holdout,
        tuple(runs),
        (_anti("control"),),
        expected_commitment_sha256=holdout.commitment_sha256,
        required_anti_bypass_ids=("control",),
    )
    assert not result.qualified
    assert "HOLDOUT_OBSERVED_RECEIPT_MISMATCH:t-defect" in result.qualification_failures

    wrong_label = BenchmarkRun(defect.manifest, "CLEAN", replace(defect.receipt, details={"observed_label": "CLEAN"}))
    runs = [wrong_label if run.manifest.target_id == "t-defect" else run for run in _good_runs(holdout)]
    result = evaluate_continuous_holdout(
        holdout,
        tuple(runs),
        (_anti("control"),),
        expected_commitment_sha256=holdout.commitment_sha256,
        required_anti_bypass_ids=("control",),
    )
    assert not result.qualified
    assert "HOLDOUT_LABEL_MISMATCH:t-defect" in result.qualification_failures


def test_ru13_positive_holdout_receipt_must_prove_successful_execution_shape():
    holdout = _holdout()
    runs = list(_good_runs(holdout))
    target = runs[0]
    bad_receipt = replace(target.receipt, exit_code=23)
    runs[0] = BenchmarkRun(target.manifest, target.observed_label, bad_receipt)
    result = evaluate_continuous_holdout(
        holdout,
        tuple(runs),
        (_anti("control"),),
        expected_commitment_sha256=holdout.commitment_sha256,
        required_anti_bypass_ids=("control",),
    )
    assert not result.qualified
    assert any(code.startswith("HOLDOUT_EXECUTION_NOT_QUALIFIED:") for code in result.qualification_failures)

    malformed = replace(target.receipt, raw_output_digest="not-a-digest")
    runs[0] = BenchmarkRun(target.manifest, target.observed_label, malformed)
    result = evaluate_continuous_holdout(
        holdout,
        tuple(runs),
        (_anti("control"),),
        expected_commitment_sha256=holdout.commitment_sha256,
        required_anti_bypass_ids=("control",),
    )
    assert not result.qualified
    assert any(code.startswith("HOLDOUT_RECEIPT_RAW_DIGEST_INVALID:") for code in result.qualification_failures)


def test_ru13_nonbinary_truth_requires_matching_nonpass_receipt_shape():
    blocked = _manifest("b-blocked", "blocked", "a" * 40, "BLOCKED")
    unsupported = _manifest("b-unsupported", "unsupported", "b" * 40, "UNSUPPORTED")
    ambiguous = _manifest("b-ambiguous", "ambiguous", "c" * 40, "AMBIGUOUS")
    holdout = FrozenHoldout.freeze((blocked, unsupported, ambiguous))
    runs = (
        _run(blocked, status="BLOCKED", exit_code=23, passed=0),
        _run(unsupported, status="INSUFFICIENT", passed=0, unsupported=1),
        _run(ambiguous, status="UNKNOWN", passed=0, unknown=1),
    )
    result = evaluate_continuous_holdout(
        holdout,
        runs,
        (_anti("control"),),
        expected_commitment_sha256=holdout.commitment_sha256,
        required_anti_bypass_ids=("control",),
    )
    assert result.qualified

    fake_pass = BenchmarkRun(
        unsupported,
        "UNSUPPORTED",
        _receipt(unsupported, "UNSUPPORTED", status="PASS", passed=1),
    )
    result = evaluate_continuous_holdout(
        holdout,
        (runs[0], fake_pass, runs[2]),
        (_anti("control"),),
        expected_commitment_sha256=holdout.commitment_sha256,
        required_anti_bypass_ids=("control",),
    )
    assert not result.qualified
    assert "HOLDOUT_UNSUPPORTED_RECEIPT_INVALID:unsupported" in result.qualification_failures


def test_ru13_antibypass_requires_exact_executed_denominator():
    holdout = _holdout()
    runs = _good_runs(holdout)
    required = ("disabled_validator", "lost_evidence")

    missing = evaluate_continuous_holdout(
        holdout,
        runs,
        (_anti("disabled_validator"),),
        expected_commitment_sha256=holdout.commitment_sha256,
        required_anti_bypass_ids=required,
    )
    assert not missing.qualified
    assert "ANTI_BYPASS_MISSING:lost_evidence" in missing.anti_bypass_failures

    failing = evaluate_continuous_holdout(
        holdout,
        runs,
        (_anti("disabled_validator"), _anti("lost_evidence", status="FAIL", passed=0, failed=1, exit_code=1)),
        expected_commitment_sha256=holdout.commitment_sha256,
        required_anti_bypass_ids=required,
    )
    assert not failing.qualified
    assert "ANTI_BYPASS_FAILED:lost_evidence" in failing.anti_bypass_failures

    extra = evaluate_continuous_holdout(
        holdout,
        runs,
        (_anti("disabled_validator"), _anti("lost_evidence"), _anti("undeclared")),
        expected_commitment_sha256=holdout.commitment_sha256,
        required_anti_bypass_ids=required,
    )
    assert not extra.qualified
    assert "ANTI_BYPASS_UNDECLARED:undeclared" in extra.anti_bypass_failures


def test_ru13_antibypass_rejects_duplicate_or_receipt_only_pass_claims():
    holdout = _holdout()
    runs = _good_runs(holdout)
    one = _anti("control")
    duplicate = replace(one, receipt_id="different-receipt")
    result = evaluate_continuous_holdout(
        holdout,
        runs,
        (one, duplicate),
        expected_commitment_sha256=holdout.commitment_sha256,
        required_anti_bypass_ids=("control",),
    )
    assert not result.qualified
    assert "ANTI_BYPASS_DUPLICATE:control" in result.anti_bypass_failures

    malformed = _anti("control", raw_output_digest="x")
    result = evaluate_continuous_holdout(
        holdout,
        runs,
        (malformed,),
        expected_commitment_sha256=holdout.commitment_sha256,
        required_anti_bypass_ids=("control",),
    )
    assert not result.qualified
    assert "ANTI_BYPASS_RAW_DIGEST_INVALID:control" in result.anti_bypass_failures
