# Testing Pipeline Audit — Why the Saṃjñā / Meta-Rule Gaps Shipped Undetected

**Date:** 2026-07-01  
**Scope:** `sanskrit_dsl/` path + `benchmarks/` + `tests/`  
**Author:** implementation audit, written during Milestone 3 of the proper-Sanskrit-engine rebuild.

---

## Executive Summary

The engine reached a point where it could join `hari + atra -> haryatra`, yet four foundational systems (saṃjñā layer, asiddhatva, conflict resolution, conditioning-factor enforcement) were broken or unwired. The testing pipeline did not catch them because it was designed as an *output-equality + inventory* gate, not a *derivation-correctness* gate. This document records exactly how each gap escaped detection, and the concrete test/pipeline changes that prevent recurrence.

---

## 1. The Four Gaps and How They Escaped Detection

### 1.1 No saṃjñā layer in the DSL executor

**What existed:** `core/sanjña_tagger.py` was wired only into the old `rules/engine.py`; `sanskrit_dsl/executor.py` never called it. `SutraContext` had no `sanjna_required` / `prohibit_if_sanjna` fields, so 3.x–7.x rules that condition on labels like `dhatu`, `sup`, `tiṅ` could not fire correctly.

**Why tests missed it:**
- `tests/` had zero references to `sanjna`, `SanjanaTagger`, or saṃjñā-gated matching.
- The benchmark fixtures contained only 6.1 sandhi cases, which do not require morphological labels.
- `CompiledSutra.matches` accepted a `context` parameter but never used it, and no test asserted that it should.

**Fix:**
- Extended `SutraContext` with `sanjna_required`, `prohibit_if_sanjna`, `sthani_phoneme`, `morphological_category`.
- Extended `core/sanjña_tagger.py` with pratyāhāra (`ac`, `iK`, `aK`, `hal`) and derivational (`dhatu`, `sup`, `tiṅ`, `kṛt`, `ārdhadhātuka`, `sārvadhātuka`, `gati`, `sarvanāmasthāna`) predicates.
- Wired `SanjanaTagger` into `sanskrit_dsl/executor.py` Phase 1 and made `_context_matches` consult `ExecutionContext`.
- Added `tests/test_sanjna_tagger.py` with 12 assertions covering phonological and morphological saṃjñās.

### 1.2 No asiddhatva / state-timeline in the executor

**What existed:** `AsiddhatvaEnforcer` lived in `meta_engine.py` but was never invoked. The executor shadowed `(left, right)` into `cur_left/cur_right`, applied one sapāda rule then one tripāḍī rule, and let later rules corrupt earlier correct output.

**Why tests missed it:**
- No test exercised the Tripāḍī boundary.
- No test inspected `trace_steps` ordering.
- The pipeline classified a sutra as `executed` based on output match, regardless of whether the derivation sequence was valid.

**Fix:**
- Added `sanskrit_dsl/derivation_timeline.py` with `DerivationTimeline`, per-chapter `checkpoint()`, `get_state_before_chapter()`, and `is_visible()`.
- Rewrote `sanskrit_dsl/executor.py` as a staged prakriyā: snapshot → saṃjñā → pragṛhya → sapāda single best rule → Tripāḍī per pāda with strict ordering.
- Added `tests/test_execution_context.py` and `tests/test_meta_engine.py::TestAsiddhatva` to assert checkpoint/visibility behavior directly.
- Pipeline now includes `trace_steps` in `benchmark_results_payload` and reports `meta_rule_unverified` classification when output matches but trace was not verified.

### 1.3 Conflict resolution was wrong

**What existed:** `AntarangaResolver.resolve` used flat `+50` per context regardless of type, and its later-sūtra-wins fallback sorted `sutra_id` *lexicographically* (`"6.1.9" > "6.1.77"`). There was no parasavaraṇa priority, no apavāda/niyama debar, and `ParibhashaRegistry.applies_to` was never consulted.

**Why tests missed it:**
- The only conflict test was accidental: `rAma + atra` was expected to produce `rAmAtra` via 6.1.101, but the engine was actually picking 6.1.87 at one point; the fixture expected the right output for the right reason, but there was no unit test isolating the resolver.
- No fixture exercised `6.1.9` vs `6.1.77` numeric ordering.
- No fixture required parasavaraṇa to win (6.1.101 over 6.1.87 on homogeneous pairs).

