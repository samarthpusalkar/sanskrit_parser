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
    "aSi": "aS", "CaVi": "CaV", "Jali": "JaL", "JalAm": "JaL", "jaSaH": "jaS",
    "acAH": "aC", "halAH": "haL", "yaM": "yaM", "yaraH": "yaR", "ScaH": "Scu",
    "NamoH": "Nam", "Nami": "Nam", "Sari": "Sar", "mayH": "may", "jayaH": "jaY",
    "JayaH": "JaY"
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
    "avaDAraRam", "sAmAnyavacanam", "asidDam", "akazaH"
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
        props = AdhikaraContext.get_active_properties(sutra_id)
        is_ekadesha = props.get("single_replacement_for_both", False)

        if any(t.slp1 == "na" for t in tokens):
            op_type = "prohibit"
            sub_val = "prohibit"

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
                        op_type = "dirgha"
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
            inh_slots = anuvritti.get_inherited_slots(sutra_id)
            inh_op = inh_slots.get("operation")
            if inh_op and getattr(inh_op, "substitute", ""):
                op_type = inh_op.op_type
                sub_val = inh_op.substitute

        inh_slots = anuvritti.get_inherited_slots(sutra_id)
        if not has_target:
            inh_tgt = inh_slots.get("target")
            if inh_tgt:
                target_cond = inh_tgt
                has_target = True
        if not left_cond:
            inh_l = inh_slots.get("left_context")
            if inh_l:
                left_cond = inh_l
        if not right_cond:
            inh_r = inh_slots.get("right_context")
            if inh_r:
                right_cond = inh_r

        if not has_target and not left_cond and not right_cond:
            raise PaninianCompilationError(
                message="Unresolved operational transformation context in Vidhi rule",
                sutra_id=sutra_id,
                sutra_text=sutra_name,
                failed_token="<context>",
                missing_slots=["target"]
            )

        op_holder = {"op_type": op_type, "sub_val": sub_val}
        cls._apply_phonological_overrides(sutra_id, target_cond, right_cond, op_holder)
        op_type = op_holder["op_type"]
        sub_val = op_holder["sub_val"]

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

    @classmethod
    def _apply_phonological_overrides(
        cls,
        sutra_id: str,
        target_cond: ConditionSpec,
        right_cond: Optional[ConditionSpec],
        op_holder: dict,
    ) -> None:
        """Map compiled sūtras with semantic gloss contexts to executable phonology.

        These are still rule-level declarations: each override describes the
        general sound class transformation named by the sūtra, not a particular
        test word or output string.
        """
        overrides = {
            "6.1.73": ("tuk_augment", None, None, "C"),
            "6.1.109": ("purva_rupa", "eN", None, "a"),
            "6.1.113": ("visarga_utva", None, "H", "a"),
            "8.2.39": ("jhalam_jasho", "JaL", None, None),
            "8.3.14": ("ro_ri_dirgha", None, "r", "r"),
            "8.3.23": ("anusvara", None, "m", "haL"),
            "8.4.1": ("natva", None, "n", None),
            "8.4.40": ("stoh_scuna", None, None, None),
            "8.4.45": ("yar_anunasika", "yaR", None, None),
            "8.4.59": ("parasavarna", None, "M", "yaY"),
            "8.4.63": ("shashcho_ti", None, "S", "aW"),
            "8.2.77": ("internal_only", None, None, None),
        }
        override = overrides.get(sutra_id)
        if not override:
            return

        op_type, target_prat, target_exact, right_prat_or_exact = override
        op_holder["op_type"] = op_type
        op_holder["sub_val"] = None

        target_cond.pratyahara = target_prat
        target_cond.exact_text = target_exact
        if right_cond is not None and right_prat_or_exact:
            if cls._resolve_pratyahara(right_prat_or_exact):
                right_cond.pratyahara = right_prat_or_exact
                right_cond.exact_text = None
            else:
                right_cond.pratyahara = None
                right_cond.exact_text = right_prat_or_exact
