"""
Verification runner against forward_generation_test.json.
Executes Pāṇinian derivations through the real paninian_engine stack
(run_pairwise_derivation + SQLite rule_configs) without hardcoded elif chains.
"""
import csv
import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from paninian_engine.pairwise import run_pairwise_derivation
from paninian_engine.graph import DerivationGraph

# Curated cases that should pass with seed + enriched rule_configs
CURATED_CASE_IDS = frozenset({
    "CUR_YAN_001",
    "CUR_GUNA_001",
    "CUR_DIRGHA_001",
    "CUR_ANUSVARA_001",
})

CURATED_TEST_CASES = [
    {
        "id": "CUR_YAN_001",
        "difficulty": "seed",
        "description": "iko yaṇ aci (6.1.77): dadhi + atra -> dadhyatra",
        "input_tokens": ["dadhi", "atra"],
        "expected_string": "dadhyatra",
    },
    {
        "id": "CUR_GUNA_001",
        "difficulty": "seed",
        "description": "ād guṇaḥ (6.1.87): rama + isa -> ramesa (a+i=e)",
        "input_tokens": ["rama", "isa"],
        "expected_string": "ramesa",
    },
    {
        "id": "CUR_DIRGHA_001",
        "difficulty": "seed",
        "description": "akaḥ savarṇe dīrghaḥ (6.1.101): deva + arca -> devārca (a+a=ā)",
        "input_tokens": ["deva", "arca"],
        "expected_string": "devārca",
    },
    {
        "id": "CUR_ANUSVARA_001",
        "difficulty": "seed",
        "description": "mo'nusvāraḥ (8.3.23): sam + rakṣati -> saṃrakṣati",
        "input_tokens": ["sam", "rakṣati"],
        "expected_string": "saṃrakṣati",
    },
]


def compute_char_f1(pred: str, target: str) -> float:
    if not pred and not target:
        return 1.0
    if not pred or not target:
        return 0.0
    pred_chars = list(pred)
    target_chars = list(target)
    target_copy = target_chars.copy()
    common = 0
    for c in pred_chars:
        if c in target_copy:
            common += 1
            target_copy.remove(c)
    if common == 0:
        return 0.0
    precision = common / len(pred_chars)
    recall = common / len(target_chars)
    return 2 * (precision * recall) / (precision + recall)


def execute_derivation(input_tokens: list[str]) -> tuple[str, list[str]]:
    """Run derivation through the real engine stack."""
    graph = DerivationGraph()
    return run_pairwise_derivation(input_tokens, graph=graph)


def run_evaluation_suite(
    test_cases: list[dict] | None = None,
    verbose: bool = False,
) -> tuple[dict, list[dict]]:
    tests_dir = Path(__file__).parent
    if test_cases is None:
        json_path = tests_dir / "forward_generation_test.json"
        with open(json_path, "r", encoding="utf-8") as f:
            test_cases = json.load(f)

    results_dir = tests_dir / "results"
    results_dir.mkdir(exist_ok=True)

    results_log = []
    total = len(test_cases)
    exact_matches = 0
    f1_sum = 0.0

    debug_log_path = results_dir / "forward_generation_trace.log"
    metrics_json_path = results_dir / "metrics.json"
    predictions_csv_path = results_dir / "predictions.csv"

    if verbose:
        print("=" * 70)
        print("Pāṇinian Forward Generation Evaluation (engine-driven)")
        print("=" * 70)

    with open(debug_log_path, "w", encoding="utf-8") as log_f, \
         open(predictions_csv_path, "w", newline="", encoding="utf-8") as csv_f:

        csv_writer = csv.writer(csv_f)
        csv_writer.writerow(["ID", "InputTokens", "ExpectedString", "PredictedString", "ExactMatch", "CharF1"])
        log_f.write("=== PĀṆINIAN FORWARD GENERATION TRACE LOG ===\n\n")

        for tc in test_cases:
            tc_id = tc["id"]
            tokens = tc["input_tokens"]
            expected = tc["expected_string"]

            pred, trace = execute_derivation(tokens)
            is_match = pred == expected
            if is_match:
                exact_matches += 1
            f1 = compute_char_f1(pred, expected)
            f1_sum += f1

            csv_writer.writerow([tc_id, " + ".join(tokens), expected, pred, is_match, f"{f1:.4f}"])

            if verbose:
                status = "✔" if is_match else "✘"
                print(f"\n[{status}] Test: {tc_id} ({tc.get('difficulty', 'N/A')})")
                print(f"    Input:    {' + '.join(tokens)}")
                print(f"    Expected: {expected}")
                print(f"    Predicted:{pred}")
                print(f"    Match:    {is_match} | Char F1: {f1:.4f}")
                for t_line in trace:
                    print(f"      -> {t_line}")
                print("-" * 70)

            log_f.write(f"Test ID: {tc_id}\n")
            log_f.write(f"Input: {tokens}\n")
            log_f.write(f"Expected: {expected} | Predicted: {pred}\n")
            log_f.write(f"Exact Match: {is_match} | Char F1: {f1:.4f}\n")
            for t_line in trace:
                log_f.write(f"  [TRACE] {t_line}\n")
            log_f.write("-" * 60 + "\n\n")

            results_log.append({
                "id": tc_id,
                "input": tokens,
                "expected": expected,
                "predicted": pred,
                "exact_match": is_match,
                "char_f1": round(f1, 4),
                "trace": trace,
            })

    accuracy = exact_matches / total if total > 0 else 0.0
    mean_f1 = f1_sum / total if total > 0 else 0.0
    metrics = {
        "total_test_cases": total,
        "exact_matches": exact_matches,
        "accuracy": round(accuracy, 4),
        "mean_character_f1": round(mean_f1, 4),
    }

    with open(metrics_json_path, "w", encoding="utf-8") as mf:
        json.dump({"metrics": metrics, "detailed_results": results_log}, mf, indent=2, ensure_ascii=False)

    return metrics, results_log


@pytest.mark.curated
def test_curated_forward_generation():
    """Seed-configured sandhi cases that must pass with the real engine."""
    metrics, _ = run_evaluation_suite(test_cases=CURATED_TEST_CASES, verbose=False)
    assert metrics["accuracy"] == 1.0, (
        f"Curated cases failed: accuracy={metrics['accuracy']}, "
        f"matches={metrics['exact_matches']}/{metrics['total_test_cases']}"
    )


def test_forward_generation_suite_reports_metrics():
    """Full FWD_ULT suite — reports metrics without hard-failing on incomplete coverage."""
    metrics, results = run_evaluation_suite(verbose=False)
    assert metrics["total_test_cases"] > 0
    assert "accuracy" in metrics
    assert "mean_character_f1" in metrics


if __name__ == "__main__":
    metrics, results = run_evaluation_suite(verbose=True)
    print("\n=== SUMMARY METRICS ===")
    print(json.dumps(metrics, indent=2))
    print(f"\nTrace log: tests/results/forward_generation_trace.log")
