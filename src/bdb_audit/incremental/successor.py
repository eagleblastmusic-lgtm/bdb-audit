"""Successor-campaign invariants for RU16.

A successor never rewrites the predecessor campaign/source or reopens its
conclusion. Competing successors require explicit selection; recency is never
used as authority.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True)
class SuccessorCampaignSpec:
    predecessor_campaign_id: str
    predecessor_conclusion_digest: str
    predecessor_source_identity: str
    successor_campaign_id: str
    successor_source_identity: str

    def __post_init__(self) -> None:
        if not self.predecessor_campaign_id or not self.successor_campaign_id:
            raise ValueError("campaign identities required")
        if not self.predecessor_conclusion_digest:
            raise ValueError("predecessor conclusion required")
        if not self.predecessor_source_identity or not self.successor_source_identity:
            raise ValueError("source identities required")
        if self.predecessor_campaign_id == self.successor_campaign_id:
            raise ValueError("successor must be a new campaign")
        if self.predecessor_source_identity == self.successor_source_identity:
            raise ValueError("successor requires a new source identity")


def validate_successor_selection(
    spec: SuccessorCampaignSpec,
    *,
    predecessor_is_concluded: bool,
    predecessor_source_after: str,
    predecessor_state_after: str,
    competing_successor_refs: Sequence[str] = (),
    selected_successor_ref: str | None = None,
) -> dict:
    reasons: list[str] = []
    if not predecessor_is_concluded:
        reasons.append("PREDECESSOR_NOT_CONCLUDED")
    if predecessor_source_after != spec.predecessor_source_identity:
        reasons.append("PREDECESSOR_SOURCE_MUTATION_FORBIDDEN")
    if predecessor_state_after == "OPEN":
        reasons.append("PREDECESSOR_REOPEN_FORBIDDEN")

    candidates = tuple(sorted(set(competing_successor_refs)))
    if len(candidates) > 1:
        if selected_successor_ref is None:
            reasons.append("EXPLICIT_SUCCESSOR_SELECTION_REQUIRED")
        elif selected_successor_ref not in candidates:
            reasons.append("SELECTED_SUCCESSOR_NOT_IN_CANDIDATES")
    elif selected_successor_ref is not None and candidates and selected_successor_ref not in candidates:
        reasons.append("SELECTED_SUCCESSOR_NOT_IN_CANDIDATES")

    return {
        "status": "PASS" if not reasons else "REJECTED",
        "reason_codes": tuple(sorted(set(reasons))),
        "predecessor_campaign_id": spec.predecessor_campaign_id,
        "successor_campaign_id": spec.successor_campaign_id,
        "predecessor_source_identity": spec.predecessor_source_identity,
        "successor_source_identity": spec.successor_source_identity,
        "selected_successor_ref": selected_successor_ref,
    }


__all__ = ["SuccessorCampaignSpec", "validate_successor_selection"]
