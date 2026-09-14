from __future__ import annotations

from ...runner.specs import OperationalToolSpec
from ..models import VerificationPlan


class LocalApiTestAdapter:
    """Adapter for an already-provisioned local API test command.

    It never opens a live network target itself; network-scoped environments
    must be provisioned and qualified separately.
    """

    @staticmethod
    def to_tool_spec(plan: VerificationPlan, *, ruleset_ref: str = "functional-local-api-v1") -> OperationalToolSpec:
        return OperationalToolSpec(
            tool_id="functional-local-api",
            action_class="FUNCTIONAL_VERIFICATION",
            argv=plan.argv,
            source_identity=plan.source_identity,
            scope_identity=plan.behavior_id,
            ruleset_ref=ruleset_ref,
            fixture_refs=plan.fixture_refs,
            cwd=plan.cwd,
            require_no_network=False,
        )
