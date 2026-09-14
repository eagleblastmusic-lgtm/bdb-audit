"""Sensitivity-aware access boundary for raw evidence bytes.

The canonical vault is content addressed.  This layer never accepts a caller-
supplied file path and defaults unknown sensitivity to the most restrictive
class so an absent classification cannot accidentally expose evidence.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

from ..core.errors import ValidationError
from .raw_store import RawArtifactVault

_SENSITIVITY_ORDER = {"PUBLIC": 0, "INTERNAL": 1, "CONFIDENTIAL": 2, "RESTRICTED": 3}


@dataclass(frozen=True)
class VaultAccessPolicy:
    max_sensitivity: str = "INTERNAL"
    allow_raw_content: bool = False
    max_raw_bytes: int = 256_000
    sensitivity_by_digest: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.max_sensitivity not in _SENSITIVITY_ORDER:
            raise ValueError("invalid max_sensitivity")
        if self.max_raw_bytes <= 0:
            raise ValueError("max_raw_bytes must be positive")

    def sensitivity(self, digest: str) -> str:
        value = self.sensitivity_by_digest.get(digest, "RESTRICTED")
        return value if value in _SENSITIVITY_ORDER else "RESTRICTED"

    def permits(self, digest: str) -> bool:
        return _SENSITIVITY_ORDER[self.sensitivity(digest)] <= _SENSITIVITY_ORDER[self.max_sensitivity]


class VaultEvidenceAccess:
    def __init__(self, vault: RawArtifactVault, policy: VaultAccessPolicy):
        self.vault = vault
        self.policy = policy

    def inspect(self, raw_digest: str) -> dict:
        metadata = self.vault.read_metadata(raw_digest)
        sensitivity = self.policy.sensitivity(raw_digest)
        permitted = self.policy.permits(raw_digest)
        return {
            "raw_digest": raw_digest,
            "byte_length": metadata["byte_length"],
            "media_type": metadata["media_type"],
            "digest_profile": metadata["digest_profile"],
            "sensitivity": sensitivity,
            "raw_content_access": "PERMITTED" if permitted and self.policy.allow_raw_content else "DENIED",
        }

    def read_bytes(self, raw_digest: str) -> bytes:
        metadata = self.vault.read_metadata(raw_digest)
        if not self.policy.allow_raw_content:
            raise ValidationError("RAW_EVIDENCE_CONTENT_NOT_AUTHORIZED", raw_digest)
        if not self.policy.permits(raw_digest):
            raise ValidationError("RAW_EVIDENCE_SENSITIVITY_DENIED", raw_digest)
        if int(metadata["byte_length"]) > self.policy.max_raw_bytes:
            raise ValidationError("RAW_EVIDENCE_SIZE_LIMIT", raw_digest)
        return self.vault.read_bytes(raw_digest)


__all__ = ["VaultAccessPolicy", "VaultEvidenceAccess"]
