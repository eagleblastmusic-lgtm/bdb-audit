"""Operational facade for the explicit E5A/E5B accepted-history lifecycle."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Sequence

from ..assurance.e5_challenge_service import E5ChallengeService
from ..core.registry import ContractRegistry
from ..history.store import TransactionalHistoryStore


class E5OperationApi:
    """Expose E5 candidate/challenger mutations without bypassing Coordinator authority."""

    def __init__(self, registry: ContractRegistry | None = None):
        self.registry = registry or ContractRegistry()

    def _service(self, store_path: str | Path) -> E5ChallengeService:
        store = TransactionalHistoryStore(Path(store_path).resolve(), registry=self.registry)
        return E5ChallengeService(store)

    def freeze_candidate(self, store_path: str | Path) -> dict[str, Any]:
        return self._service(store_path).freeze_candidate()

    def assign_required_challengers(self, store_path: str | Path) -> dict[str, Any]:
        return self._service(store_path).assign_required_challengers()

    def record_required_challenger_results(
        self,
        store_path: str | Path,
        *,
        skeptic_status: str,
        hunter_status: str,
        skeptic_evidence_qualification_refs: Sequence[dict[str, Any]] = (),
        hunter_evidence_qualification_refs: Sequence[dict[str, Any]] = (),
    ) -> dict[str, Any]:
        return self._service(store_path).record_required_challenger_results(
            skeptic_status=skeptic_status,
            hunter_status=hunter_status,
            skeptic_evidence_qualification_refs=skeptic_evidence_qualification_refs,
            hunter_evidence_qualification_refs=hunter_evidence_qualification_refs,
        )


__all__ = ["E5OperationApi"]
