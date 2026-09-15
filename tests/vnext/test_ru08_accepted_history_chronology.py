from __future__ import annotations

from bdb_audit.history.selection import chronological_accepted_records, latest_accepted_record


class _FakeStore:
    def accepted_records(self, kind, cut):
        assert kind == "stop_evaluation"
        assert cut == {"accepted_head_seq": 9}
        return (
            {"accepted_seq": 8, "ref": {"revision_digest": "0" * 64}, "body": {"marker": "newer"}},
            {"accepted_seq": 3, "ref": {"revision_digest": "f" * 64}, "body": {"marker": "older"}},
            {"accepted_seq": 8, "ref": {"revision_digest": "1" * 64}, "body": {"marker": "newer-same-commit"}},
        )


def test_chronological_selector_uses_accepted_seq_not_digest_order() -> None:
    store = _FakeStore()
    cut = {"accepted_head_seq": 9}
    rows = chronological_accepted_records(store, "stop_evaluation", cut)  # type: ignore[arg-type]
    assert [row["accepted_seq"] for row in rows] == [3, 8, 8]
    assert rows[0]["body"]["marker"] == "older"
    assert rows[-1]["body"]["marker"] == "newer-same-commit"


def test_latest_accepted_record_is_chronological() -> None:
    row = latest_accepted_record(  # type: ignore[arg-type]
        _FakeStore(),
        "stop_evaluation",
        {"accepted_head_seq": 9},
    )
    assert row is not None
    assert row["accepted_seq"] == 8
    assert row["ref"]["revision_digest"] == "1" * 64
