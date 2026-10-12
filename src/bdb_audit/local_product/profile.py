"""Local workflow instructions, deliberately outside the qualified Registry."""
from __future__ import annotations

from typing import Any

from ..core.canonical_json import canonical_bytes
from ..orchestration.native_ensemble import E1_LANE_STRATEGIES
import hashlib

MODE = "LOCAL_PRODUCT"
PROFILE = "BDB_LOCAL_WORKFLOW_1"
RESPONSE = "BDB_LOCAL_RESPONSE_1"
NOTICE = (
    "LOCAL PRODUCT MODE: manual acceptance permits use in this local audit only. "
    "Producer identities and AI claims are unverified. No PKI, independent qualification, "
    "qualified Evidence/4, Result/4 or HIGH ASSURANCE completion is established."
)

# Required outputs make each stage usable without pretending to implement the
# normative blind/reveal, qualification or STOP protocols.
STAGES: dict[str, list[tuple[str, str, tuple[str, ...]]]] = {
    "E1": [(slot, "Discovery: " + name + "; " + strategy,
            ("inventory", "invariants", "coverage"))
           for slot, (name, strategy) in E1_LANE_STRATEGIES.items()],
    "E2": [
        ("E2-CONVERGENCE", "Compare E1 claims; identify agreement, contradictions and evidence gaps",
         ("comparison", "contradictions", "evidence_gaps")),
        ("E2-ADJUDICATION", "Review claim support; retain unresolved disputes and proposed verification",
         ("claim_review", "unresolved", "verification_plan")),
    ],
    "E3": [
        ("E3-X", "Find uncovered security and authority behavior", ("coverage_gaps", "novel_checks")),
        ("E3-Y", "Find uncovered state, parsing and recovery behavior", ("coverage_gaps", "novel_checks")),
        ("E3-Z", "Find uncovered cross-layer and concurrency behavior", ("coverage_gaps", "novel_checks")),
    ],
    "E4": [
        ("E4-MODEL", "Deepen state and temporal claims with concrete scenarios", ("scenarios", "support")),
        ("E4-RESILIENCE", "Review faults, crashes and recovery; distinguish run evidence from predictions",
         ("fault_analysis", "recovery_checks")),
        ("E4-CAUSAL", "Review causal explanations and alternative causes", ("causal_review", "alternatives")),
    ],
    "E5": [
        ("E5-A-INTERACTION", "Propose and inspect interactions and combinations", ("attack_review", "checks")),
        ("E5-A-MUTATION", "Review contrastive mutations and falsifiable predictions", ("attack_review", "checks")),
        ("E5-A-CALIBRATION", "Review local check oracles and their limits; no qualified calibration",
         ("attack_review", "checks")),
        ("E5-B1", "Challenge accepted E5-A claims for false positives", ("challenge_review", "unresolved")),
        ("E5-B2", "Challenge accepted E5-A coverage for false negatives", ("challenge_review", "unresolved")),
    ],
    "E6": [
        ("E6-FOLLOWUP", "Review bounded follow-ups and remaining risks; propose actions, not normative STOP",
         ("followup_review", "residual_risks", "completion_limits")),
    ],
}
PROFILE_SHA256 = hashlib.sha256(canonical_bytes({"profile": PROFILE, "stages": {
    stage: [[slot, instruction, list(outputs)] for slot, instruction, outputs in tasks]
    for stage, tasks in STAGES.items()
}})).hexdigest()


def task_definition(stage: str, task: str) -> dict[str, Any]:
    for slot, instruction, outputs in STAGES[stage]:
        if slot == task:
            return {"task_id": slot, "instruction": instruction, "required_outputs": list(outputs)}
    raise KeyError(task)
