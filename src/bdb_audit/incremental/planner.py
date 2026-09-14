from __future__ import annotations

from typing import Mapping, Sequence


def build_requalification_plan(reuse_assessments: Sequence[Mapping[str, object]], *, control_sample_nodes: Sequence[str] = ()) -> dict:
    rerun = sorted(str(item["evidence_id"]) for item in reuse_assessments if item.get("status") != "REUSE_QUALIFIED")
    reused = sorted(str(item["evidence_id"]) for item in reuse_assessments if item.get("status") == "REUSE_QUALIFIED")
    return {"rerun_evidence_ids": rerun, "reused_evidence_ids": reused, "control_sample_nodes": sorted(set(control_sample_nodes)), "status": "TARGETED_AUDIT_REQUIRED" if rerun else "REUSE_ONLY_WITH_CONTROL_SAMPLE"}
