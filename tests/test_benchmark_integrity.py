import pytest

from benchmarks.cases import load_cases
from benchmarks.local_engine_adapter import LocalEngineAdapter
from benchmarks.pipeline import run_pipeline


@pytest.mark.integrity
def test_local_engine_cases_match_outputs_and_rule_expectations():
    adapter = LocalEngineAdapter()
    results = adapter.batch_run(load_cases())
    failures = [result for result in results if not result.passed]

    assert failures == [], [result.errors for result in failures]


@pytest.mark.integrity
def test_positive_cases_show_expected_rule_in_derivation_evidence():
    adapter = LocalEngineAdapter()
    for result in adapter.batch_run(load_cases()):
        if result.case.expected_rule_presence:
            assert result.case.sutra_id in result.evidence.applied_rule_ids
            assert result.evidence.trace_steps
        else:
            assert result.case.sutra_id not in result.evidence.applied_rule_ids


@pytest.mark.integrity
def test_pipeline_reports_no_hardcoding_suspicions_for_local_fixture_subset():
    payload = run_pipeline()
    assert payload["hardcoding_suspicions"] == []
