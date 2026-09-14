from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Sequence


@dataclass(frozen=True)
class ActionAuthorization:
    allowed_action_classes: tuple[str, ...]
    allowed_executables: tuple[str, ...]
    allowed_work_roots: tuple[str, ...] = ()
    network_policy: str = "DENY_UNLESS_EXTERNALLY_ENFORCED"
    unattended: bool = False


@dataclass(frozen=True)
class AuthorizationDecision:
    authorized: bool
    reason_codes: tuple[str, ...]


def authorize(
    policy: ActionAuthorization,
    *,
    action_class: str,
    executable: str,
    cwd: str | None,
    require_no_network: bool,
    environment_network_isolation: str,
) -> AuthorizationDecision:
    reasons: list[str] = []
    if action_class not in policy.allowed_action_classes:
        reasons.append("ACTION_CLASS_NOT_AUTHORIZED")
    exe_name = Path(executable).name.lower()
    if not any(exe_name == Path(item).name.lower() for item in policy.allowed_executables):
        reasons.append("EXECUTABLE_NOT_AUTHORIZED")
    if cwd and policy.allowed_work_roots:
        resolved = Path(cwd).resolve()
        if not any(resolved == Path(root).resolve() or Path(root).resolve() in resolved.parents for root in policy.allowed_work_roots):
            reasons.append("WORK_ROOT_NOT_AUTHORIZED")
    if require_no_network and environment_network_isolation != "EXTERNAL_ENFORCED":
        reasons.append("NETWORK_ISOLATION_NOT_ENFORCED")
    return AuthorizationDecision(not reasons, tuple(sorted(set(reasons))))


__all__ = ["ActionAuthorization", "AuthorizationDecision", "authorize"]
