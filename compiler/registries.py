"""
Pāṇinian Dedicated Registries.

Stores technical definitions (Sañjñā), meta-rule interceptors (Paribhāṣā),
and governing domain boundaries (Adhikāra) separated from operational Vidhi rules.
"""

import os
import sqlite3
from typing import Dict, Set, Any, List, Tuple, Callable


class SanjnaRegistry:
    """Registry mapping Sañjñā definition terms to dynamic phonemic sets or predicates."""

    _MAP: Dict[str, Set[str]] = {}
    _RAW_SUTRAS: Dict[str, str] = {}
    _INIT_DONE: bool = False

    @classmethod
    def _init_db(cls):
        if cls._INIT_DONE:
            return
        cls._INIT_DONE = True
        # Seed basic terms dynamically or via database
        cls._MAP.update({
            "guRa": {"a", "e", "o", "ar", "al"},
            "guna": {"a", "e", "o", "ar", "al"},
            "vfdDi": {"A", "E", "O", "Ar", "Al"},
            "vriddhi": {"A", "E", "O", "Ar", "Al"},
            "pragfhya": {"I", "U", "e"},
            "pragrhya": {"I", "U", "e"},
            "savarRa": set(PhoneticMatrix.STHANA.keys()),
            "savarna": set(PhoneticMatrix.STHANA.keys())
        })
        db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "sanskrit_master.db")
        if os.path.exists(db_path):
            try:
                conn = sqlite3.connect(db_path)
                c = conn.cursor()
                for row in c.execute("SELECT id, sutra_slp1, sutra_type, pada_cheda FROM sutras"):
                    sid, slp, stype, pc = row
                    stype = stype or ""
                    
                    is_sanjna = False
                    if stype.startswith("S$") or "saMjYA" in pc or "saMjYA" in slp:
                        is_sanjna = True
                    else:
                        from compiler.pada_cheda import PadaChedaParser
                        tokens = PadaChedaParser.parse(pc)
                        if tokens and all(t.is_substitute for t in tokens) and not any(t.is_target or t.is_left_context or t.is_right_context for t in tokens):
                            is_sanjna = True
                    
                    if is_sanjna:
                        cls._RAW_SUTRAS[sid] = slp
                        # Dynamic resolution of pratyahara-based definitions
                        if "guRa" in slp or "guRa" in pc:
                            cls._MAP["guRa"] = {"a", "e", "o", "ar", "al"}
                        elif "vfdDi" in slp or "vfdDi" in pc:
                            cls._MAP["vfdDi"] = {"A", "E", "O", "Ar", "Al"}
                conn.close()
            except Exception:
                pass

    @classmethod
    def register_sutra(cls, sutra_id: str, sutra_slp1: str):
        cls._RAW_SUTRAS[sutra_id] = sutra_slp1

    @classmethod
    def resolve(cls, term: str) -> Set[str]:
        """Resolve a Sañjñā term to its phonemic set."""
        cls._init_db()
        norm = term[:-1] if term.endswith(("s", "H", "m")) else term
        return cls._MAP.get(term, cls._MAP.get(norm, set()))

    @classmethod
    def is_sanjna(cls, term: str) -> bool:
        cls._init_db()
        norm = term[:-1] if term.endswith(("s", "H", "m")) else term
        return term in cls._MAP or norm in cls._MAP


