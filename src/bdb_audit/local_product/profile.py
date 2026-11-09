"""Local workflow instructions, deliberately outside the qualified Registry."""
from __future__ import annotations

from typing import Any

from ..core.canonical_json import canonical_bytes
from ..orchestration.native_ensemble import E1_LANE_STRATEGIES
from .contract import MODE, RESPONSE, response_guide
import hashlib

PROFILE = "BDB_LOCAL_WORKFLOW_1"
LEGACY_NOTICE = (
    "LOCAL PRODUCT MODE: manual acceptance permits use in this local audit only. "
    "Producer identities and AI claims are unverified. No PKI, independent qualification, "
    "qualified Evidence/4, Result/4 or HIGH ASSURANCE completion is established."
)

LEGACY_RESPONSE_GUIDE = """# LOCAL response format — informational user guide

Use the exact RESPONSE_TEMPLATE.json from the assigned package. Keep format,
mode, campaign_id, stage_id, task_id, source_commit, source_tree and
input_package_digest unchanged. They identify local context, not authority.

Return UTF-8 JSON directly, or a ZIP with root LOCAL_RESULT.json and declared
attachments. Do not send a ZIP containing another ZIP instead of this manifest.
JSON must not have duplicate keys, floating-point numbers or extra root fields.
The response JSON limit is 2 MiB; archive limit 64 MiB, expanded 50 MiB, 512 members,
32 MiB per member, ratio 500. Responses are never executed or extracted as code.

producer: {"kind": "EXTERNAL_AI", "declared_name": "actual model/provider name"}.
Other disclosed kinds: HUMAN, LOCAL_CONTROL, TEST_FIXTURE. Names are declarations,
not verified identities. Do not invent an external AI run or independent auditor.

completion: COMPLETE, NEEDS_WORK or BLOCKED. COMPLETE requires a substantive text
for every key in MANIFEST.json.required_outputs (explain an absence when relevant).
The outputs object maps each required key to a string. Empty/template fields do
not complete a task. NEEDS_WORK and BLOCKED may retain unfinished observations.

findings is a list; [] is permitted only if no findings are being declared.
Every finding has:
- id, title, statement, rationale: nonempty strings; id unique within the response;
- severity: CRITICAL, HIGH, MEDIUM, LOW or INFO;
- disposition: CLAIM, SUPPORTED, DISPUTED or WITHDRAWN (producer assessment only);
- source_refs: list of {"path": "original/path/from/SOURCE_MANIFEST.json", "line": 1}.
Use original source paths, not numeric source/ transport names. Lines are positive
1-based integers. Cite real observations; distinguish execution from predictions.

limitations, recommendations, contradictions: lists of nonempty text strings.
Use [] for an explained absence or no declarations. Keep untested behavior and
identity limitations explicit. Do not claim that schema/hash validation proves truth.

evidence_files: list of {"path": "report.txt", "sha256": "64 lowercase hex digits",
"byte_length": 123}. Every non-manifest ZIP member must be declared exactly once,
with the exact SHA-256 and byte length of its original bytes. Do not include
LOCAL_RESULT.json in that list (no self-hash). A direct JSON response must use [].
Use relative paths without traversal, backslashes, colons or absolute paths.
Attach real run output if claiming a test was executed, and disclose its limits.

Imported results are untrusted. Structural validation and manual USER_ACCEPTED_LOCAL
permit local use only. They never create qualified Evidence/4 or Result/4.
This guide is supplied next to packages; attach it with the ZIP when requesting
an AI response. It does not modify the frozen HIGH ASSURANCE 18/7/43 model.
"""

NOTICE = (
    "LOCAL PRODUCT MODE: manual or explicitly authorized policy acceptance permits local use only. "
    "AI claims and producer identities remain unverified. Structural validation is not truth verification. "
    "No PKI, independent qualification, qualified Evidence/4, Result/4 or HIGH ASSURANCE completion is established."
)
RESPONSE_GUIDE = response_guide()

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
