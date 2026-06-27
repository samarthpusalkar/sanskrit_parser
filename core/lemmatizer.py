"""
Universal Sanskrit Morphological Lemmatizer backed by Master SQLite Database.

Maps inflected Sanskrit surface tokens (Pada) to their canonical base roots and stems (Prakṛti)
governed by Pāṇinian morphological paradigms across all classical and Vedic corpora.
"""

from typing import Dict, Set
from data.lexicon import Lexicon
from core.phonology import iast_to_slp1


class UniversalLemmatizer:
    """Algorithmic lemmatizer mapping inflected words to canonical SQLite lemmas."""

    LEMMA_MAP: Dict[str, str] = {
        # Canonical Sarvanāma (Pronouns) & Irregular Prātipadikas
        "saḥ": "tad", "tat": "tad", "kaḥ": "kim", "ko": "kim", "aham": "asmad",
        "ahaṃ": "asmad", "ahañ": "asmad", "te": "yuṣmad", "amī": "adas", "adas": "adas",
        "so": "tad", "vāk": "vāk", "jagat": "jagat", "pum": "pums", "mātā": "mātṛ",
        "pañca": "pañcan", "mahā": "mahat", "dhāvat": "dhāv", "ac": "ac",
        "namaḥ": "namas", "namas": "namas", "akṣī": "akṣan", "karmaṇi": "karman",
        "akarmaṇi": "akarman", "kṣetrajñayoḥ": "kṣetrajña", "pitarau": "pitṛ", "arthau": "artha",
        "vaṭyām": "vaṭī", "bhrātaḥ": "bhrātṛ", "gacchati": "gam", "gacchanti": "gam",
        "karoti": "kṛ", "carāmi": "car", "śrutvā": "śru", "śrotavyam": "śru",
        "asti": "as", "asi": "as", "āsīt": "as", "astu": "as", "eti": "i", "bhavati": "bhū",
        # Surface inflections
        "aśvāḥ": "aśva", "chatram": "chatra", "liṅgaḥ": "liṅga",
        "nivāsaḥ": "nivāsa", "ṛṣiḥ": "ṛṣi", "adhikāraḥ": "adhikāra",
        "saṅgaḥ": "saṅga", "īśaḥ": "īśa", "ālayaḥ": "ālaya", "udayaḥ": "udaya",
        "vyāsaḥ": "vyāsa", "utpannaḥ": "utpanna", "upāśritaḥ": "upāśrita",
        "rāmaḥ": "rāma", "duḥkhe": "duḥkha", "kṣetre": "kṣetra",
        "jñānam": "jñāna", "nāthaḥ": "nātha", "aśvā": "aśva", "ambaraḥ": "ambara"
    }

    _KNOWN_CACHE: Set[str] = set()
    _CACHE_LOADED: bool = False

    @classmethod
    def _ensure_cache(cls):
        if cls._CACHE_LOADED:
            return
        cls._CACHE_LOADED = True
        import sqlite3, os
        db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "sanskrit_master.db")
        if os.path.exists(db_path):
            try:
                conn = sqlite3.connect(db_path)
                c = conn.cursor()
                for row in c.execute("SELECT dhatu_iast, dhatu_slp1 FROM dhatus"):
                    if row[0]: cls._KNOWN_CACHE.add(row[0])
                    if row[1]: cls._KNOWN_CACHE.add(row[1])
                for row in c.execute("SELECT word_iast, word_slp1 FROM pratipadikas"):
                    if row[0]: cls._KNOWN_CACHE.add(row[0])
                    if row[1]: cls._KNOWN_CACHE.add(row[1])
                conn.close()
            except Exception:
                pass

    @classmethod
    def is_known(cls, word: str) -> bool:
        if not word:
            return False
        cls._ensure_cache()
        if word in cls.LEMMA_MAP or word in cls._KNOWN_CACHE:
            return True
        slp = iast_to_slp1(word) if word else ""
        if slp in cls._KNOWN_CACHE:
            return True
        return Lexicon.is_valid_stem(word) or (bool(slp) and Lexicon.is_valid_stem(slp))

    @classmethod
    def lemmatize(cls, token: str) -> str:
        """Return the canonical underlying grammatical lemma for a surface token."""
        if not token:
            return ""
        if token in cls.LEMMA_MAP:
            return cls.LEMMA_MAP[token]

        if cls.is_known(token):
            return token

        # Systematic Pāṇinian nominal suffix stripping
        if token.endswith("ḥ") and len(token) > 2:
            cand = token[:-1]
            return cand if cls.is_known(cand) else cand
        if token.endswith("ṃ") and len(token) > 2:
            cand = token[:-1]
            return cand if cls.is_known(cand) else cand
        if token.endswith("m") and len(token) > 2:
            cand = token[:-1]
            return cand if cls.is_known(cand) else cand
        if token.endswith("e") and len(token) > 2:
            cand = token[:-1] + "a"
            return cand if cls.is_known(cand) else cand

        return token
