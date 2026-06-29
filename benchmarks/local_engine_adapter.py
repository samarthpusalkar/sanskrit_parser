from __future__ import annotations

import os
from typing import List, Sequence, Set

from morphology.sandhi import SandhiEngine
from paninian_engine.rule_loader import load_sandhi_rules
from rules.engine import UniversalRuleEngine

from .adapters import BenchmarkAdapter
from .models import AdapterCapabilities, BenchmarkCase, BenchmarkEvidence, BenchmarkResult

DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "data",
    "sanskrit_master.db",
)


class LocalEngineAdapter(BenchmarkAdapter):
    name = "local_engine"

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self.engine = UniversalRuleEngine.get_instance()

    def supported_domains(self) -> Sequence[str]:
        return ("sandhi",)

    def capabilities(self) -> AdapterCapabilities:
        return AdapterCapabilities(
            supports_inventory=True,
            supports_derivation_evidence=True,
            supported_domains=self.supported_domains(),
        )

    def list_loaded_rules(self) -> List[str]:
        compiled = {
            getattr(rule, "sutra_id", "")
            for rule in self.engine._rules
            if getattr(rule, "sutra_id", None)
        }
        loader = {rule.sutra_id for rule in load_sandhi_rules(self.db_path)}
        return sorted(compiled | loader)

    def run_case(self, case: BenchmarkCase) -> BenchmarkResult:
        left = case.inputs["left"]
        right = case.inputs["right"]

        if case.domain not in self.supported_domains():
            return BenchmarkResult(
                case=case,
                adapter_name=self.name,
                actual_output="",
                output_match=False,
                rule_expectation_match=False,
                hardcoding_suspected=False,
                errors=[f"Unsupported domain: {case.domain}"],
            )

        if case.interface not in {"sandhi_join", "dispatch_forward"}:
            return BenchmarkResult(
                case=case,
                adapter_name=self.name,
                actual_output="",
                output_match=False,
                rule_expectation_match=False,
                hardcoding_suspected=False,
                errors=[f"Unsupported interface: {case.interface}"],
            )

        metadata = SandhiEngine.join_with_metadata(left, right)
        actual_output = metadata["joined"]
        loaded_rule_ids = self.list_loaded_rules()
        applied_rule_ids = list(metadata.get("applied_rule_ids", []))

        expected_output = case.expected_output
        output_match = expected_output is None or actual_output == expected_output

        expected_presence = (
            case.expected_rule_presence
            if case.expected_rule_presence is not None
            else case.case_kind != "negative_control"
        )
        actual_presence = case.sutra_id in applied_rule_ids
        rule_expectation_match = actual_presence == expected_presence

        hardcoding_suspected = False
        if output_match and expected_presence and case.sutra_id not in loaded_rule_ids:
            hardcoding_suspected = True
        if output_match and expected_presence and case.sutra_id not in applied_rule_ids:
            hardcoding_suspected = True

        evidence = BenchmarkEvidence(
            loaded_rule_ids=loaded_rule_ids,
            applied_rule_ids=applied_rule_ids,
            trace_steps=list(metadata.get("trace", {}).get("steps", [])),
        )

        errors: List[str] = []
        if not output_match:
            errors.append(
                f"Output mismatch for {case.case_id}: expected {expected_output!r}, got {actual_output!r}"
            )
        if not rule_expectation_match:
            expectation = "present" if expected_presence else "absent"
            errors.append(
                f"Rule expectation mismatch for {case.case_id}: {case.sutra_id} should be {expectation}"
            )
        if hardcoding_suspected:
            errors.append(
                f"Hardcoding suspected for {case.case_id}: output matched without dynamic rule evidence"
            )

        return BenchmarkResult(
            case=case,
            adapter_name=self.name,
            actual_output=actual_output,
            output_match=output_match,
            rule_expectation_match=rule_expectation_match,
            hardcoding_suspected=hardcoding_suspected,
            evidence=evidence,
            errors=errors,
        )
