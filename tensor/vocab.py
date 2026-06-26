"""
Tensor Vocabulary Database.

Maps morphological features, roots, stems, and Pāṇinian categories to integer IDs.
"""

from typing import Dict, Optional


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
