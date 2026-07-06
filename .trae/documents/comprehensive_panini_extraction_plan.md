# Comprehensive Pāṇinian Extraction Plan — No-Information-Loss Schema + Batch LLM Script

**Date:** 2026-07-06  
**Scope:** Extract structured, compiler-ready metadata from *all* remaining Aṣṭādhyāyī chapters (1.x–7.x plus any gaps in 6.x/8.x) so that a Python compiler can derive forms without re-consulting the LLM at runtime.  
**User decisions locked (from Plan Mode questions):**
1. Cover all remaining chapters, not just 2/3/4/5/7.
2. Batch prompts include the same pāda *plus* prerequisite definitional sūtras from earlier chapters.
3. DB schema is hybrid: one main rule table + separate tables for conditions and saṃjñā references.
4. Batch granularity: definitional sūtras per pāda in one call, operational sūtras per-sūtra.
5. Paribhāṣā sūtras are extracted as executable AST/boolean expressions where possible.

---

## 1. Why a new extraction pass is necessary

Current `llm_extracted_metadata` was built for sandhi (6.x + 8.x). Its schema is too narrow for derivation:

- It has one free-text `conditioning_factors` column — not queryable by type.
- It has no explicit `anuvrtti_source_sutra_id`, so inheritance is invisible.
- It has no `rule_type` (`vidhi`/`niyama`/`paribhāṣā`/`adhikāra`/`ātideśa`).
- It cannot express operations like agama (augment), lopa (deletion), ādeśa-replacement with sthānivadbhāva.
- It cannot distinguish phonological vs morphological vs syntactic vs semantic conditions.
- It has no examples or counter-examples, so the compiler cannot validate its own matches.

The goal of this plan is to design an extraction that captures *everything* a compiler needs, in a form the compiler can trust and validate.

---

## 2. Information to extract — comprehensive field inventory

### 2.1 Identity and source

| Field | Type | Why needed |
|-------|------|------------|
| `sutra_id` | TEXT PRIMARY KEY | Canonical ID. |
| `adhyaya` | INTEGER | Book. |
| `pada` | INTEGER | Chapter. |
| `sutra_no` | INTEGER | Serial number within pāda. |
| `sutra_dev` | TEXT | Original devanāgarī text. |
| `pada_cheda` | TEXT | Word segmentation. |
| `sutra_type` | TEXT | `S$`, `P$`, `AD$`, `AT$`, `V$`, etc. |
| `samasta_sutra` | TEXT | Expanded sūtra with anuvṛtti filled in. |
| `anuvrtti_text` | TEXT | Inherited words from earlier sūtras. |
| `adhikara` | TEXT | Governing adhikāra in effect. |
| `adhikara_chain` | JSON array | Ordered list of adhikāra sūtra IDs in scope. |
| `source_text_hash` | TEXT | SHA-256 of `sutra_dev` + `pada_cheda` to detect upstream data changes. |

### 2.2 Rule classification

| Field | Type | Why needed |
|-------|------|------------|
| `rule_type` | TEXT | `vidhi`, `niyama`, `paribhasa`, `adhikara`, `atidesa`, `samjna_definition`, `pratyaya_definition`, `anuvrtti_carry`, `nirukti`, `vibhasha`. |
| `domain` | TEXT | `sapada`, `tripadi`, `samhita`, `angasya`, `taddhita`, `samasa`. |
| `is_executable` | BOOLEAN | True if the compiler can fire this rule directly. |
| `is_meta_rule` | BOOLEAN | True if it governs conflict/visibility (paribhāṣā). |
| `is_definition` | BOOLEAN | True if it defines a saṃjñā/paribhāṣā/adhikāra. |
| `anuvrtti_source_sutra_id` | TEXT | The sūtra this one inherits context from. |
| `anuvrtti_carries` | JSON | What this sūtra carries forward: `target`, `left_context`, `right_context`, `operation`, `conditioning_factors`, `sanjnas`. |

### 2.3 Operation

