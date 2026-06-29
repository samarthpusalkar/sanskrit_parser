# Paninian Benchmark Harness Plan

## Summary

Replace the current legacy test/coverage setup with a benchmark-driven black-box
Paninian validation pipeline that:

- treats the `sutras` table in `data/sanskrit_master.db` as the canonical
  universe of rules to measure;
- reports coverage separately for:
  - canonical sutra universe,
  - executable `rule_configs` coverage,
  - actual black-box runtime execution coverage;
- distinguishes "rule exists in a hardcoded list" from "rule is dynamically
  loaded and actually fires" by requiring rule-inventory evidence, derivation
  evidence where available, and perturbation/negative-control cases;
- supports external engine benchmarking through an abstract adapter contract
  without making fake coverage claims for Ambada or any other tool;
- fails only on integrity issues, adapter violations, hardcoding indicators, and
  frozen-baseline regressions, while still always generating truthful unmapped
  coverage reports.

## Current State Analysis

### Existing files and behavior

- `tests/test_panini_rule_coverage.py`
  - only checks whether IDs from `rule_configs` appear in either
    `UniversalRuleEngine._rules` or `load_sandhi_rules(...)`;
  - does not prove runtime execution, derivation correctness, or full 4000-rule
    black-box coverage;
  - uses `rule_configs` as the universe, not `sutras`.

- `tools/coverage_validator.py`
  - reports active vs passive operations from DB metadata;
  - is useful as a truth metric, but it is not a benchmark suite and does not
    test execution.

- `tools/dynamic_execution_sampler.py`
  - tries heuristic case synthesis per active rule;
  - checks only whether output changed, which is too weak to distinguish dynamic
    execution from brittle/hardcoded behavior.

- `tools/rule_coverage_report.py`
  - reports mapping gaps between DB, compiled engine, and loader;
  - again, presence/reporting only, not black-box execution.

- `tools/ambada_adapter.py`
  - provides a useful shape for an adapter, but currently uses a mock 2000-rule
    generator and mock outputs, which would create false confidence.

- `rules/engine.py`
  - already builds a real `DerivationTrace` internally during
    `dispatch_forward(...)`;
  - currently returns only `(left, right)` output, so the benchmark layer cannot
    yet consume trace evidence directly.

- `rule_engine/trace.py`
  - already records applied rule IDs and ordered derivation steps;
  - can serve as the evidence source for "dynamic rule fired" once surfaced to
    the benchmark harness.

- `morphology/sandhi.py`
  - exposes a black-box `SandhiEngine.join(...)` interface;
  - this is the cleanest current runtime surface for execution benchmarking.

- `pytest.ini`
  - currently only defines a `curated` marker from the previous testing model.

### Key gaps relative to the request

- The current suite does not measure all canonical rules from `sutras`.
- The current suite does not separate:
  - missing sutra extraction,
  - missing runtime loading,
  - missing dynamic execution,
  - output overfitting/hardcoding.
- The current external benchmark story is mocked rather than adapter-contract
  driven.
- The current tests optimize for local pass/fail rather than a frozen,
  benchmark-first grammar-development workflow.

## Assumptions And Decisions

- Canonical universe: use `sutras` as the top-level benchmark universe.
- Runtime scope for v1: full-engine reporting layer, but real black-box
  execution starts from the currently available sandhi interface and marks other
  domains as `adapter_pending` / `execution_unmapped`.
- Cleanup scope: remove all current legacy test and benchmark artifacts related
  to the old shallow coverage/heuristic benchmark direction.
- Failure mode: always generate reports, but only fail on integrity problems,
  hardcoding indicators, adapter-contract violations, or frozen-baseline
  regressions.
- External benchmarking: ship an abstract adapter contract plus canonical
  fixtures and runner support; do not keep mock rule-count coverage claims.

## Proposed Changes

### 1. Remove legacy shallow/heuristic benchmark artifacts

Delete these files because they encode the old benchmark model the user wants to
freeze and replace:

- `tests/test_panini_rule_coverage.py`
- `tests/forward_generation_test.json`
- `run_test_json.py`
- `tools/coverage_validator.py`
- `tools/dynamic_execution_sampler.py`
- `tools/rule_coverage_report.py`
- `tools/ambada_adapter.py`

### 2. Add a canonical benchmark package

