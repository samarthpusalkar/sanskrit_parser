"""
Pāṇinian Dedicated Registries.

Stores technical definitions (Sañjñā), meta-rule interceptors (Paribhāṣā),
and governing domain boundaries (Adhikāra) separated from operational Vidhi rules.
"""

from typing import Dict, Set, Any, List, Tuple, Callable


class SanjnaRegistry:
    """Registry mapping Sañjñā definition terms to dynamic phonemic sets or predicates."""

    _MAP: Dict[str, Set[str]] = {
        "guRa": {"a", "e", "o", "ar", "al"},
        "guna": {"a", "e", "o", "ar", "al"},
        "vfdDi": {"A", "E", "O", "Ar", "Al"},
        "vriddhi": {"A", "E", "O", "Ar", "Al"},
        "pragfhya": {"I", "U", "e"},
        "pragrhya": {"I", "U", "e"},
        "savarRa": {"a", "A", "i", "I", "u", "U", "f", "F", "x"},
        "savarna": {"a", "A", "i", "I", "u", "U", "f", "F", "x"}
    }

    _RAW_SUTRAS: Dict[str, str] = {}

    @classmethod
    def register_sutra(cls, sutra_id: str, sutra_slp1: str):
        cls._RAW_SUTRAS[sutra_id] = sutra_slp1

    @classmethod
    def resolve(cls, term: str) -> Set[str]:
        """Resolve a Sañjñā term to its phonemic set."""
        norm = term[:-1] if term.endswith(("s", "H", "m")) else term
        return cls._MAP.get(term, cls._MAP.get(norm, set()))

    @classmethod
    def is_sanjna(cls, term: str) -> bool:
        norm = term[:-1] if term.endswith(("s", "H", "m")) else term
        return term in cls._MAP or norm in cls._MAP


class AdhikaraContext:
    """Stores active heading domain boundaries and sticky scope properties."""

    _ACTIVE_FLAGS: Dict[str, Any] = {}
    _BOUNDARIES: List[Tuple[str, str, Dict[str, Any]]] = [
        # Sūtra 6.1.84 ekaḥ pūrvaparayoḥ governs up to 6.1.111
        ("6.1.84", "6.1.111", {"single_replacement_for_both": True}),
        # Sūtra 3.1.1 pratyayaḥ governs Adhyāyas 3-5
        ("3.1.1", "5.4.160", {"is_pratyaya_domain": True})
    ]

    @classmethod
    def get_active_properties(cls, sutra_id: str) -> Dict[str, Any]:
        """Get properties governing a specific sūtra ID."""
        props = {}
        try:
            parts = [int(p) for p in sutra_id.split(".")]
            val = parts[0] * 10000 + parts[1] * 100 + parts[2]
            for start_id, end_id, p_map in cls._BOUNDARIES:
                s_parts = [int(p) for p in start_id.split(".")]
                e_parts = [int(p) for p in end_id.split(".")]
                s_val = s_parts[0] * 10000 + s_parts[1] * 100 + s_parts[2]
                e_val = e_parts[0] * 10000 + e_parts[1] * 100 + e_parts[2]
                if s_val <= val <= e_val:
                    props.update(p_map)
        except Exception:
            pass
        return props


class ParibhasaRegistry:
    """Registry storing Paribhāṣā meta-rules acting as runtime interceptors."""

    _RAW_SUTRAS: Dict[str, str] = {}

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
        res_l, res_r = raw_result

        # Paribhāṣā 1.1.50 sthāne 'ntaratamaḥ (closest articulation affinity)
        op = getattr(rule_spec, "operation", None)
        if op and getattr(op, "op_type", "") in {"ekadesha_guna", "sanjna_substitute"}:
            if op.substitute == "guna" and left and right:
                l_char = left[-1]
                r_char = right[0]
                # If merging a + u -> o (guttural + labial -> guttural-labial o)
                if l_char in {'a', 'A'} and r_char in {'u', 'U'}:
                    return left[:-1] + 'o', right[1:]
                if l_char in {'a', 'A'} and r_char in {'i', 'I'}:
                    return left[:-1] + 'e', right[1:]
                if l_char in {'a', 'A'} and r_char in {'f', 'F'}:
                    return left[:-1] + 'ar', right[1:]

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