| Field | Type | Why needed |
|-------|------|------------|
| `operation_type` | TEXT | `exact_substitute`, `substitute`, `merge`, `elide`, `augment`, `prakritibhava`, `guna`, `vrddhi`, `dirgha`, `yan`, `bijection`, `visarga_sandhi`, `anusvara`, `natva`, `samprasarana`, `pararupa`, `purva_rupa`, `lopa`, `luk`, `slu`, `pratyaya_insert`, `niyama_prohibit`, `non_operational`. |
| `operation_subtype` | TEXT | Finer grain, e.g. `agama`, `adesha`, `vikarana`, `substitution_with_sthanivat`. |
| `replacement` | TEXT | SLP1 replacement/emit string. |
| `compute_fn` | TEXT | `guna`, `vrddhi`, `savarna_long`, `bijection`, etc. |
| `left_consume` | INTEGER | Phonemes consumed from left token. |
| `right_consume` | INTEGER | Phonemes consumed from right token. |
| `emit_side` | TEXT | `left` or `right`. |
| `emit` | TEXT | Literal string to emit (if not computed). |
| `preserve_length` | BOOLEAN | For lopa operations where the phoneme is deleted but position preserved. |
| `is_agama` | BOOLEAN | Augment (insertion). |
| `is_lopa` | BOOLEAN | Deletion. |
| `is_nipatana_exception` | BOOLEAN | Irregular form listed in nipātana. |
| `requires_sthanivadbhava` | BOOLEAN | Replacement behaves like the original in subsequent rules. |
| `sthani_phoneme` | TEXT | The original phoneme for sthānivad matching. |

### 2.4 Contexts — target, left, right

Each context is stored as a row in `rule_contexts`. Three contexts per rule: `target`, `left`, `right`.

| Field | Type | Why needed |
|-------|------|------------|
| `rule_id` | TEXT FK | Back to main rule. |
| `context_role` | TEXT | `target` / `left` / `right`. |
| `position` | TEXT | `left_end`, `right_start`, `whole_word`, `internal`, `padanta`, `samhita_boundary`. |
| `pratyahara` | TEXT | SLP1 pratyāhāra class, e.g. `aK`, `iK`, `hal`. |
| `exact_phonemes` | JSON array | List of literal phonemes, e.g. `["a", "A"]`. |
| `sanjna_required` | JSON array | Saṃjñās the token must carry. |
| `sanjna_prohibited` | JSON array | Saṃjñās that block the rule. |
| `morphological_category` | TEXT | `dhatu`, `sup`, `ting`, `krt`, `avyaya`, `nipata`, `gati`, `pratipadika`, `samasa`. |
| `morphological_features` | JSON | Key/value pairs: e.g. `{"lakara": "laT", "purusha": "prathama", "vacana": "eka"}`. |
| `is_padanta` | BOOLEAN | Condition requires word boundary. |
| `is_samhita` | BOOLEAN | Condition requires saṃhitā (continuous utterance). |
| `is_savarna` | BOOLEAN | Homogeneous class condition. |
| `meta_terms` | JSON array | Terms like `savarNa`, `aci`, `hal`, `pada`, `samhita`. |
| `tokens_required` | JSON array | Specific lexical items, e.g. `["eva", "hi"]`. |
| `sthani_phoneme` | TEXT | For matching the pre-mutation original. |

### 2.5 Conditioning factors (structured)

Stored in `rule_conditions`. Each factor is one row.

| Field | Type | Why needed |
|-------|------|------------|
| `rule_id` | TEXT FK | Back to main rule. |
| `factor_type` | TEXT | `phonological`, `morphological`, `syntactic`, `semantic`, `lexical`, `domain`, `operation_history`, `negation`. |
| `condition_text` | TEXT | Original phrase from commentary/sūtra. |
| `evaluability` | TEXT | `phonological` (executor can check), `morphological` (needs MorphExecutor), `semantic` (needs external semantics), `manual` (human-only). |
| `required_sanjnas` | JSON array | For morphological factors. |
| `prohibited_sanjnas` | JSON array | For morphological factors. |
| `required_morph_features` | JSON | Lakāra, vibhakti, etc. |
| `required_words` | JSON array | Specific lexical triggers. |
| `required_domain` | TEXT | e.g. `samhita`, `padanta`. |
| `required_operation_history` | JSON | e.g. `{"not_after": ["6.1.77"], "only_after": ["3.1.68"]}` |
| `is_negation` | BOOLEAN | `na`/`nā` condition. |
| `scope` | TEXT | `local` (this boundary), `derivation_global` (any prior step), `sentence` (whole sentence). |

### 2.6 Paribhāṣā / meta-rule axiom

