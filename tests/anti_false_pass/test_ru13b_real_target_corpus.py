from __future__ import annotations

import copy
from pathlib import Path

import pytest

from bdb_audit.core.errors import ValidationError
from bdb_audit.history.store import TransactionalHistoryStore
from bdb_audit.workflow.read_models import current_accepted_cut
from bdb_audit.qualification.real_target_harness import (
    run_v21_reference_corpus,
    score_reference_controls,
    verify_v21_reference_result,
)
from bdb_audit.qualification.reference_corpus import reference_corpus_digest, v21_reference_cases
from bdb_audit.qualification.reference_truth import v21_truth_manifests


def test_ru13b_executor_visible_corpus_has_no_expected_labels() -> None:
    cases = v21_reference_cases()
    assert len(cases) == 3
    assert len(reference_corpus_digest(cases)) == 64
    for case in cases:
        assert "expected_label" not in case.public_body()
        assert len(case.target_sha) == 40

    truth = v21_truth_manifests()
    assert [item.expected_label for item in truth] == ["CLEAN", "DEFECTIVE", "BLOCKED"]
    assert [item.target_id for item in truth] == [item.target_id for item in cases]


def test_ru13b_real_public_boundary_corpus_qualifies_clean_defective_blocked(tmp_path: Path, monkeypatch) -> None:
    def refuse_git(*args, **kwargs):
        raise AssertionError("A non-Git qualification recipe must not resolve a Git source")
    monkeypatch.setattr("bdb_audit.source.git_resolver.resolve_local_repository", refuse_git)
    monkeypatch.setattr("bdb_audit.source.git_resolver.resolve_remote_repository", refuse_git)
    result = run_v21_reference_corpus(tmp_path / "qualification")
    assert result["status"] == "QUALIFIED"
    assert result["observed_results"] == {
        "v21_clean_history": "CLEAN",
        "v21_corrupt_history": "DEFECTIVE",
        "v21_full_report_blocked": "BLOCKED",
    }
    assert len(result["receipts"]) == 3
    assert all(item["evaluated_cases_count"] == 1 for item in result["receipts"])
    assert all(len(item["raw_output_digest"]) == 64 for item in result["receipts"])
    assert result["metrics"]["is_methodology_qualified"] is True
    assert result["metrics"]["anti_bypass_total"] == 2
    assert result["metrics"]["anti_bypass_passed"] == 2

    clean = v21_reference_cases()[0]
    store = TransactionalHistoryStore(tmp_path / "qualification" / clean.case_id / "campaign.sqlite")
    source = store.accepted_records("source_identity", current_accepted_cut(store))[0]["body"]
    assert source["authority_mode"] == "AUTHORIZED_SNAPSHOT"
    assert "git_commit_object_id" not in source and "git_tree_object_id" not in source

    verified = verify_v21_reference_result(result)
    assert verified["status"] == "PASS"
    assert verified["qualification_status"] == "QUALIFIED"


def test_ru13b_wrong_control_observation_cannot_qualify() -> None:
    observed = {
        "v21_clean_history": "CLEAN",
        "v21_corrupt_history": "CLEAN",
        "v21_full_report_blocked": "CLEAN",
    }
    metrics = score_reference_controls(v21_truth_manifests(), observed)
    assert metrics.is_methodology_qualified is False
    assert metrics.false_negatives == 1
    assert metrics.anti_bypass_passed == 0
    assert metrics.unknown_cases == 1


def test_ru13b_result_tamper_fails_verification(tmp_path: Path) -> None:
    result = run_v21_reference_corpus(tmp_path / "qualification")
    tampered = copy.deepcopy(result)
    tampered["observed_results"]["v21_corrupt_history"] = "CLEAN"
    with pytest.raises(ValidationError, match="REFERENCE_RESULT_DIGEST_MISMATCH"):
        verify_v21_reference_result(tampered)
