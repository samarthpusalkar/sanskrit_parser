"""
Samasta-Sūtra Parser.

Parses fully expanded Pāṇinian sūtras (from the `ss` field) into RuleSpec predicates
by resolving grammatical roles via vibhakti (case) mappings. Replaces the naive
DeterministicSutraParser by using the complete structural meaning of the rule.
"""

import sqlite3
from typing import List, Dict, Any, Tuple, Optional
from compiler.pada_cheda import PadaChedaParser, PadaToken
from rule_engine.dsl import RuleSpec, ConditionSpec, PrimitiveOp
from rules_parser.vocab import resolve_term_to_primitive
from compiler.ast_builder import SutraAstBuilder
from core.phonology import devanagari_to_slp1


class SamastasutraParser:
    """Parses samasta-sūtra (ss) into PrimitiveOp-backed RuleSpec objects."""

    @classmethod
    def parse(cls, sutra_id: str, name: str, ss: str, an: str, ad: str, pc: str, sutra_type: str, cur: sqlite3.Cursor, priority: int = 100) -> RuleSpec:
        cat_prefix = sutra_type.split('$')[0] if sutra_type and '$' in sutra_type else (sutra_type[:2] if sutra_type else 'V')
        
        non_op = PrimitiveOp(left_consume=0, right_consume=0, emit="", emit_side="left", compute_fn=None, substitute="", op_type="non_operational")
        default_rule = RuleSpec(id=sutra_id, name=name, rule_type="vidhi_sandhi", priority=priority, target_context=ConditionSpec(), operation=non_op, governance={"domain": "sapada"})

        if cat_prefix in ('S', 'P', 'AD', 'AT'):
            return default_rule
            
        if not ss:
            # Fallback if ss is missing - mark as non-operational to avoid corrupting engine
            return RuleSpec(
                id=sutra_id, name=name, rule_type="vidhi_sandhi", priority=priority,
                target_context=None, left_context=None, right_context=None,
                operation=PrimitiveOp(left_consume=0, right_consume=0, emit="", emit_side="left", compute_fn=None, substitute="", op_type="non_operational"),
                governance={"domain": "sapada"}
            )

        # 1. Resolve tokens and their vibhaktis from pc and an
        local_tokens = PadaChedaParser.parse(pc)
        token_map = {t.devanagari: t for t in local_tokens}
        
        if an:
            chunks = an.split("##")
            for chunk in chunks:
                parts = chunk.split("$")
                if len(parts) >= 2:
                    word_dev = parts[0]
                    src_id_raw = parts[1]
                    # Convert '84053' -> '8.4.53'
                    if len(src_id_raw) == 5:
                        src_id = f"{src_id_raw[0]}.{src_id_raw[1]}.{int(src_id_raw[2:])}"
                        row = cur.execute("SELECT pada_cheda FROM sutras WHERE id=?", (src_id,)).fetchone()
                        if row and row[0]:
                            src_tokens = PadaChedaParser.parse(row[0])
                            for t in src_tokens:
                                if t.devanagari == word_dev or t.devanagari.startswith(word_dev):
                                    token_map[word_dev] = t
                                    break
        
        # 2. Extract roles
        target_cond = ConditionSpec()
        right_cond = None
        left_cond = None
        op_term = None
        has_target = False
        
        is_ekadesha = "एकः पूर्वपरयोः" in ad or "एकः पूर्वपरयोः" in ss
        
        ss_words_dev = [w.strip() for w in ss.split() if w.strip()]
        
        for w_dev in ss_words_dev:
            # Skip pure domain/scope markers
            if w_dev in {"संहितायाम्", "पूर्वत्रासिद्धम्", "पदस्य", "अन्ते"}:
                continue
                
            token = token_map.get(w_dev)
            if not token:
                # Try prefix/substring or sandhi-aware match using SLP1
                slp_w = devanagari_to_slp1(w_dev)
                for d, t in token_map.items():
                    slp_t = t.slp1
                    # exact match without last character (accounts for t/d, m/M, etc)
                    if len(slp_w) > 1 and len(slp_t) > 1 and slp_w[:-1] == slp_t[:-1]:
                        token = t
                        break
                    elif d.startswith(w_dev) or w_dev.startswith(d):
                        token = t
                        break
            
            if not token:
                slp = devanagari_to_slp1(w_dev)
                # Guess case by ending if missing from map
                case_val = None
                if slp.endswith("Am"): case_val = 6
                elif slp.endswith("i"): case_val = 7
                elif slp.endswith("H") or slp.endswith("M"): case_val = 1
                elif slp.endswith("At") or slp.endswith("as"): case_val = 5
                
                token = PadaToken(devanagari=w_dev, slp1=slp, category="", case=case_val, number=None)

            slp = token.slp1
            prat = SutraAstBuilder._resolve_pratyahara(slp)
            
            if token.is_target:
                has_target = True
                if prat:
                    target_cond.pratyahara = prat
                else:
                    norm = slp[:-1] if slp.endswith(("s", "H")) else slp
                    target_cond.exact_text = norm
            elif token.is_right_context:
                if right_cond is None: right_cond = ConditionSpec(match_pos="start")
                if prat:
                    right_cond.pratyahara = prat
                else:
                    norm = slp[:-1] if slp.endswith(("i", "e")) else slp
                    right_cond.exact_text = norm
            elif token.is_left_context:
                norm = slp[:-1] if slp.endswith(("s", "H", "t")) else slp
                if is_ekadesha and not has_target:
                    has_target = True
                    if prat:
                        target_cond.pratyahara = prat
                    elif slp in {"At", "aT", "at"}:
                        target_cond.exact_text = "a|A"
                    else:
                        target_cond.exact_text = norm
                else:
                    if left_cond is None: left_cond = ConditionSpec(match_pos="end")
                    if prat:
                        left_cond.pratyahara = prat
                    else:
                        left_cond.exact_text = norm
            elif token.is_substitute or token.case == 1 or token.is_augment:
                op_term = slp
            elif slp in {"na", "mA", "vA", "viBAzA", "anyatarasyAm", "nityam"}:
                op_term = slp

        # 3. Create PrimitiveOp
        prim_op, op_type, sub_val = resolve_term_to_primitive(op_term or "", is_ekadesha=is_ekadesha, right_cond_present=bool(right_cond))
        
        if (not has_target and not left_cond and not right_cond) or op_type in {"prohibit", "prakritibhava"}:
            prim_op = non_op
            
        if sutra_id in {"6.1.107", "6.1.108"}:
            prim_op = non_op
        
        # 4. Resolve Domain from Adhikāra
        domain = "sapada"
        if "पूर्वत्रासिद्धम्" in ad or "पूर्वत्रासिद्धम्" in ss:
            domain = "tripadi"
        elif "संहितायाम्" in ad or "संहितायाम्" in ss:
            domain = "samhita"
        elif "पदस्य" in ad or "पदस्य" in ss:
            domain = "sapada"

        return RuleSpec(
            id=sutra_id,
            name=name,
            rule_type="vidhi_sandhi",
            priority=priority,
            target_context=target_cond if has_target else None,
            left_context=left_cond,
            right_context=right_cond,
            operation=prim_op,
            governance={"domain": domain, "source": "ss_parser"}
        )
