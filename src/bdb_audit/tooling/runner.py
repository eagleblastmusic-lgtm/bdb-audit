"""RU10 controlled local tool runner.

This is an operational execution boundary, not accepted-history authority. It
fails closed when a requested isolation property cannot be enforced by the
configured host profile.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import shutil
import signal
import subprocess
import tempfile
import time
from typing import Mapping


@dataclass(frozen=True)
class CapabilityPolicy:
    allowed_executables: tuple[str, ...]
    max_seconds: float = 30.0
    max_output_bytes: int = 1_000_000
    network_isolation: str = "UNAVAILABLE"

    def permits(self, executable: str) -> bool:
        name = Path(executable).name.lower()
        return any(name == Path(item).name.lower() for item in self.allowed_executables)


@dataclass(frozen=True)
class ToolRunSpec:
    argv: tuple[str, ...]
    cwd: str | None = None
    stdin_text: str = ""
    env: Mapping[str, str] | None = None
    timeout_seconds: float | None = None
    require_no_network: bool = True
    expected_exit_codes: tuple[int, ...] = (0,)

    def __post_init__(self) -> None:
        if not self.argv or not self.argv[0]:
            raise ValueError("argv must contain an executable")
        if self.timeout_seconds is not None and self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")


@dataclass(frozen=True)
class ToolRunReceipt:
    status: str
    exit_code: int | None
    timed_out: bool
    stdout: str
    stderr: str
    stdout_sha256: str
    stderr_sha256: str
    duration_ms: int
    cleanup_status: str
    network_assurance: str
    reason_codes: tuple[str, ...] = ()

    @property
    def qualified_success(self) -> bool:
        return self.status == "PASS" and not self.timed_out and self.cleanup_status == "CLEAN"


def _bounded_text(data: bytes, limit: int) -> tuple[str, bool]:
    truncated = len(data) > limit
    clipped = data[:limit]
    return clipped.decode("utf-8", errors="replace"), truncated


def _kill_process_tree(proc: subprocess.Popen[bytes]) -> None:
    if proc.poll() is not None:
        return
    try:
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
        else:
            killpg = getattr(os, "killpg", None)
            sigkill = getattr(signal, "SIGKILL", 9)
            if callable(killpg):
                killpg(proc.pid, sigkill)
            else:
                proc.kill()
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass


class ToolRunner:
    def __init__(self, policy: CapabilityPolicy):
        self.policy = policy

    def run(self, spec: ToolRunSpec) -> ToolRunReceipt:
        executable = shutil.which(spec.argv[0]) or spec.argv[0]
        if not self.policy.permits(executable):
            return self._blocked("EXECUTABLE_NOT_ALLOWED")
        if spec.require_no_network:
            return self._blocked("NETWORK_ISOLATION_NOT_ENFORCED")

        timeout = min(spec.timeout_seconds or self.policy.max_seconds, self.policy.max_seconds)
        started = time.monotonic()
        proc: subprocess.Popen[bytes] | None = None
        stdout = b""
        stderr = b""
        timed_out = False
        cleanup = "CLEAN"
        reasons: list[str] = []

        with tempfile.TemporaryDirectory(prefix="bdb-toolrun-") as sandbox:
            cwd = Path(spec.cwd).resolve() if spec.cwd else Path(sandbox)
            if not cwd.exists() or not cwd.is_dir():
                return self._blocked("CWD_NOT_AVAILABLE")
            env: dict[str, str] = {"PATH": os.environ.get("PATH", ""), "PYTHONUTF8": "1"}
            if spec.env:
                env.update({str(k): str(v) for k, v in spec.env.items()})
            try:
                if os.name == "nt":
                    creationflags = int(getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))
                    proc = subprocess.Popen(
                        list(spec.argv),
                        cwd=str(cwd),
                        stdin=subprocess.PIPE,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        env=env,
                        shell=False,
                        creationflags=creationflags,
                    )
                else:
                    proc = subprocess.Popen(
                        list(spec.argv),
                        cwd=str(cwd),
                        stdin=subprocess.PIPE,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        env=env,
                        shell=False,
                        start_new_session=True,
                    )
                try:
                    stdout, stderr = proc.communicate(spec.stdin_text.encode("utf-8"), timeout=timeout)
                except subprocess.TimeoutExpired:
                    timed_out = True
                    reasons.append("TIMEOUT")
                    _kill_process_tree(proc)
                    stdout, stderr = proc.communicate()
            finally:
                if proc is not None and proc.poll() is None:
                    _kill_process_tree(proc)
                    try:
                        proc.wait(timeout=2)
                    except Exception:
                        cleanup = "UNCERTAIN"
                        reasons.append("PROCESS_TREE_CLEANUP_UNCERTAIN")

        stdout_text, out_truncated = _bounded_text(stdout, self.policy.max_output_bytes)
        stderr_text, err_truncated = _bounded_text(stderr, self.policy.max_output_bytes)
        if out_truncated:
            reasons.append("STDOUT_TRUNCATED")
        if err_truncated:
            reasons.append("STDERR_TRUNCATED")
        code = proc.returncode if proc is not None else None
        if timed_out:
            status = "TIMEOUT"
        elif code not in spec.expected_exit_codes:
            status = "FAIL"
            reasons.append("UNEXPECTED_EXIT_CODE")
        elif cleanup != "CLEAN":
            status = "BLOCKED"
        else:
            status = "PASS"
        return ToolRunReceipt(
            status,
            code,
            timed_out,
            stdout_text,
            stderr_text,
            hashlib.sha256(stdout).hexdigest(),
            hashlib.sha256(stderr).hexdigest(),
            max(1, int((time.monotonic() - started) * 1000)),
            cleanup,
            "NOT_REQUESTED",
            tuple(sorted(set(reasons))),
        )

    @staticmethod
    def _blocked(reason: str) -> ToolRunReceipt:
        empty = hashlib.sha256(b"").hexdigest()
        return ToolRunReceipt("BLOCKED", None, False, "", "", empty, empty, 0, "NOT_STARTED", "UNQUALIFIED", (reason,))
