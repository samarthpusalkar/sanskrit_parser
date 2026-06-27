"""
Tensor Vocabulary Database.

Maps morphological features, lemmas (roots/stems), and surface tokens to integer IDs.
"""

from typing import Dict
from core.lemmatizer import UniversalLemmatizer


class TensorVocab:
    POS_MAP = {"noun": 1, "verb": 2, "avyaya": 3, "participle": 4}
    REV_POS = {1: "noun", 2: "verb", 3: "avyaya", 4: "participle"}

    CASE_MAP = {"nominative": 1, "accusative": 2, "instrumental": 3, "dative": 4, "ablative": 5, "genitive": 6, "locative": 7, "vocative": 8}
    REV_CASE = {1: "nominative", 2: "accusative", 3: "instrumental", 4: "dative", 5: "ablative", 6: "genitive", 7: "locative", 8: "vocative"}

    NUMBER_MAP = {"singular": 1, "dual": 2, "plural": 3}
    REV_NUM = {1: "singular", 2: "dual", 3: "plural"}

    LAKARA_MAP = {"laṭ": 1, "lit": 2, "luṭ": 3, "lṛṭ": 4, "leṭ": 5, "loṭ": 6, "laṅ": 7, "liṅ": 8, "luṅ": 9, "lṛṅ": 10}
    REV_LAKARA = {1: "laṭ", 2: "lit", 3: "luṭ", 4: "lṛṭ", 5: "leṭ", 6: "loṭ", 7: "laṅ", 8: "liṅ", 9: "luṅ", 10: "lṛṅ"}

    ROOTS: Dict[str, int] = {}
    REV_ROOTS: Dict[int, str] = {}
    STEMS: Dict[str, int] = {}
    REV_STEMS: Dict[int, str] = {}

    _INIT_DONE: bool = False
    _TOKEN_TO_ID: Dict[str, int] = {}
    _ID_TO_TOKEN: Dict[int, str] = {}
    _NEXT_ID: int = 10000

    _SURFACE_TO_ID: Dict[str, int] = {}
    _ID_TO_SURFACE: Dict[int, str] = {}
    _NEXT_SURFACE_ID: int = 50000

    @classmethod
    def _init_db_vocab(cls):
        if cls._INIT_DONE:
            return
        cls._INIT_DONE = True
        seed_roots = ["bhū", "gam", "ram", "īś"]
        for idx, r in enumerate(seed_roots, start=1001):
            cls.ROOTS[r] = idx
            cls.REV_ROOTS[idx] = r
        seed_stems = ["rāma", "īśa", "yadi", "api"]
        for idx, s in enumerate(seed_stems, start=2001):
            cls.STEMS[s] = idx
            cls.REV_STEMS[idx] = s

        import sqlite3, os
        db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "sanskrit_master.db")
        if os.path.exists(db_path):
            try:
                conn = sqlite3.connect(db_path)
                c = conn.cursor()
                r_id = 1100
                for row in c.execute("SELECT dhatu_iast, dhatu_slp1 FROM dhatus"):
                    for val in row:
                        if val and val not in cls.ROOTS:
                            if r_id == 2000:
                                r_id = 3000
                            cls.ROOTS[val] = r_id
                            cls.REV_ROOTS[r_id] = val
                            r_id += 1
                s_id = 20000
                for row in c.execute("SELECT word_iast, word_slp1 FROM pratipadikas"):
                    for val in row:
                        if val and val not in cls.STEMS:
                            cls.STEMS[val] = s_id
                            cls.REV_STEMS[s_id] = val
                            s_id += 1
                conn.close()
            except Exception:
                pass

    @classmethod
    def is_plausible_token(cls, token: str) -> bool:
        """Check if a candidate string is a plausible Sanskrit vocabulary token."""
        if not token or (len(token) == 1 and token not in {"i", "a", "u"}):
            return False
        cls._init_db_vocab()
        if UniversalLemmatizer.is_known(token):
            return True
        lemma = UniversalLemmatizer.lemmatize(token)
        if UniversalLemmatizer.is_known(lemma):
            return True
        if lemma in cls.ROOTS or lemma in cls.STEMS:
            return True
        return False

    @classmethod
    def get_id(cls, token: str) -> int:
        """Get or create integer ID for a root lemma."""
        cls._init_db_vocab()
        if token in cls.ROOTS:
            return cls.ROOTS[token]
        if token in cls.STEMS:
            return cls.STEMS[token]
        if token not in cls._TOKEN_TO_ID:
            cls._TOKEN_TO_ID[token] = cls._NEXT_ID
            cls._ID_TO_TOKEN[cls._NEXT_ID] = token
            cls._NEXT_ID += 1
        return cls._TOKEN_TO_ID[token]

    @classmethod
    def get_token(cls, token_id: int) -> str:
        """Retrieve root lemma string from integer ID."""
        cls._init_db_vocab()
        if token_id in cls.REV_ROOTS:
            return cls.REV_ROOTS[token_id]
        if token_id in cls.REV_STEMS:
            return cls.REV_STEMS[token_id]
        return cls._ID_TO_TOKEN.get(token_id, "")

    @classmethod
    def get_surface_id(cls, surface: str) -> int:
        """Get or create integer ID for a surface inflected token."""
        if surface not in cls._SURFACE_TO_ID:
            cls._SURFACE_TO_ID[surface] = cls._NEXT_SURFACE_ID
            cls._ID_TO_SURFACE[cls._NEXT_SURFACE_ID] = surface
            cls._NEXT_SURFACE_ID += 1
        return cls._SURFACE_TO_ID[surface]

    @classmethod
    def get_surface(cls, surface_id: int) -> str:
        """Retrieve surface token string from integer ID."""
        return cls._ID_TO_SURFACE.get(surface_id, "")