| Field | Type | Why needed |
|-------|------|------------|
| `axiom_ast` | JSON | Executable boolean AST: `{"and": [...]}`, `{"or": [...]}`, `{"not": ...}`, `{"eq": ["side.sanjna", "dhatu"]}`, `{"later_wins": true}`, `{"closest_substitute": true}`, `{"sthanivat": ["target", "replacement"]}` |
| `paribhasa_category` | TEXT | `vipratisedhe`, `sthanivad`, `atidesa`, `samarthya`, `nirukti`, `svarya`, `anga`. |
| `scope_sutra_ids` | JSON array | IDs this paribhāṣā governs, when known. |
| `applies_to_domains` | JSON array | e.g. `sapada`, `tripadi`. |
| `applies_to_operation_types` | JSON array | Operation types it can debar/prioritize. |

### 2.7 Saṃjñā definition (for `S$` sūtras)

| Field | Type | Why needed |
|-------|------|------------|
| `defined_sanjna` | TEXT | The saṃjñā being defined. |
| `definition_type` | TEXT | `phonological`, `morphological`, `syntactic`, `derivational`. |
| `definition_criteria` | JSON | Structured criteria matching `rule_contexts` shape. |
| `equivalent_sutra_ids` | JSON array | Other sūtras defining the same/converse label. |
| `positive_examples` | JSON array | e.g. `["rāma", "kṛṣṇa"]` for `pada`. |
| `negative_examples` | JSON array | Counter-examples. |

### 2.8 Adhikāra / scope definition (for `AD$` sūtras)

| Field | Type | Why needed |
|-------|------|------------|
| `adhikara_sutra_id` | TEXT | Self ID. |
| `governs_range_start` | TEXT | First sūtra under this adhikāra. |
| `governs_range_end` | TEXT | Last sūtra under this adhikāra. |
| `scope_condition` | JSON | When the adhikāra is in force. |

### 2.9 Examples, confidence, provenance

| Field | Type | Why needed |
|-------|------|------------|
| `positive_examples` | JSON array | Known correct inputs/outputs. |
| `negative_examples` | JSON array | Known cases where the rule must *not* fire. |
| `commentary_notes` | TEXT | Vasu / other commentary summary. |
| `vyakhya_summary` | TEXT | Plain-language rule meaning. |
| `confidence` | REAL | 0–1. |
| `extraction_mode` | TEXT | `per_sutra`, `batch_pada`, `batch_group`. |
| `model` | TEXT | e.g. `deepseek-v4-pro:cloud`. |
| `extracted_at` | TEXT | ISO timestamp. |
| `commentary_used` | BOOLEAN | Whether commentary was in the prompt. |
| `hurdles` | JSON array | Uncertain fields or ambiguous cases. |
| `validation_status` | TEXT | `pending`, `validated`, `manual_review`. |

---

## 3. Hybrid DB schema

### 3.1 `rules` (main table)

All fields from §2.1, §2.2, §2.3, §2.7, §2.8, §2.9 that are single-valued per rule.

### 3.2 `rule_contexts`

One row per `(rule_id, context_role)`.
Fields from §2.4.

### 3.3 `rule_conditions`

One row per conditioning factor.
Fields from §2.5.

### 3.4 `rule_paribhasa_axioms`

One row per paribhāṣā sūtra.
Fields from §2.6.

### 3.5 `rule_anuvrtti_links`

Explicit inheritance graph.

| Field |
|-------|
| `rule_id` |
| `inherited_from_sutra_id` |
| `inherited_field` | `target_context`, `left_context`, `right_context`, `operation`, `conditioning_factors`, `sanjnas` |
| `inherited_text` | The actual anuvṛtti word(s) that carried it. |

### 3.6 `chapter_prerequisites`

Maps each pāda to the definitional sūtras that should be included in its prompts.

| Field |
|-------|
| `chapter_prefix` | e.g. `3.1` |
| `prerequisite_sutra_id` | e.g. `1.1.1` |
| `prerequisite_reason` | e.g. `pratyahara_definitions` |

---

## 4. Batch LLM extraction script

### 4.1 Script name

`tools/batch_panini_extractor.py`

### 4.2 Inputs

- `--chapter-prefix` e.g. `3.1`, `4.2`, or `all`
- `--mode` `definitions` | `operational` | `both`
- `--model` default `deepseek-v4-pro:cloud`
- `--delay` seconds between calls
- `--resume` skip already extracted IDs
- `--batch-size` max sūtras per batch call (default 50 for definitions)
- `--prerequisite-map` path to JSON file defaulting to `data/chapter_prerequisites.json`

### 4.3 Processing logic

For each target pāda:
1. Load all sūtras of that pāda from `sutras` table.
2. Partition:
   - `definitional` = `sutra_type` starts with `S$`, `P$`, `AD$`, or `AT$`
   - `operational` = everything else (mostly `V$`)
