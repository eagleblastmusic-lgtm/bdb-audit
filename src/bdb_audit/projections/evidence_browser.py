"""Exact-cut evidence navigation with optional sensitivity-aware raw drill-down."""
from __future__ import annotations

from typing import Any, Mapping

from ..core.errors import ValidationError
from ..history.store import TransactionalHistoryStore
from ..vault.access import VaultEvidenceAccess


def _is_raw_digest(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(ch in "0123456789abcdef" for ch in value)


class EvidenceBrowser:
    def __init__(self, store: TransactionalHistoryStore, cut: Mapping[str, Any], vault_access: VaultEvidenceAccess | None = None):
        self.store = store
        self.cut = dict(cut)
        self.vault_access = vault_access

    def _raw_digest_from_ref(self, value: object) -> str | None:
        if _is_raw_digest(value):
            return str(value)
        if not isinstance(value, Mapping):
            return None
        direct = value.get("raw_digest")
        if _is_raw_digest(direct):
            return str(direct)
        kind = value.get("kind")
        if kind in {"raw_artifact_ref", "legacy_raw_ref"} and value.get("revision_digest"):
            try:
                accepted = self.store.resolve_accepted(dict(value), self.cut)
            except ValidationError:
                return None
            body = accepted["body"]
            for key in ("raw_digest", "legacy_raw_digest", "review_raw_digest", "artifact_raw_digest"):
                candidate = body.get(key)
                if _is_raw_digest(candidate):
                    return str(candidate)
        return None

    def inspect_qualification(self, evidence_ref: Mapping[str, Any], *, include_raw_metadata: bool = False) -> dict:
        if evidence_ref.get("kind") != "evidence_qualification_assessment":
            raise ValidationError("EVIDENCE_REF_KIND_INVALID")
        assessment = self.store.resolve_accepted(dict(evidence_ref), self.cut)
        observation_rows: list[dict] = []
        for observation_ref in assessment["body"].get("observation_refs", []):
            observation = self.store.resolve_accepted(observation_ref, self.cut)
            raw_ref = observation["body"].get("raw_observation_ref")
            raw_digest = self._raw_digest_from_ref(raw_ref)
            row = {
                "observation_ref": observation["ref"],
                "accepted_seq": observation["accepted_seq"],
                "channel": observation["body"].get("observation_channel"),
                "raw_observation_ref": raw_ref,
                "raw_digest": raw_digest,
            }
            if include_raw_metadata and raw_digest:
                if self.vault_access is None:
                    row["raw_access"] = {"status": "UNAVAILABLE", "reason": "VAULT_ACCESS_NOT_CONFIGURED"}
                else:
                    row["raw_access"] = self.vault_access.inspect(raw_digest)
            observation_rows.append(row)
        return {
            "projection_kind": "EVIDENCE_BROWSER",
            "history_cut": dict(self.cut),
            "evidence_ref": assessment["ref"],
            "accepted_seq": assessment["accepted_seq"],
            "qualification_result": assessment["body"].get("result"),
            "reason_codes": list(assessment["body"].get("reason_codes", [])),
            "observations": observation_rows,
        }


__all__ = ["EvidenceBrowser"]
