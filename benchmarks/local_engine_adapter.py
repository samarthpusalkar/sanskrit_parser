from __future__ import annotations

import os
from typing import List, Dict, Any, Optional, Sequence
from dataclasses import field

from .adapters import BenchmarkAdapter
from .models import (
    BenchmarkCase, BenchmarkResult, BenchmarkEvidence, 
    AdapterCapabilities, RuleUniverseEntry
)

from rules.engine import UniversalRuleEngine
from morphology.sandhi import SandhiEngine
from morphology.subanta import SubantaGenerator
from morphology.tinanta import TinantaGenerator
from core.phonology import iast_to_slp1, slp1_to_iast

class LocalEngineAdapter(BenchmarkAdapter):
    """
    Adapter for the internal Pāṇinian engine.
    Bridges the benchmark suite to sandhi, verbal, and nominal interfaces.
    """
    name: str = "local_engine"

    def supported_domains(self) -> Sequence[str]:
        return ("sandhi", "tinganta", "subanta", "derivation")

    def capabilities(self) -> AdapterCapabilities:
        return AdapterCapabilities(
            supports_inventory=True,
            supports_derivation_evidence=True
        )

    def list_loaded_rules(self) -> List[str]:
        """Returns all rules currently compiled in the UniversalRuleEngine."""
        engine = UniversalRuleEngine.get_instance()
        return [r.sutra_id for r in engine._rules if hasattr(r, 'sutra_id')]

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
        # Sandhi inputs: {'left': '...', 'right': '...'}
        left = case.inputs.get("left", "")
        right = case.inputs.get("right", "")
        
        engine = UniversalRuleEngine.get_instance()
        # We use the metadata-enriched path to get rule evidence
        meta = engine.dispatch_forward_with_metadata(left, right)
        
        actual = meta["joined"]
        evidence = BenchmarkEvidence(
            applied_rule_ids=meta["applied_rule_ids"],
            trace_steps=meta["trace"].get("steps", [])
        )
        
        return self._create_result(case, actual, evidence)

    def _run_tinganta_case(self, case: BenchmarkCase) -> BenchmarkResult:
        # Verb inputs: {'root': '...', 'gana': 1, 'lakara': '...', 'purusa': 3, 'vacana': 1}
        root = case.inputs.get("root", "")
        gana = case.inputs.get("gana", 1)
        lakara = case.inputs.get("lakara", "laṭ")
        purusa = case.inputs.get("purusa", 3)
        vacana = case.inputs.get("vacana", 1)
        
        actual = TinantaGenerator.conjugate(root, gana, lakara, purusa, vacana)
        evidence = BenchmarkEvidence() 
        
        return self._create_result(case, actual, evidence)

    def _run_subanta_case(self, case: BenchmarkCase) -> BenchmarkResult:
        # Noun inputs: {'stem': '...', 'case': '...', 'number': '...'}
        stem = case.inputs.get("stem", "")
        case_type = case.inputs.get("case", "nominative")
        number = case.inputs.get("number", "singular")
        
        actual = SubantaGenerator.decline(stem, case_type, number)
        evidence = BenchmarkEvidence()
        
        return self._create_result(case, actual, evidence)

    def _create_result(self, case: BenchmarkCase, actual: str, evidence: BenchmarkEvidence) -> BenchmarkResult:
        # Hardcoding suspected if output matches but expected rule didn't fire
        hardcoding = False
        if case.expected_rule_presence is not None:
            # If a specific rule was expected to fire but didn't, it's a suspicion
            # but only if the output actually matched (which usually implies hardcoding)
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
