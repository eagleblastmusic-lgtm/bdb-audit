from __future__ import annotations

from dataclasses import dataclass

from ..tooling import CapabilityPolicy, ToolRunSpec, ToolRunner
from .environments import EnvironmentManifest, current_environment_manifest
from .permissions import ActionAuthorization, authorize
from .specs import OperationalToolResult, OperationalToolSpec


@dataclass(frozen=True)
class OperationalToolSupervisor:
    authorization: ActionAuthorization
    environment: EnvironmentManifest | None = None

    def inspect(self, spec: OperationalToolSpec) -> dict:
        env = self.environment or current_environment_manifest()
        decision = authorize(
            self.authorization,
            action_class=spec.action_class,
            executable=spec.argv[0],
            cwd=spec.cwd,
            require_no_network=spec.require_no_network,
            environment_network_isolation=env.network_isolation,
        )
        return {
            "spec_digest": spec.digest,
            "cache_key": spec.cache_key,
            "authorized": decision.authorized,
            "reason_codes": list(decision.reason_codes),
            "environment_digest": env.digest,
            "execution_profile": spec.execution_profile,
        }

    def run(self, spec: OperationalToolSpec) -> OperationalToolResult:
        env = self.environment or current_environment_manifest()
        decision = authorize(
            self.authorization,
            action_class=spec.action_class,
            executable=spec.argv[0],
            cwd=spec.cwd,
            require_no_network=spec.require_no_network,
            environment_network_isolation=env.network_isolation,
        )
        if not decision.authorized:
            return OperationalToolResult(
                spec.digest, spec.cache_key, spec.source_identity, spec.scope_identity,
                env.digest, spec.execution_profile, "BLOCKED", None,
                "0" * 64, "0" * 64, 0, "NOT_STARTED", "UNQUALIFIED",
                spec.execution_profile == "REAL", decision.reason_codes,
            )
        runner = ToolRunner(CapabilityPolicy(
            allowed_executables=self.authorization.allowed_executables,
            max_seconds=spec.timeout_seconds,
            max_output_bytes=spec.max_output_bytes,
            network_isolation=env.network_isolation,
        ))
        receipt = runner.run(ToolRunSpec(
            argv=spec.argv,
            cwd=spec.cwd,
            stdin_text=spec.stdin_text,
            env=spec.env,
            timeout_seconds=spec.timeout_seconds,
            require_no_network=spec.require_no_network,
            expected_exit_codes=spec.expected_exit_codes,
        ))
        return OperationalToolResult(
            spec.digest, spec.cache_key, spec.source_identity, spec.scope_identity,
            env.digest, spec.execution_profile, receipt.status, receipt.exit_code,
            receipt.stdout_sha256, receipt.stderr_sha256, receipt.duration_ms,
            receipt.cleanup_status, receipt.network_assurance,
            spec.execution_profile == "REAL", receipt.reason_codes,
        )
