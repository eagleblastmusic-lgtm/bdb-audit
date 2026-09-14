"""Immutable derived report models.

These objects are exports/projections. They deliberately do not masquerade as
canonical accepted-history objects and never grant PASS/READY authority.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence


@dataclass(frozen=True)
class ReportSnapshot:
    campaign_id: str
    history_cut: Mapping[str, Any]
    source_identity: Mapping[str, Any]
    report_status: str
    termination_state: str
    campaign_completed: bool
    findings: Sequence[Mapping[str, Any]] = field(default_factory=tuple)
    coverage: Sequence[Mapping[str, Any]] = field(default_factory=tuple)
    evidence_index: Sequence[Mapping[str, Any]] = field(default_factory=tuple)
    contradictions: Sequence[Mapping[str, Any]] = field(default_factory=tuple)
    root_causes: Sequence[Mapping[str, Any]] = field(default_factory=tuple)
    stop_evaluations: Sequence[Mapping[str, Any]] = field(default_factory=tuple)
    unknowns: Sequence[Mapping[str, Any]] = field(default_factory=tuple)
    report_version: str = "2"

    def as_dict(self) -> dict[str, Any]:
        return {
            "report_version": self.report_version,
            "campaign_id": self.campaign_id,
            "history_cut": dict(self.history_cut),
            "source_identity": dict(self.source_identity),
            "report_status": self.report_status,
            "termination_state": self.termination_state,
            "campaign_completed": self.campaign_completed,
            "findings": [dict(v) for v in self.findings],
            "coverage": [dict(v) for v in self.coverage],
            "evidence_index": [dict(v) for v in self.evidence_index],
            "contradictions": [dict(v) for v in self.contradictions],
            "root_causes": [dict(v) for v in self.root_causes],
            "stop_evaluations": [dict(v) for v in self.stop_evaluations],
            "unknowns": [dict(v) for v in self.unknowns],
        }


__all__ = ["ReportSnapshot"]
