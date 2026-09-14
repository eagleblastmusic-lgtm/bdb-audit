from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import os
import platform
import sys
from typing import Mapping


@dataclass(frozen=True)
class EnvironmentManifest:
    platform: str
    machine: str
    python_implementation: str
    python_version: str
    executable: str
    network_isolation: str
    process_tree_control: str
    resource_limit_profile: str
    environment_allowlist: tuple[str, ...]

    def body(self) -> dict:
        return asdict(self)

    @property
    def digest(self) -> str:
        raw = json.dumps(self.body(), sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()


def current_environment_manifest(*, network_isolation: str = "UNAVAILABLE") -> EnvironmentManifest:
    process_tree = "TASKKILL_PROCESS_TREE" if os.name == "nt" else "POSIX_PROCESS_GROUP"
    resource_profile = "TIME_AND_OUTPUT_ONLY_WINDOWS" if os.name == "nt" else "TIME_OUTPUT_PROCESS_GROUP"
    return EnvironmentManifest(
        platform=platform.platform(),
        machine=platform.machine(),
        python_implementation=sys.implementation.name,
        python_version=platform.python_version(),
        executable=sys.executable,
        network_isolation=network_isolation,
        process_tree_control=process_tree,
        resource_limit_profile=resource_profile,
        environment_allowlist=("PATH", "PYTHONUTF8"),
    )


def sanitized_environment(extra: Mapping[str, str] | None = None) -> dict[str, str]:
    env = {"PATH": os.environ.get("PATH", ""), "PYTHONUTF8": "1"}
    if extra:
        for key, value in extra.items():
            if key.upper() in {"HOME", "USERPROFILE", "GITHUB_TOKEN", "GH_TOKEN", "AWS_SECRET_ACCESS_KEY", "OPENAI_API_KEY"}:
                continue
            env[str(key)] = str(value)
    return env
