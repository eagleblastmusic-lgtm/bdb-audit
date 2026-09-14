from __future__ import annotations

import sys
from typing import Sequence

from ...runner.specs import OperationalToolSpec


class ExistingPytestAdapter:
    @staticmethod
    def plan(
        *,
        source_identity: str,
        cwd: str,
        test_ids: Sequence[str],
        ruleset_ref: str = "pytest-existing-tests-v1",
    ) -> OperationalToolSpec:
        ids = tuple(str(item) for item in test_ids if str(item).strip())
        if not ids:
            raise ValueError("at least one exact pytest test id is required")
        return OperationalToolSpec(
            tool_id="pytest",
            action_class="EXISTING_TESTS",
            argv=(sys.executable, "-m", "pytest", "-q", *ids),
            source_identity=source_identity,
            scope_identity="pytest:" + "|".join(ids),
            ruleset_ref=ruleset_ref,
            cwd=cwd,
            require_no_network=True,
        )
