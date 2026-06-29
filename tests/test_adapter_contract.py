import json
import os

import pytest

from benchmarks.adapters import BenchmarkAdapter
from benchmarks.cases import load_cases
from benchmarks.models import AdapterCapabilities, BenchmarkEvidence, BenchmarkResult


FIXTURE_PATH = os.path.join(
    os.path.dirname(__file__),
    "fixtures",
    "external_adapter_contract_cases.json",
)


class DummyExternalAdapter(BenchmarkAdapter):
    name = "dummy_external"

    def supported_domains(self):
        return ("sandhi",)

    def capabilities(self):
        return AdapterCapabilities(
            supports_inventory=False,
            supports_derivation_evidence=False,
            supported_domains=self.supported_domains(),
        )

    def list_loaded_rules(self):
        return []

    def run_case(self, case):
        return BenchmarkResult(
            case=case,
            adapter_name=self.name,
            actual_output=case.expected_output or "",
            output_match=True,
            rule_expectation_match=True,
            hardcoding_suspected=False,
            evidence=BenchmarkEvidence(),
        )


@pytest.mark.adapter
def test_adapter_contract_fixture_is_valid():
    cases = load_cases(FIXTURE_PATH)
    assert len(cases) == 1
    assert cases[0].domain == "sandhi"


@pytest.mark.adapter
def test_adapter_batch_run_returns_benchmark_results():
    adapter = DummyExternalAdapter()
    results = adapter.batch_run(load_cases(FIXTURE_PATH))
    assert len(results) == 1
    assert results[0].passed
    assert results[0].adapter_name == "dummy_external"
