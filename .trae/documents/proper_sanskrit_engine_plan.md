# Plan — Proper Sanskrit Engine: Tripāḍī, Saṃjñā, Executor Redesign & Testing-Pipeline Repair

**Date:** 2026-06-29
**Status:** Decision-complete. An executor can implement without making further choices.
**Scope:** Build a *proper* Pāṇinian engine that can handle all rule types — not just 6.1 vowel sandhi. This is non-negotiable per the user. Covers: Tripāḍī LLM extraction, full saṃjñā layer, executor state-timeline + asiddhatva + conflict-resolution rebuild, batch extraction mode, and a complete overhaul of the testing pipeline so the saṃjñā/meta-rule gaps that shipped undetected can never recur.

---

## Summary — Why this plan exists

The current engine can handle the simplest case (6.1.77 → `haryatra`) but is structurally incapable of correct Paninian derivation because four foundational systems are missing or unwired:

1. **No saṃjñā (technical-term) layer in the DSL path.** `core/sanjña_tagger.py` exists and is wired into the *old* `rules/engine.py`, but the DSL executor (`sanskrit_dsl/executor.py`) never calls it. `SutraContext` has no `sanjña_required` / `prohibit_if_sanjña` fields, so rules cannot predicate on labels like "where a kṛt affix follows" — which is how 3.x–7.x rules actually condition. This is the deepest red flag.
2. **No asiddhatva / state-timeline in the executor.** `AsiddhatvaEnforcer` exists in `meta_engine.py` but is never called. The executor shadows the original input immediately, applies one sapāda rule then one tripāḍī rule, and lets a second rule corrupt the first's correct output (e.g., 6.1.52 corrupts 6.1.87's correct `rAmeSa` → `rAmASa`).
3. **Conflict resolution is wrong.** `AntarangaResolver.resolve` uses a flat `+50` per context regardless of type, and its "later-sūtra-wins" fallback sorts `sutra_id` *lexicographically* (`"6.1.9"` > `"6.1.77"`), which is wrong for any pāda with >9 sūtras. There is no apavāda/niyama (prohibition/debarring) mechanism and `ParibhashaRegistry.applies_to` is never consulted.
4. **The testing pipeline is an inventory + output-equality gate, not a derivation-correctness gate.** It never inspects `trace_steps`, never tests saṃjñā tagging, never tests paribhāṣā application, never tests Tripāḍī asiddhatva boundaries, and one fixture is even calibrated to the engine's *known-wrong* output. That is why all of the above shipped undetected.

This plan fixes all four, in the order: **Tripāḍī extraction first → executor + saṃjñā rebuild → testing-pipeline overhaul → batch extraction → expand to remaining chapters.** Decisions locked: rebuild the state model inside `sanskrit_dsl` (no dependency on `rules/engine.py`, keep old path alive); Tripāḍī extraction before executor redesign; hybrid batch extraction (batch the definitional saṃjñā/paribhāṣā sūtras, per-sūtra for operational rules); full saṃjñā layer now.

---

## Current State Analysis (from Phase 1 exploration — evidence-grounded)

### What works (real, not faked)
- `core/phonology.py` + `core/shiva_sutras.py`: pratyāhāra expansion, guṇa/vṛddhi/dīrgha/bijection computation. Solid.
- `sanskrit_dsl/types.py` `SutraOperation.compute_emit`: correct phonological mapping for guṇa/vṛddhi/dīrgha/yaṇ.
- `sanskrit_dsl/parser.py` `_from_llm_row`: parses LLM-extracted metadata into `SutraSpec`; now handles null JSON and resolves pratyahara targets.
- `sanskrit_dsl/compiler.py` `compile_all`: returns ~3,547 executable sutras; anuvṛtti of *operation* works at compile time.
- Chapter 6.1: 223/223 LLM-extracted; 6.1.77 verified end-to-end; 6.1.87/88/101 verified at sūtra-level apply.
- `benchmarks/` suite: honest gate tests, no hardcoding detected.