3. For definitional sūtras:
   - Group by pāda.
   - Build prompt with:
     - All prerequisite sūtras from `chapter_prerequisites`.
     - Previous sūtras in the same pāda (full anuvṛtti scope).
     - Target sūtras themselves.
     - Commentary snippets.
   - Request JSON array of extraction objects.
   - Validate each object against schema; on failure, re-extract failed IDs per-sūtra.
4. For operational sūtras:
   - Per-sūtra prompt.
   - Include same-pāda previous sūtras and relevant prerequisites.
   - Request single JSON object.
5. Store results in the hybrid schema.

### 4.4 Prompt template for definitional batch

```
You are a Pāṇinian grammar expert. Extract compiler-ready metadata for EACH of the
following definitional sūtras. These sūtras define saṃjñās, paribhāṣās, adhikāras,
or ātideśas within a single pāda; their meaning depends on the full pāda scope.

Prerequisite definitions already in force (include these in your reasoning but do
not extract them again):
[prerequisite sūtras with id + text + pada_cheda]

Previous sūtras in this pāda (for anuvṛtti context):
[previous sutras in order]

TARGET SŪTRAS TO EXTRACT (in order):
--- Sūtra 1: {id} ---
Devanagari: {sutra_dev}
Pada-cheda: {pada_cheda}
Type: {sutra_type}
Expanded (samasta): {samasta_sutra}
Anuvṛtti carried: {anuvrtti}
Adhikāra: {adhikara}
Commentary: {commentary}
...

Return a JSON ARRAY with one extraction object per target sūtra, IN THE SAME ORDER.
Each object must use this schema:
{detailed_schema_json}

All phonemes in SLP1. Use null for unknown fields. For paribhāṣā sūtras, include
`axiom_ast` as a structured boolean expression. Include positive and negative
examples wherever possible.
```

### 4.5 Prompt template for operational per-sūtra

```
You are a Pāṇinian grammar expert. Extract compiler-ready metadata for ONE operational
(vidhi/niyama) sūtra.

Sūtra ID: {id}
Devanagari: {sutra_dev}
Pada-cheda: {pada_cheda}
Type: {sutra_type}
Expanded: {samasta_sutra}
Anuvṛtti: {anuvrtti}
Adhikāra: {adhikara}

Relevant definitional context in force:
[prerequisite sūtras]
Previous operational sūtras in this pāda:
[previous sutras]
Commentary: {commentary}

Return a single JSON object matching this schema:
{detailed_schema_json}

Pay special attention to:
1. Is this a vidhi (prescription) or niyama (prohibition)?
2. What is the exact target phoneme/pratyāhāra?
3. What is the replacement/operation?
4. What left/right contexts or saṃjñās condition it?
5. Does it carry anything forward via anuvṛtti?
```

### 4.6 Validation and retry pipeline

1. JSON parse check.
2. Schema validation against JSON Schema (or Python dataclass validation).
3. Cross-check: if `rule_type == "samjna_definition"`, `defined_sanjna` must be non-null.
4. Cross-check: if `rule_type == "paribhasa"`, `axiom_ast` must be non-null.
5. Cross-check: `left_consume`/`right_consume` must be ≥ 0.
6. Cross-check: `pratyahara` values must be resolvable by `PratyaharaResolver`.
7. On any failure, write to `research/hurdles/{id}.json` and retry per-sūtra once.

---

## 5. Prerequisite map — which earlier sūtras each chapter needs

Create `data/chapter_prerequisites.json` seeded manually and then refined automatically:

