from __future__ import annotations

from dataclasses import asdict, dataclass, field
import hashlib
import json
from typing import Mapping


@dataclass(frozen=True)
class OperationalToolSpec:
    tool_id: str
    action_class: str
    argv: tuple[str, ...]
    source_identity: str
    scope_identity: str
    ruleset_ref: str
    fixture_refs: tuple[str, ...] = ()
    seed: str = ""
    cwd: str | None = None
    stdin_text: str = ""
    env: Mapping[str, str] = field(default_factory=dict)
    timeout_seconds: float = 30.0
    max_output_bytes: int = 1_000_000
    require_no_network: bool = True
    expected_exit_codes: tuple[int, ...] = (0,)
    execution_profile: str = "REAL"

    def __post_init__(self) -> None:
        if not self.tool_id or not self.action_class or not self.argv:
            raise ValueError("tool_id, action_class and argv are required")
        if not self.source_identity or not self.scope_identity or not self.ruleset_ref:
            raise ValueError("source/scope/ruleset identities are required")
        if self.timeout_seconds <= 0 or self.max_output_bytes <= 0:
            raise ValueError("positive timeout/output limits are required")
        if self.execution_profile not in {"REAL", "SYNTHETIC_TEST_DOUBLE"}:
            raise ValueError("unsupported execution_profile")

    def body(self) -> dict:
        body = asdict(self)
        body["env"] = dict(sorted(self.env.items()))
        return body

    @property
    def digest(self) -> str:
        return hashlib.sha256(json.dumps(self.body(), sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()

    @property
    def cache_key(self) -> str:
        material = {
            "source_identity": self.source_identity,
            "scope_identity": self.scope_identity,
            "tool_id": self.tool_id,
            "ruleset_ref": self.ruleset_ref,
            "fixture_refs": list(self.fixture_refs),
            "seed": self.seed,
            "argv": list(self.argv),
            "execution_profile": self.execution_profile,
        }
        return hashlib.sha256(json.dumps(material, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class OperationalToolResult:
    spec_digest: str
    cache_key: str
    source_identity: str
    scope_identity: str
    environment_digest: str
    execution_profile: str
    status: str
    exit_code: int | None
    stdout_raw_digest: str
    stderr_raw_digest: str
    duration_ms: int
    cleanup_status: str
    network_assurance: str
    measured: bool
    reason_codes: tuple[str, ...] = ()

    @property
    def qualified_runtime_receipt(self) -> bool:
        return (
            self.execution_profile == "REAL"
            and self.measured
            and self.status == "PASS"
            and self.cleanup_status == "CLEAN"
        )
