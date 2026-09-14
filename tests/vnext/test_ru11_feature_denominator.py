from __future__ import annotations

from bdb_audit.features import BehaviorAssessment, FeatureRevision, feature_status_matrix


def _feature(source: str = "src-new") -> FeatureRevision:
    return FeatureRevision("feature_x", "1", source, "do x", ("cli",), ("req:1",))


def _assessment(
    behavior_id: str,
    status: str = "PASS",
    source: str = "src-new",
    *,
    executed: bool = True,
    oracle_status: str = "QUALIFIED",
    run_receipt_digest: str | None = "a" * 64,
    reason_codes: tuple[str, ...] = (),
) -> BehaviorAssessment:
    return BehaviorAssessment(
        behavior_id, source, status, executed, oracle_status,
        run_receipt_digest, reason_codes,
    )


def test_ru11_matrix_cannot_verify_when_required_behavior_is_omitted():
    result = feature_status_matrix(
        (_feature(),),
        (_assessment("feature_x:happy"),),
        {"feature_x": ("feature_x:happy", "feature_x:negative")},
    )
    row = result["features"][0]
    assert row["status"] == "PARTIAL"
    assert row["behavior_denominator"] == 2
    assert row["denominator_declared"] is True
    assert row["assessed_behavior_count"] == 1
    assert row["missing_behavior_ids"] == ["feature_x:negative"]


def test_ru11_matrix_stale_source_evidence_never_promotes_current_feature():
    result = feature_status_matrix(
        (_feature(),),
        (_assessment("feature_x:happy", source="src-old"),),
        {"feature_x": ("feature_x:happy",)},
    )
    row = result["features"][0]
    assert row["status"] == "INSUFFICIENT"
    assert row["missing_behavior_ids"] == ["feature_x:happy"]
    assert row["stale_behavior_ids"] == ["feature_x:happy"]
    assert row["evidence"] == []


def test_ru11_matrix_rejects_unexecuted_or_unqualified_pass_dto():
    unexecuted = feature_status_matrix(
        (_feature(),),
        (_assessment("feature_x:happy", executed=False),),
        {"feature_x": ("feature_x:happy",)},
    )
    assert unexecuted["features"][0]["status"] == "INSUFFICIENT"
    assert unexecuted["features"][0]["invalid_pass_behavior_ids"] == ["feature_x:happy"]

    bad_oracle = feature_status_matrix(
        (_feature(),),
        (_assessment("feature_x:happy", oracle_status="UNKNOWN"),),
        {"feature_x": ("feature_x:happy",)},
    )
    assert bad_oracle["features"][0]["status"] == "INSUFFICIENT"

    missing_receipt = feature_status_matrix(
        (_feature(),),
        (_assessment("feature_x:happy", run_receipt_digest=None),),
        {"feature_x": ("feature_x:happy",)},
    )
    assert missing_receipt["features"][0]["status"] == "INSUFFICIENT"


def test_ru11_matrix_rejects_malformed_digest_reasoned_pass_and_duplicate_assessment():
    malformed = feature_status_matrix(
        (_feature(),),
        (_assessment("feature_x:happy", run_receipt_digest="not-a-sha"),),
        {"feature_x": ("feature_x:happy",)},
    )
    assert malformed["features"][0]["status"] == "INSUFFICIENT"
    assert malformed["features"][0]["invalid_pass_behavior_ids"] == ["feature_x:happy"]

    reasoned = feature_status_matrix(
        (_feature(),),
        (_assessment("feature_x:happy", reason_codes=("UNRESOLVED",)),),
        {"feature_x": ("feature_x:happy",)},
    )
    assert reasoned["features"][0]["status"] == "INSUFFICIENT"

    duplicate = feature_status_matrix(
        (_feature(),),
        (_assessment("feature_x:happy"), _assessment("feature_x:happy", run_receipt_digest="b" * 64)),
        {"feature_x": ("feature_x:happy",)},
    )
    row = duplicate["features"][0]
    assert row["status"] == "INSUFFICIENT"
    assert row["duplicate_behavior_ids"] == ["feature_x:happy"]
    assert row["evidence"] == []


def test_ru11_matrix_verifies_only_complete_current_required_set():
    result = feature_status_matrix(
        (_feature(),),
        (_assessment("feature_x:happy"), _assessment("feature_x:negative", run_receipt_digest="b" * 64)),
        {"feature_x": ("feature_x:happy", "feature_x:negative")},
    )
    row = result["features"][0]
    assert row["status"] == "VERIFIED"
    assert row["behavior_denominator"] == 2
    assert row["denominator_declared"] is True
    assert row["missing_behavior_ids"] == []
    assert row["duplicate_behavior_ids"] == []
    assert len(row["evidence"]) == 2


def test_ru11_legacy_projection_never_claims_verified_without_declared_denominator():
    current = feature_status_matrix((_feature(),), (_assessment("feature_x:happy"),))
    row = current["features"][0]
    assert row["status"] == "PARTIAL"
    assert row["denominator_declared"] is False
    assert row["required_behavior_ids"] == []
    assert row["observed_behavior_ids"] == ["feature_x:happy"]

    stale = feature_status_matrix((_feature(),), (_assessment("feature_x:happy", source="src-old"),))
    assert stale["features"][0]["status"] == "UNASSESSED"
    fake = feature_status_matrix((_feature(),), (_assessment("feature_x:happy", executed=False),))
    assert fake["features"][0]["status"] == "INSUFFICIENT"
