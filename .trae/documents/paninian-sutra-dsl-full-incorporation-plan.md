# Paninian Sutra DSL — Full Incorporation Plan

## Summary

Build a true Sanskrit DSL that parses Patañjali's sūtra text directly into executable semantics, backed by a new meta-rule engine that faithfully implements paribhāṣā, asiddhatva, anuvṛtti, and antaraṅga/bahiraṅga. Use LLM-assisted extraction chapter-by-chapter with validation against the frozen benchmark suite. Document every failure as a "hurdle record" so we build a first-principles evidence base for feasibility judgments.

## Current State Analysis

### What exists
- **3,983 sūtras** in `sutras` table, all parsed by `ss_parser` into `rule_configs`
- **2,730 (68%) are `non_operational`** — the AST builder couldn't extract semantics
- **1,191 active** rule_configs, but only **1,031 are `exact_substitute`** (simplest op)
- **Existing DSL** (`rule_engine/dsl.py`): `RuleSpec`, `ConditionSpec`, `PrimitiveOp` — a universal primitive (consume N left, M right, emit on a side). Works but unused by the runtime path.
- **Existing meta-rule scaffolding**: `conflict.py` (5-level resolution), `visibility.py` (asiddhatva policy), `anuvritti.py` (anuvṛtti engine), `loop.py` (BFS derivation). All **structurally present but disconnected** — `conditioning_factors` always empty, `paribhasas` set empty, `AsiddhaDomainPolicy` never instantiated, `execute_bahiranga_rewind` never called.
- **Existing parser** (`ss_parser.py`): Does vibhakti-based parsing but falls back to **~10 hardcoded special cases** and marks 2,730 as non_operational.
- **Benchmark suite**: Gate tests that fail truthfully (3 fail, 5 pass). Reports 0.1% coverage.

### Core bottleneck
The `SutraAstBuilder` correctly maps vibhakti cases (6th→target, 7th→right context, 5th→left, 1st→substitute) but cannot resolve semantics because:
1. It lacks vocabulary for meta-terms (only ~30 hardcoded `PRATYAHARA_STEMS`)
2. It doesn't handle anuvṛtti at runtime (only during bootstrap)
3. It doesn't resolve paribhāṣā references
4. It can't handle multi-word conditions or complex operations
5. Commentary context (Kāśikā, Mahābhāṣya) is absent

## Proposed Changes

### Phase 1: Research Infrastructure (Prerequisite)

#### 1.1 Research log system
Create `research/` directory:
- `research/log/` — chronological markdown logs of every attempt
- `research/hurdles/` — per-sūtra hurdle records (JSON + markdown)
- `research/approaches/` — documented approaches with outcomes
- `research/feasibility.md` — living first-principles assessment

Create `research/recorder.py`:
- `record_attempt(sutra_id, approach, result, notes)` — logs to `research/log/`
- `record_hurdle(sutra_id, hurdle_type, description, blocking)` — logs to `research/hurdles/`
- `record_approach(name, description, outcome, evidence)` — logs to `research/approaches/`
- `update_feasibility(assessment, evidence)` — updates `research/feasibility.md`

#### 1.2 LLM extraction pipeline
Create `tools/llm_sutra_extractor.py`:
- Takes a chapter range (e.g., `6.1.*`)
- For each sūtra: sends `sutra_dev`, `pada_cheda`, `sutra_type`, and commentary snippets to Ollama
- Asks for structured JSON: `operation_type`, `target`, `left_context`, `right_context`, `conditioning_factors`, `applicable_paribhasas`, `domain`, `anuvrtti_carries`, `notes`
- Validates output against schema
- Caches results in `data/llm_extracted_metadata` table (idempotent — skip if already extracted)
- Writes a per-chapter extraction log to `research/log/`

### Phase 2: New Sanskrit DSL Engine

#### 2.1 Sutra text parser (`sanskrit_dsl/parser.py`)
A new parser that reads sūtra text (Devanagari) directly — not `pada_cheda` alone, but the full sūtra plus commentary context:
- Tokenize into PadaTokens (reuse `PadaChedaParser`)
- Resolve vibhakti roles (reuse the 6th/7th/5th/1st mapping from `SutraAstBuilder`)
- Resolve pratyāhāras dynamically via `PratyaharaEngine` (no hardcoded stems)
- Resolve meta-terms via the `sanjnas` table (no hardcoded `PANINIAN_META_TERMS`)
- Handle anuvṛtti by querying `AnuvrittiEngine` for inherited slots
- Output: a `SutraSpec` (richer than `RuleSpec`) that includes conditioning_factors, paribhāṣā refs, and domain scope

#### 2.2 New meta-rule engine (`sanskrit_dsl/meta_engine.py`)
Replace the disconnected scaffolding with a clean, wired-in engine:
- **Paribhāṣā registry**: Load `P$` sūtras from DB, parse them into `ParibhasaAxiom` objects with `LogicalPredicate`s. Wire into the conflict resolver.
- **Asiddhatva enforcer**: Implement `AsiddhaDomainPolicy` as a runtime visibility filter. Rules in chapter N cannot see changes from chapter M > N (8.2→8.3→8.4).
- **Anuvṛtti at runtime**: Enable `AnuvrttiPolicy` in `TraditionConfig`. Track carried-over slots across sūtra application (not just bootstrap).
- **Antaraṅga/Bahiraṅga**: Populate `conditioning_factors` from the parsed contexts. Wire `is_antaranga_relative_to()` into the resolver.
- **Tripāḍī ordering**: Strict chapter-order application for 8.2–8.4, with pūrvatrāsiddham checkpoints.

