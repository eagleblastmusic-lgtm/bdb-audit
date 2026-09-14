from __future__ import annotations

from typing import Mapping


def freshness(projection_cut: Mapping[str, object], current_head: Mapping[str, object]) -> dict:
    cut_seq = projection_cut.get("accepted_head_seq")
    cut_hash = projection_cut.get("accepted_head_hash")
    head_seq = current_head.get("commit_seq")
    head_hash = current_head.get("commit_hash")
    is_fresh = cut_seq == head_seq and cut_hash == head_hash
    return {"fresh": is_fresh, "status": "FRESH" if is_fresh else "STALE", "projection_seq": cut_seq, "current_seq": head_seq}
