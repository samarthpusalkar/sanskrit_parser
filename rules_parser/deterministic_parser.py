"""
Deterministic Vibhakti-Driven Sūtra Transducer.

Reads analytical PadaToken streams from Pāṇinian sūtras and constructs
universal RuleSpec predicates backed by PrimitiveOp operations.
"""

from typing import List, Optional, Dict, Any, Tuple
from compiler.pada_cheda import PadaChedaParser, PadaToken
from rule_engine.dsl import RuleSpec, ConditionSpec, PrimitiveOp
from compiler.registries import SanjnaRegistry, AdhikaraContext
from compiler.anuvritti import AnuvrittiEngine
from rules_parser.vocab import resolve_term_to_primitive
from compiler.ast_builder import SutraAstBuilder


class DeterministicSutraParser:
    """Parses sūtras deterministically into PrimitiveOp-backed RuleSpec objects."""

    @classmethod
    def parse(cls, sutra_id: str, sutra_name: str, pada_cheda_str: str, priority: int = 100, sutra_type: str = "V") -> RuleSpec:
        tokens = PadaChedaParser.parse(pada_cheda_str)
        cat_prefix = sutra_type.split('$')[0] if sutra_type and '$' in sutra_type else (sutra_type[:2] if sutra_type else 'V')
        if not tokens or cat_prefix in ('S', 'P', 'AD', 'AT'):
            op = PrimitiveOp(left_consume=0, right_consume=0, emit="", emit_side="left", compute_fn=None, substitute="", op_type="non_operational")
            return RuleSpec(id=sutra_id, name=sutra_name, rule_type="vidhi_sandhi", priority=priority, target_context=ConditionSpec(), operation=op, governance={"domain": "sapada"})

        target_cond = ConditionSpec()
        right_cond = None
        left_cond = None

        has_target = False
        props = AdhikaraContext.get_active_properties(sutra_id)
        is_ekadesha = props.get("single_replacement_for_both", False)

        op_term = None
        for t in tokens:
            if t.is_substitute or t.case == 1 or t.is_augment:
                op_term = t.slp1
            elif t.slp1 in {"na", "mA"}:
                op_term = "na"

        for t in tokens:
            slp = t.slp1
            prat = SutraAstBuilder._resolve_pratyahara(slp)

            if t.is_target:
                has_target = True
                if prat:
                    target_cond.pratyahara = prat
                else:
                    norm = slp[:-1] if slp.endswith(("s", "H")) else slp
                    target_cond.exact_text = norm
            elif t.is_right_context:
                if right_cond is None:
                    right_cond = ConditionSpec(match_pos="start")
                if prat:
                    right_cond.pratyahara = prat
                else:
                    norm = slp[:-1] if slp.endswith(("i", "e")) else slp
                    right_cond.exact_text = norm
            elif t.is_left_context:
                if left_cond is None:
                    left_cond = ConditionSpec(match_pos="end")
                if prat:
                    left_cond.pratyahara = prat
                else:
                    norm = slp[:-1] if slp.endswith(("s", "H", "t")) else slp
                    left_cond.exact_text = norm
                if is_ekadesha and not has_target:
                    has_target = True
                    if prat:
                        target_cond.pratyahara = prat
                    elif slp in {"At", "aT", "at"}:
                        target_cond.exact_text = "a,A"
                    else:
                        target_cond.exact_text = left_cond.exact_text

        if not op_term and tokens:
            # If no explicit 1st case found, look for last token or check anuvritti
            op_term = tokens[-1].slp1

        prim_op, op_type, sub_val = resolve_term_to_primitive(op_term or "", is_ekadesha=is_ekadesha, right_cond_present=bool(right_cond))

        anuvritti = AnuvrittiEngine.get_instance()
        inh_slots = anuvritti.get_inherited_slots(sutra_id)

        if op_type in {"substitute", "exact_substitute"} and (not sub_val or sub_val == ""):
            inh_op = inh_slots.get("operation")
            if inh_op and getattr(inh_op, "substitute", ""):
                sub_val = inh_op.substitute

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

        domain = "sapada"
        parts = sutra_id.split(".")
        if len(parts) == 3:
            try:
                if int(parts[0]) > 8 or (int(parts[0]) == 8 and int(parts[1]) >= 2):
                    domain = "tripadi"
            except Exception:
                pass

        return RuleSpec(
            id=sutra_id,
            name=sutra_name,
            rule_type="vidhi_sandhi",
            priority=priority,
            target_context=target_cond if has_target else None,
            left_context=left_cond,
            right_context=right_cond,
            operation=prim_op,
            governance={"domain": domain}
        )
