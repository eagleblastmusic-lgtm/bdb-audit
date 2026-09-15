from __future__ import annotations

from dataclasses import replace
import json

from bdb_audit.share import (
    ExportPrivacyPolicy,
    HistoricalTrendNormalizer,
    ShareBundleBuilder,
    TrendSnapshot,
    build_recipient_bundle,
    compare_trend,
    recipient_bundle_from_dict,
    recipient_bundle_to_dict,
    sanitize_document,
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
    result = verify_recipient_bundle(
        received,
        signing_key=b"shared-secret",
        expected_key_id="k1",
        expected_source_identity="src@1",
        expected_history_cut_digest="cut1",
    )
    assert result["status"] == "PASS"
    assert result["redacted_private_field_count"] == 2
    assert result["trust_model"] == "SHARED_SECRET_RECIPIENT_VERIFICATION"


def test_ru17_verifier_binds_external_metadata_to_signed_envelope():
    bundle = recipient_bundle_from_dict(recipient_bundle_to_dict(_bundle()))
    tampered = replace(bundle, source_identity="src@evil")
    result = verify_recipient_bundle(tampered, signing_key=b"shared-secret")
    assert result["status"] == "FAIL"
    assert "SOURCE_IDENTITY_BINDING_MISMATCH" in result["reason_codes"]


def test_ru17_recipient_expectations_anchor_source_and_history_cut():
    bundle = recipient_bundle_from_dict(recipient_bundle_to_dict(_bundle()))
    source_mismatch = verify_recipient_bundle(
        bundle,
        signing_key=b"shared-secret",
        expected_source_identity="src@expected",
        expected_history_cut_digest="cut1",
    )
    assert source_mismatch["status"] == "FAIL"
    assert "EXPECTED_SOURCE_IDENTITY_MISMATCH" in source_mismatch["reason_codes"]

    cut_mismatch = verify_recipient_bundle(
        bundle,
        signing_key=b"shared-secret",
        expected_source_identity="src@1",
        expected_history_cut_digest="cut-expected",
    )
    assert cut_mismatch["status"] == "FAIL"
    assert "EXPECTED_HISTORY_CUT_MISMATCH" in cut_mismatch["reason_codes"]


def test_ru17_verifier_rejects_payload_tampering_metadata_relabeling_and_empty_key():
    bundle = recipient_bundle_from_dict(recipient_bundle_to_dict(_bundle()))
    tampered = replace(bundle, payload=bundle.payload + b"x", key_id="k2", history_cut_digest="cut2")
    result = verify_recipient_bundle(tampered, signing_key=b"shared-secret")
    assert result["status"] == "FAIL"
    assert "PAYLOAD_DIGEST_MISMATCH" in result["reason_codes"]
    assert "SIGNATURE_MISMATCH" in result["reason_codes"]
    assert verify_recipient_bundle(bundle, signing_key=b"")["status"] == "FAIL"


def test_ru17_sensitivity_policy_redacts_whole_disallowed_object_case_insensitively():
    document = {
        "public": {"sensitivity": "PUBLIC", "value": "ok"},
        "confidential": {
            "Sensitivity": "CONFIDENTIAL",
            "arbitrary_field_name": "must-not-leak",
            "another": {"value": "also-secret"},
        },
    }
    cleaned, removed = sanitize_document(document, ExportPrivacyPolicy())
    encoded = json.dumps(cleaned, sort_keys=True)
    assert "must-not-leak" not in encoded
    assert "also-secret" not in encoded
    assert cleaned["confidential"] == {"redacted": True}
    assert "confidential" in removed


def test_ru17_malformed_or_ambiguous_sensitivity_is_fail_closed():
    cleaned, removed = sanitize_document(
        {"record": {"sensitivity": 7, "value": "secret"}},
        ExportPrivacyPolicy(),
    )
    assert cleaned["record"] == {"redacted": True}
    assert removed == ("record",)

    cleaned, removed = sanitize_document(
        {"record": {"sensitivity": "PUBLIC", "Sensitivity": "CONFIDENTIAL", "value": "secret"}},
        ExportPrivacyPolicy(),
    )
    assert cleaned["record"] == {"redacted": True}
    assert removed == ("record",)


def test_ru17_trend_requires_actual_history_and_unique_sources():
    one = compare_trend((TrendSnapshot("s1", "scope", "policy", 8, 10),))
    assert one["status"] == "INSUFFICIENT_HISTORY"
    duplicate = compare_trend((
        TrendSnapshot("s1", "scope", "policy", 8, 10),
        TrendSnapshot("s1", "scope", "policy", 9, 10),
    ))
    assert duplicate["status"] == "INCOMPARABLE_DUPLICATE_SOURCE"


def test_ru17_legacy_helpers_are_explicitly_non_authoritative_and_privacy_filtered():
    rows = HistoricalTrendNormalizer.compare(({"qualified": 8, "denominator": 10}, {"qualified": 9, "denominator": 10}))
    assert rows[0]["comparison_authority"] == "UNASSESSED_LEGACY_RATE_ONLY"
    bundle = ShareBundleBuilder.build({"result": "PASS", "token": "must-not-leak"}, b"local-key")
    assert b"must-not-leak" not in bundle.payload
    assert bundle.signature_profile == "HMAC-SHA256-LOCAL-ONLY"
    assert ShareBundleBuilder.verify(bundle, b"local-key")
