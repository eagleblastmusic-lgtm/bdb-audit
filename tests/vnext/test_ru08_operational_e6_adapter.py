from __future__ import annotations

import pytest

from bdb_audit.coordinator.operations import AuditOperationApi
from bdb_audit.core.errors import ValidationError
from bdb_audit.history.store import TransactionalHistoryStore
from bdb_audit.stop.e6_history import build_next_adaptive_e6_stage_spec


def _complete_e1_to_e5(api: AuditOperationApi, store_path) -> None:
    for stage in ("E1", "E2", "E3", "E4", "E5"):
        api.prepare_stage(store_path, stage)
        result = api.qualify_stage(store_path, stage)
        assert result["status"] == "SUCCESS"


def test_operational_e6_requires_accepted_stop(tmp_path) -> None:
    store_path = tmp_path / "campaign.sqlite"
    target = tmp_path / "target"
    target.mkdir()
    (target / "README.md").write_text("# target\n", encoding="utf-8")

    api = AuditOperationApi()
    api.create_campaign(store_path, seed="e6-no-stop", target_repo=str(target))
    store = TransactionalHistoryStore(store_path)

    with pytest.raises(ValidationError, match="E6_REQUIRES_ACCEPTED_STOP_EVALUATION"):
        build_next_adaptive_e6_stage_spec(store)


def test_operational_e6_is_derived_from_latest_accepted_e6_required_stop(tmp_path) -> None:
    store_path = tmp_path / "campaign.sqlite"
    target = tmp_path / "target"
    target.mkdir()
    (target / "README.md").write_text("# target\n", encoding="utf-8")
    (target / "app.py").write_text("def run(): return 1\n", encoding="utf-8")

    api = AuditOperationApi()
    api.create_campaign(store_path, seed="e6-derived", target_repo=str(target))
    _complete_e1_to_e5(api, store_path)

    stop_result = api.evaluate_stop_gate(
        store_path,
        evaluation_context="FINAL_POST_E5",
        e6_plan_approved=True,
        unknown_blocked_summary={"unknown_surfaces_count": 1, "is_blocked": False},
    )
    assert stop_result["continuation_decision"] == "E6_REQUIRED"

    store = TransactionalHistoryStore(store_path)
    spec = build_next_adaptive_e6_stage_spec(store)

    assert spec.stage_key == "E6"
    assert spec.stage_ordinal == 6
    assert spec.predecessor_requirements == ("E5",)
    assert spec.required_lane_slots == ("E6_PRIMARY",)
    assert spec.stage_spec_revision.startswith("adaptive-1-")
    assert spec.stop_e6_relationship.startswith("SOURCE_STOP_EVALUATION:")
    assert len(spec.stop_e6_relationship.split(":", 1)[1]) == 64

    body = spec.body()
    assert body["stage_key"] == "E6"
    assert body["stage_spec_revision"] == spec.stage_spec_revision
    assert "e6_stage_spec_id" not in body
    assert "source_stop_evaluation_ref" not in body
    assert spec.as_object().kind == "stage_spec"


def test_operational_e6_rejects_latest_non_e6_stop(tmp_path) -> None:
    store_path = tmp_path / "campaign.sqlite"
    target = tmp_path / "target"
    target.mkdir()
    (target / "README.md").write_text("# target\n", encoding="utf-8")
    (target / "app.py").write_text("def run(): return 1\n", encoding="utf-8")

    api = AuditOperationApi()
    api.create_campaign(store_path, seed="e6-pass-stop", target_repo=str(target))
    _complete_e1_to_e5(api, store_path)

    stop_result = api.evaluate_stop_gate(store_path, evaluation_context="FINAL_POST_E5")
    assert stop_result["continuation_decision"] == "PASS"

    store = TransactionalHistoryStore(store_path)
    with pytest.raises(ValidationError, match="E6_REQUIRES_ACCEPTED_E6_REQUIRED"):
        build_next_adaptive_e6_stage_spec(store)
