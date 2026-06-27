"""
Universal Nominal Declension Generator (Subanta).

Queries the SQLite master database for exact Pāṇinian declension paradigms across all 24 cases/numbers.
For out-of-vocabulary stems, dynamically attaches raw SuP affixes and computes phonological transformation
via UniversalRuleEngine.
"""

import os
import sqlite3
from typing import Dict, List, Tuple, Optional
from morphology.sandhi import SandhiEngine


class SubantaGenerator:
    _CASE_IDX = {
        "nominative": 0, "accusative": 1, "instrumental": 2, "dative": 3,
        "ablative": 4, "genitive": 5, "locative": 6, "vocative": 7
    }
    _NUM_IDX = {"singular": 0, "dual": 1, "plural": 2}

    _SUP_FALLBACK = {
        ("nominative", "singular"): "s", ("nominative", "dual"): "O", ("nominative", "plural"): "as",
        ("accusative", "singular"): "am", ("accusative", "dual"): "O", ("accusative", "plural"): "as",
        ("instrumental", "singular"): "ina", ("instrumental", "dual"): "ByAm", ("instrumental", "plural"): "Bis",
        ("dative", "singular"): "Aya", ("dative", "dual"): "ByAm", ("dative", "plural"): "eByas",
        ("ablative", "singular"): "At", ("ablative", "dual"): "ByAm", ("ablative", "plural"): "eByas",
        ("genitive", "singular"): "sya", ("genitive", "dual"): "ayoH", ("genitive", "plural"): "AnAm",
        ("locative", "singular"): "i", ("locative", "dual"): "ayoH", ("locative", "plural"): "ezu",
        ("vocative", "singular"): "", ("vocative", "dual"): "O", ("vocative", "plural"): "as"
    }

    _DB_CACHE: Dict[str, List[str]] = {}
    _CACHE_LOADED: bool = False

    @classmethod
    def _ensure_cache(cls):
        if cls._CACHE_LOADED:
            return
        cls._CACHE_LOADED = True
        db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "sanskrit_master.db")
        if os.path.exists(db_path):
            try:
                conn = sqlite3.connect(db_path)
                c = conn.cursor()
                for row in c.execute("SELECT word_slp1, forms_slp1 FROM pratipadikas WHERE forms_slp1 IS NOT NULL AND forms_slp1 != ''"):
                    stem, forms_str = row[0], row[1]
                    if stem and forms_str and stem not in cls._DB_CACHE:
                        forms = forms_str.split(";")
                        if len(forms) == 24:
                            cls._DB_CACHE[stem] = forms
                conn.close()
            except Exception:
                pass

    @classmethod
    def decline(cls, stem_slp1: str, case: str, number: str) -> str:
        """Decline a nominal stem across 8 cases × 3 numbers via database paradigm or sūtra compilation."""
        cls._ensure_cache()
        c_idx = cls._CASE_IDX.get(case.lower(), 0)
        n_idx = cls._NUM_IDX.get(number.lower(), 0)
        form_idx = c_idx * 3 + n_idx

        if stem_slp1 in cls._DB_CACHE:
            raw_form = cls._DB_CACHE[stem_slp1][form_idx]
            # Clean up variants or vocative prefixes
            if "-" in raw_form:
                raw_form = raw_form.split("-")[-1]
            if raw_form.startswith("he "):
                raw_form = raw_form[3:]
            return raw_form

        # OOV Fallback: attach SuP suffix and transform via SandhiEngine / UniversalRuleEngine
        suffix = cls._SUP_FALLBACK.get((case.lower(), number.lower()), "")
        if not suffix:
            return stem_slp1
        if suffix in {"s", "H"}:
            return stem_slp1 + "H"
        return SandhiEngine.join(stem_slp1, suffix)

    _INVERTED_CACHE: Optional[Dict[str, str]] = None

    @classmethod
    def get_stem(cls, inflected_slp1: str) -> str:
        """
        Reverse-resolve an inflected nominal word (Subanta) to its base stem (Prātipadika).
        Used during Samāsa (compound formation) to execute supo dhātuprātipadikayoḥ (2.4.71).
        """
        if not inflected_slp1:
            return inflected_slp1

        cls._ensure_cache()
        if cls._INVERTED_CACHE is None:
            cls._INVERTED_CACHE = {}
            for stem, forms in cls._DB_CACHE.items():
                for f in forms:
                    clean_f = f.split("-")[-1]
                    if clean_f.startswith("he "):
                        clean_f = clean_f[3:]
                    if clean_f and clean_f not in cls._INVERTED_CACHE:
                        cls._INVERTED_CACHE[clean_f] = stem

        # 1. Exact lookup in database paradigm table
        if inflected_slp1 in cls._INVERTED_CACHE:
            return cls._INVERTED_CACHE[inflected_slp1]

        # 2. Check if it's already a valid stem or root in Lexicon
        from data.lexicon import Lexicon
        if Lexicon.is_valid_stem(inflected_slp1):
            return inflected_slp1

        # 3. Dynamic OOV suffix stripping sorted by length descending
        suffixes = sorted(set(cls._SUP_FALLBACK.values()) | {"sya", "Am", "ena", "Aya", "At", "as", "is", "es", "H", "m", "O", "i"}, key=len, reverse=True)
        for suff in suffixes:
            if suff and inflected_slp1.endswith(suff) and len(inflected_slp1) > len(suff):
                cand = inflected_slp1[:-len(suff)]
                if cand.endswith("A") and not Lexicon.is_valid_stem(cand):
                    # Try restoring short 'a' stem (e.g. rāmāt -> rāmā -> rāma)
                    cand_a = cand[:-1] + "a"
                    if Lexicon.is_valid_stem(cand_a):
                        return cand_a
                if Lexicon.is_valid_stem(cand):
                    return cand

        return inflected_slp1
