"""
Benchmark Catalog Gate Tests.

Validates that the canonical sutra universe loads and that all
fixture cases reference real sutras. These are structural gates.
"""

import os
import sys

sys.path.insert(0, os.path.abspath(".."))

from benchmarks.cases import load_cases
from benchmarks.catalog import load_rule_universe, find_unknown_case_sutras


def test_canonical_universe_loads():
    """GATE: The sutras table must produce a non-empty universe."""
    universe = load_rule_universe()
    assert len(universe) > 0, "Canonical sutra universe is empty — DB missing or corrupt."


def test_all_fixture_sutras_exist():
    """GATE: Every fixture case must reference a sutra that exists in the canonical universe."""
    universe = load_rule_universe()
    sandhi_cases = load_cases("tests/fixtures/panini_blackbox_cases.json")
    morph_cases = load_cases("tests/fixtures/morphology_blackbox_cases.json")
    all_cases = sandhi_cases + morph_cases

    unknown = find_unknown_case_sutras(universe, (c.sutra_id for c in all_cases))
    assert not unknown, f"Fixtures reference unknown sutras: {unknown[:10]}"


def test_classification_buckets_are_exhaustive():
    """
    GATE: Every sutra must fall into exactly one classification bucket.
    No sutra should be unclassifiable.
    """
    universe = load_rule_universe()
    # With no loaded rules and no cases, everything should classify
    from benchmarks.catalog import annotate_rule_universe
    entries = annotate_rule_universe(
        universe,
        case_counts={},
        loaded_rule_ids=set(),
        executed_rule_ids=set(),
        hardcoding_suspect_ids=set(),
    )

    valid_classifications = {
        "missing_rule_config",
        "rule_config_only",
        "runtime_unloaded",
        "execution_unmapped",
        "executed",
        "adapter_pending",
    }

    invalid = [
        (sid, entry.classification)
        for sid, entry in entries.items()
        if entry.classification not in valid_classifications
    ]
    assert not invalid, f"Sutras with invalid classifications: {invalid[:10]}"