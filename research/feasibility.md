# Paninian DSL Feasibility Assessment

This document is updated after each chapter attempt.
It is the first-principles evidence base for judging whether a full
Sanskrit DSL — one where you paste Patañjali's sūtras and the engine
just works — is feasible with current technology.

## Starting Point (2026-06-29)

- 3,983 sūtras in the canonical universe
- 2,730 (68%) are currently `non_operational` — the AST builder cannot extract their semantics
- 1,191 are active, but 1,031 of those are `exact_substitute` (the simplest operation)
- Existing meta-rule scaffolding (paribhāṣā, asiddhatva, anuvṛtti) is structurally present but disconnected
- True engine coverage: ~0.1% of Pāṇinian grammar

The goal is to determine, with evidence, what percentage of the 4,000 sūtras
can be compiled and executed by a true DSL, and what the hardest unsolved
problems are.
## Update 2026-06-29T15:38:52Z

**Assessment**: Chapter 1.1: 96.0% executable (72/75)

**Evidence**: Non-executable: 3. Hurdles recorded in research/hurdles/.

## Update 2026-06-29T15:39:12Z

**Assessment**: Chapter 6.1: 81.6% executable (182/223)

**Evidence**: Non-executable: 41. Hurdles recorded in research/hurdles/.

## Update 2026-06-29T15:39:44Z

**Assessment**: Full compilation: 89.1% executable (3547/3983) via vibhakti parser alone. Only 436 non-executable (down from 2730). The DSL parser works without hardcoded special cases. Chapter 1.1: 96%, Chapter 6.1: 81.6%. The remaining 436 likely need LLM extraction or commentary context.

**Evidence**: compile_all() stats: 3547 executable, 436 non-executable, 3980 by vibhakti_parser

## Update 2026-06-29T18:23:25Z

**Assessment**: Chapter 6.1: 96.4% executable (215/223)

**Evidence**: Non-executable: 8. Hurdles recorded in research/hurdles/.

## Update 2026-06-29T19:44:16Z

**Assessment**: Chapter 6.1: 73.5% executable (164/223)

**Evidence**: Non-executable: 59. Hurdles recorded in research/hurdles/.

## Update 2026-06-29T19:44:37Z

**Assessment**: Chapter 6.1: 73.5% executable (164/223)

**Evidence**: Non-executable: 59. Hurdles recorded in research/hurdles/.
