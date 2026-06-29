# Next Steps — Paninian Sanskrit DSL Engine

## End Goal

**Paste Patañjali's 4,000 sūtras as Sanskrit text, and the engine compiles and executes them all correctly — producing correct sandhi, verbal conjugations, and nominal declensions.**

This requires:
1. A parser that reads sūtra text and correctly identifies vibhakti roles (target, left context, right context, operation)
2. A meta-rule engine that handles anuvṛtti, asiddhatva, antaraṅga/bahiraṅga, and paribhāṣā
3. A phonology engine that resolves pratyāhāras and computes guṇa/vṛddhi/dīrgha — **this part works**

## Current Architecture (2026-06-29)

```
sanskrit_dsl/
  types.py       — SutraSpec, SutraContext, SutraOperation, CompiledSutra
  parser.py      — Clean vibhakti parser + LLM extraction path
  compiler.py    — Compiles sutras into executable form
  meta_engine.py — Paribhāṣā, Asiddhatva, Anuvṛtti, Antaranga resolver
  executor.py    — Applies compiled rules to input pairs
  corrections.py — DEPRECATED (does nothing)

benchmarks/      — Truthful benchmark suite with gate tests
research/        — Failure logging and feasibility assessment
tools/           — LLM extractor, chapter validator

compiler/ast_builder.py — DEPRECATED (old broken parser, do not use)
```

## The Path Forward

### Step 1: Run LLM Extraction on Chapter 6.1 (FIRST PRIORITY)

The clean vibhakti parser can handle simple sutras but fails on most because it lacks commentary context. The LLM extractor is built and ready.

```bash
# Verify the extractor works (shows prompts without calling LLM)
python3 tools/llm_sutra_extractor.py --chapter 6.1 --dry-run

# Run extraction on chapter 6.1 (223 sutras)
python3 tools/llm_sutra_extractor.py --chapter 6.1

# Or with a specific model
python3 tools/llm_sutra_extractor.py --chapter 6.1 --model deepseek-v4-pro:cloud
```

**What this does:**
- Sends each sūtra to Ollama with Vasu English commentary + previous 3 sutras as context
- Extracts structured JSON: operation_type, target, left/right contexts, conditioning factors, paribhāṣā references
- Caches results in `llm_extracted_metadata` DB table
- Records failures as hurdles

**After extraction:**
- Re-run the DSL unit tests — sutras that previously failed should now work via LLM-extracted metadata
- Run `python3 -m pytest tests/test_dsl_unit.py -v` to verify

### Step 2: Validate LLM Extractions

LLM extraction can hallucinate. Validate each extracted sūtra:

```bash
# Validate a chapter
python3 tools/chapter_validator.py --chapter 6.1
```

**Validation criteria:**
- The extracted operation_type is one of the known types
- The target/left/right contexts are non-null for operational sutras
- The sūtra compiles to executable form
- The compiled sūtra produces correct output on test inputs

**If extraction is wrong:**
- Record a hurdle: `research/recorder.py` `record_hurdle()`
- Re-run extraction with `--force` for that sūtra

### Step 3: Expand the Benchmark Fixtures

The current fixtures have only 10 sandhi cases and 2 morph cases. Expand them:

**Sandhi fixtures** (`tests/fixtures/panini_blackbox_cases.json`):
- Add cases for every sutra in chapter 6.1 that produces correct output
- Each case: input pair, expected output, expected sutra_id in trace
- Each case is a GATE — it fails if the engine produces wrong output

**Morph fixtures** (`tests/fixtures/morphology_blackbox_cases.json`):
- Add verbal conjugation cases (bhū + laṭ → bhavati, etc.)
- Add nominal declension cases (rāma + nominative singular → rāmaḥ, etc.)

### Step 4: Fix the Clean Parser's Remaining Issues

The clean vibhakti parser (`sanskrit_dsl/parser.py` `_from_vibhakti_clean`) has known issues:

1. **Meta-term resolution**: Terms like `savarR` (savarṇa), `padAntA` (padānta) are not resolved. They should be looked up in a meta-term registry or resolved via commentary.

2. **Compact form handling**: Sutras like "kuṇvoḥ" (6.1.89) are compact forms that need expansion. The parser doesn't handle these.

3. **Anuvṛtti at parse time**: When a sūtra inherits context from previous sutras, the parser should query the `AnuvrttiTracker`. Currently the tracker only works during compilation, not parsing.

4. **Multi-word conditions**: Some sutras have conditions spanning multiple words (e.g., "padāntasya" requires padānta tag). The parser doesn't handle tags.

