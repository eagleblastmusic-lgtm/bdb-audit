"""Legacy RU17 helpers retained for compatibility.

These helpers are deliberately local-only. They do not claim historical scope
comparability or recipient-verifiable authority. New integrations must use
``TrendSnapshot``/``compare_trend`` and ``RecipientBundle`` APIs.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import hmac
import json
from typing import Mapping, Sequence

from .privacy import ExportPrivacyPolicy, sanitize_document


class HistoricalTrendNormalizer:
    @staticmethod
    def rate(qualified: int, denominator: int) -> float | None:
        if denominator <= 0:
            return None
        if qualified < 0 or qualified > denominator:
            raise ValueError("qualified must be within denominator")
        return qualified / denominator

    @classmethod
    def compare(cls, snapshots: Sequence[Mapping[str, int]]) -> tuple[dict[str, object], ...]:
        """Normalize rates only; never assert cross-snapshot comparability."""
        result: list[dict[str, object]] = []
        for item in snapshots:
            denominator = int(item.get("denominator", 0))
            qualified = int(item.get("qualified", 0))
            result.append({
                "qualified": qualified,
                "denominator": denominator,
                "rate": cls.rate(qualified, denominator),
                "comparison_authority": "UNASSESSED_LEGACY_RATE_ONLY",
            })
        return tuple(result)


@dataclass(frozen=True)
class ShareBundle:
    payload: bytes
    payload_sha256: str
    signature_hex: str
    signature_profile: str = "HMAC-SHA256-LOCAL-ONLY"


class ShareBundleBuilder:
    """Local integrity helper; not a recipient-verification surface."""

    @staticmethod
    def build(
        document: Mapping[str, object],
        signing_key: bytes,
        privacy_policy: ExportPrivacyPolicy | None = None,
    ) -> ShareBundle:
        if not signing_key:
            raise ValueError("signing_key required")
        cleaned, _removed = sanitize_document(document, privacy_policy or ExportPrivacyPolicy())
        payload = json.dumps(cleaned, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        digest = hashlib.sha256(payload).hexdigest()
        signature = hmac.new(signing_key, payload, hashlib.sha256).hexdigest()
        return ShareBundle(payload, digest, signature)

    @staticmethod
    def verify(bundle: ShareBundle, signing_key: bytes) -> bool:
        if not signing_key or bundle.signature_profile != "HMAC-SHA256-LOCAL-ONLY":
            return False
        digest_ok = hmac.compare_digest(hashlib.sha256(bundle.payload).hexdigest(), bundle.payload_sha256)
        expected = hmac.new(signing_key, bundle.payload, hashlib.sha256).hexdigest()
        return digest_ok and hmac.compare_digest(expected, bundle.signature_hex)


__all__ = ["HistoricalTrendNormalizer", "ShareBundle", "ShareBundleBuilder"]
