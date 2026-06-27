# Rule Config Enrichment Workflow

`rule_configs` is the source of truth for data-backed executable sūtra semantics.
Rows with `source = 'bootstrap_ast'` are mechanically migrated from the current
AST compiler and should be treated as candidates, not final scholarship.

## Enrichment Levels

1. `bootstrap_ast`
   Mechanical migration from `SutraAstBuilder`. Useful for coverage, but often
   shallow for kṛt, taddhita, governance, and inherited contexts.

2. `seed`
   Hand-curated phonological and sandhi rows needed by core runtime behavior.

3. `curated`
   Manually verified semantic rows. These should encode a real operation family,
   explicit context, domain, and tests.

## Manual Enrichment Loop

1. Run:

   ```bash
   python tools/audit_rule_configs.py --limit 100
   ```

2. Pick a cluster, not an isolated test word. Prefer one operation family:
   - `merge`
   - `insert`
   - `elide`
   - `substitute`
   - `bijection_substitute`
   - `voice`
   - `nasalize`
   - `palatalize`
   - `parasavarna`
   - `natva`
   - future families such as `affix_add`, `affix_replace`, `it_marker_elide`,
     `guna_strengthen`, `vriddhi_strengthen`, `augment_before`, `augment_after`.

3. Read the DB evidence:

   ```sql
   SELECT id, sutra_slp1, pada_cheda
   FROM sutras
   WHERE id BETWEEN '3.2.1' AND '3.2.200';
   ```

4. Replace weak fields:
   - Gloss-like replacement such as `praSaMsAyAm` should become a semantic
     condition, not a phonological replacement.
   - Contexts should use `PRAT:<pratyahara>`, symbolic classes, exact phoneme
     sets, dhātu/stem class selectors, or feature predicates.
   - Operation should name the actual transformation, not merely
     `exact_substitute` if the rule is adding an affix or assigning a condition.

5. Promote the row:

   ```sql
   UPDATE rule_configs
   SET source = 'curated'
   WHERE sutra_id = '<id>';
   ```

6. Add a focused test that proves the row applies and at least one nearby
   non-applicable case does not apply.

## Honesty Standard

A row is not considered semantically enriched merely because it is present in
SQLite. It is enriched only when the operation and contexts correspond to the
grammar claim of the sūtra and are verified by tests or a derivation fixture.
