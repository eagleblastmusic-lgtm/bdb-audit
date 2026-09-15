from __future__ import annotations

from bdb_audit.stop.input_builder import select_current_baseline_challenger_refs


def _ref(kind: str, token: str) -> dict[str, str]:
    return {
        "kind": kind,
        "revision_digest": (token * 64)[:64],
        "digest_profile": "BDB-OBJECT-DIGEST-1",
        "schema_revision_ref": f"BDB_SCHEMA_REGISTRY::{kind}/1",
        "ref_class": "CONTENT_OR_PRIOR",
    }


def _cut(seq: int) -> dict[str, object]:
    return {
        "campaign_id": "campaign-1",
        "accepted_head_seq": seq,
        "accepted_head_hash": f"{seq:064x}",
    }


def _candidate(token: str, seq: int) -> dict[str, object]:
    return {
        "ref": _ref("candidate_assurance_case", token),
        "body": {"candidate_input_history_cut": _cut(seq)},
    }


def _assignment(token: str, candidate_ref: dict[str, str], role: str, seq: int) -> dict[str, object]:
    return {
        "ref": _ref("challenger_assignment", token),
        "body": {
            "candidate_assurance_case_ref": candidate_ref,
            "challenger_type": role,
            "assignment_input_history_cut": _cut(seq),
        },
    }


def _result(
    token: str,
    candidate_ref: dict[str, str],
    assignment_ref: dict[str, str],
    seq: int,
    status: str = "NO_MATERIAL_COUNTEREVIDENCE",
) -> dict[str, object]:
    return {
        "ref": _ref("challenger_result", token),
        "body": {
            "candidate_assurance_case_ref": candidate_ref,
            "challenge_assignment_ref": assignment_ref,
            "result_input_history_cut": _cut(seq),
            "status": status,
        },
    }


def test_stop_challenger_selector_requires_two_fresh_baseline_roles() -> None:
    current = _candidate("c", 10)
    current_ref = current["ref"]
    assert isinstance(current_ref, dict)
    skeptic = _assignment("s", current_ref, "FALSE_POSITIVE_SKEPTIC", 11)
    hunter = _assignment("h", current_ref, "FALSE_NEGATIVE_HUNTER", 11)
    skeptic_ref = skeptic["ref"]
    hunter_ref = hunter["ref"]
    assert isinstance(skeptic_ref, dict) and isinstance(hunter_ref, dict)
    skeptic_result = _result("x", current_ref, skeptic_ref, 12)
    hunter_result = _result("y", current_ref, hunter_ref, 12)

    selected = select_current_baseline_challenger_refs(
        current,
        (skeptic, hunter),
        (skeptic_result, hunter_result),
    )

    assert [ref["revision_digest"] for ref in selected] == [
        skeptic_result["ref"]["revision_digest"],
        hunter_result["ref"]["revision_digest"],
    ]


def test_stop_challenger_selector_ignores_pair_for_stale_candidate_revision() -> None:
    current = _candidate("c", 20)
    stale = _candidate("o", 10)
    stale_ref = stale["ref"]
    assert isinstance(stale_ref, dict)
    skeptic = _assignment("s", stale_ref, "FALSE_POSITIVE_SKEPTIC", 11)
    hunter = _assignment("h", stale_ref, "FALSE_NEGATIVE_HUNTER", 11)
    skeptic_ref = skeptic["ref"]
    hunter_ref = hunter["ref"]
    assert isinstance(skeptic_ref, dict) and isinstance(hunter_ref, dict)

    selected = select_current_baseline_challenger_refs(
        current,
        (skeptic, hunter),
        (_result("x", stale_ref, skeptic_ref, 12), _result("y", stale_ref, hunter_ref, 12)),
    )

    assert selected == ()


def test_stop_challenger_selector_rejects_nonqualifying_or_missing_role() -> None:
    current = _candidate("c", 10)
    current_ref = current["ref"]
    assert isinstance(current_ref, dict)
    skeptic = _assignment("s", current_ref, "FALSE_POSITIVE_SKEPTIC", 11)
    hunter = _assignment("h", current_ref, "FALSE_NEGATIVE_HUNTER", 11)
    skeptic_ref = skeptic["ref"]
    hunter_ref = hunter["ref"]
    assert isinstance(skeptic_ref, dict) and isinstance(hunter_ref, dict)

    selected = select_current_baseline_challenger_refs(
        current,
        (skeptic, hunter),
        (
            _result("x", current_ref, skeptic_ref, 12),
            _result("y", current_ref, hunter_ref, 12, status="INCONCLUSIVE"),
        ),
    )

    assert selected == ()


def test_stop_challenger_selector_rejects_ambiguous_duplicate_role() -> None:
    current = _candidate("c", 10)
    current_ref = current["ref"]
    assert isinstance(current_ref, dict)
    skeptic_a = _assignment("a", current_ref, "FALSE_POSITIVE_SKEPTIC", 11)
    skeptic_b = _assignment("b", current_ref, "FALSE_POSITIVE_SKEPTIC", 11)
    hunter = _assignment("h", current_ref, "FALSE_NEGATIVE_HUNTER", 11)
    a_ref = skeptic_a["ref"]
    b_ref = skeptic_b["ref"]
    h_ref = hunter["ref"]
    assert isinstance(a_ref, dict) and isinstance(b_ref, dict) and isinstance(h_ref, dict)

    selected = select_current_baseline_challenger_refs(
        current,
        (skeptic_a, skeptic_b, hunter),
        (
            _result("x", current_ref, a_ref, 12),
            _result("z", current_ref, b_ref, 12),
            _result("y", current_ref, h_ref, 12),
        ),
    )

    assert selected == ()


def test_stop_challenger_selector_rejects_noncanonical_or_reversed_ordering() -> None:
    current = _candidate("c", 10)
    current_ref = current["ref"]
    assert isinstance(current_ref, dict)
    skeptic = _assignment("s", current_ref, "FALSE_POSITIVE_SKEPTIC", 12)
    hunter = _assignment("h", current_ref, "FALSE_NEGATIVE_HUNTER", 12)
    skeptic_ref = skeptic["ref"]
    hunter_ref = hunter["ref"]
    assert isinstance(skeptic_ref, dict) and isinstance(hunter_ref, dict)

    selected = select_current_baseline_challenger_refs(
        current,
        (skeptic, hunter),
        (_result("x", current_ref, skeptic_ref, 11), _result("y", current_ref, hunter_ref, 13)),
    )

    assert selected == ()
