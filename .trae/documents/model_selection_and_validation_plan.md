# Plan — Model Selection per Sūtra Category + Data Sanity Validation

**Date:** 2026-07-07  
**Scope:** Improve the comprehensive Pāṇinian extractor so it can use different LLM models for definitional vs operational sūtras, ground sūtra-category classification in the local `ashtadhyayi-data` `sutras` table, and verify extraction sanity across all chapters with golden-truth tests.

## User decisions locked
1. Keep a single default model, but add optional `--definition-model` and `--operational-model` flags.
2. Use the local `sutras` table from `ashtadhyayi-data` as the source of truth for whether a sūtra is definitional/operational.
3. Verify the local `sutras` table against the upstream `ashtadhyayi-data` repository (checksum/diff).
4. Validation strategy is a custom combination: schema validation + resolvable pratyāhāras + per-chapter engine integrability + golden-truth case tests.
5. Add curated golden-truth test cases for known Pāṇinian derivations.

---

## 1. Current state analysis

### What already exists
- `tools/batch_panini_extractor.py` extracts into `panini_rules` + child tables.
- `_is_definitional()` uses `sutra_type` prefixes `S$`, `P$`, `AD$`, `AT$` from the `sutras` table.
- `ExtractorDB` loads sūtras and prerequisites from `data/sanskrit_master.db`.
- `tests/test_panini_rules_engine_integrability.py` proves a sample of chapter 3 rules compile and match.
- `core/shiva_sutras.py` resolves pratyāhāras and rejects non-canonical names.

### What is missing / broken
- Only one `--model` flag exists; the same model is used for definitions and operations.
- There is no verification that the local `sutras` table matches upstream `ashtadhyayi-data`.
- The 1.x definitional extraction failures with `qwen3-coder-next:cloud` show the current model is not ideal for saṃjñā/paribhāṣā definitions.
- No automated per-chapter sanity check runs after extraction; correctness is only verified for chapter 3.
- No golden-truth test cases exist for known derivations outside chapter 3.

---

## 2. Proposed changes

### 2.1 Per-mode model flags
**File:** `tools/batch_panini_extractor.py`

Add two new CLI arguments:
- `--definition-model` — model used for batched definitional sūtras (`S$`, `P$`, `AD$`, `AT$`).
- `--operational-model` — model used for operational sūtras (`V$$`, etc.).

Both default to the value of `--model` if not provided, preserving backward compatibility.

Update `extract_definitions_for_pada` and `extract_operational_group` signatures to accept a `model` parameter, and pass the appropriate model from `main()`.

### 2.2 Sūtra category source of truth
**File:** `tools/batch_panini_extractor.py`

Keep using the existing `_is_definitional()` helper which reads `sutra_type` from the `sutras` table. Document in the script docstring that this is the authoritative classification.

No change to the classification logic.

### 2.3 Verify local `sutras` table against upstream ashtadhyayi-data
**New file:** `tools/verify_ashtadhyayi_data.py`

This script will:
1. Compare the local `sutras` table rows (id, sutra_dev, pada_cheda, sutra_type) against the upstream `ashtadhyayi-data` repository files.
2. The upstream repository is expected at `data/ashtadhyayi-data` (already present).
3. Compute a SHA-256 hash per sūtra id over `(sutra_dev, pada_cheda, sutra_type)`.
4. Report any mismatches or missing rows.
5. Optionally update the local DB if the upstream source is newer.

Usage:
```bash
python3 tools/verify_ashtadhyayi_data.py --check
python3 tools/verify_ashtadhyayi_data.py --fix
```

The `sutras` table schema and upstream data layout must be inspected during implementation to choose the right comparison columns.

### 2.4 Post-extraction validation pipeline
**New file:** `tools/validate_panini_rules.py`

