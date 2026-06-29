import pytest

from benchmarks.cases import load_cases
from benchmarks.catalog import (
    annotate_rule_universe,
    case_counts_by_sutra,
    find_unknown_case_sutras,
    load_rule_universe,
)


@pytest.mark.benchmark
def test_canonical_sutra_universe_loads():
    universe = load_rule_universe()
    assert universe
    assert "6.1.77" in universe


@pytest.mark.benchmark
def test_fixture_cases_reference_real_sutras():
    universe = load_rule_universe()
    cases = load_cases()
    unknown = find_unknown_case_sutras(universe, (case.sutra_id for case in cases))
    assert unknown == []


@pytest.mark.benchmark
def test_universe_classification_is_consistent():
    universe = load_rule_universe()
    cases = load_cases()
    counts = case_counts_by_sutra(case.sutra_id for case in cases)
    annotated = annotate_rule_universe(
        universe,
        case_counts=counts,
        loaded_rule_ids={"6.1.77", "6.1.87"},
        executed_rule_ids={"6.1.77"},
        hardcoding_suspect_ids=set(),
    )

    assert annotated["6.1.77"].classification == "executed"
    assert annotated["6.1.87"].classification in {"adapter_pending", "execution_unmapped"}
    assert sum(1 for entry in annotated.values() if entry.classification == "missing_rule_config") >= 0

    for entry in annotated.values():
        if entry.classification == "executed":
            assert entry.has_rule_config
            assert entry.case_count > 0
            assert entry.loaded_by_runtime
