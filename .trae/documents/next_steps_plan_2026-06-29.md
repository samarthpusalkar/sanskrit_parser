# Plan — Next Steps for the Paninian Sanskrit DSL Engine

**Date:** 2026-06-29
**Scope:** All four focus areas selected by the user — (1) LLM extraction for chapter 6.1, (2) fix the coverage-gate plumbing, (3) expand benchmark fixtures, (4) build a DSL morph executor. Plus one discovered bug fix in commentary loading.
**Plan type:** Decision-complete (executor can implement without further choices).

---

## Summary

The engine has a working clean vibhakti parser, a real phonology/pratyahara core, and an honest benchmark suite, but only **1 sūtra (6.1.77)** is verified end-to-end. The benchmark coverage gate *always* reports 3,983/3,983 unmapped because `test_full_sutra_coverage` hardcodes `executed_rule_ids=set()` instead of using the pipeline's real executed set. Meanwhile `compile_all()` reports 89.1% executable (3,547/3,983), so the gate is lying about progress in the opposite direction from the docs.

This plan:
1. Fixes the coverage gate so it reflects real `loaded`/`executed` sets from `run_pipeline`.
2. Runs LLM extraction on chapter 6.1 using `deepseek-v4-pro:cloud` (confirmed available in Ollama), after fixing the commentary-loader bug that silently drops commentary for 1- and 3-digit sutra numbers.
3. Validates 6.1 extractions and flips the 6.1.87 / 6.1.88 / 6.1.101 unit tests from "documents failure" to "asserts correct output".
4. Expands the sandhi + morph blackbox fixtures to gate every working 6.1 sūtra.
5. Builds `sanskrit_dsl/morph_executor.py` so verbal conjugation and nominal declension are derived through the DSL instead of the DB-lookup + `rules.engine.UniversalRuleEngine` path, and wires it into the benchmark adapter.

All changes preserve the project's core principles: no hardcoding, tests are gates, failures are documented as hurdles.

---

## Current State Analysis (from Phase 1 exploration)

### What works
- `sanskrit_dsl/types.py` — real pratyahara matching, guṇa/vṛddhi/dīrgha/bijection computation. `_context_matches` handles pratyahara + exact_text + savarṇa short-vowel fallback.
- `sanskrit_dsl/parser.py` — `SutraParser` with two paths: `_from_llm_row` (primary) and `_from_vibhakti_clean` (fallback). Records hurdles for non-executable sutras.
- `sanskrit_dsl/compiler.py` — `compile_all()` returns 3,547 executable sutras (per `research/feasibility.md`); anuvṛtti operation inheritance works.
- `sanskrit_dsl/executor.py` — `DSLExecutor.execute_sandhi` does a sapāda pass then a tripāḍī pass, single best rule each.
- `sanskrit_dsl/meta_engine.py` — Paribhāṣā registry, Asiddhatva enforcer, Anuvṛtti tracker, Antaranga resolver with specificity scoring.
- 6.1.77 (iko yan aci) works end-to-end: `execute_sandhi("hari","atra")` → `"haryatra"` with `["6.1.77"]` in trace.

### What's broken / incomplete (verified facts)
- **`tests/test_benchmark_integrity.py::test_full_sutra_coverage`** calls `annotate_rule_universe(..., executed_rule_ids=set(), ...)` with a hard-coded empty set. Every sutra is classified `missing_rule_config`/`adapter_pending`/`execution_unmapped` and the test always fails at "3,983 of 3,983 unmapped". This contradicts `run_pipeline` in `benchmarks/pipeline.py`, which already computes `executed_rule_ids` correctly from passing results. The gate is wired wrong, not the pipeline.
- **`tools/llm_sutra_extractor.py::load_commentary`** builds the commentary lookup key with broken zero-padding. It does `numeric_id = sutra_id.replace(".","")`, then only reformats when `len==4`. The JSON keys in `data/ashtadhyayi-data/sutraani/vasu_english.txt` are `{adhyaya}{pada}{sutra zero-padded to 3 digits}` (e.g. `"11001"` for 1.1.1, `"61077"` for 6.1.77). Current code: 1.1.1 → `"111"` (misses); 6.1.77 → `"61077"` (hits, by luck); 6.1.7 → `"617"` (misses, should be `"61007"`); 8.2.66 → `"8266"` len 4 → `"82066"` (hits). So commentary is silently missing for all 1-digit and 3-digit sutra numbers.
- **`llm_extracted_metadata` table is empty** (0 rows). No LLM extraction has ever been run.
- **Morph path bypasses the DSL.** `benchmarks/local_engine_adapter.py` routes `tinganta`→`TinantaGenerator.conjugate` and `subanta`→`SubantaGenerator.decline`, both of which do DB paradigm lookup and fall back to `morphology.sandhi.SandhiEngine`, which in turn imports `rules.engine.UniversalRuleEngine` (the old dispatch path, not `DSLExecutor`). There is no `sanskrit_dsl/morph_executor.py`.
- **Morph fixtures** (`tests/fixtures/morphology_blackbox_cases.json`) have only 2 cases (bhū→bhavati, rāma→rāmaḥ), both tagged `sutra_id: "1.1.1"` which is a sañjñā definition, not a derivational rule — so they can never produce real derivation evidence.

