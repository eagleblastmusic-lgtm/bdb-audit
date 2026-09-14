from __future__ import annotations

from ...runner.specs import OperationalToolSpec
from ..models import VerificationPlan


class CliBehaviorAdapter:
    @staticmethod
    def to_tool_spec(plan: VerificationPlan, *, ruleset_ref: str = "functional-cli-v1", require_no_network: bool = True) -> OperationalToolSpec:
        return OperationalToolSpec(
            tool_id="functional-cli",
            action_class="FUNCTIONAL_VERIFICATION",
            argv=plan.argv,
            source_identity=plan.source_identity,
            scope_identity=plan.behavior_id,
            ruleset_ref=ruleset_ref,
            fixture_refs=plan.fixture_refs,
            cwd=plan.cwd,
            require_no_network=require_no_network,
        )
