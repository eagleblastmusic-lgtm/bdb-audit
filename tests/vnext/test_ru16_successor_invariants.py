from __future__ import annotations

import pytest

from bdb_audit.incremental.successor import SuccessorCampaignSpec, validate_successor_selection


def _spec() -> SuccessorCampaignSpec:
    return SuccessorCampaignSpec(
        predecessor_campaign_id="campaign-old",
        predecessor_conclusion_digest="a" * 64,
        predecessor_source_identity="source@old",
        successor_campaign_id="campaign-new",
        successor_source_identity="source@new",
    )


def test_ru16_successor_preserves_predecessor_source_and_conclusion_state():
    result = validate_successor_selection(
        _spec(),
        predecessor_is_concluded=True,
        predecessor_source_after="source@old",
        predecessor_state_after="COMPLETED",
    )
    assert result["status"] == "PASS"


def test_ru16_successor_rejects_reopening_or_mutating_predecessor():
    result = validate_successor_selection(
        _spec(),
        predecessor_is_concluded=True,
        predecessor_source_after="source@new",
        predecessor_state_after="OPEN",
    )
    assert result["status"] == "REJECTED"
    assert "PREDECESSOR_SOURCE_MUTATION_FORBIDDEN" in result["reason_codes"]
    assert "PREDECESSOR_REOPEN_FORBIDDEN" in result["reason_codes"]


def test_ru16_competing_successors_require_explicit_selection():
    result = validate_successor_selection(
        _spec(),
        predecessor_is_concluded=True,
        predecessor_source_after="source@old",
        predecessor_state_after="COMPLETED",
        competing_successor_refs=("successor:a", "successor:b"),
    )
    assert result["status"] == "REJECTED"
    assert "EXPLICIT_SUCCESSOR_SELECTION_REQUIRED" in result["reason_codes"]


def test_ru16_same_source_is_not_a_successor_campaign():
    with pytest.raises(ValueError, match="new source identity"):
        SuccessorCampaignSpec("c1", "a" * 64, "source@one", "c2", "source@one")