**Fix:**
- Added `_sutra_sort_key` returning `(adhyaya, pada, sutra_no)` tuple.
- Rewrote `AntarangaResolver.resolve` with weighted specificity (exact=1000, pratyāhāra=40–100, saṃjñā=120, sthāni=60, savarṇa=90) and `+150` parasavaraṇa bonus.
- Added apavāda/niyama debar and parasavaraṇa debar in `MetaRuleEngine.resolve_conflict`.
- Added `tests/test_meta_engine.py::TestNumericOrdering`, `TestParasavarnaPriority`, and a pragṛhya short-circuit test.

### 1.4 Conditioning factors were ignored

**What existed:** `CompiledSutra.matches` never checked `conditioning_factors`. Tripāḍī rules with semantic/morphological conditions (e.g., 8.2.67 word-specific, 8.2.77 `hali ca`, 8.2.104 finite-verb) fired on every phonological match and corrupted sandhi output.

**Why tests missed it:**
- Fixtures contained no Tripāḍī cases, so these rules never fired during benchmarks.
- `_context_matches` accepted `context` but never consulted conditioning factors.
- The `LocalEngineAdapter` routed every `sandhi` case through the same executor, so once Tripāḍī data arrived, the corruption surfaced immediately.

**Fix:**
- Added `_passes_conditioning_factors` and `_filter_matching` in `sanskrit_dsl/executor.py`.
- Implemented a blacklist of non-evaluable semantic/morphological keywords (sentence, finite verb, root, pluta, etc.) and a strict mode for Tripāḍī.
- Added structural guards: bare-pratyāhāra Tripāḍī targets and vowel-sandhi op_types in Tripāḍī are blocked from the sandhi pass.
- Calibrated fixtures: `hotf + fzya` now expects `hotFzya` (6.1.101, savarṇa dīrgha), and the 6.1.89 family is correctly re-attributed to 6.1.88.

---

## 2. Pipeline Changes That Prevent Recurrence

### 2.1 From output-equality to derivation-correctness

Previously, `executed_rule_ids` was defined as cases where `output_match and rule_expectation_match and not hardcoding_suspected`. Now the pipeline:

- Includes `trace_steps` in `benchmark_results_payload` (was dropped before).
- Computes `trace_verified_ids` from `derive_trace_verified_ids()`.
- Adds `meta_rule_unverified` classification for sutras whose output matches but whose trace was not verified.
- Adds `meta_rule_unverified_sutras` and `trace_verified_sutras` to the summary.

This means a sutra can no longer be considered fully `executed` simply because the final string matches; the derivation path must be present and, where declared, must match the expected ordered rule sequence.

### 2.2 New test files

| Test file | What it guards |
|-----------|----------------|
| `tests/test_meta_engine.py` | Numeric ordering, parasavaraṇa, asiddhatva, anuvṛtti, non-executable rules. |
| `tests/test_sanjna_tagger.py` | Phonological saṃjñās (`ac`, `iK`, `aK`, `hal`), pragṛhya, morphological predicates. |
| `tests/test_execution_context.py` | `ExecutionContext` saṃjñā isolation and `DerivationTimeline` checkpoint/visibility. |

### 2.3 Fixture honesty

- Removed the note that calibrated the 6.1.89 family to the engine's wrong attribution.
- Re-attributed `tava+eva` and `na+eva` to 6.1.88.
- Corrected `hotf+fzya` to `hotFzya` (6.1.101) rather than the incorrect `hotrfzya`.

---

## 3. Remaining Known Limitations

- **Morphology executor:** `MorphExecutor.conjugate`/`decline` still uses placeholder logic. The morphological benchmark cases fail (expected until M4/M5 build a real derivation pipeline).
- **Full sutra coverage gate:** `test_full_sutra_coverage` intentionally fails because 3,979 of 3,983 sutras are not yet benchmarked/executed. This is a coverage gate, not a bug.
- **Tripāḍī sandhi rules:** True phonological Tripāḍī rules (e.g., visarga sandhi 8.2.66, 8.3.15, 8.3.23, natva 8.4) require additional fixture cases and careful conditioning-factor validation. They are now *safe* from corrupting 6.1 output, but not yet positively exercised.

---

## 4. Conclusion

The original pipeline passed because it only asked: "did the output string match?" It never asked: "did the right rule fire?", "did the timeline enforce asiddhatva?", "were saṃjñā labels consulted?", or "did a semantic rule corrupt a phonological one?". The new tests and pipeline metrics ask those questions explicitly. Future regressions in these mechanisms will fail immediately, not after months of silent wrong output.
