from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence


@dataclass
class AdapterCapabilities:
    supports_inventory: bool = False
    supports_derivation_evidence: bool = False
    supported_domains: Sequence[str] = field(default_factory=tuple)


@dataclass
class RuleUniverseEntry:
    sutra_id: str
    has_rule_config: bool = False
    rule_config_count: int = 0
    case_count: int = 0
    loaded_by_runtime: bool = False
    executed_dynamically: bool = False
    adapter_supported: bool = False
    hardcoding_suspected: bool = False
    classification: str = "adapter_pending"


@dataclass
class BenchmarkCase:
    case_id: str
    sutra_id: str
    domain: str
    interface: str
    inputs: Dict[str, str]
    expected_output: Optional[str]
    case_kind: str
    family_id: str
    expected_rule_presence: Optional[bool] = None
    notes: str = ""
    source: str = ""
    tags: List[str] = field(default_factory=list)


@dataclass
class BenchmarkEvidence:
    loaded_rule_ids: List[str] = field(default_factory=list)
    applied_rule_ids: List[str] = field(default_factory=list)
    trace_steps: List[Dict[str, Any]] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)


@dataclass
class BenchmarkResult:
    case: BenchmarkCase
    adapter_name: str
    actual_output: str
    output_match: bool
    rule_expectation_match: bool
    hardcoding_suspected: bool
    evidence: BenchmarkEvidence = field(default_factory=BenchmarkEvidence)
    errors: List[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return (
            self.output_match
            and self.rule_expectation_match
            and not self.hardcoding_suspected
            and not self.errors
        )


@dataclass
class CoverageSummary:
    total_sutras: int
    sutras_with_rule_configs: int
    runtime_loaded_sutras: int
    benchmarked_sutras: int
    dynamically_executed_sutras: int
    hardcoding_suspicions: int
    counts_by_classification: Dict[str, int]
