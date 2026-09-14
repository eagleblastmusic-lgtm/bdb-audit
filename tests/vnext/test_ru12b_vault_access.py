from __future__ import annotations

import pytest

from bdb_audit.core.errors import ValidationError
from bdb_audit.vault import RawArtifactVault, VaultAccessPolicy, VaultEvidenceAccess


def test_raw_vault_metadata_is_verified_and_unknown_sensitivity_fails_closed(tmp_path):
    vault = RawArtifactVault(tmp_path / "vault")
    receipt = vault.put_bytes(b"evidence", media_type="text/plain")
    metadata = vault.read_metadata(receipt.raw_digest)
    assert metadata["raw_digest"] == receipt.raw_digest
    assert metadata["byte_length"] == 8

    access = VaultEvidenceAccess(vault, VaultAccessPolicy(max_sensitivity="INTERNAL", allow_raw_content=True))
    inspected = access.inspect(receipt.raw_digest)
    assert inspected["sensitivity"] == "RESTRICTED"
    assert inspected["raw_content_access"] == "DENIED"
    with pytest.raises(ValidationError) as exc:
        access.read_bytes(receipt.raw_digest)
    assert exc.value.code == "RAW_EVIDENCE_SENSITIVITY_DENIED"


def test_raw_content_requires_explicit_content_permission_and_classification(tmp_path):
    vault = RawArtifactVault(tmp_path / "vault")
    receipt = vault.put_bytes(b"safe evidence", media_type="text/plain")
    no_content = VaultEvidenceAccess(vault, VaultAccessPolicy(max_sensitivity="INTERNAL", allow_raw_content=False, sensitivity_by_digest={receipt.raw_digest: "INTERNAL"}))
    with pytest.raises(ValidationError) as exc:
        no_content.read_bytes(receipt.raw_digest)
    assert exc.value.code == "RAW_EVIDENCE_CONTENT_NOT_AUTHORIZED"

    allowed = VaultEvidenceAccess(vault, VaultAccessPolicy(max_sensitivity="INTERNAL", allow_raw_content=True, sensitivity_by_digest={receipt.raw_digest: "INTERNAL"}))
    assert allowed.read_bytes(receipt.raw_digest) == b"safe evidence"
