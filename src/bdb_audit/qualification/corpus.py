"""Small independent executable target corpus for methodology qualification.

Expected answers live in BenchmarkCase/BenchmarkManifest and are never embedded in
the target source. The checker observes behavior through a separate subprocess.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from typing import Any, Sequence

from .receipts import ActualRunReceipt, BenchmarkManifest


@dataclass(frozen=True)
class BenchmarkCase:
    target_id: str
    source: str
    input_value: Any
    expected_value: Any
    expected_label: str
    split_membership: str = "VALIDATION"
    defect_id: str | None = None

    @property
    def source_sha(self) -> str:
        return hashlib.sha256(self.source.encode("utf-8")).hexdigest()

    def manifest(self) -> BenchmarkManifest:
        # BenchmarkManifest historically calls this field target_sha and only
        # requires >=40 chars. For local qualification targets it binds exact
        # source bytes rather than pretending to be a Git commit.
        return BenchmarkManifest(
            benchmark_id=f"benchmark_{self.target_id}",
            target_id=self.target_id,
            target_sha=self.source_sha,
            expected_label=self.expected_label,
            defect_id=self.defect_id,
            allowed_exposures=("TARGET_SOURCE", "PUBLIC_INPUT_CONTRACT"),
            split_membership=self.split_membership,
            domain_tags=("FUNCTIONAL_CONTROL",),
            metadata={"target_identity_profile": "SHA256_SOURCE_BYTES"},
        )


@dataclass(frozen=True)
class BenchmarkRun:
    manifest: BenchmarkManifest
    observed_label: str
    receipt: ActualRunReceipt


_HARNESS = r'''
import json, runpy, sys
try:
    namespace = runpy.run_path(sys.argv[1])
    fn = namespace.get("transform")
    if not callable(fn):
        raise RuntimeError("transform callable missing")
    value = json.loads(sys.stdin.read())
    result = fn(value)
    print(json.dumps({"kind": "RESULT", "value": result}, sort_keys=True))
except Exception as exc:
    print(json.dumps({"kind": "EXECUTION_ERROR", "error_type": type(exc).__name__}, sort_keys=True))
    raise SystemExit(23)
'''


def _timeout_output(value: bytes | str | None) -> bytes:
    if value is None:
        return b""
    if isinstance(value, bytes):
        return value
    return value.encode("utf-8", errors="replace")


class SmallTargetCorpusRunner:
    def __init__(self, timeout_seconds: float = 5.0):
        self.timeout_seconds = timeout_seconds

    def run_case(self, case: BenchmarkCase) -> BenchmarkRun:
        manifest = case.manifest()
        started = time.monotonic()
        with tempfile.TemporaryDirectory(prefix="bdb-qualification-") as td:
            target = Path(td) / "target.py"
            target.write_text(case.source, encoding="utf-8")
            try:
                proc = subprocess.run(
                    [sys.executable, "-I", "-c", _HARNESS, str(target)],
                    input=json.dumps(case.input_value, ensure_ascii=False),
                    text=True,
                    capture_output=True,
                    timeout=self.timeout_seconds,
                    check=False,
                )
                raw = (proc.stdout + "\n" + proc.stderr).encode("utf-8", errors="replace")
                if proc.returncode == 0:
                    try:
                        observed = json.loads(proc.stdout.strip())
                        actual_value = observed["value"]
                        label = "CLEAN" if actual_value == case.expected_value else "DEFECTIVE"
                        status = "PASS"
                        passed = 1
                        failed = 0
                    except Exception:
                        label = "UNKNOWN"
                        status = "ERROR"
                        passed = 0
                        failed = 1
                else:
                    label = "BLOCKED"
                    status = "BLOCKED"
                    passed = 0
                    failed = 0
            except subprocess.TimeoutExpired as exc:
                raw = _timeout_output(exc.stdout) + b"\n" + _timeout_output(exc.stderr)
                proc = None
                label = "BLOCKED"
                status = "BLOCKED"
                passed = 0
                failed = 0

        duration_ms = max(1, int((time.monotonic() - started) * 1000))
        raw_digest = hashlib.sha256(raw).hexdigest()
        receipt = ActualRunReceipt(
            receipt_id=f"run_{manifest.target_id}_{raw_digest[:16]}",
            benchmark_id=manifest.benchmark_id,
            target_id=manifest.target_id,
            checker_id="small_target_behavior_checker",
            execution_timestamp="EXECUTION_TIMESTAMP_REDACTED_NON_AUTHORITY",
            exit_code=proc.returncode if proc is not None else 124,
            status=status,
            raw_output_digest=raw_digest,
            evaluated_cases_count=1,
            passed_cases_count=passed,
            failed_cases_count=failed,
            unsupported_cases_count=0,
            unknown_cases_count=1 if label == "UNKNOWN" else 0,
            execution_duration_ms=duration_ms,
            details={"observed_label": label, "target_source_sha256": case.source_sha},
        )
        return BenchmarkRun(manifest, label, receipt)

    def run_corpus(self, cases: Sequence[BenchmarkCase]) -> tuple[BenchmarkRun, ...]:
        return tuple(self.run_case(case) for case in cases)


def reference_small_corpus() -> tuple[BenchmarkCase, ...]:
    return (
        BenchmarkCase(
            target_id="clean_normalizer",
            source="def transform(value):\n    return value.strip().lower()\n",
            input_value="  HeLLo  ",
            expected_value="hello",
            expected_label="CLEAN",
            split_membership="VALIDATION",
        ),
        BenchmarkCase(
            target_id="defective_normalizer",
            source="def transform(value):\n    return value.strip()\n",
            input_value="  HeLLo  ",
            expected_value="hello",
            expected_label="DEFECTIVE",
            defect_id="CASE_NORMALIZATION_MISSING",
            split_membership="VALIDATION",
        ),
        BenchmarkCase(
            target_id="blocked_normalizer",
            source="import dependency_that_does_not_exist\n\ndef transform(value):\n    return value\n",
            input_value="x",
            expected_value="x",
            expected_label="BLOCKED",
            split_membership="VALIDATION",
        ),
    )


__all__ = ["BenchmarkCase", "BenchmarkRun", "SmallTargetCorpusRunner", "reference_small_corpus"]
