from __future__ import annotations

from pathlib import Path

from bdb_audit.coordinator.operations import AuditOperationApi


def _completed_e1_e5(tmp_path: Path, seed: str) -> tuple[AuditOperationApi, Path]:
    target = tmp_path / f"target-{seed}"
    target.mkdir()
    (target / "app.py").write_text("def run(): return 42\n", encoding="utf-8")
    store = tmp_path / f"{seed}.sqlite"
    api = AuditOperationApi()
    api.create_campaign(store, seed=seed, target_repo=str(target))
    for stage in ("E1", "E2", "E3", "E4", "E5"):
        api.prepare_stage(store, stage)
        result = api.qualify_stage(store, stage)
        assert result["status"] == "SUCCESS"
    return api, store


def test_ru08_e6_approval_without_material_gap_does_not_force_e6(tmp_path: Path) -> None:
    api, store = _completed_e1_e5(tmp_path, "e6-no-gap")

    result = api.evaluate_stop_gate(
        store,
        evaluation_context="FINAL_POST_E5",
        e6_plan_approved=True,
    )

    assert result["continuation_decision"] == "PASS"
    assert result["assurance_level"] == "ADEQUATE_FOR_DECLARED_SCOPE"
    assert result["release_readiness"] in {"READY", "READY_WITH_RESIDUAL_RISK"}


def test_ru08_material_unknown_scope_requires_e6_only_with_approved_plan(tmp_path: Path) -> None:
    api, store = _completed_e1_e5(tmp_path, "e6-material-gap")

    result = api.evaluate_stop_gate(
        store,
        evaluation_context="FINAL_POST_E5",
        e6_plan_approved=True,
        unknown_blocked_summary={
            "unknown_surfaces_count": 1,
            "has_unknown_scope": True,
            "is_blocked": False,
        },
    )

    assert result["continuation_decision"] == "E6_REQUIRED"
    assert result["assurance_level"] == "BOUNDED"
    assert result["release_readiness"] == "QUALIFICATION_BLOCKED"


def test_ru08_material_unknown_scope_blocks_when_e6_plan_is_not_approved(tmp_path: Path) -> None:
    api, store = _completed_e1_e5(tmp_path, "e6-gap-no-plan")

    result = api.evaluate_stop_gate(
        store,
        evaluation_context="FINAL_POST_E5",
        e6_plan_approved=False,
        unknown_blocked_summary={
            "unknown_surfaces_count": 1,
            "has_unknown_scope": True,
            "is_blocked": False,
        },
    )

    assert result["continuation_decision"] == "BLOCKED"
    assert result["assurance_level"] == "INSUFFICIENT"
    assert result["release_readiness"] == "QUALIFICATION_BLOCKED"
