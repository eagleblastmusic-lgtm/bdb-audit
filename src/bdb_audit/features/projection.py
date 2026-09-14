from __future__ import annotations

from typing import Mapping, Sequence

from .models import BehaviorAssessment, FeatureRevision


def _is_qualified_pass(item: BehaviorAssessment) -> bool:
    return (
        item.status == "PASS"
        and item.executed
        and item.oracle_status == "QUALIFIED"
        and bool(item.run_receipt_digest)
    )


def feature_status_matrix(
    features: Sequence[FeatureRevision],
    assessments: Sequence[BehaviorAssessment],
    required_behavior_ids: Mapping[str, Sequence[str]] | None = None,
) -> dict:
    """Project feature assurance with an explicit behavior denominator.

    VERIFIED requires an explicitly declared full behavior set, current-source
    evidence, an executed run, a qualified oracle and a run receipt for every
    PASS. The legacy two-arg form remains readable for compatibility but lacks
    denominator authority and therefore can never claim VERIFIED.
    """
    grouped: dict[str, list[BehaviorAssessment]] = {feature.feature_id: [] for feature in features}
    for assessment in assessments:
        for feature in features:
            if assessment.behavior_id.startswith(feature.feature_id + ":"):
                grouped[feature.feature_id].append(assessment)
                break

    rows = []
    denominator_declared = required_behavior_ids is not None
    for feature in features:
        items = grouped[feature.feature_id]
        current = [item for item in items if item.source_identity == feature.source_identity]
        stale = sorted({item.behavior_id for item in items if item.source_identity != feature.source_identity})

        if required_behavior_ids is None:
            expected = tuple(sorted({item.behavior_id for item in current}))
        else:
            expected = tuple(dict.fromkeys(str(item) for item in required_behavior_ids.get(feature.feature_id, ())))
        expected_set = set(expected)
        relevant = [item for item in current if item.behavior_id in expected_set]
        present = {item.behavior_id for item in relevant}
        missing = sorted(expected_set - present)
        extras = sorted({item.behavior_id for item in current if item.behavior_id not in expected_set})
        invalid_passes = sorted({item.behavior_id for item in relevant if item.status == "PASS" and not _is_qualified_pass(item)})

        effective_statuses = [
            "PASS" if _is_qualified_pass(item) else item.status if item.status != "PASS" else "INSUFFICIENT"
            for item in relevant
        ]
        if not expected:
            status = "UNASSESSED"
        elif any(state == "BLOCKED" for state in effective_statuses):
            status = "BLOCKED"
        elif missing:
            status = "PARTIAL" if any(state == "PASS" for state in effective_statuses) else "INSUFFICIENT"
        elif not denominator_declared:
            status = "PARTIAL" if any(state == "PASS" for state in effective_statuses) else "INSUFFICIENT"
        elif relevant and all(state == "PASS" for state in effective_statuses):
            status = "VERIFIED"
        elif any(state == "PASS" for state in effective_statuses):
            status = "PARTIAL"
        else:
            status = "INSUFFICIENT"

        rows.append({
            "feature_id": feature.feature_id,
            "revision": feature.revision,
            "source_identity": feature.source_identity,
            "status": status,
            "behavior_denominator": len(expected),
            "denominator_declared": denominator_declared,
            "assessed_behavior_count": len(present),
            "required_behavior_ids": list(expected) if denominator_declared else [],
            "observed_behavior_ids": sorted(present),
            "missing_behavior_ids": missing if denominator_declared else [],
            "stale_behavior_ids": stale,
            "invalid_pass_behavior_ids": invalid_passes,
            "extra_behavior_ids": extras if denominator_declared else [],
            "evidence": sorted(
                item.run_receipt_digest
                for item in relevant
                if _is_qualified_pass(item) and item.run_receipt_digest
            ),
        })
    return {"features": rows, "feature_denominator": len(features)}
