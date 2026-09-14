from __future__ import annotations

from dataclasses import replace

from bdb_audit.share import build_recipient_bundle, verify_recipient_bundle


def _bundle():
    return build_recipient_bundle(
        {"result": "PASS", "token": "must-not-leak", "nested": {"password": "no"}},
        signing_key=b"shared-secret",
        key_id="k1",
        source_identity="src@1",
        history_cut_digest="cut1",
    )


def test_ru17_verifier_binds_external_metadata_to_signed_envelope():
    bundle = _bundle()
    tampered = replace(bundle, source_identity="src@evil")
    result = verify_recipient_bundle(tampered, signing_key=b"shared-secret")
    assert result["status"] == "FAIL"
    assert "SOURCE_IDENTITY_BINDING_MISMATCH" in result["reason_codes"]


def test_ru17_verifier_binds_redaction_summary_without_disclosing_names():
    bundle = _bundle()
    assert b"password" not in bundle.payload
    assert b"token" not in bundle.payload
    tampered = replace(bundle, removed_private_fields=("secret", "other"))
    result = verify_recipient_bundle(tampered, signing_key=b"shared-secret")
    assert result["status"] == "FAIL"
    assert "REDACTION_SET_BINDING_MISMATCH" in result["reason_codes"]


def test_ru17_verifier_rejects_key_and_cut_metadata_relabeling():
    bundle = _bundle()
    tampered = replace(bundle, key_id="k2", history_cut_digest="cut2")
    result = verify_recipient_bundle(tampered, signing_key=b"shared-secret")
    assert result["status"] == "FAIL"
    assert "KEY_ID_BINDING_MISMATCH" in result["reason_codes"]
    assert "HISTORY_CUT_BINDING_MISMATCH" in result["reason_codes"]
