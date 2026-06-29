# Honest DSL Wiring & Validation Plan

## Summary

The previous "89.1% executable" claim was a lie. The compiled sutras have correct op_type labels but **zero runtime behavior** — `left_consume=0`, `right_consume=0`, `emit=""` for all sutras, and pratyahara matching is a `return True` placeholder. This plan wires the DSL compiler into actual execution, fixes the placeholder matching, writes real unit tests on compiled sutras, and sets up the LLM extraction pipeline correctly using the user's actual Ollama models with commentary context.

## Current State Analysis (Honest)

### What actually works
- `SutraParser._from_vibhakti()` correctly calls the old `SutraAstBuilder` and extracts op_type labels
- The research infrastructure (`research/recorder.py`) is real and functional
- The LLM extractor structure is complete but targets a non-existent model
- Commentary data EXISTS in the repo: `data/ashtadhyayi-data/sutraani/kashika.txt`, `bhashya.txt`, `vasu_english.txt`, `sutrartha_english.txt`, etc.

### What is broken/lying
1. **SutraOperation has no behavior**: Every compiled sutra has `left_consume=0, right_consume=0, emit=""`. The `apply()` method is a no-op.
2. **Pratyahara matching is `return True`**: `_context_matches()` in `types.py` line 146 always returns True for pratyahara contexts.
3. **No execution path**: The benchmark adapter still calls `dispatch_forward_with_metadata` (old engine). The DSL compiler is never invoked at runtime.
4. **No unit tests on compiled sutras**: The "89.1%" number has zero validation.
5. **LLM extractor uses wrong model**: Hardcoded `gpt-oss:20b` which doesn't exist. User has `deepseek-v4-pro:cloud`, `kimi-k2.6:cloud`, `qwen3-coder:480b-cloud`, etc.
6. **No commentary context in prompts**: The LLM extractor sends only sutra text + pada_cheda, not commentary.
7. **No anuvṛtti context in LLM prompts**: Each sutra is sent individually without previous sutra context.
8. **Tripāḍī not handled in LLM extraction**: No special handling for 8.2–8.4 ordering.

### The 436 non-executable sutras
- Scattered across ALL chapters (not concentrated in one place)
- Heaviest: 6.3 (42), 6.1 (41), 5.4 (29), 2.3 (28), 8.2 (23), 8.1 (22)
- Types: mostly `governance` (meta-rule markers like vā, vibhāṣā, nityam) and Sañjñā definitions
- Many require commentary context to interpret
- Some are legitimately non-operational (pure definitions, scope markers)

## Proposed Changes

### 1. Fix SutraOperation to carry real behavior

#### `sanskrit_dsl/types.py`
- Add `compute_fn` resolution: when `op_type` is `guna`, `vrddhi`, `dirgha`, `savarna_long`, or `bijection`, the `apply()` method must call the actual phonological computation (reusing `core.phonology.GUNA_MAP`, `VRDDHI_MAP`, `SAVARNA_LONG`).
- Add `left_consume`/`right_consume` inference: when the target context specifies a pratyahara (e.g., `iK`), the consume count = number of phonemes to replace. When `exact_text` is specified, consume = `len(exact_text)`.
- Add `emit` computation: for `exact_substitute`, `emit = replacement`. For `merge` (guna/vrddhi/dirgha), `emit = compute_fn(target_phoneme)`. For `bijection`, `emit = bijection_map[target]`.

#### `sanskrit_dsl/executor.py` (NEW)
- A proper execution module that:
  - Takes `(left, right, compiled_sutras)` 
  - Iterates sutras in order (sapada then tripadi)
  - For each sutra, checks `matches()` with REAL pratyahara expansion (via `core.shiva_sutras.PratyaharaResolver`)
  - Applies the operation with REAL phonological computation
  - Records applied rule IDs in a trace
  - Returns `(final_left, final_right, applied_rule_ids, trace_steps)`

### 2. Fix pratyahara matching

