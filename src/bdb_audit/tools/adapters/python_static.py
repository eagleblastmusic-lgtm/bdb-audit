from __future__ import annotations

import sys
from typing import Sequence

from ...runner.specs import OperationalToolSpec


class PythonCompileAdapter:
    @staticmethod
    def plan(*, source_identity: str, cwd: str, paths: Sequence[str]) -> OperationalToolSpec:
        selected = tuple(str(item) for item in paths if str(item).strip())
        if not selected:
            raise ValueError("at least one path is required")
        return OperationalToolSpec(
            tool_id="python-compileall",
            action_class="STATIC_ANALYSIS",
            argv=(sys.executable, "-m", "compileall", "-q", *selected),
            source_identity=source_identity,
            scope_identity="compileall:" + "|".join(selected),
            ruleset_ref="python-compileall-v1",
            cwd=cwd,
            require_no_network=True,
        )
