"""Recipient-verifiable shared-secret export attestation.

This is intentionally labelled HMAC shared-secret verification.  It is not a
public-key signature and does not claim non-repudiation.
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
    removed_private_fields: tuple[str, ...]
    signature_profile: str = "HMAC-SHA256-SHARED-SECRET"


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
        "removed_private_fields": list(removed),
    }
    payload = json.dumps(envelope, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    digest = hashlib.sha256(payload).hexdigest()
    signature = hmac.new(signing_key, payload, hashlib.sha256).hexdigest()
    return RecipientBundle(payload, digest, signature, key_id, source_identity, history_cut_digest, removed)


def verify_recipient_bundle(bundle: RecipientBundle, *, signing_key: bytes, expected_key_id: str | None = None) -> dict:
    reasons: list[str] = []
    if bundle.signature_profile != "HMAC-SHA256-SHARED-SECRET":
        reasons.append("SIGNATURE_PROFILE_UNSUPPORTED")
    if expected_key_id is not None and bundle.key_id != expected_key_id:
        reasons.append("KEY_ID_MISMATCH")
    if not hmac.compare_digest(hashlib.sha256(bundle.payload).hexdigest(), bundle.payload_sha256):
        reasons.append("PAYLOAD_DIGEST_MISMATCH")
    expected = hmac.new(signing_key, bundle.payload, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, bundle.signature_hex):
        reasons.append("SIGNATURE_MISMATCH")
    return {"status": "PASS" if not reasons else "FAIL", "reason_codes": reasons, "key_id": bundle.key_id, "source_identity": bundle.source_identity, "history_cut_digest": bundle.history_cut_digest}


__all__ = ["RecipientBundle", "build_recipient_bundle", "verify_recipient_bundle"]
