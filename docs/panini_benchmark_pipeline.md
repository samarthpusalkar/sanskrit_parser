# Panini Benchmark Pipeline

This repository now treats benchmarking as a grammar-development control system,
not as a local pass-rate optimizer.

## Coverage Layers

- Canonical universe: every sutra from `sutras` in `data/sanskrit_master.db`.
- Extracted coverage: whether a sutra has one or more `rule_configs`.
- Runtime coverage: whether the current engine/loader inventory includes that
  sutra.
- Dynamic execution coverage: whether a benchmark case for that sutra both
  matches the expected output and shows derivation evidence that the sutra
  actually fired.

These layers are intentionally kept separate so "missing config", "not loaded",
and "not dynamically executed" do not collapse into the same shallow status.

## Hardcoding Suspected

A benchmark case is marked as hardcoding-suspected when:

- its output matches the expected form, but
- the target sutra is not present in the runtime inventory, or
- the target sutra is not present in derivation evidence for a case that should
  fire dynamically.

This keeps output-only coincidences from being counted as genuine Paninian
execution.

## Fixture Rules

Benchmark fixtures live in `tests/fixtures/panini_blackbox_cases.json`.

Each case must specify:

- canonical `sutra_id`
- `domain`
- `interface`
- `inputs.left` and `inputs.right`
- `expected_output`
- `case_kind`
- `family_id`
- `expected_rule_presence`

Use families to group:

- positive cases
- perturbations
- negative controls

Do not add cases just because the current engine happens to pass them. Add cases
because they represent a stable grammatical target worth tracking over time.

## Running

Generate reports:

```bash
python3 tools/panini_benchmark_pipeline.py --engine local --domain all
```

Run the benchmark-oriented pytest suite:

```bash
python3 -m pytest tests/test_benchmark_catalog.py tests/test_benchmark_integrity.py tests/test_adapter_contract.py tests/test_benchmark_regression.py -q
```

## External Adapters

External tools such as Ambada should integrate through the abstract contract in
`benchmarks/adapters.py`.

Do not fake external rule inventories or placeholder coverage numbers. If an
external adapter lacks derivation evidence, the benchmark should still compare
outputs, but it must not claim dynamic proof that it cannot provide.