### What's broken / unwired (verified facts, with file:line evidence)
- **`sanskrit_dsl/executor.py:45,50-89`** — `execute_sandhi` shadows `(left,right)` into `cur_left/cur_right`; never snapshots the original; never calls `AsiddhatvaEnforcer.checkpoint` or `is_visible`. The enforcer is dead code at runtime. Exactly one sapāda then one tripāḍī rule fires; no re-filter loop, so cascades of ≥2 sapāda rules are impossible.
- **`sanskrit_dsl/meta_engine.py:164-210`** — `AntarangaResolver.resolve`: `is_antaranga` returns `False` whenever `conditioning_factors` is empty (common case), so antaraṅga is dead. Specificity scores left/right context `+50` flat regardless of exact-text vs pratyahara vs tags. Line 210: `sorted(candidates, key=lambda s: s.sutra_id)[-1]` — *lexicographic* string sort, wrong for `pada` with >9 sūtras.
- **`sanskrit_dsl/meta_engine.py:232-246`** — `MetaRuleEngine.resolve_conflict` never calls `paribhasas.applies_to` or `asiddhatva.is_visible`. Terminal `candidates[-1]` fallback is unreachable.
- **`sanskrit_dsl/types.py:96-113`** — `CompiledSutra.matches` ignores `conditioning_factors`, `applicable_paribhasas`, `rule_type`; `context` param is accepted but never used. No saṃjñā fields on `SutraContext`.
- **`sanskrit_dsl/meta_engine.py` `ParibhashaRegistry`** — `load()` loads `P$` sūtras into `axioms`; `applies_to` only returns precomputed lists; never consulted by conflict resolution.
- **`sanskrit_dsl/meta_engine.py` `AnuvrttiTracker`** — `get_inherited` is defined and never called; `right_context` carry is tracked but never inherited; runtime anuvṛtti during execution does not happen.
- **`core/sanjña_tagger.py`** — models 5 saṃjñās (pragrhya, padanta, amredita, nipata, avyaya) as Python predicates; wired only into `rules/engine.py` Phase 1, *never* into `sanskrit_dsl/executor.py`. Missing: ṣaṭ-pratyaya, ārdhadhātuka, dhātu, gati, sarvanāmasthāna, kāraka roles.
- **`data/bootstrap_sanjnas.py` + `sanjnas` DB table** — a terminology lookup (vṛddhi/guṇa/lopa/luk/etc. → op_type), *separate* from the runtime tagger; the two systems don't read each other.
- **`rules/engine.py`** — the OLD path has `DerivationTrace` (asiddhatva via `get_state_before_chapter`), `ExecutionContext` (sanjña_map), `SanjanaTagger` integration, an iterative Tripāḍī loop, a specificity scorer, and a prohibit short-circuit. The DSL executor has *none* of this. Per the locked decision: rebuild inside `sanskrit_dsl`, keep `rules/engine.py` alive (still used by `morphology/sandhi.py`).

### Why the testing pipeline missed all of this (evidence)
- **`benchmarks/pipeline.py:49-56`** — `executed_rule_ids` is derived from `output_match and rule_expectation_match and not hardcoding_suspected`. It is *output-equality*, not derivation-correctness. `trace_steps` is collected but `reports.py:45` drops it from the payload; no test ever inspects it.
- **`benchmarks/local_engine_adapter.py:109-126`** — the hardcoding heuristic fires only when the *nominal* sutra_id is *absent* from `applied_rule_ids` AND output matched. It cannot catch "right output via wrong rule that stamps the right id", nor "right output via wrong reason".
- **Fixtures** — `panini_blackbox_cases.json` has only 6.1.x cases; `morphology_blackbox_cases.json` has 3.4.78 + 8.2.66 only. **Zero** cases for 1.x saṃjñā definitions, 3.x/4.x derivations, or the 8.2.1–8.4.68 Tripāḍī boundary. One 6.1.89 family fixture is explicitly calibrated to the engine's *wrong* attribution.
- **`tests/`** — zero references to `sanjna`, `paribhasha`, `asiddha`, `antaranga`, `anuvrtti`, `MetaRuleEngine`, `AsiddhatvaEnforcer`, `AntarangaResolver`, `AnuvrttiTracker`, `SanjanaTagger`. No test exercises the Tripāḍī boundary, antaraṅga/bahiraṅga, or saṃjñā tagging.
- **`benchmarks/catalog.py:41-82`** — classification is inventory-level: `has_rule_config`, `loaded_by_runtime`, `executed_dynamically`. No field captures saṃjñā/paribhāṣā/asiddhatva correctness.

---

## Proposed Changes

