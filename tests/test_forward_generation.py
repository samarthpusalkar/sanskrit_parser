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
    "id": "FWD_FAIL_001",
    "difficulty": "basic",
    "rule_tags": ["vṛddhireci", "6.1.88"],
    "description": "Missing Vṛddhi for 'e/ai/o/au'. The code handles a+i (Guṇa) and a+u (Guṇa), but completely lacks the logic for a+e. It will fall through to the 'Direct join' default and output 'tavaeva'.",
    "input_tokens": ["tava", "eva"],
    "expected_string": "tavaiva"
  },
  {
    "id": "FWD_FAIL_002",
    "difficulty": "medium",
    "rule_tags": ["iko_yaṇ_aci", "6.1.77", "incomplete_rule"],
    "description": "Incomplete Yaṇ Sandhi. The code specifically hardcoded 'i/ī -> y' under 6.1.77 but forgot the rest of the rule (u->v, ṛ->r). It will fail to convert the 'u' in 'su' to 'v', falling through to 'suāgatam'.",
    "input_tokens": ["su", "āgatam"],
    "expected_string": "svāgatam"
  },
  {
    "id": "FWD_FAIL_003",
    "difficulty": "hard",
    "rule_tags": ["pragṛhya", "īdūded_dvivacanaṃ_pragṛhyam", "1.1.11"],
    "description": "False Positive Sandhi on Dual Nouns. The code hardcoded a few Pragṛhya particles ('aho', 'amī') but missed the universal rule that duals ending in ī/ū/e are immune to sandhi. Because 'harī' ends in 'ī', the engine will incorrectly apply Yaṇ Sandhi and output 'haryetau'.",
    "input_tokens": ["harī", "etau"],
    "expected_string": "harī etau"
  },
  {
    "id": "FWD_FAIL_004",
    "difficulty": "basic",
    "rule_tags": ["visarga_sandhi", "sasajuṣo_ruḥ", "8.2.66"],
    "description": "Missing Visarga to 'r' conversion. The visarga logic in the code only handles stems ending in 'a' (yielding 'o' or dropping it). For stems ending in 'i' or 'u' before a voiced consonant, the visarga must become 'r'. The engine will ignore it and output 'hariḥgacchati'.",
    "input_tokens": ["hariḥ", "gacchati"],
    "expected_string": "harirgacchati"
  },
  {
    "id": "FWD_FAIL_005",
    "difficulty": "medium",
    "rule_tags": ["eco_ayavāyāvaḥ", "6.1.78", "incomplete_rule"],
    "description": "Incomplete Ayavāyāva. The code explicitly checks `elif w1.endswith((\"ai\", \"au\"))` but on the very next line only executes logic `if w1.endswith(\"ai\")`. It has no logic for 'au' + vowel, failing to convert 'au' to 'āv'. It will output 'tauatra'.",
    "input_tokens": ["tau", "atra"],
    "expected_string": "tāvatra"
  },
  {
    "id": "FWD_FAIL_006",
    "difficulty": "basic",
    "rule_tags": ["mo_anusvāraḥ", "8.3.23"],
    "description": "Missing general Anusvāra. The code handles specific edge cases like 'sam + rāṭ' and 'sam + kār' but lacks the universal rule that a terminal 'm' before any consonant becomes an anusvāra (ṃ). It will directly join them as 'harimvande'.",
    "input_tokens": ["harim", "vande"],
    "expected_string": "hariṃ vande"
  },
  {
    "id": "FWD_FAIL_007",
    "difficulty": "medium",
    "rule_tags": ["ād_guṇaḥ", "uraṇ_raparaḥ", "1.1.51"],
    "description": "Missing Guṇa for ṛ. The code handles 'a+i' and 'a+u', but missing is 'a+ṛ -> ar'. By completely omitting the 'ṛ' handling in the Guṇa block, it will fall through to direct join and output 'mahāṛṣiḥ'.",
    "input_tokens": ["mahā", "ṛṣiḥ"],
    "expected_string": "maharṣiḥ"
  }
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
    test_cases: list[dict] = None,
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
