from __future__ import annotations

from .models import FrictionCandidate, UserTaskTrace


def analyze_trace(trace: UserTaskTrace) -> tuple[FrictionCandidate, ...]:
    if not trace.evidence_refs:
        return ()
    result: list[FrictionCandidate] = []
    if len(trace.steps) >= 5:
        result.append(FrictionCandidate(
            friction_id=f"friction_{trace.trace_id}_steps",
            trace_id=trace.trace_id,
            statement=f"Task requires {len(trace.steps)} recorded steps",
            evidence_refs=trace.evidence_refs,
            basis=trace.observation_basis,
        ))
    return tuple(result)