#### 2.3 Sutra compiler (`sanskrit_dsl/compiler.py`)
Compiles `SutraSpec` → executable `CompiledSutra`:
- Converts contexts to `ConditionSpec` (reuses existing DSL)
- Converts operation to `PrimitiveOp` (reuses existing DSL)
- Attaches meta-rule metadata (paribhāṣā refs, conditioning factors, domain)
- Caches compiled sūtras per-chapter

### Phase 3: Chapter-by-Chapter Incorporation

For each chapter (starting with 6.1.x as the highest-value sandhi chapter):

#### 3.1 Extract
- Run `llm_sutra_extractor.py --chapter 6.1`
- Review extracted metadata for each sūtra
- Record hurdles for sūtras where extraction fails or is ambiguous

#### 3.2 Compile
- Run the new `sanskrit_dsl/parser.py` on each sūtra
- Cross-check parser output against LLM extraction
- Where they disagree, investigate and record the hurdle

#### 3.3 Validate
- Run the benchmark suite against the newly compiled rules
- Any case that passes output but fails evidence → hardcoding suspicion
- Any case that fails output → record the specific failure

#### 3.4 Iterate
- Fix parser/compiler issues revealed by failures
- Re-run extraction if needed
- Update `research/feasibility.md` with assessment

### Phase 4: Domain Expansion

After 6.1.x reaches 100% benchmark pass:
- Expand to 8.2.x (Tripāḍī sandhi)
- Then 8.3.x, 8.4.x
- Then 3.x (Tiṅanta verbal derivations)
- Then 4.x (Subanta nominal declension)
- Then 5.x (Kṛdanta/Taddhita derivations)
- Finally 1.x–2.x (Sañjñās, Paribhāṣās, Adhikāras)

## Failure Documentation Protocol

For every sūtra that cannot be compiled or executed:

1. **Hurdle record** (`research/hurdles/{sutra_id}.json`):
   ```json
   {
     "sutra_id": "6.1.X",
     "sutra_text": "...",
     "approach_attempted": "vibhakti_parse | llm_extract | manual",
     "hurdle_type": "vocabulary_missing | context_ambiguous | meta_rule_unclear | commentary_dependent | infinite_recursion | edge_case",
     "description": "What specifically blocked compilation",
     "commentary_reference": "Kāśikā on X says...",
     "blocking": true | false,
     "workaround": "What we did instead (or null)"
   }
   ```

2. **Approach record** (`research/approaches/{approach_name}.md`):
   - What the approach was
   - What sūtras it could/couldn't handle
   - Why it succeeded or failed
   - Evidence (benchmark results, test outputs)

3. **Feasibility assessment** (`research/feasibility.md`):
   - Updated after each chapter
   - Lists what % of sūtras are tractable
   - Identifies the hardest unsolved problems
   - Provides first-principles judgment: "Is full DSL feasible with current tech?"

## Cache Strategy

- **LLM extraction results**: Cached in DB table `llm_extracted_metadata`. Never re-extract a sūtra unless explicitly forced.
- **Compiled sūtras**: Cached in DB table `compiled_sutras_v2` (new schema). Re-compile only when parser changes.
- **Benchmark results**: Cached in `tests/results/`. Re-run only when rules change.
- **Research logs**: Append-only. Never delete. This is the institutional memory.

## Files to Create

```
research/
  recorder.py
  log/
  hurdles/
  approaches/
  feasibility.md

sanskrit_dsl/
  __init__.py
  parser.py
  meta_engine.py
  compiler.py
  types.py

tools/
  llm_sutra_extractor.py
  chapter_validator.py
```

## Files to Modify

- `benchmarks/catalog.py` — add `compiled_sutras_v2` to the universe
- `benchmarks/local_engine_adapter.py` — route through `sanskrit_dsl` compiler
- `tests/test_benchmark_integrity.py` — gate tests stay the same (they already fail truthfully)

## Verification

After each chapter:
1. `python tools/chapter_validator.py --chapter 6.1`
2. `python3 -m pytest tests/test_benchmark_integrity.py -q` (gates should show progress)
3. `python3 tools/panini_benchmark_pipeline.py --engine local --domain all`
4. Review `research/feasibility.md` for updated assessment

## Assumptions & Decisions

- **Full DSL is the goal**, but we accept it may be impossible for some sūtras. Those get hurdle records, not silent non_operational flags.
- **New meta-rule engine** replaces the disconnected scaffolding. The old `conflict.py`/`visibility.py`/`loop.py` are reference material, not the runtime path.
- **LLM extraction is chapter-by-chapter** with validation. No blind batch extraction.
- **Every failure is documented**. If we eventually conclude "X% is impossible with current tech," we have the evidence to prove it.
- **Caching is mandatory**. No recompute without explicit reason.
- **The benchmark suite is the source of truth**. No test is marked passing unless the engine truly executes the rule.