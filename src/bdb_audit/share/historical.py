"""RU17 scope-normalized historical view and verifiable share bundle."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import hmac
import json
from typing import Mapping, Sequence


class HistoricalTrendNormalizer:
    @staticmethod
    def rate(qualified: int, denominator: int) -> float | None:
        if denominator <= 0:
            return None
        if qualified < 0 or qualified > denominator:
            raise ValueError("qualified must be within denominator")
        return qualified / denominator

    @classmethod
    def compare(cls, snapshots: Sequence[Mapping[str, int]]) -> tuple[dict, ...]:
        result = []
        for item in snapshots:
            denominator = int(item.get("denominator", 0))
            qualified = int(item.get("qualified", 0))
            result.append({"qualified": qualified, "denominator": denominator, "rate": cls.rate(qualified, denominator)})
        return tuple(result)


@dataclass(frozen=True)
class ShareBundle:
    payload: bytes
    payload_sha256: str
    signature_hex: str
    signature_profile: str = "HMAC-SHA256-LOCAL-VERIFY"


class ShareBundleBuilder:
    @staticmethod
    def build(document: Mapping[str, object], signing_key: bytes) -> ShareBundle:
        if not signing_key:
            raise ValueError("signing_key required")
        payload = json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        digest = hashlib.sha256(payload).hexdigest()
        signature = hmac.new(signing_key, payload, hashlib.sha256).hexdigest()
        return ShareBundle(payload, digest, signature)

    @staticmethod
    def verify(bundle: ShareBundle, signing_key: bytes) -> bool:
        digest_ok = hmac.compare_digest(hashlib.sha256(bundle.payload).hexdigest(), bundle.payload_sha256)
        expected = hmac.new(signing_key, bundle.payload, hashlib.sha256).hexdigest()
        return digest_ok and hmac.compare_digest(expected, bundle.signature_hex)
