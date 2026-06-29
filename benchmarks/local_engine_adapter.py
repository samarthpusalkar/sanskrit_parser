from __future__ import annotations

from typing import List, Dict, Any, Optional, Sequence

from .adapters import BenchmarkAdapter
from .models import (
    BenchmarkCase, BenchmarkResult, BenchmarkEvidence, 
    AdapterCapabilities, RuleUniverseEntry
)

from sanskrit_dsl.executor import DSLExecutor
from sanskrit_dsl.morph_executor import MorphExecutor

class LocalEngineAdapter(BenchmarkAdapter):
    """
    Adapter for the internal Pāṇinian engine.
    Routes through the DSL executor for sandhi cases and through the
    MorphExecutor for tinganta/subanta cases so morph derivation produces
    real evidence (applied_rule_ids) instead of a DB-lookup shortcut.
    """
    name: str = "local_engine"

    def __init__(self):
        self._dsl_executor: Optional[DSLExecutor] = None
        self._morph_executor: Optional[MorphExecutor] = None

    def supported_domains(self) -> Sequence[str]:
        return ("sandhi", "tinganta", "subanta", "derivation")

    def capabilities(self) -> AdapterCapabilities:
        return AdapterCapabilities(
            supports_inventory=True,
            supports_derivation_evidence=True
        )

    def _get_executor(self) -> DSLExecutor:
        if self._dsl_executor is None:
            self._dsl_executor = DSLExecutor()
        return self._dsl_executor

    def _get_morph_executor(self) -> MorphExecutor:
        if self._morph_executor is None:
            self._morph_executor = MorphExecutor()
        return self._morph_executor

    def list_loaded_rules(self) -> List[str]:
        """Returns all rules compiled by the DSL compiler."""
        return self._get_executor().list_loaded_rules()

    def run_case(self, case: BenchmarkCase) -> BenchmarkResult:
        """Dispatch case to the correct morphological or sandhi interface."""
        try:
            if case.domain == "sandhi":
                return self._run_sandhi_case(case)
            elif case.domain == "tinganta":
                return self._run_tinganta_case(case)
            elif case.domain == "subanta":
                return self._run_subanta_case(case)
            else:
                return self._fail_case(case, f"Unsupported domain: {case.domain}")
        except Exception as e:
            return self._fail_case(case, str(e))

    def _run_sandhi_case(self, case: BenchmarkCase) -> BenchmarkResult:
        left = case.inputs.get("left", "")
        right = case.inputs.get("right", "")

        executor = self._get_executor()
        result = executor.execute_sandhi(left, right)

        actual = result["joined"]
        evidence = BenchmarkEvidence(
            applied_rule_ids=result["applied_rule_ids"],
            trace_steps=result["trace_steps"]
        )

        return self._create_result(case, actual, evidence)

    def _run_tinganta_case(self, case: BenchmarkCase) -> BenchmarkResult:
        root = case.inputs.get("root", "")
        gana = case.inputs.get("gana", 1)
        lakara = case.inputs.get("lakara", "laṭ")
        purusa = case.inputs.get("purusa", 3)
        vacana = case.inputs.get("vacana", 1)

        morph = self._get_morph_executor()
        result = morph.conjugate(root, gana, lakara, purusa, vacana)
        evidence = BenchmarkEvidence(
            applied_rule_ids=result["applied_rule_ids"],
            trace_steps=result["trace_steps"]
        )

        return self._create_result(case, result["form"], evidence)

    def _run_subanta_case(self, case: BenchmarkCase) -> BenchmarkResult:
        stem = case.inputs.get("stem", "")
        case_type = case.inputs.get("case", "nominative")
        number = case.inputs.get("number", "singular")

        morph = self._get_morph_executor()
        result = morph.decline(stem, case_type, number)
        evidence = BenchmarkEvidence(
            applied_rule_ids=result["applied_rule_ids"],
            trace_steps=result["trace_steps"]
        )

        return self._create_result(case, result["form"], evidence)

    def _create_result(self, case: BenchmarkCase, actual: str, evidence: BenchmarkEvidence) -> BenchmarkResult:
        hardcoding = False
        if case.expected_rule_presence is not None:
            if case.expected_rule_presence and not any(
                r_id == case.sutra_id for r_id in evidence.applied_rule_ids
            ) and actual == case.expected_output:
                hardcoding = True

        return BenchmarkResult(
            case=case,
            adapter_name=self.name,
            actual_output=actual,
            output_match=(actual == case.expected_output),
            rule_expectation_match=True if not case.expected_rule_presence else 
                                   any(r_id == case.sutra_id for r_id in evidence.applied_rule_ids),
            hardcoding_suspected=hardcoding,
            evidence=evidence
        )

    def _fail_case(self, case: BenchmarkCase, error: str) -> BenchmarkResult:
        return BenchmarkResult(
            case=case,
            adapter_name=self.name,
            actual_output="",
            output_match=False,
            rule_expectation_match=False,
            hardcoding_suspected=False,
            errors=[error]
        )