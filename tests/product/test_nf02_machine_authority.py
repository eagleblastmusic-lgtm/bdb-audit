"""Real boundary guards and simulated cryptographic verifier unit controls.

No root/certificate/qualification is generated or installed by this suite.
"""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
import os

import pytest

from bdb_audit.core.canonical_json import canonical_bytes
from bdb_audit.core.errors import ValidationError
from bdb_audit.history.installation_authority import MachineAuthority, verify_cms, _protected, sha
from bdb_audit.history.installation_authority import verify_q1_record


def test_grant_is_independent_scoped_and_signature_binds_exact_command(monkeypatch):
    now = datetime.now(timezone.utc)
    scope = {"assignment_ref": {"revision_digest": "a" * 64}, "result_slot_contract_refs": [{"revision_digest": "b" * 64}]}
    grant = {"actor_ref": "independent producer", "campaign_id": "new campaign", "operations": ["START_ATTEMPT"],
             "scope": scope, "not_before": (now - timedelta(hours=1)).isoformat(), "not_after": (now + timedelta(hours=1)).isoformat(),
             "certificate_sha256": "c" * 64}
    leased = {"identity": "d" * 64, "installation": {"grants": [grant]}}
    command = SimpleNamespace(actor_ref=grant["actor_ref"], campaign_ref=grant["campaign_id"], proposed_campaign_id=None,
                              command_kind="START_ATTEMPT", digest="e" * 64)
    statement = canonical_bytes({"domain": "BDB_NF02_AUTHENTICATED_COMMAND/1", "installation": leased["identity"],
                                 "command_digest": command.digest, "scope": scope})
    signature = sha(statement).encode()
    calls = []

    def simulated_crypto(raw, signed, pin):
        calls.append((raw, pin))
        if signed != sha(raw).encode() or pin != grant["certificate_sha256"]:
            raise ValidationError("SIMULATED_CRYPTO_REJECTED")

    monkeypatch.setattr("bdb_audit.history.installation_authority.verify_cms", simulated_crypto)
    authority = MachineAuthority()
    authority.authenticate(leased, command, signature, scope)
    assert calls == [(statement, grant["certificate_sha256"])]
    for field, value in (("actor_ref", "self-appointed"), ("campaign_ref", "foreign"), ("command_kind", "INGEST_EXTERNAL_LANE_RESULT")):
        wrong = SimpleNamespace(**vars(command))
        setattr(wrong, field, value)
        with pytest.raises(ValidationError, match="NF02_PRODUCER_NOT_AUTHORIZED"):
            authority.authenticate(leased, wrong, signature, scope)
    with pytest.raises(ValidationError, match="NF02_PRODUCER_NOT_AUTHORIZED"):
        authority.authenticate(leased, command, signature, {**scope, "result_slot_contract_refs": []})
    with pytest.raises(ValidationError, match="SIMULATED_CRYPTO_REJECTED"):
        authority.authenticate(leased, SimpleNamespace(**{**vars(command), "digest": "f" * 64}), signature, scope)
    grant["not_after"] = (now - timedelta(minutes=1)).isoformat()
    with pytest.raises(ValidationError, match="NF02_PRODUCER_NOT_AUTHORIZED"):
        authority.authenticate(leased, command, signature, scope)


def test_signature_required_and_public_storage_selector_cannot_activate(tmp_path):
    with pytest.raises(ValidationError, match="NF02_PRODUCER_SIGNATURE_REQUIRED"):
        verify_cms(b"content", b"", "a" * 64)
    with pytest.raises(ValidationError, match="NF02_PROTECTED_HISTORY_LOCATION_REQUIRED"):
        with MachineAuthority().storage_lease(tmp_path / "caller.sqlite"):
            pytest.fail("unprotected storage was allowed")
    assert not (tmp_path / "caller.sqlite").exists()


def test_historical_author_only_record_cannot_activate_current_implementation():
    # Even an owner-signed install/qualifier PASS wrapper must not turn the
    # predecessor qualification into fresh successor qualification.
    with pytest.raises(ValidationError, match="NF02_FRESH_EXACT_SUCCESSOR_Q1_REQUIRED"):
        verify_q1_record({}, {}, {"revision": "R5.4.1"})


@pytest.mark.skipif(os.name != "nt", reason="production Windows CMS/ACL boundary")
def test_real_os_verifier_rejects_invalid_cms_and_unprotected_owner(tmp_path):
    with pytest.raises(ValidationError, match="NF02_AUTHORITY_VERIFICATION_FAILED"):
        verify_cms(b"content", b"invalid CMS bytes", "a" * 64)
    with pytest.raises(ValidationError, match="NF02_AUTHORITY_VERIFICATION_FAILED"):
        _protected(tmp_path)
