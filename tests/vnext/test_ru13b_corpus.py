from __future__ import annotations

from bdb_audit.qualification.corpus import SmallTargetCorpusRunner, reference_small_corpus
from bdb_audit.qualification.runner import MethodologyQualifier


def test_small_target_corpus_executes_clean_defective_and_blocked_controls():
    runs = SmallTargetCorpusRunner(timeout_seconds=3.0).run_corpus(reference_small_corpus())
    observed = {run.manifest.target_id: run.observed_label for run in runs}
    assert observed == {
        "clean_normalizer": "CLEAN",
        "defective_normalizer": "DEFECTIVE",
        "blocked_normalizer": "BLOCKED",
    }
    for run in runs:
        assert run.receipt.evaluated_cases_count == 1
        assert run.receipt.raw_output_digest


def test_methodology_scoring_has_explicit_denominator_and_no_false_pass():
    cases = reference_small_corpus()[:2]
    runs = SmallTargetCorpusRunner(timeout_seconds=3.0).run_corpus(cases)
    manifests = [run.manifest for run in runs]
    actual = {run.manifest.target_id: run.observed_label for run in runs}
    metrics = MethodologyQualifier.score_benchmark_corpus(manifests, actual)
    assert metrics.denominator == 2
    assert metrics.true_positives == 1
    assert metrics.true_negatives == 1
    assert metrics.false_positives == 0
    assert metrics.false_negatives == 0
    # The benchmark alone cannot qualify methodology without anti-bypass controls.
    assert metrics.is_methodology_qualified is False
