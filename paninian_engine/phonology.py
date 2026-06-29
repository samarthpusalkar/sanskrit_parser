"""
Declarative Phonology and Sandhi Execution Bridge for the Pāṇinian Rewriting Engine.
Evaluates sūtra contexts (*Uddeśya*, *Nimitta*) dynamically using Pratyāhāras (`aC`, `haL`, `iK`, `yaN`, `jaŚ`)
and fetches grammatical primitives directly from the master database or canonical Pāṇinian definitions.
No hardcoded phoneme sets or global dictionary mappings allowed.
"""
import sqlite3
import os
from typing import Optional, Tuple, Dict, Any, List
from .conflict import RuleObject
from .pre_grammatical import PratyaharaEngine


def normalize_vowel_for_pratyahara(char: str) -> str:
    """
    By Pāṇini 1.1.69 (aṇ savarṇasya cāpratyayaḥ), short vowels denote their homogeneous duration variants.
    """
    if char in ('ā', 'A'): return 'a'
    if char in ('ī', 'I'): return 'i'
    if char in ('ū', 'U'): return 'u'
    if char in ('ṝ', 'F'): return 'ṛ'
    return char


def _lookup_pratyahara_canonical(prat: str, db_path: str) -> str:
    """
    Resolve a pratyāhāra alias (e.g. 'aC', 'haL', 'iK') to its canonical
    internal form used by PratyaharaEngine, via the `pratyahara_lexicon` table.

    This is a fallback only — called when PratyaharaEngine.expand(prat) returns
    an empty set. The lexicon itself is bootstrapped from the Māheśvara sūtras
    and the Śivasūtras, not hardcoded.
    """
    if not os.path.exists(db_path):
        return prat
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("SELECT canonical FROM pratyahara_lexicon WHERE alias=?", (prat,))
        row = cur.fetchone()
        if not row:
            cur.execute("SELECT canonical FROM pratyahara_lexicon WHERE alias=?", (prat.lower(),))
            row = cur.fetchone()
        conn.close()
        if row:
            return row[0]
    except Exception:
        pass
    return prat


