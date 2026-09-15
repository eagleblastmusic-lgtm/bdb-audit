from __future__ import annotations

import pytest

from bdb_audit.coordinator.operations import AuditOperationApi
from bdb_audit.core.errors import ValidationError
from bdb_audit.history.store import TransactionalHistoryStore
from bdb_audit.workflow.read_models import current_accepted_cut


def _complete_e1_to_e5(api: AuditOperationApi, store_path) -> None:
    for stage in ("E1", "E2", "E3", "E4", "E5"):
        api.prepare_stage(store_path, stage)
        result = api.qualify_stage(store_path, stage)
        assert result["status"] == "SUCCESS"


def _target(tmp_path):
    target = tmp_path / "target"
    target.mkdir()
    (target / "README.md").write_text("# target\n", encoding="utf-8")
    (target / "app.py").write_text("def run(): return 1\n", encoding="utf-8")
    return target


def test_prepare_stage_e6_fails_closed_without_accepted_e6_required(tmp_path) -> None:
    store_path = tmp_path / "campaign.sqlite"
    api = AuditOperationApi()
    api.create_campaign(store_path, seed="prepare-e6-pass", target_repo=str(_target(tmp_path)))
    _complete_e1_to_e5(api, store_path)

    pass_stop = api.evaluate_stop_gate(store_path, evaluation_context="FINAL_POST_E5")
    assert pass_stop["continuation_decision"] == "PASS"

    with pytest.raises(ValidationError, match="E6_REQUIRES_ACCEPTED_E6_REQUIRED"):
        api.prepare_stage(store_path, "E6")


def test_prepare_stage_e6_materializes_exact_adaptive_spec_from_stop(tmp_path) -> None:
    store_path = tmp_path / "campaign.sqlite"
    api = AuditOperationApi()
    api.create_campaign(store_path, seed="prepare-e6-required", target_repo=str(_target(tmp_path)))
    _complete_e1_to_e5(api, store_path)

    stop_result = api.evaluate_stop_gate(
        store_path,
        evaluation_context="FINAL_POST_E5",
        e6_plan_approved=True,
        unknown_blocked_summary={"unknown_surfaces_count": 1, "is_blocked": False},
    )
    assert stop_result["continuation_decision"] == "E6_REQUIRED"

    prepared = api.prepare_stage(store_path, "E6")
    assert prepared["status"] == "SUCCESS"
    assert prepared["stage_key"] == "E6"
    assert prepared["stage_spec_revision"].startswith("adaptive-1-")

    store = TransactionalHistoryStore(store_path)
    status = api.get_campaign_status(store_path)
    assert status["stages_prepared"][-1] == "E6"
    records = store.accepted_records("stage_spec", current_accepted_cut(store))
    e6_records = [row for row in records if row["body"].get("stage_key") == "E6"]
    assert len(e6_records) == 1
    e6_body = e6_records[0]["body"]
    assert e6_records[0]["ref"]["revision_digest"] == prepared["stage_spec_digest"]
    assert e6_body["stage_spec_revision"] == prepared["stage_spec_revision"]
    assert e6_body["stop_e6_relationship"] == f"SOURCE_STOP_EVALUATION:{stop_result['stop_evaluation_digest']}"


def test_prepare_stage_e6_does_not_accept_caller_revision_as_authority(tmp_path) -> None:
    store_path = tmp_path / "campaign.sqlite"
    api = AuditOperationApi()
    api.create_campaign(store_path, seed="prepare-e6-revision", target_repo=str(_target(tmp_path)))
    _complete_e1_to_e5(api, store_path)
    api.evaluate_stop_gate(
        store_path,
        evaluation_context="FINAL_POST_E5",
        e6_plan_approved=True,
        unknown_blocked_summary={"unknown_surfaces_count": 1, "is_blocked": False},
    )

    prepared = api.prepare_stage(store_path, "E6", stage_spec_revision="caller-controlled")
    assert prepared["stage_spec_revision"] != "caller-controlled"
    assert prepared["stage_spec_revision"].startswith("adaptive-1-")
