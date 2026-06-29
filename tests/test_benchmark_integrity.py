"""
Paninian Benchmark Gate Tests.

These tests are GATES, not smoke tests. They MUST FAIL while the engine
is incomplete. They only pass when the engine achieves true coverage.

- test_full_sutra_coverage: FAILS if any sutra is unmapped
- test_morphological_execution: FAILS if morph cases produce wrong output
- test_sandhi_execution: FAILS if sandhi cases produce wrong output
- test_no_hardcoding: FAILS if hardcoding is suspected
- test_dynamic_execution_gate: FAILS if rules aren't dynamically executed
"""

import os
import sys
import json

sys.path.insert(0, os.path.abspath(".."))

from benchmarks.local_engine_adapter import LocalEngineAdapter
from benchmarks.cases import load_cases
from benchmarks.catalog import load_rule_universe, annotate_rule_universe
from benchmarks.reports import build_coverage_summary
from benchmarks.pipeline import run_pipeline


def test_full_sutra_coverage():
    """
    GATE: Every sutra in the canonical universe must be mapped.
    FAILS if any sutra is unmapped (missing rule_config, unloaded, or unexecuted).
    """
    universe = load_rule_universe()
    adapter = LocalEngineAdapter()
    loaded_rule_ids = set(adapter.list_loaded_rules())
    
    entries = annotate_rule_universe(
        universe,
        case_counts={},
        loaded_rule_ids=loaded_rule_ids,
        executed_rule_ids=set(),
        hardcoding_suspect_ids=set(),
    )
    
    unmapped = [
        sutra_id for sutra_id, entry in entries.items()
        if entry.classification != "executed"
    ]
    
    if unmapped:
        raise AssertionError(
            f"ENGINE INCOMPLETE: {len(unmapped)} of {len(entries)} sutras are unmapped.\n"
            f"Coverage: {100*(len(entries)-len(unmapped))/len(entries):.1f}%\n"
            f"Sample unmapped: {sorted(unmapped)[:20]}"
        )


def test_sandhi_execution():
    """
    GATE: All sandhi benchmark cases must produce correct output.
    FAILS if any sandhi case produces wrong output.
    """
    cases = load_cases("tests/fixtures/panini_blackbox_cases.json")
    adapter = LocalEngineAdapter()
    results = adapter.batch_run(cases)
    
    failures = [r for r in results if not r.output_match]
    
    if failures:
        details = "\n".join(
            f"  {r.case.case_id} [{r.case.sutra_id}]: "
            f"expected '{r.case.expected_output}', got '{r.actual_output}'"
            for r in failures
        )
        raise AssertionError(
            f"SANDHI EXECUTION FAILURES: {len(failures)} of {len(results)} cases failed.\n"
            f"{details}"
        )


def test_morphological_execution():
    """
    GATE: All morphological benchmark cases must produce correct output.
    FAILS if any morph case produces wrong output.
    """
    cases = load_cases("tests/fixtures/morphology_blackbox_cases.json")
    adapter = LocalEngineAdapter()
    results = adapter.batch_run(cases)
    
    failures = [r for r in results if not r.output_match]
    
    if failures:
        details = "\n".join(
            f"  {r.case.case_id} [{r.case.sutra_id}] ({r.case.domain}): "
            f"expected '{r.case.expected_output}', got '{r.actual_output}'"
            for r in failures
        )
        raise AssertionError(
            f"MORPHOLOGICAL EXECUTION FAILURES: {len(failures)} of {len(results)} cases failed.\n"
            f"{details}"
        )


def test_no_hardcoding():
    """
    GATE: No benchmark case should show hardcoding suspicion.
    FAILS if any case passes output but lacks derivation evidence.
    """
    cases = load_cases("tests/fixtures/panini_blackbox_cases.json")
    adapter = LocalEngineAdapter()
    results = adapter.batch_run(cases)
    
    suspicions = [r for r in results if r.hardcoding_suspected]
    
    if suspicions:
        details = "\n".join(
            f"  {r.case.case_id} [{r.case.sutra_id}]: "
            f"output matched but rule {r.case.sutra_id} not in applied rules"
            for r in suspicions
        )
        raise AssertionError(
            f"HARDCODING SUSPICIONS: {len(suspicions)} cases flagged.\n"
            f"{details}"
        )


def test_dynamic_execution_gate():
    """
    GATE: All benchmarked sutras must be dynamically executed.
    FAILS if any benchmarked sutra is not in the executed classification.
    """
    payload = run_pipeline(
        case_paths=(
            "tests/fixtures/panini_blackbox_cases.json",
            "tests/fixtures/morphology_blackbox_cases.json",
        ),
    )
    
    summary = payload["summary"]
    
    if summary["benchmarked_sutras"] != summary["dynamically_executed_sutras"]:
        raise AssertionError(
            f"DYNAMIC EXECUTION GAP: {summary['benchmarked_sutras']} benchmarked, "
            f"but only {summary['dynamically_executed_sutras']} dynamically executed.\n"
            f"Classification: {summary['counts_by_classification']}"
        )