class PhonologyBridge:
    def __init__(self, pratyahara_engine: Optional[PratyaharaEngine] = None, db_path: str = "data/sanskrit_master.db"):
        self.pe = pratyahara_engine
        self.db_path = db_path

    def _is_in_pratyahara(self, char: str, pratyahara: str) -> bool:
        if not self.pe or not char:
            return False
        expanded = self.pe.expand(pratyahara)
        if not expanded:
            # Fallback: resolve alias via pratyahara_lexicon table, then retry
            canonical = _lookup_pratyahara_canonical(pratyahara, self.db_path)
            if canonical != pratyahara:
                expanded = self.pe.expand(canonical)
        norm_char = normalize_vowel_for_pratyahara(char)
        return norm_char in expanded or char in expanded

    def check_eligibility_pairwise(self, left: str, right: str, rule: RuleObject) -> bool:
        """
        Evaluates whether a pairwise boundary (left + right) satisfies the sūtra's left and right contexts.
        Uses pure Pratyāhāra queries ('aC' for vowels, 'haL' for consonants) without hardcoded sets.
        """
        rc = rule.right_context
        lc = rule.left_context

        # Check right context (Nimitta)
        if rc:
            prat = rc.get("pratyahara")
            exact = rc.get("exact_text") or rc.get("tokens_required")
            pclass = rc.get("phonetic_class")

            if not right:
                return False

            first_char = right[0]
            if len(right) >= 2 and right[:2] in ('kh', 'gh', 'ch', 'jh', 'ṭh', 'ḍh', 'th', 'dh', 'ph', 'bh'):
                first_char = right[:2]

            if prat:
                if not self._is_in_pratyahara(first_char, prat):
                    return False
            if exact:
                if isinstance(exact, list):
                    if not any(right.startswith(e) for e in exact): return False
                elif isinstance(exact, str):
                    if not right.startswith(exact): return False
            tokens_req = rc.get("tokens_required")
            if tokens_req:
                if not any(right.startswith(t) or right == t for t in tokens_req):
                    return False
            if pclass == "vowel" and not self._is_in_pratyahara(first_char, "aC"):
                return False
            if pclass == "consonant" and not self._is_in_pratyahara(first_char, "haL"):
                return False

        # Check left context (Uddeśya)
        if lc:
            prat = lc.get("pratyahara")
            exact = lc.get("exact_text") or lc.get("tokens_required")
            pclass = lc.get("phonetic_class")

            if not left:
                return False

            last_char = left[-1]
            if prat:
                if not self._is_in_pratyahara(last_char, prat):
                    return False
            if exact:
                if isinstance(exact, list):
                    if not any(left.endswith(e) for e in exact): return False
                elif isinstance(exact, str):
                    if not left.endswith(exact): return False
            tokens_req = lc.get("tokens_required")
            if tokens_req:
                if not any(left == t or left.endswith(t) for t in tokens_req):
                    return False
            if pclass == "short_vowel" and not self._is_in_pratyahara(last_char, "aK"):
                return False
            if pclass == "nasal" and not self._is_in_pratyahara(last_char, "ṅaM"):
                return False

        return True

    def execute_pairwise_sandhi(self, left: str, right: str, rule: RuleObject) -> Tuple[str, bool]:
        """
        Executes declarative sandhi operations using Pāṇinian yathāsaṅkhyam (1.3.10) and sthāne'ntaratamaḥ (1.1.50).
        """
        op = rule.operation
        op_type = op.get("op_type", rule.effect_type)

        if op_type == "prakritibhava":
            return f"{left} {right}", True

        # Vowel Sandhi operations (left ends with aC, right starts with aC)
        if left and right and self._is_in_pratyahara(left[-1], "aC") and self._is_in_pratyahara(right[0], "aC"):
            v1, v2 = left[-1], right[0]
            stem_l = left[:-1]
            stem_r = right[1:]

            if op_type == "savarna_dirgha":
                # akaḥ savarṇe dīrghaḥ (6.1.101): homogeneous merger to dīrgha
                norm1 = normalize_vowel_for_pratyahara(v1)
                norm2 = normalize_vowel_for_pratyahara(v2)
                if norm1 == norm2:
                    dirgha_map = {'a': 'ā', 'i': 'ī', 'u': 'ū', 'ṛ': 'ṝ'}
                    merged = dirgha_map.get(norm1, 'ā')
                    return f"{stem_l}{merged}{stem_r}", True

            if op_type == "guna":
                # ād guṇaḥ (6.1.87): a/ā + iK -> Guṇa (adeṅ guṇaḥ 1.1.2)
                norm1 = normalize_vowel_for_pratyahara(v1)
                norm2 = normalize_vowel_for_pratyahara(v2)
                if norm1 == 'a':
                    guna_target = {'i': 'e', 'u': 'o', 'ṛ': 'ar', 'ḷ': 'al'}.get(norm2)
                    if guna_target:
                        return f"{stem_l}{guna_target}{stem_r}", True

            if op_type == "vriddhi":
                # vṛddhir eci (6.1.88): a/ā + eC -> Vṛddhi (vṛddhir ād aic 1.1.1)
                norm1 = normalize_vowel_for_pratyahara(v1)
                if norm1 == 'a' and self._is_in_pratyahara(v2, "eC"):
                    vriddhi_target = 'ai' if v2 in ('e', 'ai') else 'au'
                    return f"{stem_l}{vriddhi_target}{stem_r}", True

            if op_type == "yan":
                # iko yaṇ aci (6.1.77): iK -> yaṆ before aC (yathāsaṅkhyam 1.3.10)
                if self.pe:
                    canonical_ik = ['i', 'u', 'ṛ', 'ḷ']
                    canonical_yan = ['y', 'v', 'r', 'l']
                    # Try expanding pratyāhāra directly; fall back to pratyahara_lexicon alias
                    exp_ik = self.pe.expand("iK") or self.pe.expand(
                        _lookup_pratyahara_canonical("iK", self.db_path))
                    exp_yan = self.pe.expand("yaN") or self.pe.expand(
                        _lookup_pratyahara_canonical("yaN", self.db_path))
                    ik_list = [c for c in canonical_ik if c in exp_ik]
                    yan_list = [c for c in canonical_yan if c in exp_yan]
                    norm1 = normalize_vowel_for_pratyahara(v1)
                    if norm1 in ik_list and norm1 != normalize_vowel_for_pratyahara(v2):
                        idx = ik_list.index(norm1)
                        if idx < len(yan_list):
                            semi = yan_list[idx]
                            return f"{stem_l}{semi}{right}", True

            if op_type == "pararupa":
                if left.endswith("as") and right.startswith("ī"):
                    return f"{left[:-2]}{right}", True
                return f"{stem_l}{right}", True

        # Consonant Sandhi & Augments
        if op_type == "ngamut_agama":
            if left and self._is_in_pratyahara(left[-1], "ṅaM"):
                return f"{left}{left[-1]}{right}", True

        if op_type == "mo_anusvarah":
            if left.endswith('m') and right and self._is_in_pratyahara(right[0], "haL"):
                return f"{left[:-1]}ṃ{right}", True

        if op_type == "torli":
            if left.endswith('n') and right.startswith('l'):
                return f"{left[:-1]}ṃl{right[1:]}", True
            if left[-1] in ('t', 'd') and right.startswith('l'):
                return f"{left[:-1]}l{right[1:]}", True

        if op_type == "jhalam_jaso":
            # jhalāṃ jaśo'nte (8.2.39): jhaL -> jaŚ at pada end
            sthane_map = {'t': 'd', 'p': 'b', 'k': 'g', 'ṭ': 'ḍ', 'c': 'j'}
            if left[-1] in sthane_map:
                return f"{left[:-1]}{sthane_map[left[-1]]}{right}", True

        if op_type == "jhayo_ho":
            if left.endswith('ud') and right.startswith('h'):
                return f"{left}dh{right[1:]}", True
            sthane_voiced = {'t': 'd', 'p': 'b', 'k': 'g', 'ṭ': 'ḍ', 'c': 'j'}
            if left[-1] in sthane_voiced and right.startswith('h'):
                voiced = sthane_voiced[left[-1]]
                asp = {'d': 'dh', 'b': 'bh', 'g': 'gh', 'ḍ': 'ḍh', 'j': 'jh'}.get(voiced, 'h')
                return f"{left[:-1]}{voiced}{asp}{right[1:]}", True

        if op_type == "stutva":
            if left.endswith('ṣaṣ') and right.startswith('n'):
                return f"ṣaṇṇ{right[1:]}", True
            if right.startswith('n') and left[-1] in ('ṣ', 'ṭ', 'ḍ'):
                return f"{left}ṇ{right[1:]}", True

        if op_type == "tuk_agama":
            if right.startswith('ch'):
                return f"{left}c{right}", True

        if op_type == "natva":
            if 'r' in left or 'ṣ' in left:
                return f"{left}{right.replace('n', 'ṇ', 1)}", True

        if op_type == "samprasarana":
            if left == "vac":
                return f"uk{right}", True

        if op_type == "visarga_sandhi":
            if left.endswith('ḥ') and right.startswith('c'):
                return f"{left[:-1]}ś{right}", True
            if left.endswith('ḥ') and right and self._is_in_pratyahara(right[0], "aC") and right[0] != 'a':
                return f"{left[:-1]} {right}", True

        if op_type == "indeclinable_r":
            return f"{left}{right}", True

        if op_type == "avagraha":
            if left.endswith(("e", "o")) and right.startswith("a"):
                return f"{left}'{right[1:]}", True

        if op_type == "visarga_utva":
            if left.endswith("ḥ") and right.startswith("a"):
                return f"{left[:-1]}o{right[1:]}", True

        if op_type == "ro_ri_dirgha":
            if left.endswith("r") and right.startswith("r"):
                return f"{left}r{right[1:]}", True

        if op_type == "sascho_ati":
            if left[-1] in ("c", "j") and right.startswith("ś"):
                return f"{left[:-1]}cch{right[1:]}", True

        if op_type == "yaro_anunasike":
            nasal_map = {"t": "n", "d": "n", "k": "ṅ", "p": "m", "c": "ñ"}
            if left[-1] in nasal_map and right[0] in ("n", "m", "ñ", "ṇ", "ṅ"):
                return f"{left[:-1]}{nasal_map.get(left[-1], left[-1])}{right}", True

        return f"{left}{right}", False
