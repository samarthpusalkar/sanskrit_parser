"""
Sūtra AST Builder.

Translates grammatical case tags of Pāṇinian words (Genitive 6, Locative 7, Nominative 1)
into executable formal generative RuleSpec AST predicates.
"""

from typing import List, Optional
from compiler.pada_cheda import PadaToken
from rule_engine.dsl import RuleSpec, ConditionSpec, OperationSpec


# Classical Vibhakti stem to Pratyāhāra mappings
PRATYAHARA_STEMS = {
    "ikaH": "iK", "akaH": "aK", "acaH": "aC", "halaH": "haL", "yaRaH": "yaR",
    "ecaH": "eC", "icaH": "iC", "ayaH": "aY", "Kar": "Kar", "JaS": "JaS",
    "aci": "aC", "hali": "haL", "yayi": "yaY", "JaSi": "JaS", "Kari": "Kar",
    "aSi": "aS", "CaVi": "CaV", "Jali": "JaL",
    "acAH": "aC", "halAH": "haL"
}


from core.shiva_sutras import PratyaharaResolver


class SutraAstBuilder:
    """Converts a resolved list of PadaTokens into a Pāṇinian RuleSpec AST."""

    @classmethod
    def _resolve_pratyahara(cls, slp: str) -> Optional[str]:
        if slp in PRATYAHARA_STEMS:
            return PRATYAHARA_STEMS[slp]
        stems_to_try = [slp]
        for suffix in ("aH", "AH", "i", "e", "s", "H"):
            if slp.endswith(suffix) and len(slp) > len(suffix):
                stems_to_try.append(slp[:-len(suffix)])
        for stem in stems_to_try:
            if len(stem) >= 2:
                candidate = stem[:-1] + stem[-1].upper()
                try:
                    PratyaharaResolver.resolve(candidate)
                    return candidate
                except Exception:
                    pass
        return None

    @classmethod
    def build(cls, sutra_id: str, sutra_name: str, tokens: List[PadaToken], priority: int = 100) -> RuleSpec:
        target_cond = ConditionSpec()
        right_cond = None
        left_cond = None

        op_type = "substitute"
        sub_val = ""

        has_target = False

        for t in tokens:
            slp = t.slp1
            prat = cls._resolve_pratyahara(slp)

            # 1. Target condition (Genitive / 6th case)
            if t.is_target:
                has_target = True
                if prat:
                    target_cond.pratyahara = prat
                else:
                    target_cond.exact_text = slp[:-1] if slp.endswith(("s", "H")) else slp

            # 2. Right Context condition (Locative / 7th case)
            elif t.is_right_context:
                if right_cond is None:
                    right_cond = ConditionSpec(match_pos="start")
                if prat:
                    right_cond.pratyahara = prat
                else:
                    right_cond.exact_text = slp[:-1] if slp.endswith(("i", "e")) else slp

            # 3. Left Context condition (Ablative / 5th case)
            elif t.is_left_context:
                if left_cond is None:
                    left_cond = ConditionSpec(match_pos="end")
                if prat:
                    left_cond.pratyahara = prat
                else:
                    norm = slp[:-1] if slp.endswith(("s", "H", "t")) else slp
                    left_cond.exact_text = norm
                if sutra_id.startswith("6.1.") and not has_target:
                    has_target = True
                    if prat:
                        target_cond.pratyahara = prat
                    elif slp in {"At", "aT", "at"}:
                        target_cond.exact_text = "a,A"
                    else:
                        target_cond.exact_text = left_cond.exact_text

            # 4. Substitute / Operation (Nominative / 1st case)
            elif t.is_substitute:
                norm = slp[:-1] if slp.endswith(("s", "H")) else slp
                if norm in {"lopa", "adarSana"}:
                    op_type = "elide"
                    sub_val = None
                elif norm in {"guRa", "guRa-vfdDI"}:
                    op_type = "sanjna_substitute"
                    sub_val = "guna"
                elif norm in {"vfdDi", "vfddhi"}:
                    op_type = "sanjna_substitute"
                    sub_val = "vriddhi"
                elif norm == "dIrGa":
                    op_type = "merge_savarna" if right_cond else "dirgha"
                    sub_val = "dirgha"
                elif slp in PRATYAHARA_STEMS or norm in PRATYAHARA_STEMS:
                    op_type = "bijection_substitute"
                    sub_val = PRATYAHARA_STEMS.get(slp, PRATYAHARA_STEMS.get(norm, slp))
                elif norm in {"yaR", "jaS", "Scu", "ac", "hal"}:
                    op_type = "bijection_substitute"
                    sub_val = norm
                else:
                    op_type = "exact_substitute"
                    sub_val = "H" if norm in {"visarga", "H"} else slp

        if not has_target:
            target_cond.pratyahara = "aC"

        op_spec = OperationSpec(op_type=op_type, substitute=sub_val)

        domain = "sapada"
        # Tripādī boundary: 8.2.1 onwards
        parts = sutra_id.split(".")
        if len(parts) == 3 and (int(parts[0]) > 8 or (int(parts[0]) == 8 and int(parts[1]) >= 2)):
            domain = "tripadi"

        return RuleSpec(
            id=sutra_id,
            name=sutra_name,
            rule_type="vidhi_sandhi",
            priority=priority,
            target_context=target_cond,
            left_context=left_cond,
            right_context=right_cond,
            operation=op_spec,
            governance={"domain": domain}
        )