Create a new package at `benchmarks/` to hold reusable benchmark logic instead
of scattering truth/reporting code across ad hoc scripts.

#### `benchmarks/__init__.py`
- package marker only.

#### `benchmarks/models.py`
- define shared dataclasses / typed structures for:
  - `RuleUniverseEntry`
  - `BenchmarkCase`
  - `BenchmarkResult`
  - `BenchmarkEvidence`
  - `CoverageSummary`
  - `AdapterCapabilities`
- include fields that explicitly separate:
  - `sutra_known`
  - `has_rule_config`
  - `loaded_by_runtime`
  - `executed_dynamically`
  - `adapter_supported`
  - `hardcoding_suspected`

#### `benchmarks/catalog.py`
- load the canonical sutra universe from `sutras`;
- join to `rule_configs` when present;
- produce the classification buckets:
  - `missing_rule_config`
  - `rule_config_only`
  - `runtime_unloaded`
  - `execution_unmapped`
  - `executed`
  - `adapter_pending`
- keep the authoritative logic for "what counts toward 4000-rule coverage."

#### `benchmarks/cases.py`
- load benchmark case fixtures from JSON;
- validate schema and normalize case groups;
- support positive cases, negative controls, and perturbation families so the
  same rule family is tested beyond a single memorized string pair.

#### `benchmarks/adapters.py`
- define the abstract contract for all benchmarked engines:
  - `name`
  - `supported_domains()`
  - `capabilities()`
  - `list_loaded_rules()`
  - `run_case(case)`
  - `batch_run(cases)` default implementation
- keep this adapter abstract and real; do not ship fake coverage adapters.

#### `benchmarks/local_engine_adapter.py`
- implement the in-repo adapter around the current engine;
- use `SandhiEngine.join(...)` / `UniversalRuleEngine.dispatch_forward(...)`
  for black-box execution;
- use `load_sandhi_rules(...)` and compiled engine rule IDs as inventory
  evidence;
- convert derivation evidence into benchmark-friendly structures once trace is
  exposed by the engine.

#### `benchmarks/reports.py`
- produce stable JSON/Markdown summaries for:
  - canonical coverage,
  - runtime-loaded coverage,
  - dynamically executed coverage,
  - unmapped sutras,
  - hardcoding suspicions,
  - external adapter comparison summaries.

#### `benchmarks/pipeline.py`
- orchestrate the end-to-end run:
  - load canonical sutras,
  - load benchmark cases,
  - execute selected adapter(s),
  - compute classification buckets,
  - emit report artifacts,
  - raise failures only for chosen integrity gates.

### 3. Add canonical benchmark fixtures

Create a new fixtures tree under `tests/fixtures/`.

#### `tests/fixtures/panini_blackbox_cases.json`
- frozen benchmark dataset keyed by canonical `sutra_id`;
- each case records:
  - `sutra_id`
  - `domain`
  - `interface` (for now mostly `sandhi_join` / `dispatch_forward`)
  - `inputs`
  - `expected_output`
  - `case_kind` (`positive`, `negative_control`, `perturbation`)
  - `family_id`
  - optional `notes`, `source`, `tags`
- this becomes the benchmark artifact the engine must grow into, not a set of
  cases reverse-fit to current implementation.

#### `tests/fixtures/external_adapter_contract_cases.json`
- canonical adapter contract examples used to validate third-party adapters;
- no fake Ambada outputs unless real authoritative data is provided later.

### 4. Replace old tests with benchmark-gated integrity tests

Create a focused new test suite under `tests/`.

#### `tests/test_benchmark_catalog.py`
- validates that:
  - canonical sutra universe loads from `sutras`;
  - every fixture case points to a real `sutra_id`;
  - missing `rule_configs` are surfaced as explicit benchmark gaps rather than
    silently ignored;
  - classification buckets remain mutually consistent.

#### `tests/test_benchmark_integrity.py`
- validates dynamic-integrity conditions for the local adapter:
  - benchmarked sandhi cases must map to rules present in runtime inventory;
  - evidence-capable local runs must report applied `sutra_id` in derivation
    evidence for positive cases;
  - negative-control and perturbation family expectations are honored;
  - cases that pass output-only but fail evidence checks are flagged as
    `hardcoding_suspected`.

#### `tests/test_adapter_contract.py`
- validates the abstract adapter interface against any registered external
  adapter implementation;
