from __future__ import annotations

from bdb_audit.incremental import (
    DependencyEdge,
    EvidenceReuseBinding,
    SourceManifest,
    propagate_impact,
    qualify_reuse,
)


def _old() -> SourceManifest:
    return SourceManifest(
        "source@old",
        {"db.py": "1", "service.py": "2", "api.py": "3"},
        "lock-a",
        "policy-a",
        "runtime-a",
    )


def _binding(*, dependency_nodes: tuple[str, ...] = ("api.py",)) -> EvidenceReuseBinding:
    return EvidenceReuseBinding(
        evidence_id="ev-1",
        evidence_digest="a" * 64,
        source_identity="source@old",
        dependency_lock_digest="lock-a",
        policy_digest="policy-a",
        runtime_profile_digest="runtime-a",
        dependency_nodes=dependency_nodes,
    )


def test_ru16_unchanged_bound_evidence_can_be_reused_with_complete_impact_map():
    old = _old()
    new = SourceManifest("source@new", dict(old.file_digests), "lock-a", "policy-a", "runtime-a")
    result = qualify_reuse(
        binding=_binding(),
        old_manifest=old,
        new_manifest=new,
        impact=propagate_impact((), ()),
    )
    assert result["status"] == "REUSE_QUALIFIED"
    assert result["reason_codes"] == []


def test_ru16_out_of_diff_dependency_change_invalidates_relevant_evidence():
    old = _old()
    new = SourceManifest(
        "source@new",
        {"db.py": "9", "service.py": "2", "api.py": "3"},
        "lock-a",
        "policy-a",
        "runtime-a",
    )
    impact = propagate_impact(
        ("db.py",),
        (
            DependencyEdge("db.py", "service.py"),
            DependencyEdge("service.py", "api.py"),
        ),
    )
    result = qualify_reuse(binding=_binding(), old_manifest=old, new_manifest=new, impact=impact)
    assert result["status"] == "REQUALIFICATION_REQUIRED"
    assert "DEPENDENCY_IMPACTED" in result["reason_codes"]


def test_ru16_dependency_lock_policy_and_runtime_drift_are_derived_not_caller_declared():
    old = _old()
    new = SourceManifest(
        "source@new",
        dict(old.file_digests),
        "lock-b",
        "policy-b",
        "runtime-b",
    )
    result = qualify_reuse(
        binding=_binding(),
        old_manifest=old,
        new_manifest=new,
        impact=propagate_impact((), ()),
    )
    assert result["status"] == "REQUALIFICATION_REQUIRED"
    assert "DEPENDENCY_LOCK_CHANGED" in result["reason_codes"]
    assert "POLICY_CHANGED" in result["reason_codes"]
    assert "RUNTIME_CHANGED" in result["reason_codes"]


def test_ru16_incomplete_impact_map_cannot_hide_changed_path():
    old = _old()
    new = SourceManifest(
        "source@new",
        {"db.py": "9", "service.py": "2", "api.py": "3"},
        "lock-a",
        "policy-a",
        "runtime-a",
    )
    result = qualify_reuse(
        binding=_binding(dependency_nodes=("unrelated.py",)),
        old_manifest=old,
        new_manifest=new,
        impact={"changed": (), "impacted": (), "uncertain_impacts": ()},
    )
    assert result["status"] == "REQUALIFICATION_REQUIRED"
    assert "IMPACT_MAP_INCOMPLETE" in result["reason_codes"]


def test_ru16_stale_evidence_binding_cannot_be_reused():
    old = _old()
    stale = EvidenceReuseBinding(
        evidence_id="ev-1",
        evidence_digest="a" * 64,
        source_identity="source@different",
        dependency_lock_digest="lock-old",
        policy_digest="policy-old",
        runtime_profile_digest="runtime-old",
        dependency_nodes=("api.py",),
    )
    new = SourceManifest("source@new", dict(old.file_digests), "lock-a", "policy-a", "runtime-a")
    result = qualify_reuse(
        binding=stale,
        old_manifest=old,
        new_manifest=new,
        impact=propagate_impact((), ()),
    )
    assert result["status"] == "REQUALIFICATION_REQUIRED"
    assert "OLD_EVIDENCE_SOURCE_BINDING_MISMATCH" in result["reason_codes"]
    assert "OLD_EVIDENCE_DEPENDENCY_BINDING_MISMATCH" in result["reason_codes"]
    assert "OLD_EVIDENCE_POLICY_BINDING_MISMATCH" in result["reason_codes"]
    assert "OLD_EVIDENCE_RUNTIME_BINDING_MISMATCH" in result["reason_codes"]


def test_ru16_changed_content_requires_advanced_source_identity():
    old = _old()
    new = SourceManifest(
        "source@old",
        {"db.py": "9", "service.py": "2", "api.py": "3"},
        "lock-a",
        "policy-a",
        "runtime-a",
    )
    impact = propagate_impact(("db.py",), ())
    result = qualify_reuse(
        binding=_binding(dependency_nodes=("unrelated.py",)),
        old_manifest=old,
        new_manifest=new,
        impact=impact,
    )
    assert result["status"] == "REQUALIFICATION_REQUIRED"
    assert "SOURCE_IDENTITY_NOT_ADVANCED" in result["reason_codes"]