### MILESTONE 1 — Tripāḍī LLM Extraction (8.2, 8.3, 8.4) — FIRST

Per locked decision: extract the Tripāḍī before redesigning the executor, so the redesign has real asiddhatva data to design against.

#### 1a. Hybrid batch-extraction mode in the extractor
**File:** `tools/llm_sutra_extractor.py`
**What:** Add a `--batch-definitions` mode that, for a given chapter, sends all `sutra_type LIKE 'S$%'` (saṃjñā) and `sutra_type LIKE 'P$%'` (paribhāṣā) sūtras of that pāda in a *single* LLM call requesting a JSON array of extraction objects. Operational sūtras (`V$`) stay per-sūtra (proven on 6.1).
**Why:** Saṃjñā/paribhāṣā sūtras are *definitional* and only make sense in their full pāda scope — the LLM sees the entire adhikāra and anuvṛtti scope natively in one call. This directly addresses the anuvṛtti-spanning concern. Operational rules stay per-sūtra to avoid JSON truncation risk on the large array.
**How:**
- New function `build_batch_prompt(sutras: List[Dict], commentary_map) -> str` returning a prompt requesting `[{...schema...}, ...]`.
- New function `store_batch_extraction(conn, extractions: List[Dict], model)` that iterates and stores each element (same `store_extraction` per row, plus a `batch_index` column added to `llm_extracted_metadata` for traceability).
- `extract_chapter` gains a `--batch-definitions` flag: when set, it partitions sutras into `definitional` (S$/P$) and `operational` (V$/others), sends one batch call for definitional, then per-sūtra for operational.
- Fallback: if the batch JSON is truncated (last element lacks closing `}`) or any element fails schema validation, re-extract those specific sutras per-sūtra.
- Keep the retry/backoff and `--delay` already added.

#### 1b. Run extraction on 8.2, 8.3, 8.4
**Execution step (no code change beyond 1a):**
```bash
python3 tools/llm_sutra_extractor.py --chapter 8.2 --batch-definitions --model deepseek-v4-pro:cloud --delay 3
python3 tools/llm_sutra_extractor.py --chapter 8.3 --batch-definitions --model deepseek-v4-pro:cloud --delay 3
python3 tools/llm_sutra_extractor.py --chapter 8.4 --batch-definitions --model deepseek-v4-pro:cloud --delay 3
python3 tools/chapter_validator.py --chapter 8.2   # etc.
```
**After:** the `llm_extracted_metadata` table covers 6.1 + 8.2 + 8.3 + 8.4. The Tripāḍī sūtras (8.2.1 pūrvatrāsiddham, 8.3.x ṣaṭḥ/visarga, 8.4.x natva/etc.) are all present with structured op_type/target/context/replacement.

#### 1c. Extract chapter 1.1 saṃjñā definitions (parallel, cheap via batch)
**Why:** 1.1 defines pratyāhāras, hrasva/dīrgha, guṇa/vṛddhi, savarṇa, and the foundational saṃjñās the saṃjñā layer (Milestone 2) must tag with. Extracting 1.1 now lets the saṃjñā layer reference real definitions.
**Command:** `python3 tools/llm_sutra_extractor.py --chapter 1.1 --batch-definitions --model deepseek-v4-pro:cloud --delay 3`

---

### MILESTONE 2 — Executor + Saṃjñā Rebuild (inside `sanskrit_dsl`)

Per locked decision: rebuild the state model inside `sanskrit_dsl`, keep `rules/engine.py` alive. This is the core of the plan.

#### 2a. New `sanskrit_dsl/execution_context.py` — typed runtime state
**New file:** `sanskrit_dsl/execution_context.py`
**What:** A clean `ExecutionContext` dataclass holding: `left_token`, `right_token`, `sanjna_map: Dict[str, Set[str]]`, `trace: DerivationTimeline`, `domain`, `is_samasa`, `morphological_features`, `is_padanta`. Plus `has_sanjna(side, name)` / `add_sanjna(side, name)`.
**Why:** Rules need a single object carrying all runtime state — boundary strings, saṃjñā tags, the derivation timeline for asiddhatva/sthānivadbhāva queries. `CompiledSutra.matches(left, right, context=None)` already has the `context` param; we thread this through it.
**Note:** This is a rebuild (not a port) of `rule_engine/context.py`'s shape, owned by `sanskrit_dsl`, with no import dependency on `rules/engine.py`.

