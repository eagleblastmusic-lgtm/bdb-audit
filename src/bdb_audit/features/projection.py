from __future__ import annotations

from typing import Mapping, Sequence

from .models import BehaviorAssessment, FeatureRevision


def _is_sha256(value: str | None) -> bool:
    return value is not None and len(value) == 64 and all(ch in "0123456789abcdef" for ch in value)


def _is_qualified_pass(item: BehaviorAssessment) -> bool:
    return (
        item.status == "PASS"
        and item.executed
        and item.oracle_status == "QUALIFIED"
        and _is_sha256(item.run_receipt_digest)
        and not item.reason_codes
    )


def feature_status_matrix(
    features: Sequence[FeatureRevision],
    assessments: Sequence[BehaviorAssessment],
    required_behavior_ids: Mapping[str, Sequence[str]] | None = None,
) -> dict:
    """Project feature assurance with an explicit behavior denominator.

    VERIFIED requires an explicitly declared full behavior set, current-source
    evidence, exactly one unambiguous assessment per required behavior, an
    executed run, a qualified oracle, a SHA-256 run receipt and no unresolved
    reason codes for every PASS. The legacy two-arg form remains readable for
    compatibility but lacks denominator authority and therefore can never claim
    VERIFIED.
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

        current_by_behavior: dict[str, list[BehaviorAssessment]] = {}
        for item in current:
            current_by_behavior.setdefault(item.behavior_id, []).append(item)

        if required_behavior_ids is None:
            expected = tuple(sorted(current_by_behavior))
        else:
            expected = tuple(dict.fromkeys(str(item) for item in required_behavior_ids.get(feature.feature_id, ())))
        expected_set = set(expected)
        present = expected_set.intersection(current_by_behavior)
        missing = sorted(expected_set - present)
        extras = sorted(set(current_by_behavior) - expected_set)
        duplicates = sorted(
            behavior_id for behavior_id in expected
            if len(current_by_behavior.get(behavior_id, ())) > 1
        )
        invalid_passes = sorted({
            behavior_id
            for behavior_id in expected
            for item in current_by_behavior.get(behavior_id, ())
            if item.status == "PASS" and not _is_qualified_pass(item)
        })

        effective_statuses: list[str] = []
        evidence: list[str] = []
        for behavior_id in expected:
            behavior_items = current_by_behavior.get(behavior_id, [])
            if not behavior_items:
                continue
            if any(item.status == "BLOCKED" for item in behavior_items):
                effective_statuses.append("BLOCKED")
                continue
            if len(behavior_items) != 1:
                effective_statuses.append("INSUFFICIENT")
                continue
            item = behavior_items[0]
            if _is_qualified_pass(item):
                effective_statuses.append("PASS")
                assert item.run_receipt_digest is not None
                evidence.append(item.run_receipt_digest)
            else:
                effective_statuses.append(item.status if item.status != "PASS" else "INSUFFICIENT")

        if not expected:
            status = "UNASSESSED"
        elif any(state == "BLOCKED" for state in effective_statuses):
            status = "BLOCKED"
        elif missing:
            status = "PARTIAL" if any(state == "PASS" for state in effective_statuses) else "INSUFFICIENT"
        elif duplicates:
            status = "PARTIAL" if any(state == "PASS" for state in effective_statuses) else "INSUFFICIENT"
        elif not denominator_declared:
            status = "PARTIAL" if any(state == "PASS" for state in effective_statuses) else "INSUFFICIENT"
        elif effective_statuses and all(state == "PASS" for state in effective_statuses):
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
            "duplicate_behavior_ids": duplicates,
            "invalid_pass_behavior_ids": invalid_passes,
            "extra_behavior_ids": extras if denominator_declared else [],
            "evidence": sorted(evidence),
        })
    return {"features": rows, "feature_denominator": len(features)}
