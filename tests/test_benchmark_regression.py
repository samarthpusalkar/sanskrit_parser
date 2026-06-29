import os

import pytest

from benchmarks.pipeline import compare_with_baseline, run_pipeline


BASELINE_PATH = os.path.join(
    os.path.dirname(__file__),
    "fixtures",
    "panini_baseline.json",
)


@pytest.mark.regression
def test_pipeline_matches_frozen_baseline():
    payload = run_pipeline()
    diffs = compare_with_baseline(payload, BASELINE_PATH)
    assert diffs == []
