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

    ROOTS = {"bhū": 1001, "gam": 1002, "ram": 1003, "īś": 1004}
    REV_ROOTS = {v: k for k, v in ROOTS.items()}

    STEMS = {"rāma": 2001, "īśa": 2002, "yadi": 2003, "api": 2004}
    REV_STEMS = {v: k for k, v in STEMS.items()}

    _TOKEN_TO_ID: Dict[str, int] = {}
    _ID_TO_TOKEN: Dict[int, str] = {}
    _NEXT_ID: int = 10000

    _SURFACE_TO_ID: Dict[str, int] = {}
    _ID_TO_SURFACE: Dict[int, str] = {}
    _NEXT_SURFACE_ID: int = 50000

    @classmethod
    def is_plausible_token(cls, token: str) -> bool:
        """Check if a candidate string is a plausible Sanskrit vocabulary token."""
        if not token or (len(token) == 1 and token not in {"i", "a", "u"}):
            return False
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