**How to fix:**
- Do NOT rewrite the parser from scratch. Fix issues incrementally.
- For each issue, find a sūtra that demonstrates it, write a test, fix the parser, verify the test passes.
- Use LLM extraction as the override for sutras the parser can't handle.

### Step 5: Implement Morphological Derivation

The current executor only handles sandhi (joining two words). Morphological derivation (root → verb, stem → noun) is not implemented in the DSL path.

**What's needed:**
- `sanskrit_dsl/morph_executor.py` — Executes verbal conjugation and nominal declension
- The executor takes a root/stem + grammatical parameters, applies derivational rules (chapters 3-7), and produces the final form
- This is harder than sandhi because it involves multi-step derivation, not single-step joining

### Step 6: Expand to All Chapters

After chapter 6.1 is validated:
1. Run LLM extraction on chapter 8.2 (Tripāḍī sandhi)
2. Then 8.3, 8.4
3. Then 3.x (verbal derivations)
4. Then 4.x (nominal declension)
5. Then 5.x (Kṛdanta/Taddhita)
6. Finally 1.x–2.x (Sañjñās, Paribhāṣās)

For each chapter:
```bash
python3 tools/llm_sutra_extractor.py --chapter X.Y
python3 tools/chapter_validator.py --chapter X.Y
python3 -m pytest tests/test_benchmark_integrity.py -v
```

## Parser Migration Guide

### The old parser (DEPRECATED)

`compiler/ast_builder.py` `SutraAstBuilder`:
- Misassigns vibhakti roles for many sutras
- Has hardcoded `PRATYAHARA_STEMS` (30 entries)
- Has hardcoded `PANINIAN_META_TERMS`
- Does not handle anuvṛtti at runtime
- **DO NOT USE** — The DSL parser no longer calls it

### The new parser

`sanskrit_dsl/parser.py` `SutraParser`:
- `_from_llm_row()` — Primary path: uses LLM-extracted metadata
- `_from_vibhakti_clean()` — Fallback: clean vibhakti parser
- `_try_resolve_pratyahara()` — Dynamic pratyahara resolution via `PratyaharaResolver`
- Records hurdles for sutras it can't parse

### How to add a new sutra to the system

1. **If the clean parser handles it**: Nothing to do. It will compile and execute.
2. **If the clean parser fails**: Run LLM extraction:
   ```bash
   python3 tools/llm_sutra_extractor.py --chapter X.Y --force
   ```
3. **If LLM extraction fails**: Record a hurdle and investigate manually:
   ```python
   from research.recorder import record_hurdle
   record_hurdle("X.Y.Z", "manual_investigation_needed", "Description of the issue")
   ```

## How to Verify Progress

```bash
# Run all tests
python3 -m pytest -q

# Run only DSL unit tests
python3 -m pytest tests/test_dsl_unit.py -v

# Run benchmark gates
python3 -m pytest tests/test_benchmark_integrity.py -v

# Validate a chapter
python3 tools/chapter_validator.py --chapter 6.1

# Check feasibility assessment
cat research/feasibility.md

# Check recorded hurdles
ls research/hurdles/
```

## Key Principles

1. **No hardcoding**: If a sutra works, it must work because the parser/LLM understood it, not because someone manually wrote the answer.
2. **Tests are gates**: Tests fail when the engine is incomplete. They do not lie.
3. **Failures are documented**: Every failure gets a hurdle record. We build an evidence base.
4. **LLM extraction is the pragmatic path**: The clean parser handles simple cases. LLM extraction handles the rest. Manual annotation is forbidden.
5. **The benchmark suite is the source of truth**: No claim of progress is valid unless the benchmark gates show improvement.

## File Reference

| File | Purpose |
|------|---------|
| `sanskrit_dsl/parser.py` | Sutra text → SutraSpec |
| `sanskrit_dsl/compiler.py` | SutraSpec → CompiledSutra |
| `sanskrit_dsl/executor.py` | CompiledSutra + input → output + trace |
| `sanskrit_dsl/meta_engine.py` | Conflict resolution, anuvṛtti, asiddhatva |
| `sanskrit_dsl/types.py` | Data types with real pratyahara matching |
| `benchmarks/local_engine_adapter.py` | Routes benchmark cases through DSL executor |
| `tools/llm_sutra_extractor.py` | LLM-based metadata extraction |
| `tools/chapter_validator.py` | Per-chapter validation |
| `research/recorder.py` | Failure logging |
| `tests/test_dsl_unit.py` | Unit tests on compiled sutras |
| `tests/test_benchmark_integrity.py` | Gate tests on engine completeness |