#### 2b. New `sanskrit_dsl/derivation_timeline.py` — state timeline + asiddhatva
**New file:** `sanskrit_dsl/derivation_timeline.py`
**What:** A `DerivationTimeline` class recording an ordered list of `DerivationStep(sutra_id, rule_chapter, rule_pada, left_before, right_before, left_after, right_after, sthani_tags)`. Methods:
- `checkpoint(chapter, left, right)` — record the state *before* any rule in a chapter fires.
- `get_state_before_chapter(chapter) -> (left, right)` — the pūrvatrāsiddham query: "what did the boundary look like before chapter N rules touched it?"
- `is_visible(current_chapter, rule_chapter) -> bool` — within Tripāḍī (8.2–8.4), a rule in pāda M is invisible to pāda N if M > N (i.e., `rule_pada <= current_pada`); outside 8.x, always visible.
- `last_chapter_applied()`, `rules_applied()`.
**Why:** This is what makes `rAmeSa` survive — after 6.1.87 fires, 6.1.52 must consult the timeline and see it is *not* allowed to fire on the 6.1 output in the same pass, or must see the pre-6.1 state.

#### 2c. Saṃjñā layer — extend `SutraContext` + wire `SanjanaTagger` into the executor
**File:** `sanskrit_dsl/types.py`
**What:** Add fields to `SutraContext`:
- `sanjna_required: Set[str]` — the token must carry these saṃjñā tags (e.g., `{"dhatu"}`, `{"sup"}`).
- `prohibit_if_sanjna: Set[str]` — block if the token has *any* of these.
- `sthani_phoneme: Optional[str]` — match the original (sthāni) phoneme via the timeline.
- `morphological_category: Optional[str]` — `'avyaya'`, `'nipata'`, `'dhatu'`, `'sup'`, etc.
Extend `_context_matches` to consult the `ExecutionContext`: when `sanjna_required` is non-empty, return `False` unless `context.has_sanjna(side, name)` for all; when `prohibit_if_sanjna` is non-empty, return `False` if any matches. When `sthani_phoneme` is set, match against `trace.get_original_left_boundary()`, not the current mutated string.
**File:** `sanskrit_dsl/parser.py`
**What:** `_from_llm_row` must populate `sanjna_required`/`prohibit_if_sanjna` from two new LLM JSON columns (`sanjna_required`, `prohibit_if_sanjna`) added to `llm_extracted_metadata` (schema migration in 2h). Also teach `_ctx_from_llm_term` to recognize saṃjñā labels (e.g., when target is `aci`, set `sanjna_required={"ac"}` if 1.1 defines `ac` as a saṃjñā, rather than treating it as exact text).
**File:** `core/sanjña_tagger.py`
**What:** Extend `SANJÑA_PREDICATES` with the missing saṃjñās needed for 3.x–8.x: `ac`/`iK`/`aK`/`hal` (pratyāhāra saṃjñās from 1.1), `dhatu`, `sup`, `ting`, `krt`, `ardhadhatuka`, `sarvadhatuka`, `gati`, `sarvanamasthana`. Where a predicate needs morphology (gana, lakara), read `morphological_features` from the `ExecutionContext`. Document that predicates depending on an unwired morphology layer degrade gracefully (return `False`).
**Why this is the full layer (not deferred):** per the locked decision "Full saṃjñā layer now". Without saṃjñā-gated matching, 3.x/4.x derivation rules cannot fire correctly and the engine stays a 6.1-only sandhi toy.

