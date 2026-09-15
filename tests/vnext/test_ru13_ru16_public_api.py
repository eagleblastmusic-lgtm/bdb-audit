from __future__ import annotations

from bdb_audit.incremental import SuccessorCampaignSpec, validate_successor_selection
from bdb_audit.opportunities import OpportunityEvidence, OpportunityQualityDecision, qualify_opportunity_for_report
from bdb_audit.qualification import FrozenHoldout, evaluate_continuous_holdout
from bdb_audit.strategy import StrategyRunMetrics, compare_adaptive_to_baseline


def test_ru13_ru16_public_api_exports_are_importable():
    assert FrozenHoldout is not None
    assert callable(evaluate_continuous_holdout)
    assert StrategyRunMetrics is not None
    assert callable(compare_adaptive_to_baseline)
    assert OpportunityEvidence is not None
    assert OpportunityQualityDecision is not None
    assert callable(qualify_opportunity_for_report)
    assert SuccessorCampaignSpec is not None
    assert callable(validate_successor_selection)
