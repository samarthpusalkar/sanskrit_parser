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

        # --- Hardcoded phonological exceptions based on Vārtikas/complex rules ---
        if sutra_id == '6.1.109':
            return RuleSpec(
                id=sutra_id, name=name, rule_type="vidhi_sandhi", priority=priority,
                left_context=ConditionSpec(pratyahara="eN", match_pos="end"),
                right_context=ConditionSpec(exact_text="a", match_pos="start"),
                target_context=ConditionSpec(tags_required={"padanta"}, match_pos="end"),
                operation=PrimitiveOp(left_consume=0, right_consume=1, emit="'", emit_side="left", substitute="purva_rupa", op_type="purva_rupa"),
                governance={"source": "ss_parser", "domain": "samhita"}
            )
        if sutra_id == '8.2.66':
            return RuleSpec(
                id=sutra_id, name=name, rule_type="vidhi_sandhi", priority=priority,
                left_context=ConditionSpec(exact_text="s", match_pos="end"),
                right_context=None,
                target_context=ConditionSpec(tags_required={"padanta"}, match_pos="end"),
                operation=PrimitiveOp(left_consume=1, right_consume=0, emit="r", emit_side="left", substitute="r", op_type="exact_substitute"),
                governance={"source": "ss_parser", "domain": "tripadi"}
            )
        if sutra_id == '6.1.113': # ato roraplutad
            return RuleSpec(
                id=sutra_id, name=name, rule_type="vidhi_sandhi", priority=priority,
                left_context=ConditionSpec(exact_text="as", match_pos="end"),
                right_context=ConditionSpec(exact_text="a", match_pos="start"),
                target_context=ConditionSpec(tags_required={"padanta"}, match_pos="end"),
                operation=PrimitiveOp(left_consume=2, right_consume=1, emit="o'", emit_side="left", substitute="u", op_type="exact_substitute"),
                governance={"source": "ss_parser", "domain": "samhita"}
            )
        if sutra_id == '6.1.114': # hasi ca
            return RuleSpec(
                id=sutra_id, name=name, rule_type="vidhi_sandhi", priority=priority,
                left_context=ConditionSpec(exact_text="as", match_pos="end"),
                right_context=ConditionSpec(pratyahara="haS", match_pos="start"),
                target_context=ConditionSpec(tags_required={"padanta"}, match_pos="end"),
                operation=PrimitiveOp(left_consume=2, right_consume=0, emit="o", emit_side="left", substitute="u", op_type="exact_substitute"),
                governance={"source": "ss_parser", "domain": "samhita"}
            )

        if sutra_id == '8.3.12': # kan amredite
            return RuleSpec(
                id=sutra_id, name=name, rule_type="vidhi_sandhi", priority=priority,
                left_context=ConditionSpec(exact_text="kAn", match_pos="end"),
                right_context=ConditionSpec(exact_text="kAn", match_pos="start"),
                target_context=ConditionSpec(tags_required={"padanta"}, match_pos="end"),
                operation=PrimitiveOp(left_consume=1, right_consume=0, emit="Ms", emit_side="left", substitute="bijection", op_type="exact_substitute"),
                governance={"source": "ss_parser", "domain": "tripadi"}
            )
        if sutra_id == '8.2.39': # jhalam jaso 'nte
            return RuleSpec(
                id=sutra_id, name=name, rule_type="vidhi_sandhi", priority=priority,
                left_context=None,
                right_context=None,
                target_context=ConditionSpec(pratyahara="JaL", exact_text="NOT:s|z|S", tags_required={"padanta"}, match_pos="end"),
                operation=PrimitiveOp(left_consume=1, right_consume=0, emit="", emit_side="left", substitute="PRAT:jaS", op_type="bijection", compute_fn="bijection"),
                governance={"source": "ss_parser", "domain": "tripadi"}
            )
        if sutra_id == '8.4.55': # khari ca
            return RuleSpec(
                id=sutra_id, name=name, rule_type="vidhi_sandhi", priority=priority,
                left_context=None,
                right_context=ConditionSpec(pratyahara="Kar", match_pos="start"),
                target_context=ConditionSpec(pratyahara="JaL", match_pos="end"),
                operation=PrimitiveOp(left_consume=1, right_consume=0, emit="", emit_side="left", substitute="PRAT:car", op_type="bijection", compute_fn="bijection"),
                governance={"source": "ss_parser", "domain": "tripadi"}
            )
        if sutra_id == '8.3.15': # kharavasanayor visarjaniyah
            return RuleSpec(
                id=sutra_id, name=name, rule_type="vidhi_sandhi", priority=priority,
                left_context=ConditionSpec(exact_text="r", match_pos="end"),
                right_context=ConditionSpec(pratyahara="Kar", match_pos="start"),
                target_context=ConditionSpec(tags_required={"padanta"}, match_pos="end"),
                operation=PrimitiveOp(left_consume=1, right_consume=0, emit="H", emit_side="left", substitute="H", op_type="exact_substitute"),
                governance={"source": "ss_parser", "domain": "tripadi"}
            )
        if sutra_id == '8.3.34': # visarjaniyasya sah
            return RuleSpec(
                id=sutra_id, name=name, rule_type="vidhi_sandhi", priority=priority,
                left_context=ConditionSpec(exact_text="H", match_pos="end"),
                right_context=ConditionSpec(pratyahara="Kar", match_pos="start"),
                target_context=ConditionSpec(tags_required={"padanta"}, match_pos="end"),
                operation=PrimitiveOp(left_consume=1, right_consume=0, emit="s", emit_side="left", substitute="s", op_type="exact_substitute"),
                governance={"source": "ss_parser", "domain": "tripadi"}
            )
        if sutra_id == '8.4.40': # stoH ScunA ScuH
            return RuleSpec(
                id=sutra_id, name=name, rule_type="vidhi_sandhi", priority=priority,
                left_context=None,
                right_context=ConditionSpec(exact_text="S|c|C|j|J|Y", match_pos="start"),
                target_context=ConditionSpec(exact_text="s|t|T|d|D|n", match_pos="end"),
                operation=PrimitiveOp(left_consume=1, right_consume=0, emit="", emit_side="left", substitute="S|c|C|j|J|Y", op_type="bijection", compute_fn="bijection"),
                governance={"source": "ss_parser", "domain": "tripadi"}
            )
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
            
        # 4. Resolve Domain from Adhikāra and Sūtra ID
        domain = "sapada"
        parts = sutra_id.split(".")
        if len(parts) >= 2:
            try:
                adhyaya = int(parts[0])
                pada = int(parts[1])
                if adhyaya > 8 or (adhyaya == 8 and pada >= 2):
                    domain = "tripadi"
            except ValueError:
                pass

        if domain != "tripadi":
            if sutra_id in {"6.1.102", "6.1.103", "6.1.104", "6.1.105", "6.1.106", "6.1.107", "6.1.108", "6.1.110", "6.1.111", "6.1.112"}:
                domain = "angasya"
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
