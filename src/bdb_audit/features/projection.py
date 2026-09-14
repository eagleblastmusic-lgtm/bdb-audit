from __future__ import annotations

from typing import Sequence

from .models import BehaviorAssessment, FeatureRevision


def feature_status_matrix(features: Sequence[FeatureRevision], assessments: Sequence[BehaviorAssessment]) -> dict:
    grouped: dict[str, list[BehaviorAssessment]] = {feature.feature_id: [] for feature in features}
    for assessment in assessments:
        for feature in features:
            if assessment.behavior_id.startswith(feature.feature_id + ":"):
                grouped[feature.feature_id].append(assessment)
                break
    rows = []
    for feature in features:
        items = grouped[feature.feature_id]
        if not items:
            status = "UNASSESSED"
        elif any(item.status == "BLOCKED" for item in items):
            status = "BLOCKED"
        elif all(item.status == "PASS" for item in items):
            status = "VERIFIED"
        elif any(item.status == "PASS" for item in items):
            status = "PARTIAL"
        else:
            status = "INSUFFICIENT"
        rows.append({
            "feature_id": feature.feature_id,
            "revision": feature.revision,
            "source_identity": feature.source_identity,
            "status": status,
            "behavior_denominator": len(items),
            "evidence": sorted(item.run_receipt_digest for item in items if item.run_receipt_digest),
        })
    return {"features": rows, "feature_denominator": len(features)}
