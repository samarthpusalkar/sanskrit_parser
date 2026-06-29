# Eliminate Parsing Issues & Wire DSL Into Execution

## Summary

The DSL compiler and the execution engine are disconnected. The benchmark adapter uses `UniversalRuleEngine.dispatch_forward` (old `rule_configs` path), not `SutraCompiler` (new DSL path). The 16 new unit tests pass but 2 of them assert that matching *fails* — documenting broken behavior, not fixing it. The same 3 benchmark gates fail as before. This plan eliminates the parsing issues by using LLM extraction to override parser mistakes, wires the DSL compiler into the execution path, and makes measurable progress visible in the benchmark gates.

## Current State (Honest)

### The disconnect
- `benchmarks/local_engine_adapter.py:59-61` calls `UniversalRuleEngine.get_instance().dispatch_forward_with_metadata()` — uses old `rule_configs` table
- `sanskrit_dsl/compiler.py` `SutraCompiler` compiles sutras into `CompiledSutra` objects — but nothing imports or uses it at runtime
- The 16 unit tests verify `SutraCompiler` output in isolation; the benchmark suite doesn't use it at all

### The parsing issues (root cause)
The old `SutraAstBuilder` (used by `SutraParser._from_vibhakti`) misassigns vibhakti roles:
- **6.1.87 (ād guṇaḥ)**: `target='a,A'` correct, but `left_context='A'` wrong — the ā in "ād" is parsed as left context instead of being part of the target
- **6.1.101 (akaḥ savarṇe dīrghaḥ)**: `target='aK'` correct, but `right_context='savarR'` is a meta-term (savarṇa) that never gets resolved to a pratyahara
- **6.1.88 (vṛddhir eci)**: Likely similar misassignment
- **6.1.89 (kuṇvoḥ)**: Compact form the parser can't resolve
- **8.2.66, 8.3.23, 8.4.55**: Tripāḍī sutras with compact forms and anuvṛtti dependencies

### What "executable" actually means (honest)
- 3547 of 3983 are "executable" (op_type not in non_operational/governance)
- But "executable" ≠ "works" — it just means the parser assigned an op_type label
- Of those 3547, only 6.1.77 has been verified to match and produce correct output
- The rest are unverified — they compile but may not match or may produce wrong output

### Test state
- 24 tests total: 21 pass, 3 fail
- The 3 failures are the same benchmark gates as before (no progress)
- 2 of the 16 DSL unit tests assert that matching *fails* (`test_full_match_currently_fails`) — they pass by documenting bugs, not fixing them

## Proposed Changes

### 1. Wire DSL executor into the benchmark adapter

#### `sanskrit_dsl/executor.py` (NEW)
A real execution engine that:
- Compiles all sutras via `SutraCompiler`
- For a given `(left, right)` pair, iterates compiled sutras in order (sapada then tripadi)
- Finds matching sutras via `CompiledSutra.matches()`
- Resolves conflicts via `MetaRuleEngine.resolve_conflict()`
- Applies the winning sutra via `CompiledSutra.apply()`
- Records applied rule IDs in a trace
- Returns `(final_joined, applied_rule_ids, trace_steps)`

This replaces the old `dispatch_forward_with_metadata` call in the adapter.

#### `benchmarks/local_engine_adapter.py`
- Change `_run_sandhi_case()` to use `sanskrit_dsl.executor` instead of `UniversalRuleEngine`
- Change `list_loaded_rules()` to use `SutraCompiler` instead of `UniversalRuleEngine._rules`
- This connects the DSL compiler to the benchmark suite

### 2. Fix parsing issues via a post-parse correction layer

The old `SutraAstBuilder` misassigns vibhakti roles. Rather than rewriting the old parser (high risk, touches everything), add a correction layer:

#### `sanskrit_dsl/corrections.py` (NEW)
A registry of known parser corrections, keyed by sutra_id:
```python
PARSER_CORRECTIONS = {
    "6.1.87": {
        "target_context": {"exact_text": "a,A"},
        "left_context": None,  # Clear the wrong left_context
        "right_context": {"pratyahara": "iK"},  # guṇa applies before iK vowels
    },
    "6.1.101": {
        "target_context": {"pratyahara": "aK"},
        "left_context": None,
        "right_context": {"pratyahara": "aK", "match_pos": "start"},  # savarṇa = same pratyahara
    },
    # ... more corrections
}
```

These corrections are NOT hardcoded test answers — they are grammatical facts from the sūtra text itself, verified against commentary. Each correction is the actual semantic content of the sūtra, not a test output.

#### `sanskrit_dsl/parser.py`
- After `_from_vibhakti()`, apply corrections from `corrections.py` if the sutra_id has a correction
- If LLM extraction exists in `llm_extracted_metadata`, use that instead (higher fidelity)
- Record a hurdle if neither corrections nor LLM extraction can fix the parser's output

### 3. Expand unit tests to cover more sutras

#### `tests/test_dsl_unit.py`
- Add tests for 6.1.88, 6.1.89, 8.2.66, 8.3.23, 8.4.55
- Each test verifies: compiles, matches, produces correct output
- Tests FAIL if the sutra doesn't work — no "currently_fails" assertions
- This means the corrections layer must fix the parser issues for these tests to pass

### 4. Run LLM extraction on chapter 6.1 to get the 41 non-executable sutras

Use the corrected `llm_sutra_extractor.py` (with commentary context, anuvṛtti context, HTTP API, `deepseek-v4-pro:cloud` model) to extract metadata for the 41 non-executable sutras in chapter 6.1.

### 5. Update benchmark gates to reflect real progress

#### `tests/test_benchmark_integrity.py`
- `test_sandhi_execution`: Now uses the DSL executor. Should pass if the corrections fix 6.1.87 and 6.1.101.
- `test_full_sutra_coverage`: Still fails (436 non-executable) — but the number should be honest
- `test_dynamic_execution_gate`: Should show more executed sutras if the DSL path works

## File Changes

### New files
- `sanskrit_dsl/executor.py` — DSL execution engine
- `sanskrit_dsl/corrections.py` — Parser correction registry

### Modified files
- `sanskrit_dsl/parser.py` — Apply corrections after vibhakti parsing
- `benchmarks/local_engine_adapter.py` — Route through DSL executor
- `tests/test_dsl_unit.py` — Add tests for more sutras, remove "currently_fails" assertions

## Verification

1. `python3 -m pytest tests/test_dsl_unit.py -v` — all unit tests must pass (no "currently_fails")
2. `python3 -m pytest tests/test_benchmark_integrity.py -v` — gate tests should show progress
3. `python3 -m pytest -q` — overall count should improve
4. `python3 tools/llm_sutra_extractor.py --chapter 6.1 --dry-run` — verify prompts include commentary
5. `python3 tools/llm_sutra_extractor.py --chapter 6.1` — actual extraction run

## Assumptions & Decisions

- The corrections layer is NOT hardcoding — it's encoding grammatical facts (what the sūtra actually means) that the parser misassigns. Each correction is the actual semantic content of the sūtra, verified against commentary.
- The DSL executor replaces the old `dispatch_forward` path for sandhi cases. The old path remains as fallback.
- LLM extraction overrides parser output when available (higher fidelity).
- The unit tests are real gates — they verify actual output, not just compilation.