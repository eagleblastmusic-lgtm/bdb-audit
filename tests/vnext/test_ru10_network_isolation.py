from __future__ import annotations

import hashlib
import sys

from bdb_audit.tooling.runner import CapabilityPolicy, ToolRunner, ToolRunSpec


def test_ru10_external_network_isolation_can_satisfy_no_network_requirement():
    runner = ToolRunner(CapabilityPolicy((sys.executable,), network_isolation="EXTERNAL_ENFORCED"))
    receipt = runner.run(ToolRunSpec((sys.executable, "-c", "print('READY')"), require_no_network=True))
    assert receipt.status == "PASS"
    assert receipt.qualified_success
    assert receipt.network_assurance == "EXTERNAL_ENFORCED"


def test_ru10_no_network_requirement_still_fails_closed_without_enforcement():
    runner = ToolRunner(CapabilityPolicy((sys.executable,), network_isolation="UNAVAILABLE"))
    receipt = runner.run(ToolRunSpec((sys.executable, "-c", "print('SHOULD_NOT_RUN')"), require_no_network=True))
    assert receipt.status == "BLOCKED"
    assert "NETWORK_ISOLATION_NOT_ENFORCED" in receipt.reason_codes
    assert not receipt.qualified_success


def test_ru10_massive_output_is_drained_but_only_bounded_prefix_is_retained():
    stdout_bytes = b"x" * 200_000
    stderr_bytes = b"y" * 150_000
    script = "import sys; sys.stdout.write('x'*200000); sys.stderr.write('y'*150000)"
    runner = ToolRunner(CapabilityPolicy((sys.executable,), max_output_bytes=1024, network_isolation="UNAVAILABLE"))
    receipt = runner.run(ToolRunSpec((sys.executable, "-c", script), require_no_network=False))
    assert receipt.status == "PASS"
    assert len(receipt.stdout.encode("utf-8")) <= 1024
    assert len(receipt.stderr.encode("utf-8")) <= 1024
    assert receipt.stdout_sha256 == hashlib.sha256(stdout_bytes).hexdigest()
    assert receipt.stderr_sha256 == hashlib.sha256(stderr_bytes).hexdigest()
    assert "STDOUT_TRUNCATED" in receipt.reason_codes
    assert "STDERR_TRUNCATED" in receipt.reason_codes
