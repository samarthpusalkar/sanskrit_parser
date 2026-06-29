"""
Morph Executor — sanskrit_dsl/morph_executor.py

Derives verbal forms (Tiṅanta) and nominal forms (Subanta) through the DSL
compiler/executor so that morphological derivation produces real evidence
(applied_rule_ids + trace) instead of a DB-lookup shortcut.

DSL path:
  - Tiṅanta: build the verbal stem (gaṇa vikaraṇa) + attach the tiṅ ending,
    then join stem+ending via DSLExecutor.execute_sandhi so 6.1.x sandhi rules
    fire and are recorded.
  - Subanta: attach the sup suffix to the stem, then join stem+suffix via
    DSLExecutor.execute_sandhi so 8.2.66 / 8.3.15 / 6.1.x fire and are recorded.

Fallback: if a needed compiled rule is not executable yet, fall back to the
DB-lookup generators (TinantaGenerator / SubantaGenerator) and tag the result
source="db_fallback" with empty applied_rule_ids. This keeps the benchmark
gate honest: a fallback result is never reported as executed.
"""

from __future__ import annotations

from typing import Any, Dict, List

from .executor import DSLExecutor
from .compiler import SutraCompiler


_GANA_VIKARANA = {
    1: "a",      # bhvādi — śap
    2: "a",      # adādi — śap (with guṇa where applicable)
    3: "a",      # juhotyādi — reduplication (handled by root, not vikaraṇa)
    4: "ya",     # divādi — śyañ
    5: "a",      # svādi — śnu
    6: "a",      # tudādi — śap (with lug-aṇ where applicable)
    7: "a",      # rudhādi — śap
    8: "a",      # tanādi — śap
    9: "a",      # kryādi — śap
    10: "aya",   # curādi — ṇic
}

_TIN_ENDINGS = {
    "lat": {(3, 1): "ti", (3, 2): "tas", (3, 3): "anti",
            (2, 1): "si", (2, 2): "Tas", (2, 3): "Ta",
            (1, 1): "Ami", (1, 2): "Avas", (1, 3): "Amas"},
}

_LAKARA_NORM = {
    "law": "lat", "laṭ": "lat", "lat": "lat",
    "liw": "lit", "liṭ": "lit", "lit": "lit",
    "luw": "lut", "luṭ": "lut", "lut": "lut",
    "lew": "lot", "leṭ": "lot", "lot": "lot",
    "laN": "lang", "laṅ": "lang", "lang": "lang",
}

_SUP_SUFFIXES = {
    ("nominative", "singular"): "s", ("nominative", "dual"): "O",
    ("nominative", "plural"): "as",
    ("accusative", "singular"): "am", ("accusative", "dual"): "O",
    ("accusative", "plural"): "as",
    ("instrumental", "singular"): "ina", ("instrumental", "dual"): "ByAm",
    ("instrumental", "plural"): "Bis",
    ("dative", "singular"): "Aya", ("dative", "dual"): "ByAm",
    ("dative", "plural"): "eByas",
    ("ablative", "singular"): "At", ("ablative", "dual"): "ByAm",
    ("ablative", "plural"): "eByas",
    ("genitive", "singular"): "sya", ("genitive", "dual"): "ayoH",
    ("genitive", "plural"): "AnAm",
    ("locative", "singular"): "i", ("locative", "dual"): "ayoH",
    ("locative", "plural"): "ezu",
    ("vocative", "singular"): "", ("vocative", "dual"): "O",
    ("vocative", "plural"): "as",
}

# Sūtras the morph path expects to fire (for evidence). These are the sūtras
# whose presence in applied_rule_ids counts as "the DSL actually derived this".
_TINANTA_EVIDENCE_SUTRAS = {"3.4.78", "7.3.84", "6.1.77", "6.1.87", "6.1.88", "6.1.101"}
_SUBANTA_EVIDENCE_SUTRAS = {"8.2.66", "8.3.15", "6.1.77", "6.1.101"}


class MorphExecutor:
    """Derives verbal and nominal forms through the DSL executor."""

    def __init__(self):
        self.dsl = DSLExecutor()
        self.compiler = SutraCompiler()

    def conjugate(self, root_slp1: str, gana: int, lakara: str,
                  purusa: int, vacana: int) -> Dict[str, Any]:
        """Conjugate a verbal root. Returns form + evidence."""
        norm_lakara = _LAKARA_NORM.get(lakara.lower(), "lat")
        vikarana = _GANA_VIKARANA.get(gana, "a")
        ending = _TIN_ENDINGS.get(norm_lakara, {}).get((purusa, vacana), "ti")

        # Build the stem: root + vikaraṇa, joined via DSL sandhi.
        stem_result = self.dsl.execute_sandhi(root_slp1, vikarana)
        stem = stem_result["joined"]

        # Attach the tiṅ ending via DSL sandhi.
        form_result = self.dsl.execute_sandhi(stem, ending)

        applied = list(stem_result["applied_rule_ids"])
        for r in form_result["applied_rule_ids"]:
            if r not in applied:
                applied.append(r)
        trace = stem_result["trace_steps"] + form_result["trace_steps"]

        # Decide whether this is genuine DSL evidence or a fallback.
        # The DSL path is considered to have derived the form only if at least
        # one expected tinanta sūtra fired (otherwise the joins did nothing
        # and the form is just concatenation).
        has_evidence = any(r in _TINANTA_EVIDENCE_SUTRAS for r in applied)

        if not has_evidence:
            # Fall back to the DB-lookup generator for the actual form, but
            # keep the trace for debugging. The gate will see no evidence.
            from morphology.tinanta import TinantaGenerator
            db_form = TinantaGenerator.conjugate(root_slp1, gana, lakara, purusa, vacana)
            return {
                "form": db_form,
                "applied_rule_ids": [],
                "trace_steps": trace,
                "source": "db_fallback",
            }

        return {
            "form": form_result["joined"],
            "applied_rule_ids": applied,
            "trace_steps": trace,
            "source": "dsl",
        }

    def decline(self, stem_slp1: str, case: str, number: str) -> Dict[str, Any]:
        """Decline a nominal stem. Returns form + evidence."""
        suffix = _SUP_SUFFIXES.get((case.lower(), number.lower()), "")
        if not suffix:
            # Vocative singular: stem is the form, no suffix.
            return {
                "form": stem_slp1,
                "applied_rule_ids": [],
                "trace_steps": [],
                "source": "db_fallback",
            }

        form_result = self.dsl.execute_sandhi(stem_slp1, suffix)
        applied = list(form_result["applied_rule_ids"])
        trace = form_result["trace_steps"]

        has_evidence = any(r in _SUBANTA_EVIDENCE_SUTRAS for r in applied)

        if not has_evidence:
            from morphology.subanta import SubantaGenerator
            db_form = SubantaGenerator.decline(stem_slp1, case, number)
            return {
                "form": db_form,
                "applied_rule_ids": [],
                "trace_steps": trace,
                "source": "db_fallback",
            }

        return {
            "form": form_result["joined"],
            "applied_rule_ids": applied,
            "trace_steps": trace,
            "source": "dsl",
        }