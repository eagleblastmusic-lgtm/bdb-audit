from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class SourceManifest:
    source_identity: str
    file_digests: Mapping[str, str]
    dependency_lock_digest: str
    policy_digest: str
    runtime_profile_digest: str


def build_change_map(old: SourceManifest, new: SourceManifest) -> dict:
    old_files = dict(old.file_digests)
    new_files = dict(new.file_digests)
    paths = sorted(set(old_files).union(new_files))
    changed = [path for path in paths if old_files.get(path) != new_files.get(path)]
    external_inputs = []
    if old.dependency_lock_digest != new.dependency_lock_digest:
        external_inputs.append("DEPENDENCY_LOCK")
    if old.policy_digest != new.policy_digest:
        external_inputs.append("POLICY")
    if old.runtime_profile_digest != new.runtime_profile_digest:
        external_inputs.append("RUNTIME_PROFILE")
    return {
        "old_source_identity": old.source_identity,
        "new_source_identity": new.source_identity,
        "changed_paths": changed,
        "external_input_changes": external_inputs,
    }
