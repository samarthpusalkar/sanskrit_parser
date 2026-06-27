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
        op = self.spec.operation
        if op.op_type == "elide":
            return left[:-1], right
        elif op.op_type == "merge_sandhi":
            # Basic savarna/guna/vriddhi approximation for AST execution
            sub = op.substitute or ""
            if sub == "dirgha":
                # savarna dirgha
                vmap = {'a': 'A', 'A': 'A', 'i': 'I', 'I': 'I', 'u': 'U', 'U': 'U', 'f': 'F', 'F': 'F'}
                return left[:-1] + vmap.get(left[-1], left[-1]), right[1:]
            return left[:-1] + sub, right[1:]
        elif op.op_type == "substitute":
            sub = op.substitute or ""
            if sub == "yan":
                ymap = {'i': 'y', 'I': 'y', 'u': 'v', 'U': 'v', 'f': 'r', 'F': 'r'}
                return left[:-1] + ymap.get(left[-1], left[-1]), right
            return left[:-1] + sub, right

        return left, right

    def revert(self, combined_surface: str, grammatical_context: Dict[str, Any]) -> List[Tuple[str, str]]:
        # AST retrograde inversion
        splits = []
        op = self.spec.operation
        if op.op_type == "substitute" and op.substitute == "yan":
            for y_char, i_chars in [('y', ['i', 'I']), ('v', ['u', 'U']), ('r', ['f', 'F'])]:
                idx = combined_surface.find(y_char)
                while idx != -1 and idx + 1 < len(combined_surface):
                    r_part = combined_surface[idx+1:]
                    for ic in i_chars:
                        l_part = combined_surface[:idx] + ic
                        splits.append((l_part, r_part))
                    idx = combined_surface.find(y_char, idx + 1)
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