```json
{
  "1.1": [],
  "1.2": ["1.1.1", "1.1.2", "1.1.9", "1.1.10", "1.1.11"],
  "1.3": ["1.1.1", "1.2.27", "1.2.28", "1.2.29"],
  "1.4": ["1.1.1", "1.2.45", "1.2.46", "1.3.1", "1.3.2"],
  "2.1": ["1.1.1", "1.2.27", "1.2.45", "1.4.1"],
  "2.2": ["1.1.1", "2.1.1"],
  "2.3": ["1.1.1", "2.1.1", "2.2.1"],
  "2.4": ["1.1.1", "2.1.1", "2.2.1", "2.3.1"],
  "3.1": ["1.1.1", "1.2.45", "1.3.1", "1.3.2", "3.1.1", "3.1.2"],
  "3.2": ["1.1.1", "3.1.1", "3.1.91", "3.1.92"],
  "3.3": ["1.1.1", "3.1.1", "3.1.133"],
  "3.4": ["1.1.1", "3.1.1", "1.4.1", "3.1.68"],
  "4.1": ["1.1.1", "1.2.45", "1.2.46", "1.4.1", "4.1.1", "4.1.2"],
  "4.2": ["1.1.1", "4.1.1", "4.1.82"],
  "5.1": ["1.1.1", "4.1.1", "5.1.1"],
  "5.2": ["1.1.1", "5.1.1", "5.1.119"],
  "5.3": ["1.1.1", "5.1.1", "5.1.1", "5.2.1"],
  "5.4": ["1.1.1", "5.1.1", "5.3.1"],
  "6.1": ["1.1.1", "1.2.27", "1.2.45", "6.1.1"],
  "6.4": ["1.1.1", "6.1.1", "6.1.77", "6.4.1"],
  "7.1": ["1.1.1", "6.4.1", "7.1.1"],
  "7.2": ["1.1.1", "6.4.1", "7.1.1"],
  "7.3": ["1.1.1", "6.4.1", "7.1.1", "7.2.1"],
  "7.4": ["1.1.1", "6.4.1", "7.1.1", "7.2.1", "7.3.1"],
  "8.1": ["1.1.1", "6.1.1", "8.1.1"],
  "8.2": ["1.1.1", "6.1.1", "8.1.1", "8.2.1"],
  "8.3": ["1.1.1", "6.1.1", "8.1.1", "8.2.1"],
  "8.4": ["1.1.1", "6.1.1", "8.1.1", "8.2.1", "8.3.1"]
}
```

This map is **editable** and can be auto-extended by analyzing `adhikara` and `anuvrtti` fields in the `sutras` table.

---

## 6. Phased rollout

| Phase | What | Output |
|-------|------|--------|
| A. Schema + script | Create DB migration, `batch_panini_extractor.py`, `chapter_prerequisites.json`. | New empty tables + script. |
| B. Pilot 1.x | Extract all 1.1–1.4 definitions. | Validate schema completeness. |
| C. Pilot 2.x + 3.1 | Extract definitional + operational pilot; compare quality to per-sūtra. | Adjust prompts and prerequisites. |
| D. Remaining derivation chapters | 3.x, 4.x, 5.x, 7.x operational per-sūtra; definitions batched. | Database populated. |
| E. Sandhi gap fill | Re-extract any missing 6.x/8.x; migrate old wide rows to new schema. | Full coverage. |
| F. Validation pipeline | Add tests that check schema validity, pratyāhāra resolution, and examples. | CI gate. |

---

## 7. Verification steps

```bash
# After extraction, check coverage per chapter prefix
cd "/Users/samarthpusalkar/Desktop/AI Slop Projects/Sanskrit_parser/sanskrit_new"
sqlite3 data/sanskrit_master.db "SELECT substr(sutra_id,1,3) AS ch, COUNT(*) FROM rules GROUP BY ch ORDER BY ch"

# Check schema-validity of extracted rows
python3 -m pytest tests/test_extraction_schema.py -v

# Check that every referenced pratyāhāra resolves
python3 -c "from sanskrit_dsl.parser import SutraParser; ..."

# Run compiler over all extracted rules
python3 -m pytest tests/test_compiler_load.py -v
```

---

## 8. Risks and mitigations

| Risk | Mitigation |
|------|------------|
| LLM context overflow for later chapters | Limit batches to 50 definitional sūtras; split large pādas. |
| JSON truncation on batch calls | Validate each element has closing braces; retry per-sūtra. |
| Inconsistent operation-type vocabulary | Publish canonical enum list in prompt and validate. |
| Anuvṛtti misunderstood by LLM | Include `samasta_sutra` and explicit anuvṛtti text in prompt. |
| Semantic conditions over-abstracted | Force `factor_type` + `evaluability` classification; flag `semantic` for review. |
| Paribhāṣā AST too complex | Start with a small catalog of mechanically expressible paribhāṣās. |

---

## 9. What "no information loss / no compression" means here

It does **not** mean the LLM produces perfect truth. It means the schema is wide enough that the compiler can decide whether a rule applies without asking the LLM again. Every condition — phonological, morphological, syntactic, semantic, lexical, historical — is stored in a typed field the compiler can inspect. If a condition is too semantic for the compiler, it is explicitly tagged `evaluability: manual` so the compiler knows it cannot autonomously fire that rule.

This is the closest feasible approximation to a no-loss extraction given that the source text itself is highly compressed Sanskrit sūtras.
