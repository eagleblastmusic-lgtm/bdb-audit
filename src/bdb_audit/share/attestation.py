"""Recipient-verifiable shared-secret export attestation.

This is intentionally labelled HMAC shared-secret verification. It is not a
public-key signature and does not claim non-repudiation. Redacted field names
remain local diagnostics; recipient exports contain only a signed count and an
opaque digest of the redaction set.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import hmac
import json
from typing import Mapping

from .privacy import ExportPrivacyPolicy, sanitize_document


@dataclass(frozen=True)
class RecipientBundle:
    payload: bytes
    payload_sha256: str
    signature_hex: str
    key_id: str
    source_identity: str
    history_cut_digest: str
    removed_private_fields: tuple[str, ...] = ()
    signature_profile: str = "HMAC-SHA256-SHARED-SECRET"


def _removed_fields_digest(removed: tuple[str, ...]) -> str:
    material = json.dumps(list(removed), ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(material).hexdigest()


def _is_sha256(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(ch in "0123456789abcdef" for ch in value)


def build_recipient_bundle(
    document: Mapping[str, object],
    *,
    signing_key: bytes,
    key_id: str,
    source_identity: str,
    history_cut_digest: str,
    privacy_policy: ExportPrivacyPolicy | None = None,
) -> RecipientBundle:
    if not signing_key or not key_id or not source_identity or not history_cut_digest:
        raise ValueError("signing key, key id, source identity and history cut are required")
    cleaned, removed = sanitize_document(document, privacy_policy or ExportPrivacyPolicy())
    envelope = {
        "document": cleaned,
        "source_identity": source_identity,
        "history_cut_digest": history_cut_digest,
        "key_id": key_id,
        "signature_profile": "HMAC-SHA256-SHARED-SECRET",
        "removed_private_field_count": len(removed),
        "removed_private_fields_sha256": _removed_fields_digest(removed),
    }
    payload = json.dumps(envelope, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    digest = hashlib.sha256(payload).hexdigest()
    signature = hmac.new(signing_key, payload, hashlib.sha256).hexdigest()
    return RecipientBundle(payload, digest, signature, key_id, source_identity, history_cut_digest, removed)


def recipient_bundle_to_dict(bundle: RecipientBundle) -> dict[str, object]:
    """Serialize only recipient-safe fields; local redaction paths never leave."""
    return {
        "payload": bundle.payload.decode("utf-8"),
        "payload_sha256": bundle.payload_sha256,
        "signature_hex": bundle.signature_hex,
        "key_id": bundle.key_id,
        "source_identity": bundle.source_identity,
        "history_cut_digest": bundle.history_cut_digest,
        "signature_profile": bundle.signature_profile,
    }


def recipient_bundle_from_dict(value: Mapping[str, object]) -> RecipientBundle:
    return RecipientBundle(
        str(value["payload"]).encode("utf-8"),
        str(value["payload_sha256"]),
        str(value["signature_hex"]),
        str(value["key_id"]),
        str(value["source_identity"]),
        str(value["history_cut_digest"]),
        (),
        str(value.get("signature_profile", "HMAC-SHA256-SHARED-SECRET")),
    )


def verify_recipient_bundle(
    bundle: RecipientBundle,
    *,
    signing_key: bytes,
    expected_key_id: str | None = None,
    expected_source_identity: str | None = None,
    expected_history_cut_digest: str | None = None,
) -> dict[str, object]:
    reasons: list[str] = []
    if not signing_key:
        reasons.append("SIGNING_KEY_MISSING")
    if bundle.signature_profile != "HMAC-SHA256-SHARED-SECRET":
        reasons.append("SIGNATURE_PROFILE_UNSUPPORTED")
    if not bundle.key_id:
        reasons.append("KEY_ID_MISSING")
    if not bundle.source_identity:
        reasons.append("SOURCE_IDENTITY_MISSING")
    if not bundle.history_cut_digest:
        reasons.append("HISTORY_CUT_MISSING")
    if expected_key_id is not None and bundle.key_id != expected_key_id:
        reasons.append("KEY_ID_MISMATCH")
    if expected_source_identity is not None and bundle.source_identity != expected_source_identity:
        reasons.append("EXPECTED_SOURCE_IDENTITY_MISMATCH")
    if expected_history_cut_digest is not None and bundle.history_cut_digest != expected_history_cut_digest:
        reasons.append("EXPECTED_HISTORY_CUT_MISMATCH")
    if not _is_sha256(bundle.payload_sha256):
        reasons.append("PAYLOAD_DIGEST_INVALID")
    elif not hmac.compare_digest(hashlib.sha256(bundle.payload).hexdigest(), bundle.payload_sha256):
        reasons.append("PAYLOAD_DIGEST_MISMATCH")
    expected = hmac.new(signing_key, bundle.payload, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, bundle.signature_hex):
        reasons.append("SIGNATURE_MISMATCH")

    envelope: dict[str, object] | None = None
    try:
        decoded = json.loads(bundle.payload.decode("utf-8"))
        if isinstance(decoded, dict):
            envelope = {str(key): item for key, item in decoded.items()}
        else:
            reasons.append("PAYLOAD_ENVELOPE_INVALID")
    except (UnicodeDecodeError, json.JSONDecodeError):
        reasons.append("PAYLOAD_JSON_INVALID")

    redaction_count: int | None = None
    if envelope is not None:
        if envelope.get("key_id") != bundle.key_id:
            reasons.append("KEY_ID_BINDING_MISMATCH")
        if envelope.get("source_identity") != bundle.source_identity:
            reasons.append("SOURCE_IDENTITY_BINDING_MISMATCH")
        if envelope.get("history_cut_digest") != bundle.history_cut_digest:
            reasons.append("HISTORY_CUT_BINDING_MISMATCH")
        if envelope.get("signature_profile") != bundle.signature_profile:
            reasons.append("SIGNATURE_PROFILE_BINDING_MISMATCH")
        count_value = envelope.get("removed_private_field_count")
        digest_value = envelope.get("removed_private_fields_sha256")
        if not isinstance(count_value, int) or isinstance(count_value, bool) or count_value < 0:
            reasons.append("REDACTION_COUNT_INVALID")
        else:
            redaction_count = count_value
        if not _is_sha256(digest_value):
            reasons.append("REDACTION_DIGEST_INVALID")
        document_value = envelope.get("document")
        if not isinstance(document_value, dict):
            reasons.append("DOCUMENT_PAYLOAD_INVALID")

    return {
        "status": "PASS" if not reasons else "FAIL",
        "reason_codes": sorted(set(reasons)),
        "key_id": bundle.key_id,
        "source_identity": bundle.source_identity,
        "history_cut_digest": bundle.history_cut_digest,
        "redacted_private_field_count": redaction_count,
        "verification_profile": "HMAC_SHA256_SHARED_SECRET_RECIPIENT_VERIFICATION",
        "trust_model": "SHARED_SECRET_RECIPIENT_VERIFICATION",
    }


__all__ = [
    "RecipientBundle", "build_recipient_bundle", "recipient_bundle_from_dict",
    "recipient_bundle_to_dict", "verify_recipient_bundle",
]