### Environment facts (verified)
- Ollama is running at `localhost:11434`. `deepseek-v4-pro:cloud` IS available (confirmed via `/api/tags`). Other cloud models available: `deepseek-v3.1:671b-cloud`, `qwen3-coder:480b-cloud`, `kimi-k2.6:cloud`, `minimax-m2:cloud`, `glm-5.1:cloud`, `gemma4:31b-cloud`, `qwen3-vl:235b-cloud`.
- User instruction: **only use cloud Ollama pro models.** Default stays `deepseek-v4-pro:cloud`.
- DB `sutras` table has 3,983 rows; `rule_configs` has 4,007 rows; `llm_extracted_metadata` is empty.
- Commentary file `data/ashtadhyayi-data/sutraani/vasu_english.txt` is valid JSON (~4.6 MB), keyed by `{adhyaya}{pada}{sutra 3-digit zero-padded}`.

---

## Proposed Changes

### Step 1 — Fix the coverage-gate plumbing (FIRST, unblocks honest measurement)

**File:** `tests/test_benchmark_integrity.py`
**What:** Replace the hand-rolled, hard-coded-empty `annotate_rule_universe` call in `test_full_sutra_coverage` with the real classification from `run_pipeline`, so the gate reflects actual loaded + executed sets.
**Why:** Today the gate always reports 3,983/3,983 unmapped regardless of engine state. After this fix, the gate fails *only* on the real gap (sutras with cases but no successful execution), which is the honest signal.
**How:**
- In `test_full_sutra_coverage`, call `run_pipeline(case_paths=(...sandhi..., ...morph...))` to get `payload`.
- Derive `entries` from `payload["universe"]` (already classified by `annotate_rule_universe` inside `run_pipeline`).
- Compute `unmapped = [sid for sid, e in entries.items() if e.classification != "executed"]`.
- Keep the assertion: fail with coverage % and a sample of unmapped, but now the numbers are real.
- Do NOT lower the bar — the test still fails while the engine is incomplete; it just stops lying about *how* incomplete.

**File:** `tests/test_benchmark_integrity.py` (same file, `test_dynamic_execution_gate`)
**What:** This test already calls `run_pipeline` correctly — leave its logic intact. After Step 1, both gates use the same source of truth.

