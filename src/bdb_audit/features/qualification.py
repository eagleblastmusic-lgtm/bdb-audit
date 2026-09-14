from __future__ import annotations

from ..runner.specs import OperationalToolResult
from .models import BehaviorAssessment, VerificationPlan


def qualify_behavior(plan: VerificationPlan, run: OperationalToolResult) -> BehaviorAssessment:
    reasons: list[str] = []
    if plan.oracle.status != "QUALIFIED":
        reasons.append("ORACLE_NOT_QUALIFIED")
    if plan.source_identity != run.source_identity:
        reasons.append("SOURCE_IDENTITY_MISMATCH")
    if run.execution_profile != "REAL" or not run.measured:
        reasons.append("SYNTHETIC_OR_UNMEASURED_RUN")
    if not run.qualified_runtime_receipt:
        reasons.extend(run.reason_codes or ("RUN_NOT_QUALIFIED",))
    status = "PASS" if not reasons else ("BLOCKED" if run.status in {"BLOCKED", "TIMEOUT"} else "INSUFFICIENT")
    return BehaviorAssessment(
        plan.behavior_id, plan.source_identity, status, run.exit_code is not None,
        plan.oracle.status, run.stdout_raw_digest if run.exit_code is not None else None,
        tuple(sorted(set(reasons))),
    )
