from __future__ import annotations

from dataclasses import replace
import json

from bdb_audit.share import (
    build_recipient_bundle,
    recipient_bundle_from_dict,
    recipient_bundle_to_dict,
    verify_recipient_bundle,
)


def _bundle():
    return build_recipient_bundle(
        {"result": "PASS", "token": "must-not-leak", "nested": {"password": "no"}},
        signing_key=b"shared-secret",
        key_id="k1",
        source_identity="src@1",
        history_cut_digest="cut1",
    )


def test_ru17_recipient_export_never_serializes_local_redaction_paths():
    bundle = _bundle()
    exported = recipient_bundle_to_dict(bundle)
    encoded = json.dumps(exported, sort_keys=True).encode("utf-8")
    assert b"password" not in encoded
    assert b"token" not in encoded
    assert "removed_private_fields" not in exported
    assert bundle.removed_private_fields


def test_ru17_recipient_roundtrip_verifies_without_private_field_names():
    bundle = _bundle()
    exported = recipient_bundle_to_dict(bundle)
    received = recipient_bundle_from_dict(exported)
    assert received.removed_private_fields == ()
    result = verify_recipient_bundle(received, signing_key=b"shared-secret", expected_key_id="k1")
    assert result["status"] == "PASS"
    assert result["redacted_private_field_count"] == 2


def test_ru17_verifier_binds_external_metadata_to_signed_envelope():
    bundle = recipient_bundle_from_dict(recipient_bundle_to_dict(_bundle()))
    tampered = replace(bundle, source_identity="src@evil")
    result = verify_recipient_bundle(tampered, signing_key=b"shared-secret")
    assert result["status"] == "FAIL"
    assert "SOURCE_IDENTITY_BINDING_MISMATCH" in result["reason_codes"]


def test_ru17_verifier_rejects_payload_tampering_and_metadata_relabeling():
    bundle = recipient_bundle_from_dict(recipient_bundle_to_dict(_bundle()))
    tampered = replace(bundle, payload=bundle.payload + b"x", key_id="k2", history_cut_digest="cut2")
    result = verify_recipient_bundle(tampered, signing_key=b"shared-secret")
    assert result["status"] == "FAIL"
    assert "PAYLOAD_DIGEST_MISMATCH" in result["reason_codes"]
    assert "SIGNATURE_MISMATCH" in result["reason_codes"]