**Verification:** `python3 -m pytest tests/test_benchmark_integrity.py -v` — `test_full_sutra_coverage` now reports a real coverage number (small but nonzero once 6.1.77's case is counted as executed).

---

### Step 2 — Fix `load_commentary` zero-padding (enables quality LLM extraction)

**File:** `tools/llm_sutra_extractor.py`
**What:** Fix `load_commentary` so the commentary key is always `{adhyaya}{pada}{sutra zero-padded to 3 digits}`.
**Why:** Currently commentary is silently dropped for 1-digit and 3-digit sutra numbers, which weakens every LLM extraction prompt that hits those sutras.
**How:**
- Replace the `numeric_id` construction with:
  ```python
  parts = sutra_id.split(".")
  if len(parts) == 3:
      adhyaya, pada, sutra_no = parts
      key = f"{adhyaya}{pada}{int(sutra_no):03d}"
  else:
      key = sutra_id.replace(".", "")
  commentary = data.get(key, "")
  ```
- Keep the 500-char truncation and the existing exception swallowing (return `""` on failure).
- No other changes to the extractor's prompt/schema/storage.

**Verification:** `python3 tools/llm_sutra_extractor.py --chapter 6.1 --dry-run` — prompts for 6.1.7, 6.1.77, 6.1.101 now include a "Commentary (Vasu English):" section.

---

### Step 3 — Run LLM extraction on chapter 6.1

**File:** `tools/llm_sutra_extractor.py` (no code change beyond Step 2; this is an execution step)
**What:** Run extraction for all 223 sutras in chapter 6.1 using `deepseek-v4-pro:cloud`, populating `llm_extracted_metadata`.
**Why:** This is the FIRST PRIORITY in `docs/NEXT_STEPS.md`. The clean parser fails 6.1.87/88/101 because it lacks commentary context; LLM extraction provides structured `operation_type`/`target`/`left_context`/`right_context`/`replacement` that `_from_llm_row` consumes directly.
**How (commands, in order):**
```bash
# Sanity check prompts + commentary loading
python3 tools/llm_sutra_extractor.py --chapter 6.1 --dry-run

# Real run (223 sutras). Caches per-sutra; safe to re-run.
python3 tools/llm_sutra_extractor.py --chapter 6.1 --model deepseek-v4-pro:cloud

# Re-run only failures with --force as needed:
python3 tools/llm_sutra_extractor.py --chapter 6.1 --force --model deepseek-v4-pro:cloud
```
**Constraints:**
- Use only cloud pro models per user instruction. Default `deepseek-v4-pro:cloud` is fine.
- The extractor already caches in DB and records hurdles on failure — no change needed.
- Expected runtime: ~223 × (up to 120s timeout each). If a sutra times out, it's recorded as a hurdle and skipped; re-run with `--force` for just those.

**After extraction, validate:**
```bash
python3 tools/chapter_validator.py --chapter 6.1
```
This compiles 6.1 with LLM rows present and prints the executable rate. Record any new hurdles via the validator.

---

### Step 4 — Flip the 6.1.87 / 6.1.88 / 6.1.101 unit tests to assert correct output

**File:** `tests/test_dsl_unit.py`
**What:** Replace the `TestSutrasNeedingLLMExtraction` class (which asserts the clean parser *fails*) with positive assertions that the LLM-extracted specs compile, match, and produce correct output.
**Why:** Once `llm_extracted_metadata` is populated for 6.1.87/88/101, the parser's `_from_llm_row` path produces executable specs. The tests must become real gates.
**How — exact expected behaviour (from fixtures):**
- **6.1.87 (ād guṇaḥ):** `a/A` + `i/u/ṛ/ḷ` → guṇa (`e/o/ar/al`). Test: `compile_sutra("6.1.87")` is executable; `s.matches("rAma","ISa")`; `s.apply("rAma","ISa")` → `("rAm","eSa")`? — verify against `panini_blackbox_cases.json` expected `rAmeSa`. Note: the fixture's expected joined form is `rAmeSa`; the executor returns `joined = new_left+new_right`. Keep the unit test at the `s.apply` level and let the benchmark fixture gate the joined form.
- **6.1.88 (vṛddhir eci):** `a/A` + `e/o` → vṛddhi (`ai/au`). The existing fixture 6.1.89 (`tava+eva→tavEva`) is tagged `vrddhi` but attributed to 6.1.89 in the fixture. **Decision:** keep 6.1.88's unit test asserting it compiles executable and matches a vṛddhi case; correct the sutra attribution in the fixture in Step 5.
- **6.1.101 (akaḥ savarṇe dīrghaḥ):** homogeneous vowel pair → dīrgha. Test: `s.matches("rAma","atra")`; `s.apply("rAma","atra")` produces the dīrgha merge `("rAm","Atra")` so joined = `rAmAtra` matching the fixture.

**If an LLM extraction is wrong** (e.g. 6.1.88 still has `target=None`): do NOT fake the test. Instead record a hurdle via `research/recorder.record_hurdle` and leave that one test asserting the failure with an updated message. Hardcoding the answer is forbidden (project principle).

**Verification:** `python3 -m pytest tests/test_dsl_unit.py -v` — previously-failing LLM-extraction tests now pass; 6.1.77 tests still pass.

---

### Step 5 — Expand the benchmark fixtures

**File:** `tests/fixtures/panini_blackbox_cases.json`
**What:** Add positive + perturbation + negative-control cases for every 6.1 sūtra that produces correct output after Step 3. Keep the existing 10 cases (correct the 6.1.89/6.1.88 attribution if Step 4 surfaced it).
**Why:** Each fixture case is a gate. More gates = tighter evidence that the engine is actually executing rules.
**How:**
- For each working 6.1 sūtra, add at least: 1 positive (canonical pair), 1 perturbation (different lexical pair, same rule), 1 negative control (pair that must NOT trigger the rule, `expected_rule_presence: false`).
- Each case carries `sutra_id`, `domain: "sandhi"`, `interface: "sandhi_join"`, `inputs: {left, right}`, `expected_output`, `expected_rule_presence`, `tags`.
- Use SLP1 for `left`/`right`/`expected_output` (matches existing cases and the executor's SLP1 contract).
- Do not invent outputs — derive each expected output from Paninian grammar (guna/vṛddhi/dīrgha/yan rules).

**File:** `tests/fixtures/morphology_blackbox_cases.json`
**What:** Replace the two placeholder cases (both mis-tagged `sutra_id: "1.1.1"`) with real morph cases whose `sutra_id` references actual derivational sūtras (3.x for tinanta, 4.x + 7.x for subanta), and add 4–6 more cases.
**Why:** The current morph fixtures can never produce derivation evidence because 1.1.1 is a sañjñā definition. They must reference operational sūtras so the gate can check `applied_rule_ids`.
**How:**
- Tinanta cases: `bhū + laṭ → bhavati` (3.3.18 bhāve karmani, 3.4.78 tiṅ, 7.3.84 sārvadhātuke...). Tag with the sūtra that the morph executor (Step 6) will actually apply.
- Subanta cases: `rāma + sup → rāmaḥ` (7.3.103, 8.2.66, 8.3.15). Tag with 8.2.66 (visarjanīya) and 8.3.15 (ṣaṭḥ) where applicable.
- Each case: `domain: "tinganta"`/`"subanta"`, `interface: "conjugate"`/`"decline"`, `inputs` with `root`/`gana`/`lakara`/`purusa`/`vacana` or `stem`/`case`/`number`, `expected_output` in SLP1 (e.g. `bhavati`, `rAmaH`).

**Verification:** `python3 -m pytest tests/test_benchmark_catalog.py -v` (validates fixtures load and classification is exhaustive); `python3 -m pytest tests/test_benchmark_integrity.py -v` (gates fail honestly where the engine doesn't yet produce the output).

---

### Step 6 — Build `sanskrit_dsl/morph_executor.py` and wire it into the adapter

**New file:** `sanskrit_dsl/morph_executor.py`
**What:** A morph executor that derives verbal forms and nominal forms through the DSL compiler/executor instead of the DB-lookup + `rules.engine.UniversalRuleEngine` path.
**Why:** The end goal (paste 4,000 sūtras → engine executes them) requires morph to go through the same compiled-sūtra pipeline as sandhi. The current `TinantaGenerator`/`SubantaGenerator` are DB-lookup shortcuts — fine as a fallback, but they don't produce derivation evidence and don't exercise the DSL.
**How — interface:**
```python
class MorphExecutor:
    def __init__(self): ...
    def conjugate(self, root_slp1: str, gana: int, lakara: str,
                  purusa: int, vacana: int) -> Dict[str, Any]:
        # returns {"form": str, "applied_rule_ids": List[str],
        #          "trace_steps": List[Dict], "source": "dsl"|"db_fallback"}
    def decline(self, stem_slp1: str, case: str, number: str) -> Dict[str, Any]:
        # same shape
```
**Approach (decision-locked):**
1. **Tiṅanta:** Build the verbal stem by applying the gaṇa vikaraṇa sūtras (3.1.x) as compiled `CompiledSutra` objects via `DSLExecutor`-style matching on the root + affix, then attach the tiṅ ending (3.4.78) and apply sandhi via `DSLExecutor.execute_sandhi`. Each applied sūtra is recorded in `applied_rule_ids`.
2. **Subanta:** Attach the sup suffix (4.1.x) to the stem, then run the resulting pair through `DSLExecutor.execute_sandhi` so 8.2.66 / 8.3.15 / 6.1.sandhi fire and record evidence.
3. **Fallback:** If a needed sūtra isn't compiled/executable yet, fall back to `TinantaGenerator`/`SubantaGenerator` and set `source: "db_fallback"` with empty `applied_rule_ids`. This keeps the gate honest (the case will be flagged as not-yet-executed) without faking evidence.
4. Do NOT hardcode forms. The DSL path must actually apply compiled rules.

**File:** `benchmarks/local_engine_adapter.py`
**What:** Route `tinganta` and `subanta` cases through `MorphExecutor` instead of the generators directly. Keep the generators as the in-`MorphExecutor` fallback.
**How:**
- `_run_tinganta_case`: call `MorphExecutor().conjugate(...)`, build `BenchmarkEvidence(applied_rule_ids=result["applied_rule_ids"], trace_steps=result["trace_steps"])`, return `_create_result(case, result["form"], evidence)`.
- `_run_subanta_case`: same with `decline`.
- The existing hardcoding-detection logic in `_create_result` then works for morph too (it already checks `applied_rule_ids`).

**Verification:**
- `python3 -m pytest tests/test_benchmark_integrity.py::test_morphological_execution -v` — fails honestly until the DSL path produces the right forms, then passes with real evidence.
- `python3 -m pytest tests/test_benchmark_integrity.py::test_no_hardcoding -v` — passes (no morph case matches output without the rule in `applied_rule_ids`).

---

## Assumptions & Decisions

1. **LLM model:** `deepseek-v4-pro:cloud` (confirmed available). User instruction: only cloud pro models. No local-model fallback will be added.
2. **No hardcoding:** If LLM extraction produces a wrong spec for 6.1.87/88/101, the unit test stays as an honest failure + hurdle record. We do not patch the answer.
3. **Coverage gate semantics:** After Step 1, "executed" means a sūtra has ≥1 passing benchmark case with the rule in `applied_rule_ids` (per `run_pipeline`'s existing definition). Sutras with no cases are `adapter_pending`, not failures — the gate fails only on `execution_unmapped` (has cases, loaded, but not executed) and `runtime_unloaded` (has cases, not loaded).
4. **Morph executor fallback:** DB-lookup remains as a fallback inside `MorphExecutor` so out-of-vocabulary roots/stems still produce *a* form, but the result is tagged `source: "db_fallback"` and contributes no `applied_rule_ids`, so the gate stays honest.
5. **Fixture encoding:** SLP1 throughout (matches the executor contract and existing sandhi fixtures).
6. **Order of execution:** Steps 1 → 2 → 3 → 4 → 5 → 6. Step 1 first because it makes all subsequent progress measurable. Step 2 before 3 because it improves extraction quality. Steps 4/5 after 3 because they depend on the extracted data. Step 6 last (largest; independent of 6.1 extraction).
7. **No new docs files** unless the user asks. Progress is recorded via `research/recorder.py` (`record_attempt`, `record_hurdle`, `update_feasibility`) and `docs/PROGRESS_2026-06-29.md` is not modified by this plan.

---

## Verification Steps (end-to-end)

```bash
# 1. Coverage gate reflects reality (no longer 3983/3983 by construction)
python3 -m pytest tests/test_benchmark_integrity.py::test_full_sutra_coverage -v

# 2. Commentary loads for all sutra number widths
python3 tools/llm_sutra_extractor.py --chapter 6.1 --dry-run

# 3. LLM extraction populated
sqlite3 data/sanskrit_master.db "SELECT COUNT(*) FROM llm_extracted_metadata WHERE sutra_id LIKE '6.1.%'"
# expect: close to 223

# 4. Chapter 6.1 executable rate with LLM rows
python3 tools/chapter_validator.py --chapter 6.1

# 5. DSL unit tests — 6.1.87/88/101 now pass
python3 -m pytest tests/test_dsl_unit.py -v

# 6. Fixtures valid & gates honest
python3 -m pytest tests/test_benchmark_catalog.py tests/test_benchmark_integrity.py -v

# 7. Morph executor wired
python3 -m pytest tests/test_benchmark_integrity.py::test_morphological_execution -v

# 8. Full suite
python3 -m pytest -q

# 9. Feasibility log updated by the validator
tail -40 research/feasibility.md
```

**Exit criteria for this plan:**
- `test_full_sutra_coverage` reports a real coverage number (not hard-coded 0%).
- `llm_extracted_metadata` has ≥ ~200 rows for chapter 6.1.
- 6.1.77, 6.1.87, 6.1.101 unit tests pass on LLM-extracted specs (or are documented as hurdles if extraction failed).
- Sandhi fixtures cover every 6.1 sūtra that produces correct output.
- `MorphExecutor` exists, is wired into the adapter, and morph gate tests fail honestly (passing only when the DSL path actually derives the form with evidence).
- No new hardcoding; `test_no_hardcoding` continues to pass.