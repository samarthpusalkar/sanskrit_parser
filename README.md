# Sanskrit New

Sanskrit New is a Python project for exploring Sanskrit as a rule-based, compiler-like system inspired by Pāṇini’s Aṣṭādhyāyī. It combines morphology, phonology, sandhi, and rule-engine components to support tasks such as verb conjugation, noun declension, sandhi joining/splitting, and rule compilation.

## What this project does

This repository provides a practical implementation of several classical Sanskrit processing capabilities:

- Sandhi joining and splitting
- Noun declension (subanta)
- Verb conjugation (tiṅanta)
- Pratyāhāra expansion through the Shiva Sūtras
- Rule-based compilation and execution for Pāṇinian-style grammar operations

It is intended both as a research-oriented Sanskrit processing engine and as a teaching tool for understanding how Sanskrit grammar can be modeled computationally.

## Project layout

- compiler/: rule compilation and AST building pipeline
- core/: phonology, root/phonological utilities, and core grammar primitives
- morphology/: noun/verb generation and sandhi logic
- rules/: rule engine and grammar rule definitions
- tests/: regression and behavior tests
- examples/: runnable demonstration scripts

## Quick start

### 1. Clone the repository

```bash
git clone <your-repo-url>
cd sanskrit_new
```

### 2. Run the demo

```bash
python3 examples/demo_generator.py
```

This will print example outputs for:

- pratyāhāra resolution
- verb conjugation
- noun declension
- sandhi joining and splitting

### 3. Use the high-level API

```python
from morphology.api import SanskritCompiler

print(SanskritCompiler.conjugate_verb("bhū", gana=1, lakara="laṭ", purusa=3, vacana=1))
print(SanskritCompiler.decline_noun("rāma", case="locative", number="singular"))
print(SanskritCompiler.join_words("rāma", "īśa", output_encoding="iast"))
```

Example output:

```text
bhavati
rāme
rāmeśa
```

## Running tests

The repository includes tests for the pipeline and rule engine:

```bash
python3 -m pytest -q tests/test_pipeline.py
```

You can also run the full test suite:

```bash
python3 -m pytest -q
```

## Notes

This project is an experimental and evolving implementation of Sanskrit grammar processing. It is useful for exploration, prototyping, and educational purposes, but it should be considered a research-oriented codebase rather than a production-ready linguistic platform.

## Contributing

Contributions are welcome. If you want to improve the grammar engine, add new rules, expand morphology coverage, or improve test coverage, feel free to open an issue or submit a pull request.
