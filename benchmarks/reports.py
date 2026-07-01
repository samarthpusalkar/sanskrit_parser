from __future__ import annotations

import json
from typing import Dict, Iterable, List, Mapping

from .models import BenchmarkResult, CoverageSummary, RuleUniverseEntry


def build_coverage_summary(
    entries: Mapping[str, RuleUniverseEntry],
    hardcoding_case_count: int,
) -> CoverageSummary:
    counts_by_classification: Dict[str, int] = {}
    for entry in entries.values():
        counts_by_classification[entry.classification] = (
            counts_by_classification.get(entry.classification, 0) + 1
        )

    return CoverageSummary(
        total_sutras=len(entries),
        sutras_with_rule_configs=sum(1 for entry in entries.values() if entry.has_rule_config),
        runtime_loaded_sutras=sum(1 for entry in entries.values() if entry.loaded_by_runtime),
        benchmarked_sutras=sum(1 for entry in entries.values() if entry.case_count > 0),
        dynamically_executed_sutras=sum(1 for entry in entries.values() if entry.executed_dynamically),
        hardcoding_suspicions=hardcoding_case_count,
        meta_rule_unverified_sutras=sum(1 for entry in entries.values() if entry.meta_rule_unverified),
        counts_by_classification=counts_by_classification,
    )


def benchmark_results_payload(results: Iterable[BenchmarkResult]) -> List[dict]:
    payload = []
    for result in results:
        payload.append(
            {
                "case_id": result.case.case_id,
                "sutra_id": result.case.sutra_id,
                "family_id": result.case.family_id,
                "case_kind": result.case.case_kind,
                "adapter_name": result.adapter_name,
                "actual_output": result.actual_output,
                "expected_output": result.case.expected_output,
                "output_match": result.output_match,
                "rule_expectation_match": result.rule_expectation_match,
                "hardcoding_suspected": result.hardcoding_suspected,
                "applied_rule_ids": result.evidence.applied_rule_ids,
                "trace_steps": result.evidence.trace_steps,
                "errors": result.errors,
            }
        )
    return payload


def universe_payload(entries: Mapping[str, RuleUniverseEntry]) -> Dict[str, dict]:
    return {
        sutra_id: {
            "has_rule_config": entry.has_rule_config,
            "rule_config_count": entry.rule_config_count,
            "case_count": entry.case_count,
            "loaded_by_runtime": entry.loaded_by_runtime,
            "executed_dynamically": entry.executed_dynamically,
            "adapter_supported": entry.adapter_supported,
            "hardcoding_suspected": entry.hardcoding_suspected,
            "meta_rule_unverified": entry.meta_rule_unverified,
            "classification": entry.classification,
        }
        for sutra_id, entry in entries.items()
    }


def write_json(path: str, payload: object) -> None:
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)


def build_summary_markdown(summary: CoverageSummary, results: Iterable[BenchmarkResult]) -> str:
    lines = [
        "# Paninian Benchmark Summary",
        "",
        f"- Total canonical sutras: {summary.total_sutras}",
        f"- Sutras with rule_configs: {summary.sutras_with_rule_configs}",
        f"- Runtime-loaded sutras: {summary.runtime_loaded_sutras}",
        f"- Benchmarked sutras: {summary.benchmarked_sutras}",
        f"- Dynamically executed sutras: {summary.dynamically_executed_sutras}",
        f"- Trace-verified sutras: {summary.dynamically_executed_sutras - summary.meta_rule_unverified_sutras}",
        f"- Meta-rule unverified sutras: {summary.meta_rule_unverified_sutras}",
        f"- Hardcoding suspicions: {summary.hardcoding_suspicions}",
        "",
        "## Classification Counts",
    ]
    for key in sorted(summary.counts_by_classification):
        lines.append(f"- {key}: {summary.counts_by_classification[key]}")

    lines.extend(["", "## Case Results"])
    for result in results:
        status = "PASS" if result.passed else "FAIL"
        lines.append(
            f"- {status} {result.case.case_id} [{result.case.sutra_id}] -> {result.actual_output}"
        )
    return "\n".join(lines) + "\n"
