"""
Sūtra AST Builder.

Translates grammatical case tags of Pāṇinian words (Genitive 6, Locative 7, Nominative 1)
into executable formal generative RuleSpec AST predicates.
"""

from typing import List, Optional
from compiler.pada_cheda import PadaToken
from rule_engine.dsl import RuleSpec, ConditionSpec, OperationSpec
from compiler.registries import SanjnaRegistry, AdhikaraContext
from compiler.anuvritti import AnuvrittiEngine
from compiler.exceptions import PaninianCompilationError


# Classical Vibhakti stem to Pratyāhāra mappings
PRATYAHARA_STEMS = {
    "ikaH": "iK", "akaH": "aK", "acaH": "aC", "halaH": "haL", "yaRaH": "yaR",
    "ecaH": "eC", "icaH": "iC", "ayaH": "aY", "Kar": "Kar", "JaS": "JaS",
    "aci": "aC", "hali": "haL", "yayi": "yaY", "JaSi": "JaS", "Kari": "Kar",
    "aSi": "aS", "CaVi": "CaV", "Jali": "JaL",
    "acAH": "aC", "halAH": "haL"
}

PANINIAN_META_TERMS = {
    "visarjanIya": "H", "visarjanIyaH": "H", "visarga": "H", "ru": "r", "roH": "r",
    "anusvAra": "M", "anusvAraH": "M",
    "anunAsika": "~", "anunAsikaH": "~",
    "ut": "u", "it": "i", "at": "a", "At": "A",
}

PANINIAN_GOVERNANCE_FLAGS = {
    "viBAzA", "bahulam", "saMyogAdayaH", "nityam", "anudAttam", "svaritaH", "svaritam",
    "udAttaH", "udAttam", "anudAttaH", "parasavarRaH", "savarRaH", "laGuprayatnataraH",
    "pUrvam", "param", "antaram", "Amreqitam", "praTamA", "dvitIyA", "tftIyA", "sAkANkzam",
    "avaDAraRam", "sAmAnyavacanam", "asidDam", "akazaH", "jaSaH"
}


from core.shiva_sutras import PratyaharaResolver


