"""
Master Pāṇinian AST Compiler Pipeline (Phase A Implementation).

Automates the compilation of all 3,983 SQLite sūtras via Vibhakti decoding (`PadaChedaParser`),
translating them into formal AST predicates (`SutraAstBuilder`), and bridging them into
concrete operational runtime transducer objects (`CompiledVidhiRule`).
"""

import sqlite3
from pathlib import Path
from typing import List, Dict, Any, Tuple
from compiler.pada_cheda import PadaChedaParser
from compiler.ast_builder import SutraAstBuilder
from rule_engine.dsl import RuleSpec
from rules.base import PaniniRule
from core.shiva_sutras import PratyaharaResolver


class CompiledVidhiRule(PaniniRule):
    """Runtime executable rule object compiled from a formal RuleSpec AST."""

    def __init__(self, spec: RuleSpec):
        super().__init__(spec.id, spec.name)
        self.spec = spec

    def matches(self, left: str, right: str, grammatical_context: Dict[str, Any]) -> bool:
        if not left or not right:
            return False

        # 1. Check Target Context (left ending)
        tgt = self.spec.target_context
        l_char = left[-1]
        if tgt.pratyahara:
            if not PratyaharaResolver.contains(tgt.pratyahara, l_char):
                return False
        elif tgt.exact_text:
            allowed = set(tgt.exact_text.split(","))
            if l_char not in allowed and left != tgt.exact_text:
                return False

        # 2. Check Right Context (right start)
        rgt = self.spec.right_context
        if rgt:
            r_char = right[0]
            if rgt.pratyahara:
                if not PratyaharaResolver.contains(rgt.pratyahara, r_char):
                    return False
            elif rgt.exact_text:
                allowed = set(rgt.exact_text.split(","))
                if r_char not in allowed and right != rgt.exact_text:
                    return False

        return True

    def apply(self, left: str, right: str, grammatical_context: Dict[str, Any]) -> Tuple[str, str]:
        if not left:
            return left, right
        op = self.spec.operation
        l_char = left[-1]

        if op.op_type == "elide":
            return left[:-1], right

        elif op.op_type in {"merge_savarna", "dirgha"} or op.substitute == "dirgha":
            dirgha_map = {'a': 'A', 'A': 'A', 'i': 'I', 'I': 'I', 'u': 'U', 'U': 'U', 'f': 'F', 'F': 'F'}
            res_char = dirgha_map.get(l_char, l_char)
            return left[:-1] + res_char, right[1:] if op.op_type == "merge_savarna" and right else right

        elif op.op_type == "sanjna_substitute":
            sub = op.substitute
            if sub == "guna":
                gmap = {'i': 'e', 'I': 'e', 'u': 'o', 'U': 'o', 'f': 'ar', 'F': 'ar', 'x': 'al'}
                return left[:-1] + gmap.get(l_char, 'a'), right
            elif sub == "vriddhi":
                vmap = {'a': 'A', 'A': 'A', 'i': 'E', 'I': 'E', 'u': 'O', 'U': 'O', 'f': 'Ar', 'F': 'Ar'}
                return left[:-1] + vmap.get(l_char, 'A'), right

        elif op.op_type in {"bijection_substitute", "substitute"}:
            t_prat = self.spec.target_context.pratyahara
            s_prat = op.substitute
            if t_prat and s_prat:
                try:
                    t_list = PratyaharaResolver.resolve_list(t_prat)
                    s_list = PratyaharaResolver.resolve_list(s_prat)
                    if len(t_list) == len(s_list):
                        fwd_map = dict(zip(t_list, s_list))
                        # Expand short/long savarna pairs for vowels
                        savarna = {'A': 'a', 'I': 'i', 'U': 'u', 'F': 'f'}
                        lookup = fwd_map.get(l_char) or fwd_map.get(savarna.get(l_char, ''))
                        if lookup:
                            return left[:-1] + lookup, right
                except Exception:
                    pass
            if op.substitute and op.substitute not in {"dirgha", "guna", "vriddhi"}:
                return left[:-1] + op.substitute, right

        return left, right

    def revert(self, combined_surface: str, grammatical_context: Dict[str, Any]) -> List[Tuple[str, str]]:
        splits = []
        op = self.spec.operation
        if not combined_surface:
            return splits

        if op.op_type in {"bijection_substitute", "substitute"}:
            t_prat = self.spec.target_context.pratyahara
            s_prat = op.substitute
            if t_prat and s_prat:
                try:
                    t_list = PratyaharaResolver.resolve_list(t_prat)
                    s_list = PratyaharaResolver.resolve_list(s_prat)
                    if len(t_list) == len(s_list):
                        bwd_map = dict(zip(s_list, t_list))
                        savarna_long = {'i': ['i', 'I'], 'u': ['u', 'U'], 'f': ['f', 'F'], 'a': ['a', 'A']}
                        for s_char, t_char in bwd_map.items():
                            targets = savarna_long.get(t_char, [t_char])
                            idx = combined_surface.find(s_char)
                            while idx != -1 and idx + 1 < len(combined_surface):
                                r_part = combined_surface[idx+len(s_char):]
                                for tc in targets:
                                    l_part = combined_surface[:idx] + tc
                                    splits.append((l_part, r_part))
                                idx = combined_surface.find(s_char, idx + 1)
                except Exception:
                    pass
        return splits


class MasterCompilerPipeline:
    """Master Pipeline orchestrating SQLite ingestion -> AST compilation -> Runtime Registration."""

    _compiled_cache: List[PaniniRule] = []
    _loaded = False

    @classmethod
    def compile_all(cls, db_path: str = None) -> List[PaniniRule]:
        if cls._loaded and cls._compiled_cache:
            return cls._compiled_cache

        if db_path is None:
            db_path = str(Path(__file__).parent.parent / "data/sanskrit_master.db")

        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        rows = cur.execute("SELECT id, sutra_slp1, pada_cheda FROM sutras WHERE pada_cheda != ''").fetchall()
        conn.close()

        compiled = []
        for sid, slp, pc in rows:
            tokens = PadaChedaParser.parse(pc)
            spec = SutraAstBuilder.build(sid, slp, tokens)
            rule = CompiledVidhiRule(spec)
            compiled.append(rule)

        cls._compiled_cache = compiled
        cls._loaded = True
        return cls._compiled_cache
