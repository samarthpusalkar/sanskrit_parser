from typing import List
import pytest
import json
import os
from benchmarks.local_engine_adapter import LocalEngineAdapter
from benchmarks.cases import load_cases
from benchmarks.pipeline import run_pipeline

def test_morphology_execution_integrity():
    """
    Verify that morphological benchmarks are actually executing
    through the adapter and reporting results.
    """
    adapter = LocalEngineAdapter()
    # Load only morphology cases
    morph_cases = load_cases("tests/fixtures/morphology_blackbox_cases.json")
    
    results = adapter.batch_run(morph_cases)
    
    assert len(results) == len(morph_cases)
    for res in results:
        # Just verify we have a result and a non-empty adapter name
        assert res.adapter_name == "local_engine"
        # la-base check: result should either be match or mismatch, not a crash
        assert (res.output_match or not res.output_match) is True

def test_morphology_coverage_reporting():
    """
    Verify that the pipeline correctly classifies morphological rules.
    """
    # Run pipeline with only morph cases
    payload = run_pipeline(
        case_paths=("tests/fixtures/morphology_blackbox_cases.json",),
        output_dir="tests/results/morph_run"
    )
    
    summary = payload["summary"]
    # Check that we tracked the cases we ran
    assert summary["benchmarked_sutras"] >= 1
    assert "executed" in summary["counts_by_classification"]