This script reads all rows in `panini_rules` and checks:
1. **Schema validity:** every required field type is correct (non-null sutra_id, valid rule_type, valid operation_type).
2. **Pratyāhāra resolution:** every `pratyahara` value in `panini_rule_contexts` resolves via `PratyaharaResolver`.
3. **Compilability:** every rule can be loaded by `PaniniRuleParser` and compiled into a `CompiledSutra` without exception.
4. **Executability ratio:** for each chapter, report `% executable` and flag chapters with too few executable rules.
5. **Hurdle summary:** list all `research/hurdles/*.json` files and group by error type.

Output a JSON report:
```json
{
  "total_rules": 1209,
  "schema_invalid": [],
  "unresolvable_pratyaharas": [],
  "uncompilable_rules": [],
  "per_chapter": {"3.1": {"total": 150, "executable": 138}},
  "hurdles_by_type": {"unresolvable pratyahara": 5}
}
```

### 2.5 Golden-truth test fixtures
**New file:** `tests/fixtures/panini_golden_truth.json`

Curated cases covering multiple chapters:
- Sandhi: `rAma + atra → rAmAtra` [6.1.101]
- Vikaraṇa: `bhU + ti → Bavati` (via śap) [3.1.68]
- Kṛt: `pA + ka → pAka` [3.2.3]
- Definition: `vfdDi` applies to `A, E, O` [1.1.1]
- Each case includes `left`, `right`, `expected_output`, `expected_trace`.

**New file:** `tests/test_panini_golden_truth.py`

Loads golden-truth cases, runs them through the engine, and asserts:
- Final output matches expected.
- Trace matches expected rule sequence (when known).
- Only rules with `evaluability != manual` are required to fire; manual rules are skipped with a warning.

### 2.6 Chapter-level integrability tests
**File:** `tests/test_panini_rules_engine_integrability.py`

Extend existing tests to cover all extracted chapters dynamically:
- For each chapter present in `panini_rules`, verify all rules load.
- Verify executable count is above a chapter-specific threshold.
- This acts as a regression test after each extraction run.

---

## 3. Assumptions & decisions

1. **Model selection is at category level, not per-sūtra.** We use `definition-model` for all `S$/P$/AD$/AT$` sūtras and `operational-model` for the rest. This is simpler than per-sūtra model assignment and matches the user's request.
2. **`sutras` table is authoritative.** The `sutra_type` column from `ashtadhyayi-data` is the ground truth for category classification.
3. **Upstream data is trusted.** `verify_ashtadhyayi_data.py` treats `data/ashtadhyayi-data` as the reference and reports/fixes local drift.
4. **Golden truth is curated, not exhaustive.** We add a representative set of cases, not all 3,983 sūtras. The community/user can expand the fixture.
5. **Validation is post-hoc.** It runs after extraction, not during, to avoid slowing down the LLM calls.
6. **No runtime LLM.** Validation uses only the extracted data and the deterministic engine.

---

## 4. Verification steps

1. Add flags and run extraction with different models:
   ```bash
   python3 tools/batch_panini_extractor.py --chapter-prefix 1.1 --mode both \
       --definition-model qwen3-coder-next:cloud \
       --operational-model deepseek-v4-pro:cloud \
       --delay 0.5
   ```
2. Verify local data matches upstream:
   ```bash
   python3 tools/verify_ashtadhyayi_data.py --check
   ```
3. Validate all extracted rules:
   ```bash
   python3 tools/validate_panini_rules.py
   ```
4. Run golden-truth tests:
   ```bash
   python3 -m pytest tests/test_panini_golden_truth.py -v
   ```
5. Run full targeted test suite:
   ```bash
   python3 -m pytest tests/test_dsl_unit.py tests/test_meta_engine.py tests/test_sanjna_tagger.py tests/test_execution_context.py tests/test_comprehensive_schema.py tests/test_panini_rule_parser.py tests/test_panini_rules_engine_integrability.py tests/test_panini_golden_truth.py tests/test_benchmark_integrity.py::test_sandhi_execution tests/test_benchmark_integrity.py::test_no_hardcoding -q
   ```

---

## 5. Out of scope

- Rewriting the morphological derivation engine (MorphExecutor remains future work).
- Adding a web UI or API for extraction.
- Training or fine-tuning any model.
- Real-time validation during LLM extraction (would add latency and cost).