class SutraAstBuilder:
    """Converts a resolved list of PadaTokens into a Pāṇinian RuleSpec AST."""

    @classmethod
    def _inherit_anuvritti_substitute(cls, sutra_id: str) -> str:
        """Lightweight lookback window querying SQLite for inherited replacements."""
        import sqlite3, os
        db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "sanskrit_master.db")
        if not os.path.exists(db_path):
            return ""
        try:
            conn = sqlite3.connect(db_path)
            c = conn.cursor()
            parts = sutra_id.split(".")
            if len(parts) != 3:
                return ""
            ady, pad, num = int(parts[0]), int(parts[1]), int(parts[2])
            for prev_num in range(num - 1, max(0, num - 6), -1):
                prev_id = f"{ady}.{pad}.{prev_num}"
                row = c.execute("SELECT pada_cheda FROM sutras WHERE id=?", (prev_id,)).fetchone()
                if row and row[0]:
                    from compiler.pada_cheda import PadaChedaParser
                    prev_tokens = PadaChedaParser.parse(row[0])
                    for pt in prev_tokens:
                        if pt.is_substitute:
                            norm = pt.slp1[:-1] if pt.slp1.endswith(("s", "H")) else pt.slp1
                            if norm in PANINIAN_META_TERMS or pt.slp1 in PANINIAN_META_TERMS:
                                conn.close()
                                return PANINIAN_META_TERMS.get(pt.slp1, PANINIAN_META_TERMS.get(norm, ""))
                            if pt.slp1 in {"ut", "u"}:
                                conn.close()
                                return "u"
            conn.close()
        except Exception:
            pass
        return ""

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
        props = AdhikaraContext.get_active_properties(sutra_id)
        is_ekadesha = props.get("single_replacement_for_both", False)

        for t in tokens:
            slp = t.slp1
            prat = cls._resolve_pratyahara(slp)

            # 1. Target condition (Genitive / 6th case)
            if t.is_target:
                has_target = True
                if prat:
                    target_cond.pratyahara = prat
                else:
                    norm = slp[:-1] if slp.endswith(("s", "H")) else slp
                    target_cond.exact_text = PANINIAN_META_TERMS.get(slp, PANINIAN_META_TERMS.get(norm, norm))

            # 2. Right Context condition (Locative / 7th case)
            elif t.is_right_context:
                if right_cond is None:
                    right_cond = ConditionSpec(match_pos="start")
                if prat:
                    right_cond.pratyahara = prat
                else:
                    norm = slp[:-1] if slp.endswith(("i", "e")) else slp
                    right_cond.exact_text = PANINIAN_META_TERMS.get(slp, PANINIAN_META_TERMS.get(norm, norm))

            # 3. Left Context condition (Ablative / 5th case)
            elif t.is_left_context:
                if left_cond is None:
                    left_cond = ConditionSpec(match_pos="end")
                if prat:
                    left_cond.pratyahara = prat
                else:
                    norm = slp[:-1] if slp.endswith(("s", "H", "t")) else slp
                    left_cond.exact_text = PANINIAN_META_TERMS.get(slp, PANINIAN_META_TERMS.get(norm, norm))
                if is_ekadesha and not has_target:
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
                if slp in PANINIAN_GOVERNANCE_FLAGS or norm in PANINIAN_GOVERNANCE_FLAGS:
                    op_type = "governance"
                    sub_val = slp
                elif norm in {"lopa", "adarSana"}:
                    op_type = "elide"
                    sub_val = None
                elif norm in {"guRa", "guRa-vfdDI"}:
                    op_type = "ekadesha_guna" if is_ekadesha else "sanjna_substitute"
                    sub_val = "guna"
                elif norm in {"vfdDi", "vfddhi"}:
                    op_type = "ekadesha_vriddhi" if is_ekadesha else "sanjna_substitute"
                    sub_val = "vriddhi"
                elif norm == "dIrGa":
                    is_savarna = any("savarR" in tok.slp1 for tok in tokens)
                    if is_ekadesha and (right_cond or is_savarna or sutra_id == "6.1.101"):
                        op_type = "ekadesha_savarna_dirgha"
                    else:
                        op_type = "merge_savarna" if right_cond else "dirgha"
                    sub_val = "dirgha"
                elif slp in PRATYAHARA_STEMS or norm in PRATYAHARA_STEMS:
                    op_type = "bijection_substitute"
                    sub_val = PRATYAHARA_STEMS.get(slp, PRATYAHARA_STEMS.get(norm, slp))
                elif norm in {"yaR", "jaS", "Scu", "ac", "hal"}:
                    op_type = "bijection_substitute"
                    sub_val = norm
                elif slp in PANINIAN_META_TERMS or norm in PANINIAN_META_TERMS:
                    op_type = "exact_substitute"
                    sub_val = PANINIAN_META_TERMS.get(slp, PANINIAN_META_TERMS.get(norm))
                elif SanjnaRegistry.is_sanjna(slp) or SanjnaRegistry.is_sanjna(norm):
                    op_type = "sanjna_substitute"
                    sub_val = slp if SanjnaRegistry.is_sanjna(slp) else norm
                else:
                    op_type = "exact_substitute"
                    sub_val = slp

        anuvritti = AnuvrittiEngine.get_instance()

        if (op_type in {"substitute", "exact_substitute"} and not sub_val) or sub_val == "":
            inh = cls._inherit_anuvritti_substitute(sutra_id)
            if inh:
                op_type = "exact_substitute"
                sub_val = inh
            else:
                inh_slots = anuvritti.get_inherited_slots(sutra_id)
                inh_op = inh_slots.get("operation")
                if inh_op and getattr(inh_op, "substitute", ""):
                    op_type = inh_op.op_type
                    sub_val = inh_op.substitute

        if not has_target:
            inh_slots = anuvritti.get_inherited_slots(sutra_id)
            inh_tgt = inh_slots.get("target")
            if inh_tgt:
                target_cond = inh_tgt
                has_target = True
            else:
                target_cond.pratyahara = "aC"

        op_spec = OperationSpec(op_type=op_type, substitute=sub_val)
        anuvritti.step(sutra_id, target_cond if has_target else None, left_cond, right_cond, op_spec)

        domain = "sapada"
        parts = sutra_id.split(".")
        if len(parts) == 3:
            if int(parts[0]) > 8 or (int(parts[0]) == 8 and int(parts[1]) >= 2):
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