#### 2d. Executor redesign — `sanskrit_dsl/executor.py`
**File:** `sanskrit_dsl/executor.py`
**What:** Replace the single-pass two-phase `execute_sandhi` with a staged executor mirroring the Pāṇinian prakriyā:
1. **Snapshot** the original `(left, right)` as an immutable `DerivationTimeline.checkpoint` before any rule fires.
2. **Phase 0 — Nipātana lookup:** consult the `nipatana_lexicon` table (already exists); if the pair is an irregular ready-made form, return it with `source="nipatana"`.
3. **Phase 1 — Saṃjñā tagging:** call `SanjanaTagger.tag(left, right, morph)` and write the result into `ExecutionContext.sanjna_map`.
4. **Phase 2 — Pragṛhya prakṛtibhāva (6.1.125):** if `left` carries the `pragrhya` saṃjñā and `right` starts with a vowel, return the un-joined pair (no sandhi). This is a real rule we currently miss.
5. **Phase 3 — Sapādāsaptādhyāyī (1.1–8.1):** iterate to a fixpoint (cap at ~15 steps to prevent runaway): filter matching sapāda rules, pick the winner via the rebuilt conflict resolver (2e), apply, record a `DerivationStep`, re-filter against the new state. **Crucially:** before applying a candidate, consult `DerivationTimeline.is_visible(current_chapter, rule_chapter)` — though outside the Tripāḍī this is always true, this is where it plugs in.
6. **Phase 4 — Tripāḍī (8.2–8.4):** iterate in *strict chapter order* (8.2 rules, then 8.3, then 8.4). For each rule, before matching, call `DerivationTimeline.get_state_before_chapter(rule_chapter)` and match against *that* snapshot — not the mutated current state. This is pūrvatrāsiddham: an 8.2 rule sees the pre-8.3 state, not the post-8.3 state. Apply the winner, record the step, advance.
7. Return `{"joined", "applied_rule_ids", "trace_steps", "timeline"}`. The `timeline` is new and is what the testing pipeline (Milestone 3) inspects.
**Why:** This fixes the cascading-corruption bug (6.1.52 on 6.1.87), the over-application bug (6.1.87 on a+a), and the Tripāḍī invisibility bug, in one coherent model.

