from __future__ import annotations

from bdb_audit.coordinator.e5_operations import E5OperationApi
from bdb_audit.coordinator.operations import AuditOperationApi


def _target(tmp_path):
    target = tmp_path / "target"
    target.mkdir()
    (target / "README.md").write_text("# target\n", encoding="utf-8")
    (target / "app.py").write_text("def run(): return 1\n", encoding="utf-8")
    return target


def test_e5_operation_api_preserves_explicit_commit_order(tmp_path) -> None:
    store_path = tmp_path / "campaign.sqlite"
    audit = AuditOperationApi()
    audit.create_campaign(store_path, seed="e5-operation-api", target_repo=str(_target(tmp_path)))
    for stage in ("E1", "E2", "E3", "E4"):
        audit.prepare_stage(store_path, stage)
        assert audit.qualify_stage(store_path, stage)["status"] == "SUCCESS"
    audit.prepare_stage(store_path, "E5")

    e5 = E5OperationApi()
    candidate = e5.freeze_candidate(store_path)
    assignments = e5.assign_required_challengers(store_path)
    results = e5.record_required_challenger_results(
        store_path,
        skeptic_status="INCONCLUSIVE",
        hunter_status="MATERIAL_COUNTEREVIDENCE_FOUND",
    )

    assert candidate["commit_seq"] < assignments["commit_seq"] < results["commit_seq"]
