from __future__ import annotations

import pytest

from bdb_audit.coordinator.operations import AuditOperationApi
from bdb_audit.core.errors import ValidationError
from bdb_audit.projections.workbench import CoverageEvidenceWorkbench


def test_workbench_genesis_is_current_and_exposes_not_concluded_blocker(tmp_path):
    db = tmp_path / "campaign.sqlite"
    AuditOperationApi().create_campaign(db, seed="ru12-a")
    wb = CoverageEvidenceWorkbench.from_path(db)
    assert wb.freshness()["status"] == "CURRENT"
    assert wb.coverage_matrix()["coverage"] == []
    blockers = wb.blockers()
    assert blockers["blocker_count"] >= 1
    assert any(b["type"] == "CAMPAIGN_NOT_CONCLUDED" for b in blockers["blockers"])


def test_explain_unknown_obligation_fails_closed(tmp_path):
    db = tmp_path / "campaign.sqlite"
    AuditOperationApi().create_campaign(db, seed="ru12-a-unknown")
    wb = CoverageEvidenceWorkbench.from_path(db)
    with pytest.raises(ValidationError) as exc:
        wb.explain_obligation("f" * 64)
    assert exc.value.code == "COVERAGE_OBLIGATION_NOT_ACCEPTED_AT_CUT"


def test_evidence_inspection_rejects_wrong_kind(tmp_path):
    db = tmp_path / "campaign.sqlite"
    AuditOperationApi().create_campaign(db, seed="ru12-a-evidence")
    wb = CoverageEvidenceWorkbench.from_path(db)
    with pytest.raises(ValidationError) as exc:
        wb.inspect_evidence({"kind": "finding_claim_revision", "revision_digest": "a" * 64})
    assert exc.value.code == "EVIDENCE_REF_KIND_INVALID"
