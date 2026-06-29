from __future__ import annotations

import json
import os
from typing import Dict, List, Optional, Iterable, Sequence

from .adapters import BenchmarkAdapter
from .cases import DEFAULT_CASES_PATH, load_cases
from .catalog import (
    DB_PATH,
    annotate_rule_universe,
    case_counts_by_sutra,
    find_unknown_case_sutras,
    load_rule_universe,
)
from .local_engine_adapter import LocalEngineAdapter
from .reports import (
    benchmark_results_payload,
    build_coverage_summary,
    build_summary_markdown,
    universe_payload,
    write_json,
)


def run_pipeline(
    *,
    adapter: Optional[BenchmarkAdapter] = None,
    case_paths: Sequence[str] = (DEFAULT_CASES_PATH,), # Support multiple fixture files
    db_path: str = DB_PATH,
    output_dir: Optional[str] = None,
) -> Dict[str, object]:
    benchmark_adapter = adapter or LocalEngineAdapter(db_path=db_path)
    
    # Load and merge all cases from multiple paths
    all_cases = []
    for path in case_paths:
        all_cases.extend(load_cases(path))
        
    universe = load_rule_universe(db_path)

    unknown_sutras = find_unknown_case_sutras(universe, (case.sutra_id for case in all_cases))
    if unknown_sutras:
        raise ValueError(f"Benchmark fixtures reference unknown sutras: {unknown_sutras[:10]}")

    results = benchmark_adapter.batch_run(all_cases)
    loaded_rule_ids = benchmark_adapter.list_loaded_rules()
    
    executed_rule_ids = {
        result.case.sutra_id
        for result in results
        if result.output_match
        and result.rule_expectation_match
        and not result.hardcoding_suspected
        and (result.case.expected_rule_presence is not False)
    }
    hardcoding_suspect_ids = {
        result.case.sutra_id for result in results if result.hardcoding_suspected
    }
    
    entries = annotate_rule_universe(
        universe,
        case_counts=case_counts_by_sutra(case.sutra_id for case in all_cases),
        loaded_rule_ids=loaded_rule_ids,
        executed_rule_ids=executed_rule_ids,
        hardcoding_suspect_ids=hardcoding_suspect_ids,
    )

    summary = build_coverage_summary(
        entries,
        hardcoding_case_count=sum(1 for result in results if result.hardcoding_suspected),
    )
    hardcoding_results = [result for result in results if result.hardcoding_suspected]
    failing_results = [result for result in results if not result.passed]

    payload = {
        "adapter": benchmark_adapter.name,
        "summary": {
            "total_sutras": summary.total_sutras,
            "sutras_with_rule_configs": summary.sutras_with_rule_configs,
            "runtime_loaded_sutras": summary.runtime_loaded_sutras,
            "benchmarked_sutras": summary.benchmarked_sutras,
            "dynamically_executed_sutras": summary.dynamically_executed_sutras,
            "hardcoding_suspicions": summary.hardcoding_suspicions,
            "counts_by_classification": summary.counts_by_classification,
        },
        "results": benchmark_results_payload(results),
        "universe": universe_payload(entries),
        "hardcoding_suspicions": benchmark_results_payload(hardcoding_results),
        "failing_results": benchmark_results_payload(failing_results),
    }

    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        write_json(os.path.join(output_dir, "panini_coverage.json"), payload)
        write_json(
            os.path.join(output_dir, "unmapped_sutras.json"),
            {
                sutra_id: entry.classification
                for sutra_id, entry in entries.items()
                if entry.classification != "executed"
            },
        )
        write_json(
            os.path.join(output_dir, "hardcoding_suspicions.json"),
            benchmark_results_payload(hardcoding_results),
        )
        with open(
            os.path.join(output_dir, "panini_summary.md"),
            "w",
            encoding="utf-8",
        ) as handle:
            handle.write(build_summary_markdown(summary, results))

    return payload


def compare_with_baseline(payload: Dict[str, object], baseline_path: str) -> List[str]:
    with open(baseline_path, "r", encoding="utf-8") as handle:
        baseline = json.load(handle)

    current_summary = payload["summary"]
    baseline_summary = baseline["summary"]
    diffs: List[str] = []

    tracked_metrics = [
        "benchmarked_sutras",
        "dynamically_executed_sutras",
        "hardcoding_suspicions",
    ]
    for key in tracked_metrics:
        if current_summary.get(key) != baseline_summary.get(key):
            diffs.append(
                f"{key}: expected {baseline_summary.get(key)}, got {current_summary.get(key)}"
            )

    if current_summary.get("counts_by_classification") != baseline_summary.get(
        "counts_by_classification"
    ):
        diffs.append("counts_by_classification changed")

    return diffs