#### `sanskrit_dsl/types.py`
- Replace the `return True` placeholder with actual pratyahara expansion:
  ```python
  from core.shiva_sutras import PratyaharaResolver
  if ctx.pratyahara:
      phonemes = PratyaharaResolver.resolve(ctx.pratyahara)
      char = text[-1] if pos == "end" else text[0]
      return char in phonemes
  ```

### 3. Wire DSL compiler into the benchmark adapter

#### `benchmarks/local_engine_adapter.py`
- Add a new execution path: `_run_sandhi_case_via_dsl()` that uses `SutraCompiler` + the new executor instead of `dispatch_forward_with_metadata`.
- Keep the old path as fallback for comparison.
- The adapter should report which path it used (old engine vs DSL).

### 4. Write real unit tests on compiled sutras

#### `tests/test_dsl_unit.py` (NEW)
- Test specific sutras with specific inputs:
  - `6.1.77` (iko yan aci): `('hari', 'atra')` → `('hary', 'atra')` with rule 6.1.77 in trace
  - `6.1.87` (ad gunah): `('rAma', 'ISa')` → `('rAme', 'Sa')` with rule 6.1.87 in trace
  - `6.1.101` (akah savarne dirghah): `('rAma', 'atra')` → `('rAmA', 'tra')` with rule 6.1.101 in trace
  - `8.2.66` (sasajuso ruh): `('hariH', 'gacCati')` → `('harir', 'gacCati')` with rule 8.2.66 in trace
- These tests FAIL if the compiled sutra doesn't match, doesn't apply, or produces wrong output.
- These are GATES, not smoke tests.

### 5. Fix the LLM extractor

#### `tools/llm_sutra_extractor.py`
- Change default model to `deepseek-v4-pro:cloud` (or make it configurable)
- Use HTTP API (`http://localhost:11434/api/generate`) instead of subprocess
- Add commentary context to the prompt:
  - Load commentary from `data/ashtadhyayi-data/sutraani/vasu_english.txt` (English translation)
  - Load commentary from `data/ashtadhyayi-data/sutraani/kashika.txt` (Kāśikā)
  - Include relevant commentary snippet in the prompt
- Add anuvṛtti context to the prompt:
  - For each sutra, include the previous 2-3 sutras' text as context
  - Note what the previous sutra's operation was (if any)
- Add Tripāḍī handling:
  - For 8.2–8.4 sutras, note in the prompt that these are Tripāḍī rules with pūrvatrāsiddham
  - Include the Tripāḍī boundary marker in the context

### 6. Validate all chapters

#### `tools/validate_all_chapters.py` (NEW)
- Run `chapter_validator.py` for every chapter (1.1 through 8.4)
- Record results in `research/log/`
- Update `research/feasibility.md` with honest per-chapter rates
- Identify which chapters need LLM extraction first

## Assumptions & Decisions

- The old `SutraAstBuilder` produces correct op_type labels but not correct primitive operations. We need to infer `left_consume`/`right_consume`/`emit` from the op_type + contexts.
- The existing `PratyaharaResolver` in `core/shiva_sutras.py` works and should be reused for matching.
- The existing `GUNA_MAP`, `VRDDHI_MAP`, `SAVARNA_LONG` in `core/phonology.py` should be reused for computation.
- LLM extraction should use `deepseek-v4-pro:cloud` as default (best available cloud model).
- Commentary context is critical — the Vasu English commentary is the most accessible for LLM understanding.
- Anuvṛtti context (previous sutras) should be sent with each prompt, not just the single sutra.

## Verification

1. `python3 -m pytest tests/test_dsl_unit.py -q` — unit tests on compiled sutras (must FAIL initially, then pass after fixes)
2. `python3 -m pytest tests/test_benchmark_integrity.py -q` — gate tests (should show progress)
3. `python3 tools/validate_all_chapters.py` — per-chapter validation
4. `python3 tools/llm_sutra_extractor.py --chapter 6.1 --dry-run` — verify LLM prompts include commentary
5. `python3 tools/llm_sutra_extractor.py --chapter 6.1` — actual extraction run