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


class SutraAstBuilder:
    """Converts a resolved list of PadaTokens into a Pāṇinian RuleSpec AST."""

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

            # 1. Target condition (Genitive / 6th case)
            if t.is_target:
                has_target = True
                if slp in PRATYAHARA_STEMS:
                    target_cond.pratyahara = PRATYAHARA_STEMS[slp]
                else:
                    target_cond.exact_text = slp[:-1] if slp.endswith(("s", "H")) else slp

            # 2. Right Context condition (Locative / 7th case)
            elif t.is_right_context:
                if right_cond is None:
                    right_cond = ConditionSpec(match_pos="start")
                if slp in PRATYAHARA_STEMS:
                    right_cond.pratyahara = PRATYAHARA_STEMS[slp]
                else:
                    right_cond.exact_text = slp[:-1] if slp.endswith(("i", "e")) else slp

            # 3. Left Context condition (Ablative / 5th case)
            elif t.is_left_context:
                if left_cond is None:
                    left_cond = ConditionSpec(match_pos="end")
                if slp in PRATYAHARA_STEMS:
                    left_cond.pratyahara = PRATYAHARA_STEMS[slp]

            # 4. Substitute / Operation (Nominative / 1st case)
            elif t.is_substitute:
                if "lopa" in slp.lower() or "adarSana" in slp.lower():
                    op_type = "elide"
                    sub_val = ""
                elif "dIrGa" in slp or "guRa" in slp or "vfddhi" in slp.lower() or "vfdDi" in slp:
                    op_type = "merge_sandhi"
                    if "dIrGa" in slp: sub_val = "dirgha"
                    elif "guRa" in slp: sub_val = "guna"
                    else: sub_val = "vriddhi"
                else:
                    op_type = "substitute"
                    # E.g. yaR, ay, av, H, ru
                    if slp == "yaR": sub_val = "yan"
                    elif slp in {"H", "visargaH"}: sub_val = "H"
                    else: sub_val = slp

        if not has_target:
            # Default target to any vowel if unspecified in starter rules
            target_cond.pratyahara = "aC"

        op_spec = OperationSpec(op_type=op_type, substitute=sub_val if op_type != "elide" else None)

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