#### 2e. Conflict resolution rebuild — `sanskrit_dsl/meta_engine.py`
**File:** `sanskrit_dsl/meta_engine.py`
**What:** Rebuild `AntarangaResolver.resolve` and `MetaRuleEngine.resolve_conflict`:
- **Numeric ordering:** add `_sutra_sort_key(sutra_id) -> (adhyaya, pada, sutra_no)` tuple; "later-sūtra-wins" uses tuple sort, not lexicographic string sort. Fixes `6.1.9` vs `6.1.77`.
- **Weighted specificity:** exact-text target `1000 - 100·N`; pratyahara target `100 - |phonemes|`; left/right context weighted by *type* (exact-text `+80`, pratyahara `+40`, saṃjñā-gated `+120`, sthāni `+60`), not flat `+50`. A savarṇa meta-term condition counts as `+90` (it's a tight constraint).
- **Antaraṅga via conditioning_factors + context-subset:** an inner rule is antaraṅga if its *full condition set* (target + left + right + saṃjñā-required) is a proper subset of the outer's. Don't gate only on `conditioning_factors` being non-empty.
- **Apavāda / niyama:** if any candidate has `rule_type == "niyama"` (prohibition) and its scope subsumes a vidhi candidate's, the vidhi is debarrred (removed from candidates). If a candidate's `applicable_paribhasas` includes a paribhāṣā that `ParibhashaRegistry` evaluates as "debar", remove it.
- **Paribhāṣā consultation:** `MetaRuleEngine.resolve_conflict` calls `paribhasas.applies_to(sutra_id, specs)` and, for each returned paribhāṣā, evaluates its axiom (initially: just `vipratisedhe parah karyam` = later-wins, and `sthanetaratamah` = closest substitute; others recorded as TODO).
- **Parasavaraṇa priority (the key fix for 6.1.101 vs 6.1.87):** when two rules match and one requires `savarRa` (homogeneous) and the other doesn't, the savarṇa rule wins for homogeneous pairs. Encode this as: a rule whose right_context is the savarṇa meta-term gets `+150` specificity *when the pair is actually savarṇa* (checked via `_is_savarna`), making it outscore a non-savarṇa rule on the same pair.
**Why:** This is what makes `rAma+atra` pick 6.1.101 (dirgha, savarṇa) over 6.1.87 (guṇa, plain aC), and `vadi+iti` pick 6.1.101 over 6.1.77 (yaṇ).

#### 2f. Anuvṛtti at runtime — wire `AnuvrttiTracker.get_inherited`
**File:** `sanskrit_dsl/executor.py`
**What:** During Phase 3/4 iteration, before filtering matches, call `anuvrtti.get_inherited(spec)` for any compiled sūtra whose target/contexts are empty — fill them from the active carried slots. Call `anuvrtti.step(spec)` after each application (not just at compile time). Carry `right_context` forward (currently tracked but never inherited).
**File:** `sanskrit_dsl/meta_engine.py`
**What:** Fix `AnuvrttiTracker.get_inherited` to also inherit `right_context`; reset `active_right_context` on domain change.

#### 2g. Extend `CompiledSutra.matches` / `apply` to use `ExecutionContext`
**File:** `sanskrit_dsl/types.py`
**What:** `matches(left, right, context)`: if `context` is an `ExecutionContext`, pass it to `_context_matches` so saṃjñā-gated and sthāni conditions can be evaluated. `apply(left, right, context)`: record a `DerivationStep` on `context.trace` (the apply itself stays a pure string transform, but it *also* logs to the timeline so asiddhatva queries work).
**Why:** the `context` param already exists; this is non-breaking.

#### 2h. DB schema migration for saṃjñā fields
**File:** `tools/llm_sutra_extractor.py` (`ensure_table`) + a one-time migration script `tools/migrate_sanjna_fields.py`
**What:** Add columns `sanjna_required TEXT`, `prohibit_if_sanjna TEXT`, `sthani_phoneme TEXT`, `morphological_category TEXT` to `llm_extracted_metadata`. Update `EXTRACTION_SCHEMA` to ask the LLM for these. Update `_from_llm_row` to read them.
**Why:** the saṃjñā layer needs the LLM to extract saṃjñā-requires/prohibits per sūtra; the DB must store them.

---

### MILESTONE 3 — Testing-Pipeline Overhaul (so this can never recur)

This is the user's explicit demand: document why these issues weren't flagged, and fix the pipeline so they will be.

#### 3a. New `tests/test_meta_engine.py` — unit tests for conflict resolution, asiddhatva, anuvṛtti, antaraṅga, saṃjñā
**New file:** `tests/test_meta_engine.py`
**What:** Gate tests for each meta-rule mechanism:
- `test_numeric_sutra_ordering`: `6.1.9` sorts before `6.1.77` (tuple key), not after.
- `test_parasavarna_priority`: given 6.1.87 (guṇa, aC) and 6.1.101 (dirgha, savarRa) both matching `rAma+atra`, the winner is 6.1.101.
- `test_prohibit_debars_vidhi`: a niyama candidate removes a matching vidhi.
- `test_asiddhatva_tripadi`: an 8.3 rule does not see an 8.2 rule's output (construct a minimal pair from the extracted 8.2/8.3 data).
- `test_anuvrtti_carries_right_context`: a sūtra with empty right_context inherits the carried one.
- `test_sanjna_gated_match`: a rule requiring `sanjna_required={"dhatu"}` does not match a non-dhatu token.
- `test_pragrhya_short_circuit`: `pragrhya` + vowel-initial right → no sandhi.
- `test_sthani_match`: `sthani_phoneme` matches the *original* boundary, not the mutated one.

#### 3b. New `tests/test_sanjna_tagger.py` — saṃjñā assignment tests
**New file:** `tests/test_sanjna_tagger.py`
**What:** Test that `SanjanaTagger.tag` assigns the correct saṃjñās for: pragṛhya (dual endings, daśa, se-endings, nipāta single-vowel, oṭ pragṛhya), padānta, āmreḍita, nipāta, avyaya, and the new pratyāhāra/dhātu/sup/tiṅ/kṛt predicates added in 2c.
**Why:** saṃjñā tagging had *zero* test coverage — the root cause of the blind spot.

#### 3c. New `tests/test_execution_context.py` — timeline + asiddhatva state tests
**New file:** `tests/test_execution_context.py`
**What:** Test `DerivationTimeline.checkpoint`, `get_state_before_chapter`, `is_visible` directly: construct a timeline with steps in chapters 8.2 and 8.3, verify an 8.3 rule sees the pre-8.3 checkpoint, verify `is_visible("8.2", "8.3")` is False.

#### 3d. Fixtures: add Tripāḍī, saṃjñā, derivation cases; de-calibrate the 6.1.89 fixture
**File:** `tests/fixtures/panini_blackbox_cases.json`
**What:**
- Remove the note on the 6.1.89 family that calibrated it to the engine's wrong attribution; re-attribute it to 6.1.88 (vṛddhi) with correct expected outputs (`tavEva`, `nEva`) — these now *fail honestly* until 2e's parasavaraṇa fix lands.
- Add Tripāḍī cases: 8.2.66 (saḥ suḥ visarga), 8.3.23 (mo ḥnusvānaḥ anusvāra before consonants), 8.3.15 (bho obhāṇ), 8.2.1 scope (a case where an 8.3 rule must *not* see an 8.2 output).
**File:** `tests/fixtures/morphology_blackbox_cases.json`
**What:** Add 3.1.x vikaraṇa cases, 4.1.x sup cases, tagged to real derivational sūtras (not 1.1.1). These fail until 3.x/4.x extraction.
**New file:** `tests/fixtures/sanjna_blackbox_cases.json`
**What:** Cases gating saṃjñā assignment: e.g., "does `dvi` carry the pragṛhya saṃjñā", "does `kṛ` carry the dhātu saṃjñā". These test the *tagger*, not sandhi output.

#### 3e. Pipeline: inspect `trace_steps` + `timeline`; new "derivation-correctness" classification
**File:** `benchmarks/reports.py`
**What:** Stop dropping `trace_steps` from `benchmark_results_payload` — include them so tests can assert on ordering.
**File:** `benchmarks/pipeline.py`
**What:** Add a `derivation_correct` flag to the summary: a case is derivation-correct iff `output_match` AND the `applied_rule_ids` trace, in order, matches the expected derivation sequence (declared per case in a new optional `expected_trace` field in fixtures). This is the shift from "output equality" to "derivation correctness".
**File:** `benchmarks/catalog.py`
**What:** Add classification `meta_rule_unverified` for sūtras that fire but whose paribhāṣā/asiddhatva interaction wasn't exercised — so the catalog honestly reports "we don't know if the meta-rules worked" instead of silently passing.
**File:** `benchmarks/local_engine_adapter.py`
**What:** Strengthen the hardcoding heuristic: if `actual == expected_output` but the `trace_steps` don't show the *expected* rule's conditions being satisfied (right context matched, saṃjñā present), flag as hardcoding. This catches "right output via wrong rule" — the current heuristic's blind spot.

#### 3f. Document the blind spots — `docs/TESTING_PIPELINE_AUDIT.md`
**New file (explicitly requested by user):** `docs/TESTING_PIPELINE_AUDIT.md`
**What:** A written record of *why* the saṃjñā gap, the meta-rule unwiring, and the conflict-resolution bugs shipped undetected, with the evidence from Phase 1:
1. `executed` was output-equality, not derivation-correctness.
2. `trace_steps` collected but dropped from reports.
3. Fixtures confined to 6.1 + 3.4.78/8.2.66; one calibrated to wrong engine output.
4. No test imported any meta-engine symbol.
5. Hardcoding heuristic only caught nominal-id-absence.
And what 3a–3e change to prevent recurrence. This is the "document all these important changes" the user demanded.

---

### MILESTONE 4 — Batch Extraction for Definitional Sūtras (all chapters)

#### 4a. Run batch extraction for 1.x saṃjñā + paribhāṣā sūtras
**Commands:**
```bash
for ch in 1.1 1.2 1.3 1.4 2.x; do
  python3 tools/llm_sutra_extractor.py --chapter $ch --batch-definitions --model deepseek-v4-pro:cloud --delay 3
done
```
**Why:** the saṃjñā layer (2c) needs the definitional sūtras extracted so `sanjna_required`/`prohibit_if_sanjna` can reference real labels.

#### 4b. Per-sūtra extraction for remaining operational chapters (3.x, 4.x, 5.x, 7.x)
**Commands:** per chapter, `--model deepseek-v4-pro:cloud --delay 3` (no `--batch-definitions`).
**Why:** operational sūtras stay per-sūtra (proven, low JSON risk).

---

### MILESTONE 5 — Morph derivation through the DSL (after 3.x/4.x extracted)

#### 5a. Real `MorphExecutor` derivation chains
**File:** `sanskrit_dsl/morph_executor.py`
**What:** Replace the current stub (which just calls `DSLExecutor.execute_sandhi` on root+vikaraṇa) with a real multi-step derivation that applies 3.1.x (vikaraṇa), 3.4.78 (tiṅ), then sandhi (6.1.x) + final adjustment (7.x + 8.x), recording each step on a `DerivationTimeline`. Only fall back to the DB-lookup `TinantaGenerator`/`SubantaGenerator` when a required sūtra isn't compiled (tag `source="db_fallback"`, no evidence).
**Why:** end goal — paste sūtras, engine derives forms. This is where the saṃjñā layer pays off: 3.x rules condition on "where a tiṅ affix follows" = `sanjna_required={"ting"}`.

---

## Assumptions & Decisions (locked)

1. **State model:** rebuild inside `sanskrit_dsl` (`execution_context.py`, `derivation_timeline.py`), no import dependency on `rules/engine.py`. Old path stays alive (still used by `morphology/sandhi.py`). Per user: "Rebuild, keep old alive".
2. **Sequencing:** Tripāḍī extraction (8.2–8.4) + 1.1 saṃjñā definitions FIRST, then executor + saṃjñā rebuild, so the redesign has real asiddhatva + saṃjñā data to validate against. Per user: "Tripāḍī extraction first".
3. **Batch extraction:** hybrid — batch the definitional (S$/P$) sūtras per pāda (full adhikāra/anuvṛtti scope in one call), per-sūtra for operational (V$) sūtras. Per user: "Hybrid: batch definitions only".
4. **Saṃjñā layer:** full layer now — tagger extension + `SutraContext` saṃjñā fields + `_context_matches` consulting `ExecutionContext`. Per user: "Full saṃjñā layer now".
5. **LLM model:** `deepseek-v4-pro:cloud` only (cloud pro models, per earlier constraint).
6. **No hardcoding:** the engine never special-cases a form; irregulars go in the `nipatana_lexicon` and are looked up in Phase 0.
7. **Testing pipeline:** shift from output-equality to derivation-correctness; inspect `trace_steps`/`timeline`; add meta-engine unit tests; de-calibrate the 6.1.89 fixture; document blind spots in `docs/TESTING_PIPELINE_AUDIT.md`.
8. **Exceptions (later commentators):** hardcode as lexicon entries in `nipatana_lexicon`, never in the rule engine. Per user.
9. **Runtime LLM:** never — LLM is extraction-time only; runtime is pure Python.

---

## Verification Steps

```bash
# M1: Tripāḍī + 1.1 extraction
sqlite3 data/sanskrit_master.db "SELECT substr(sutra_id,1,3), COUNT(*) FROM llm_extracted_metadata GROUP BY substr(sutra_id,1,3)"
# expect rows for 1.1, 6.1, 8.2, 8.3, 8.4

# M2: executor + saṃjñā + meta-engine
python3 -m pytest tests/test_meta_engine.py tests/test_sanjna_tagger.py tests/test_execution_context.py -v
python3 -m pytest tests/test_dsl_unit.py -v   # 6.1.77/87/88/101 still pass
# Key regression: rAma+atra -> rAmAtra [6.1.101] (not 6.1.87); rAma+ISa -> rAmeSa (not corrupted)

# M2: asiddhatva on real Tripāḍī data
python3 -c "from sanskrit_dsl.executor import DSLExecutor; ..." # construct an 8.2/8.3 pair, verify is_visible

# M3: testing pipeline
python3 -m pytest tests/test_benchmark_integrity.py -v   # gates now inspect trace + timeline
python3 -m pytest -q   # full suite

# M4: batch extraction quality comparison
sqlite3 data/sanskrit_master.db "SELECT COUNT(*) FROM llm_extracted_metadata WHERE sutra_id LIKE '1.1.%'"

# M5: morph
python3 -m pytest tests/test_benchmark_integrity.py::test_morphological_execution -v
```

**Exit criteria:**
- Tripāḍī (8.2–8.4) + 1.1 saṃjñā definitions extracted; `llm_extracted_metadata` covers them.
- `DerivationTimeline` enforces asiddhatva: an 8.3 rule does not see an 8.2 rule's output (unit-tested).
- `rAma+atra → rAmAtra [6.1.101]` (parasavaraṇa priority works); `rAma+ISa → rAmeSa` (no cascade corruption).
- Saṃjñā-gated rule matching works (unit-tested: a `dhatu`-required rule rejects a non-dhātu).
- `test_meta_engine.py`, `test_sanjna_tagger.py`, `test_execution_context.py` pass.
- Benchmark gates inspect `trace_steps`; a "right output via wrong rule" case is flagged as hardcoding.
- `docs/TESTING_PIPELINE_AUDIT.md` documents the blind spots and the fixes.
- No new hardcoding; `test_no_hardcoding` continues to pass.