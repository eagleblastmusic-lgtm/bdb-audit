from __future__ import annotations

import pytest

from bdb_audit.assurance.e5_challenge_service import E5ChallengeService
from bdb_audit.coordinator.operations import AuditOperationApi
from bdb_audit.core.errors import ValidationError
from bdb_audit.history.selection import chronological_accepted_records
from bdb_audit.history.store import TransactionalHistoryStore
from bdb_audit.workflow.read_models import current_accepted_cut


def _target(tmp_path):
    target = tmp_path / "target"
    target.mkdir()
    (target / "README.md").write_text("# target\n", encoding="utf-8")
    (target / "app.py").write_text("def run(): return 1\n", encoding="utf-8")
    return target


def _prepare_e5a(api: AuditOperationApi, store_path) -> None:
    for stage in ("E1", "E2", "E3", "E4"):
        api.prepare_stage(store_path, stage)
        assert api.qualify_stage(store_path, stage)["status"] == "SUCCESS"
    api.prepare_stage(store_path, "E5")


def test_e5_challenge_lifecycle_uses_three_distinct_accepted_commits(tmp_path) -> None:
    store_path = tmp_path / "campaign.sqlite"
    api = AuditOperationApi()
    api.create_campaign(store_path, seed="e5-temporal", target_repo=str(_target(tmp_path)))
    _prepare_e5a(api, store_path)

    store = TransactionalHistoryStore(store_path)
    svc = E5ChallengeService(store)

    candidate = svc.freeze_candidate()
    assignments = svc.assign_required_challengers()
    results = svc.record_required_challenger_results(
        skeptic_status="INCONCLUSIVE",
        hunter_status="MATERIAL_COUNTEREVIDENCE_FOUND",
    )

    assert candidate["commit_seq"] < assignments["commit_seq"] < results["commit_seq"]

    cut = current_accepted_cut(store)
    candidates = chronological_accepted_records(store, "candidate_assurance_case", cut)
    assignment_rows = chronological_accepted_records(store, "challenger_assignment", cut)
    result_rows = chronological_accepted_records(store, "challenger_result", cut)
    assert len(candidates) == 1
    assert len(assignment_rows) == 2
    assert len(result_rows) == 2
    assert {row["accepted_seq"] for row in assignment_rows} == {assignments["commit_seq"]}
    assert {row["accepted_seq"] for row in result_rows} == {results["commit_seq"]}
    assert candidates[0]["accepted_seq"] == candidate["commit_seq"]
    assert {row["body"]["status"] for row in result_rows} == {
        "INCONCLUSIVE",
        "MATERIAL_COUNTEREVIDENCE_FOUND",
    }

    current = svc.current_pair()
    assert current[1].challenger_type == "FALSE_POSITIVE_SKEPTIC"
    assert current[2].challenger_type == "FALSE_NEGATIVE_HUNTER"
    assert current[3].status == "INCONCLUSIVE"
    assert current[4].status == "MATERIAL_COUNTEREVIDENCE_FOUND"


def test_e5_challenge_service_never_defaults_positive_results(tmp_path) -> None:
    store_path = tmp_path / "campaign.sqlite"
    api = AuditOperationApi()
    api.create_campaign(store_path, seed="e5-no-default", target_repo=str(_target(tmp_path)))
    _prepare_e5a(api, store_path)

    svc = E5ChallengeService(TransactionalHistoryStore(store_path))
    svc.freeze_candidate()
    svc.assign_required_challengers()

    with pytest.raises(TypeError):
        svc.record_required_challenger_results()  # type: ignore[call-arg]


def test_e5_challenge_service_rejects_temporal_shortcuts_and_duplicates(tmp_path) -> None:
    store_path = tmp_path / "campaign.sqlite"
    api = AuditOperationApi()
    api.create_campaign(store_path, seed="e5-shortcuts", target_repo=str(_target(tmp_path)))
    _prepare_e5a(api, store_path)

    svc = E5ChallengeService(TransactionalHistoryStore(store_path))
    with pytest.raises(ValidationError, match="E5_CHALLENGER_CANDIDATE_REQUIRED"):
        svc.assign_required_challengers()

    svc.freeze_candidate()
    svc.assign_required_challengers()
    with pytest.raises(ValidationError, match="E5_CHALLENGERS_ALREADY_ASSIGNED"):
        svc.assign_required_challengers()

    svc.record_required_challenger_results(
        skeptic_status="INCONCLUSIVE",
        hunter_status="INCONCLUSIVE",
    )
    with pytest.raises(ValidationError, match="E5_CHALLENGER_RESULTS_ALREADY_RECORDED"):
        svc.record_required_challenger_results(
            skeptic_status="INCONCLUSIVE",
            hunter_status="INCONCLUSIVE",
        )
