"""RU11 functional verification matrix with explicit oracle qualification."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from ..tooling.runner import ToolRunSpec, ToolRunner


@dataclass(frozen=True)
class FeatureRevision:
    feature_id: str
    revision: str
    user_task: str
    entrypoints: tuple[str, ...]
    requirement_refs: tuple[str, ...] = ()


@dataclass(frozen=True)
class ExpectedOracle:
    oracle_id: str
    source: str
    expected_exit_code: int = 0
    stdout_contains: str | None = None
    qualification_status: str = "QUALIFIED"

    @property
    def independent_enough(self) -> bool:
        return self.qualification_status == "QUALIFIED" and self.source != "IMPLEMENTATION"


@dataclass(frozen=True)
class BehaviorCase:
    case_id: str
    feature_id: str
    argv: tuple[str, ...]
    oracle: ExpectedOracle
    require_no_network: bool = True
    mock_only: bool = False


@dataclass(frozen=True)
class FunctionalAssessment:
    case_id: str
    feature_id: str
    status: str
    executed: bool
    oracle_qualified: bool
    evidence_digest: str | None
    reason_codes: tuple[str, ...]


class FunctionalVerifier:
    def __init__(self, runner: ToolRunner):
        self.runner = runner

    def verify(self, case: BehaviorCase) -> FunctionalAssessment:
        if case.mock_only:
            return FunctionalAssessment(case.case_id, case.feature_id, "INSUFFICIENT", False, case.oracle.independent_enough, None, ("MOCK_ONLY_CANNOT_PASS",))
        if not case.oracle.independent_enough:
            return FunctionalAssessment(case.case_id, case.feature_id, "INSUFFICIENT", False, False, None, ("ORACLE_NOT_INDEPENDENT_OR_UNKNOWN",))
        receipt = self.runner.run(ToolRunSpec(argv=case.argv, require_no_network=case.require_no_network, expected_exit_codes=(case.oracle.expected_exit_code,)))
        if not receipt.qualified_success:
            return FunctionalAssessment(case.case_id, case.feature_id, "BLOCKED" if receipt.status in {"BLOCKED", "TIMEOUT"} else "FAIL", receipt.exit_code is not None, True, receipt.stdout_sha256, receipt.reason_codes or ("TOOL_RUN_NOT_QUALIFIED",))
        if case.oracle.stdout_contains is not None and case.oracle.stdout_contains not in receipt.stdout:
            return FunctionalAssessment(case.case_id, case.feature_id, "FAIL", True, True, receipt.stdout_sha256, ("ORACLE_MISMATCH",))
        return FunctionalAssessment(case.case_id, case.feature_id, "PASS", True, True, receipt.stdout_sha256, ())

    @staticmethod
    def matrix(features: Sequence[FeatureRevision], assessments: Sequence[FunctionalAssessment]) -> dict:
        by_feature: dict[str, list[FunctionalAssessment]] = {f.feature_id: [] for f in features}
        for assessment in assessments:
            by_feature.setdefault(assessment.feature_id, []).append(assessment)
        rows = []
        for feature in features:
            cases = by_feature.get(feature.feature_id, [])
            if not cases:
                status = "UNASSESSED"
            elif any(c.status in {"FAIL", "BLOCKED"} for c in cases):
                status = "NOT_VERIFIED"
            elif all(c.status == "PASS" for c in cases):
                status = "VERIFIED"
            else:
                status = "INSUFFICIENT"
            rows.append({"feature_id": feature.feature_id, "revision": feature.revision, "status": status, "case_count": len(cases), "evidence_digests": sorted(c.evidence_digest for c in cases if c.evidence_digest)})
        return {"features": rows, "denominator": len(features)}
