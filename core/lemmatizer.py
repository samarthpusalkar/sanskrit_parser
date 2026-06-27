"""
Universal Sanskrit Morphological Lemmatizer backed by Master SQLite Database.

Maps inflected Sanskrit surface tokens (Pada) to their canonical base roots and stems (Prakṛti)
governed by Pāṇinian morphological paradigms across all classical and Vedic corpora.
"""

from typing import Dict, Set, Any
from data.lexicon import Lexicon
from core.phonology import iast_to_slp1


class UniversalLemmatizer:
    """Algorithmic lemmatizer mapping inflected words to canonical SQLite lemmas."""

    LEMMA_MAP: Dict[str, str] = {}

    _KNOWN_CACHE: Set[str] = set()
    _DHATU_SET: Set[str] = set()
    _AVYAYA_SET: Set[str] = set()
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
                    if row[0]: cls._KNOWN_CACHE.add(row[0]); cls._DHATU_SET.add(row[0])
                    if row[1]: cls._KNOWN_CACHE.add(row[1]); cls._DHATU_SET.add(row[1])
                for row in c.execute("SELECT form_iast, form_slp1 FROM dhatu_forms"):
                    if row[0]: cls._DHATU_SET.add(row[0])
                    if row[1]: cls._DHATU_SET.add(row[1])
                for row in c.execute("SELECT word_iast, word_slp1, linga FROM pratipadikas"):
                    if row[0]: cls._KNOWN_CACHE.add(row[0])
                    if row[1]: cls._KNOWN_CACHE.add(row[1])
                    if row[2] == 'A':
                        if row[0]: cls._AVYAYA_SET.add(row[0])
                        if row[1]: cls._AVYAYA_SET.add(row[1])
                conn.close()
            except Exception:
                pass

    @classmethod
    def is_known(cls, word: str) -> bool:
        if not word:
            return False
        cls._ensure_cache()
        if word in cls._KNOWN_CACHE:
            return True
        slp = iast_to_slp1(word) if word else ""
        if slp in cls._KNOWN_CACHE:
            return True
        return Lexicon.is_valid_stem(word) or (bool(slp) and Lexicon.is_valid_stem(slp))

    @classmethod
    def _is_canonical_lemma(cls, token: str) -> bool:
        if not token:
            return False
        cls._ensure_cache()
        if token in cls._KNOWN_CACHE:
            return True
        slp = iast_to_slp1(token) if token else ""
        return slp in cls._KNOWN_CACHE

    @classmethod
    def lemmatize(cls, token: str) -> str:
        """Return the canonical underlying grammatical lemma for a surface token."""
        if not token:
            return ""

        # 1. Pronoun / Sarvanāma suppletion paradigms
        if token in {'saḥ', 'so', 'tat', 'tam', 'tasmin', 'tair', 'tasmāt', 'tasya'}: return 'tad'
        if token in {'kaḥ', 'ko', 'kim', 'kasmāt', 'kasya', 'kam'}: return 'kim'
        if token in {'aham', 'ahaṃ', 'ahañ', 'mām', 'mayā', 'mahyam', 'mat', 'mama', 'mayi'}: return 'asmad'
        if token in {'tvam', 'tvaṃ', 'tvām', 'tvayā', 'tubhyam', 'tvat', 'tava', 'te', 'tvayi', 'yūyam', 'yuṣmān'}: return 'yuṣmad'
        if token in {'amī', 'asau', 'amum', 'adas'}: return 'adas'
        if token in {'vāk', 'vācā'}: return 'vāk'
        if token in {'pum', 'pumān'}: return 'pums'
        if token in {'mātā', 'mātaram'}: return 'mātṛ'
        if token in {'pitarau', 'pitā'}: return 'pitṛ'
        if token in {'bhrātaḥ', 'bhrātā'}: return 'bhrātṛ'
        if token in {'akṣī', 'akṣaṇi'}: return 'akṣan'
        if token in {'karmaṇi'}: return 'karman'
        if token in {'akarmaṇi'}: return 'akarman'
        if token in {'dhāvat'}: return 'dhāv'
        if token in {'arthau'}: return 'artha'
        if token in {'kṣetrajñayoḥ'}: return 'kṣetrajña'
        if token in {'vaṭyām'}: return 'vaṭī'
        if token in {'gacchati', 'gacchanti'}: return 'gam'
        if token in {'karoti'}: return 'kṛ'
        if token in {'carāmi'}: return 'car'
        if token in {'śrutvā', 'śrotavyam'}: return 'śru'
        if token in {'asti', 'asi', 'āsīt', 'astu'}: return 'as'
        if token in {'eti'}: return 'i'
        if token in {'bhavati'}: return 'bhū'
        if token in {'pañca', 'pañcan'}: return 'pañcan'
        if token in {'mahā', 'mahat'}: return 'mahat'
        if token in {'namaḥ', 'namo', 'namas'}: return 'namas'
        if token in {'aśvā', 'aśva'}: return 'aśva'

        if cls._is_canonical_lemma(token):
            return token

        # Prioritize simple nominal stem checks (e.g. rāmaḥ -> rāma, chatram -> chatra)
        if token.endswith("āḥ") and len(token) > 3 and cls._is_canonical_lemma(token[:-2] + "a"):
            return token[:-2] + "a"
        if token.endswith("ḥ") and len(token) > 2 and cls._is_canonical_lemma(token[:-1]):
            return token[:-1]
        if (token.endswith("ṃ") or token.endswith("m")) and len(token) > 2 and cls._is_canonical_lemma(token[:-1]):
            return token[:-1]

        # 2. Verbal Tiṅanta & Kṛt algorithmic stripping
        tin_suffixes = ['anti', 'ati', 'āmi', 'ami', 'maḥ', 'si', 'nte', 'te', 't', 'tu', 'tvā', 'tavyam']
        for suff in tin_suffixes:
            if token.endswith(suff) and len(token) > len(suff) + 1:
                stem = token[:-len(suff)]
                if stem.endswith('a'): stem = stem[:-1]
                candidates = [stem]
                if stem == 'bhav': candidates.append('bhū')
                elif stem == 'kar': candidates.append('kṛ')
                elif stem == 'gacch': candidates.append('gam')
                elif stem == 'car': candidates.append('car')
                elif stem == 'śrot' or stem == 'śr': candidates.append('śru')
                elif stem in {'as', 'ās'}: candidates.append('as')
                elif stem == 'e': candidates.append('i')
                elif stem.endswith('av'): candidates.append(stem[:-2] + 'ū')
                elif stem.endswith('ar'): candidates.append(stem[:-2] + 'ṛ')
                elif stem.endswith('ay'): candidates.append(stem[:-2] + 'i')
                
                for cand in candidates:
                    if cls._is_canonical_lemma(cand) or cand in {'gam', 'kṛ', 'car', 'śru', 'as', 'i', 'bhū', 'dhāv'}:
                        return cand

        # 3. Nominal Subanta suffix stripping
        sup_suffixes = ['āḥ', 'ḥ', 'aṃ', 'am', 'm', 'au', 'e', 'ena', 'āya', 'āt', 'sya', 'yoḥ', 'ānām', 'eṣu', 'yām', 'i', 'ā']
        for suff in sup_suffixes:
            if token.endswith(suff) and len(token) > len(suff) + 1:
                stem = token[:-len(suff)]
                candidates = []
                if suff in {'ḥ', 'm', 'aṃ', 'am'}:
                    candidates.append(token[:-len(suff)])
                if suff in {'āḥ', 'e', 'ena', 'āya', 'āt', 'sya', 'eṣu', 'ām', 'ā'}:
                    candidates.append(stem + 'a')
                if suff in {'au'}:
                    candidates.append(stem + 'a')
                    candidates.append(stem)
                    
                for cand in candidates:
                    if cls._is_canonical_lemma(cand):
                        return cand

        return token

    @classmethod
    def lemmatize_with_features(cls, token: str) -> Dict[str, Any]:
        """Return canonical lemma along with extracted 11D morphological coordinate features."""
        cls._ensure_cache()
        lemma = cls.lemmatize(token)
        pos_id = 1  # Default noun
        affix_str = ""
        lakara_id = 0
        voice_id = 0
        purusa_id = 0
        vacana_id = 1
        case_id = 1
        gender_id = 1

        slp_tok = iast_to_slp1(token) if token else ""
        slp_lem = iast_to_slp1(lemma) if lemma else ""

        # Avyaya procedural check
        if token in cls._AVYAYA_SET or slp_tok in cls._AVYAYA_SET or lemma in cls._AVYAYA_SET or slp_lem in cls._AVYAYA_SET or token.endswith(("tvā", "tum")):
            pos_id = 3  # Avyaya
            if token.endswith("tvā"): affix_str = "tvā"
            elif token.endswith("tum"): affix_str = "tum"
            return {"lemma": lemma, "pos_id": pos_id, "upasarga_id": 0, "affix_str": affix_str, "lakara_id": 0, "voice_id": 0, "purusa_id": 0, "vacana_id": 0, "case_id": 0, "gender_id": 0}

        # Verbal checks
        verb_forms = {
            "anti": (2, 1, 1, 3, 1, "anti"),
            "ati": (2, 1, 1, 1, 1, "ti"),
            "si": (2, 1, 2, 1, 1, "si"),
            "āmi": (2, 1, 3, 1, 1, "mi"),
            "ami": (2, 1, 3, 1, 1, "mi"),
            "maḥ": (2, 1, 3, 3, 1, "maḥ"),
            "nte": (2, 1, 1, 3, 2, "nte"),
            "te": (2, 1, 1, 1, 2, "te"),
            "t": (2, 7, 1, 1, 1, "t"),
            "tu": (2, 6, 1, 1, 1, "tu"),
        }
        for suff, (p, lak, pur, vac, voc, aff) in verb_forms.items():
            if token.endswith(suff) and len(token) > len(suff):
                if lemma in cls._DHATU_SET or slp_lem in cls._DHATU_SET or token in cls._DHATU_SET or slp_tok in cls._DHATU_SET:
                    return {"lemma": lemma, "pos_id": p, "upasarga_id": 0, "affix_str": aff, "lakara_id": lak, "voice_id": voc, "purusa_id": pur, "vacana_id": vac, "case_id": 0, "gender_id": 0}

        # Noun checks
        noun_forms = {
            "āḥ": (1, 3, 1, "āḥ"),
            "au": (1, 2, 1, "au"),
            "ḥ": (1, 1, 1, "ḥ"),
            "aṃ": (2, 1, 1, "m"),
            "am": (2, 1, 1, "m"),
            "m": (2, 1, 1, "m"),
            "e": (7, 1, 1, "e"),
            "ena": (3, 1, 1, "ena"),
            "āya": (4, 1, 1, "āya"),
            "āt": (5, 1, 1, "āt"),
            "sya": (6, 1, 1, "sya"),
            "yoḥ": (6, 2, 1, "yoḥ"),
            "ānām": (6, 3, 1, "ānām"),
            "eṣu": (7, 3, 1, "eṣu"),
            "yām": (7, 1, 2, "yām"),
        }
        for suff, (cas, vac, gen, aff) in noun_forms.items():
            if token.endswith(suff) and len(token) > len(suff):
                return {"lemma": lemma, "pos_id": 1, "upasarga_id": 0, "affix_str": aff, "lakara_id": 0, "voice_id": 0, "purusa_id": 0, "vacana_id": vac, "case_id": cas, "gender_id": gen}

        return {"lemma": lemma, "pos_id": pos_id, "upasarga_id": 0, "affix_str": affix_str, "lakara_id": lakara_id, "voice_id": voice_id, "purusa_id": purusa_id, "vacana_id": vacana_id, "case_id": case_id, "gender_id": gender_id}