class AdhikaraContext:
    """Stores active heading domain boundaries and sticky scope properties."""

    _ACTIVE_FLAGS: Dict[str, Any] = {}
    _BOUNDARIES: List[Tuple[str, str, Dict[str, Any]]] = []
    _INIT_DONE: bool = False

    @classmethod
    def _init_db(cls):
        if cls._INIT_DONE:
            return
        cls._INIT_DONE = True
        cls._BOUNDARIES = [
            ("6.1.84", "6.1.111", {"single_replacement_for_both": True}),
            ("3.1.1", "5.4.160", {"is_pratyaya_domain": True})
        ]
        db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "sanskrit_master.db")
        if os.path.exists(db_path):
            try:
                conn = sqlite3.connect(db_path)
                c = conn.cursor()
                for row in c.execute("SELECT id, sutra_type FROM sutras WHERE sutra_type LIKE '%AD$%'"):
                    sid, stype = row
                    parts = stype.split("##")
                    for p in parts:
                        if p.startswith("AD$"):
                            sub = p.split("$")
                            if len(sub) >= 3 and sub[2].isdigit():
                                e_code = sub[2]
                                if len(e_code) >= 3:
                                    e_id = f"{e_code[0]}.{e_code[1]}.{int(e_code[2:])}"
                                    cls._BOUNDARIES.append((sid, e_id, {"domain": sub[1]}))
                conn.close()
            except Exception:
                pass

    @classmethod
    def get_active_properties(cls, sutra_id: str) -> Dict[str, Any]:
        """Get properties governing a specific sūtra ID."""
        cls._init_db()
        props = {}
        try:
            parts = [int(p) for p in sutra_id.split(".")]
            val = parts[0] * 100000 + parts[1] * 1000 + parts[2]
            for start_id, end_id, p_map in cls._BOUNDARIES:
                s_parts = [int(p) for p in start_id.split(".")]
                e_parts = [int(p) for p in end_id.split(".")]
                s_val = s_parts[0] * 100000 + s_parts[1] * 1000 + s_parts[2]
                e_val = e_parts[0] * 100000 + e_parts[1] * 1000 + e_parts[2]
                if s_val <= val <= e_val:
                    props.update(p_map)
            raw_dom = props.get("domain", "")
            if any(k in raw_dom for k in ("संहिता", "samhita", "एकः पूर्वपरयोः")):
                props["semantic_domain"] = "samhita"
            elif any(k in raw_dom for k in ("पूर्वत्रासिद्धम्", "tripadi")):
                props["semantic_domain"] = "tripadi"
            elif any(k in raw_dom for k in ("अङ्गस्य", "angasya", "भस्य")):
                props["semantic_domain"] = "angasya"
            elif any(k in raw_dom for k in ("समास", "aluk")):
                props["semantic_domain"] = "aluk"
            else:
                if (parts[0] == 6 and parts[1] == 1 and parts[2] <= 157) or parts[0] == 8:
                    props["semantic_domain"] = "samhita"
                elif parts[0] == 6 and parts[1] == 3:
                    props["semantic_domain"] = "aluk"
                elif parts[0] in {6, 7}:
                    props["semantic_domain"] = "angasya"
                else:
                    props["semantic_domain"] = "general"
        except Exception:
            pass
        return props


class PhoneticMatrix:
    """Declarative feature matrix encoding classical Pāṇinian articulation features."""
    STHANA = {
        # Kantha (Guttural)
        'a': {'kantha', 'vowel'}, 'A': {'kantha', 'vowel'},
        'k': {'kantha', 'stop', 'unvoiced', 'alpaprana'}, 'K': {'kantha', 'stop', 'unvoiced', 'mahaprana'},
        'g': {'kantha', 'stop', 'voiced', 'alpaprana'}, 'G': {'kantha', 'stop', 'voiced', 'mahaprana'},
        'N': {'kantha', 'stop', 'voiced', 'alpaprana', 'nasal'},
        'h': {'kantha', 'fricative', 'voiced', 'mahaprana'}, 'H': {'kantha', 'fricative', 'unvoiced'},

        # Talu (Palatal)
        'i': {'talu', 'vowel'}, 'I': {'talu', 'vowel'},
        'c': {'talu', 'stop', 'unvoiced', 'alpaprana'}, 'C': {'talu', 'stop', 'unvoiced', 'mahaprana'},
        'j': {'talu', 'stop', 'voiced', 'alpaprana'}, 'J': {'talu', 'stop', 'voiced', 'mahaprana'},
        'Y': {'talu', 'stop', 'voiced', 'alpaprana', 'nasal'},
        'y': {'talu', 'semivowel', 'voiced', 'alpaprana'},
        'S': {'talu', 'fricative', 'unvoiced', 'mahaprana'},

        # Murdhan (Retroflex)
        'f': {'murdhan', 'vowel'}, 'F': {'murdhan', 'vowel'},
        'w': {'murdhan', 'stop', 'unvoiced', 'alpaprana'}, 'W': {'murdhan', 'stop', 'unvoiced', 'mahaprana'},
        'q': {'murdhan', 'stop', 'voiced', 'alpaprana'}, 'Q': {'murdhan', 'stop', 'voiced', 'mahaprana'},
        'R': {'murdhan', 'stop', 'voiced', 'alpaprana', 'nasal'},
        'r': {'murdhan', 'semivowel', 'voiced', 'alpaprana'},
        'z': {'murdhan', 'fricative', 'unvoiced', 'mahaprana'},

        # Danta (Dental)
        'x': {'danta', 'vowel'}, 'X': {'danta', 'vowel'},
        't': {'danta', 'stop', 'unvoiced', 'alpaprana'}, 'T': {'danta', 'stop', 'unvoiced', 'mahaprana'},
        'd': {'danta', 'stop', 'voiced', 'alpaprana'}, 'D': {'danta', 'stop', 'voiced', 'mahaprana'},
        'n': {'danta', 'stop', 'voiced', 'alpaprana', 'nasal'},
        'l': {'danta', 'semivowel', 'voiced', 'alpaprana'},
        's': {'danta', 'fricative', 'unvoiced', 'mahaprana'},

        # Ostha (Labial)
        'u': {'ostha', 'vowel'}, 'U': {'ostha', 'vowel'},
        'p': {'ostha', 'stop', 'unvoiced', 'alpaprana'}, 'P': {'ostha', 'stop', 'unvoiced', 'mahaprana'},
        'b': {'ostha', 'stop', 'voiced', 'alpaprana'}, 'B': {'ostha', 'stop', 'voiced', 'mahaprana'},
        'm': {'ostha', 'stop', 'voiced', 'alpaprana', 'nasal'},

        # Kantha-talu
        'e': {'kantha', 'talu', 'vowel'}, 'E': {'kantha', 'talu', 'vowel'},

        # Kantha-ostha
        'o': {'kantha', 'ostha', 'vowel'}, 'O': {'kantha', 'ostha', 'vowel'},

        # Danta-ostha
        'v': {'danta', 'ostha', 'semivowel', 'voiced', 'alpaprana'},

        # Nasika / Anusvara / Visarga
        'M': {'nasika', 'nasal'},
        '~': {'nasika', 'nasal'},
    }

    @classmethod
    def get_features(cls, char: str) -> Set[str]:
        return cls.STHANA.get(char, set())

    @classmethod
    def select_closest(cls, input_chars: List[str], candidates: Set[str]) -> str:
        """Paribhāṣā 1.1.50 sthāne 'ntaratamaḥ: Select candidate minimizing Hamming feature distance."""
        target_features = set()
        for c in input_chars:
            target_features.update(cls.get_features(c))

        best_cand = None
        min_dist = 999
        for cand in sorted(candidates):
            cand_features = cls.get_features(cand)
            diff = len(target_features.symmetric_difference(cand_features))
            if diff < min_dist:
                min_dist = diff
                best_cand = cand
        return best_cand or sorted(candidates)[0]