- ensures external tools can be benchmarked consistently without coupling the
  suite to a single vendor.

#### `tests/test_benchmark_regression.py`
- compares generated summary metrics against a frozen JSON baseline;
- fails only on disallowed regressions in:
  - canonical mapped coverage,
  - dynamic execution coverage,
  - unmapped-rule counts for already-benchmarked domains,
  - hardcoding suspicion count.

### 5. Surface derivation evidence from the local engine

Modify runtime code so the benchmark harness can distinguish real execution from
mere output coincidence.

#### `rules/engine.py`
- add a structured execution path, e.g. a helper alongside `dispatch_forward(...)`
  that returns:
  - final output,
  - applied rule IDs,
  - derivation trace steps,
  - maybe scope/domain metadata;
- preserve existing `dispatch_forward(...)` behavior for callers that only need
  strings.

#### `rule_engine/trace.py`
- add a serializable export helper for derivation steps/results so benchmark
  reports do not need to reach into internal dataclass layout manually.

#### `morphology/sandhi.py`
- optionally add a structured helper or adapter-friendly wrapper so benchmark
  execution can use the same black-box interface while still retrieving evidence
  when available.

### 6. Add a benchmark CLI/report entrypoint

Create a top-level runner script:

#### `tools/panini_benchmark_pipeline.py`
- command-line entrypoint for:
  - local engine benchmark,
  - external adapter benchmark,
  - report-only mode,
  - selected-domain runs,
  - baseline update mode if later authorized;
- writes deterministic artifacts such as:
  - `tests/results/panini_coverage.json`
  - `tests/results/panini_summary.md`
  - `tests/results/unmapped_sutras.json`
  - `tests/results/hardcoding_suspicions.json`
- keeps the truth-reporting workflow available outside pytest while the tests
  still gate integrity/regression conditions.

### 7. Update pytest configuration for the new suite

#### `pytest.ini`
- replace the stale `curated` marker setup with markers such as:
  - `benchmark`
  - `integrity`
  - `adapter`
  - `regression`
- keep the suite organized around benchmark truth rather than hand-curated
  engine-specific examples.

### 8. Document the benchmark contract

Add a brief doc describing:

#### `docs/panini_benchmark_pipeline.md`
- canonical sutra universe vs executable configs vs dynamic execution;
- what "hardcoding suspected" means;
- how to add new canonical cases without biasing toward current outputs;
- how future Ambada or other tool adapters should plug in.

## Hardcoding-Detection Strategy

The suite must not trust output equality alone. The implementation should use
all three layers below for the local engine, and as many as are available for
external adapters:

1. Inventory evidence
   - if a case passes but its `sutra_id` is absent from runtime-loaded rules,
     flag it immediately.

2. Derivation evidence
   - for the local engine, require positive benchmark cases to show the expected
     `sutra_id` in applied-rule trace evidence once surfaced from
     `DerivationTrace`.

3. Generalization controls
   - each benchmark family should include negative controls and perturbations so
     a memorized `(input -> output)` table fails even if one literal example
     happens to match.

A case should be marked `hardcoding_suspected` if output appears correct but
inventory evidence or derivation evidence is missing, or if a family shows
memorized positives without matching control behavior.

## Verification Steps

After implementation, verify in this order:

1. Fixture and catalog integrity
   - `pytest tests/test_benchmark_catalog.py -q`

2. Local engine dynamic-evidence checks
   - `pytest tests/test_benchmark_integrity.py -q`

3. Adapter contract checks
   - `pytest tests/test_adapter_contract.py -q`

4. Frozen benchmark regression gates
   - `pytest tests/test_benchmark_regression.py -q`

5. End-to-end benchmark pipeline output
   - `python tools/panini_benchmark_pipeline.py --engine local --domain all`

6. Report inspection
   - confirm generated artifacts explicitly list:
     - total canonical sutras,
     - sutras without `rule_configs`,
     - runtime-unloaded rules,
     - dynamically executed rules,
     - hardcoding suspicions,
     - adapter-pending domains/rules.

## Executor Notes

- Do not reintroduce mock coverage numbers or fake Ambada rule inventories.
- Do not collapse missing-config, unloaded, and unexecuted states into one pass/fail.
- Preserve compatibility for existing engine callers by keeping the plain string
  sandhi interface intact while adding structured evidence paths for the
  benchmark harness.