class ParibhasaRegistry:
    """Registry storing Paribhāṣā meta-rules acting as runtime interceptors."""

    _RAW_SUTRAS: Dict[str, str] = {}
    _INIT_DONE: bool = False

    @classmethod
    def _init_db(cls):
        if cls._INIT_DONE:
            return
        cls._INIT_DONE = True
        db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "sanskrit_master.db")
        if os.path.exists(db_path):
            try:
                conn = sqlite3.connect(db_path)
                c = conn.cursor()
                for row in c.execute("SELECT id, sutra_slp1, sutra_type FROM sutras"):
                    sid, slp, stype = row
                    stype = stype or ""
                    if stype.startswith("P$") or stype.startswith("AT$") or stype.startswith("AD$") or any(
                        marker in slp for marker in ("sTAne", "prasaNge", "vat", "atiDeSa")
                    ):
                        cls._RAW_SUTRAS[sid] = slp
                conn.close()
            except Exception:
                pass

    @classmethod
    def register_sutra(cls, sutra_id: str, sutra_slp1: str):
        cls._RAW_SUTRAS[sutra_id] = sutra_slp1

    @classmethod
    def intercept_apply(
        cls,
        rule_spec: Any,
        left: str,
        right: str,
        context: Dict[str, Any],
        raw_result: Tuple[str, str]
    ) -> Tuple[str, str]:
        """Apply Paribhāṣā meta-rule logic to forward transformations."""
        cls._init_db()
        res_l, res_r = raw_result

        # Paribhāṣā 1.1.50 sthāne 'ntaratamaḥ (closest articulation affinity)
        op = getattr(rule_spec, "operation", None)
        if op and getattr(op, "op_type", "") in {"ekadesha_guna", "sanjna_substitute"}:
            if op.substitute in {"guna", "vriddhi"} and left and right:
                l_char = left[-1]
                r_char = right[0]
                sanjna_key = "guRa" if op.substitute == "guna" else "vfdDi"
                candidates = SanjnaRegistry.resolve(sanjna_key)
                if candidates:
                    closest = PhoneticMatrix.select_closest([l_char, r_char], candidates)
                    return left[:-1] + closest, right[1:]

        return res_l, res_r

    @classmethod
    def intercept_revert(
        cls,
        rule_spec: Any,
        surface: str,
        context: Dict[str, Any],
        raw_splits: List[Tuple[str, str]]
    ) -> List[Tuple[str, str]]:
        """Apply Paribhāṣā meta-rule logic to backward splits."""
        return raw_splits
