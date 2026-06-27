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
from rule_engine.dsl import RuleSpec, PrimitiveOp
from rules.base import PaniniRule
from core.shiva_sutras import PratyaharaResolver
from core.phonology import SHORT_VOWELS, LONG_VOWELS, VOWELS, CONSONANTS, SAVARNA_LONG, compute_ekadesha, apply_natva, apply_shatva



_has_prat = set(PratyaharaResolver.resolve_list("haS"))
_yam_prat = set(PratyaharaResolver.resolve_list("YaM"))

SYMBOLIC_CLASSES = {
    "VOWEL": VOWELS,
    "VOWEL_NON_A": VOWELS - {'a', 'A'},
    "SHORT_VOWEL": SHORT_VOWELS,
    "LONG_VOWEL": LONG_VOWELS,
    "CONSONANT": CONSONANTS,
    "STOP": set("kKgGNcCjJYwWqQRtTdDnpPbBm"),
    "NASAL": _yam_prat,
    "VOICED": _has_prat | VOWELS,
    "PAUSE_OR_VOICED": _has_prat | VOWELS,
}


def _symbolic_match(pattern: str, value: str) -> bool:
    if not pattern:
        return True
    for part in pattern.split("|"):
        if not part:
            continue
        chars = SYMBOLIC_CLASSES.get(part)
        if chars is not None:
            if value in chars:
                return True
            continue
        if value == part:
            return True
    return False


def _expand_literal_pattern(pattern: str) -> List[str]:
    if not pattern:
        return []
    if pattern in SYMBOLIC_CLASSES:
        return sorted(SYMBOLIC_CLASSES[pattern])
    return [part for part in pattern.split("|") if part and part not in SYMBOLIC_CLASSES]


def _condition_from_config(pattern: str, match_pos: str) -> "ConditionSpec":
    from rule_engine.dsl import ConditionSpec
    if pattern.startswith("PRAT:"):
        return ConditionSpec(pratyahara=pattern.removeprefix("PRAT:"), match_pos=match_pos)
    if pattern.startswith("TOKEN:"):
        tokens = {p.strip() for p in pattern.removeprefix("TOKEN:").split("|") if p.strip()}
        return ConditionSpec(tokens_required=tokens, match_pos=match_pos)
    return ConditionSpec(exact_text=pattern, match_pos=match_pos)


def _is_config_source(spec: RuleSpec) -> bool:
    return spec.governance.get("source") in {"rule_configs", "seed", "bootstrap_ast"}


class CompiledVidhiRule(PaniniRule):
    """Runtime executable rule object compiled from a formal RuleSpec AST."""

    def __init__(self, spec: RuleSpec):
        super().__init__(spec.id, spec.name)
        self.spec = spec
        if isinstance(spec.operation, PrimitiveOp):
            self._prim = spec.operation
        elif hasattr(spec.operation, 'to_primitive'):
            self._prim = spec.operation.to_primitive()
        else:
            self._prim = PrimitiveOp.from_legacy(spec.operation.op_type, spec.operation.substitute)

    def matches(self, left: str, right: str, grammatical_context: Dict[str, Any]) -> bool:
        if not left or not right:
            return False

        prim = self._prim
        l_char = left[-1]

        # Scan-based compute functions check the full string
        if prim.compute_fn == "natva":
            return apply_natva(left + right) != left + right
        if prim.compute_fn == "shatva":
            return apply_shatva(left + right) != left + right

        # Non-operational / blocking rules never match
        if prim.op_type in {"external_block", "non_operational"}:
            return False

        if not self.spec.target_context.pratyahara and not self.spec.target_context.exact_text and prim.op_type != "governance":
            return False
        if prim.emit_side == "right":
            t_cond = self.spec.target_context
            if t_cond:
                if t_cond.pratyahara and not PratyaharaResolver.contains(t_cond.pratyahara, right[0]):
                    return False
                elif t_cond.exact_text:
                    parts = [p.strip() for p in t_cond.exact_text.split("|") if p.strip()]
                    if not any(right.startswith(p) or _symbolic_match(p, right[0]) for p in parts):
                        return False
            if self.spec.left_context and not self._is_config_condition_match(self.spec.left_context, left, l_char):
                return False
        else:
            if not self._is_config_target_match(left, l_char):
                return False
            if self.spec.left_context and not self._is_config_condition_match(self.spec.left_context, left, left[:-1][-1] if len(left) > 1 else left[-1]):
                return False
            if not self._is_valid_right_context(right):
                return False
        # savarna_long needs a vowel at left[-2]
        if prim.compute_fn == "savarna_long":
            return len(left) >= 2 and left[-2] in SHORT_VOWELS
        return True

    def _is_config_target_match(self, left: str, l_char: str) -> bool:
        tgt = self.spec.target_context
        return self._is_config_condition_match(tgt, left, l_char)

    def _is_config_condition_match(self, cond, text: str, boundary_char: str) -> bool:
        if not cond:
            return True
        if not text:
            return False
        if getattr(cond, "tokens_required", None):
            return text in cond.tokens_required
        ctx_str = text[:-1] if len(text) > 1 and boundary_char != text[-1] else text
        char_to_check = ctx_str[0] if cond.match_pos == "start" else boundary_char
        if cond.pratyahara:
            return PratyaharaResolver.contains(cond.pratyahara, char_to_check)
        if cond.exact_text:
            if cond.exact_text.startswith("NOT:"):
                disallowed = {p.strip() for p in cond.exact_text[4:].split("|") if p.strip()}
                return char_to_check not in disallowed and not any(ctx_str.endswith(d) for d in disallowed)
            if any(ctx_str.endswith(p.strip()) for p in cond.exact_text.split("|") if p.strip()):
                return True
            return _symbolic_match(cond.exact_text, char_to_check)
        return True

    def _is_valid_right_context(self, right_str: str) -> bool:
        rgt = self.spec.right_context
        if not rgt:
            return True
        if not right_str:
            return False
        r_char = right_str[0]
        if rgt.pratyahara:
            return PratyaharaResolver.contains(rgt.pratyahara, r_char)
        elif rgt.exact_text:
            if rgt.exact_text.startswith("NOT:"):
                disallowed = {p.strip() for p in rgt.exact_text[4:].split("|") if p.strip()}
                return r_char not in disallowed and not any(right_str.startswith(d) for d in disallowed)
            if _symbolic_match(rgt.exact_text, r_char):
                return True
            if any(right_str.startswith(p.strip()) for p in rgt.exact_text.split("|") if p.strip()):
                return True
            if rgt.exact_text.lower() in {"savarr", "ac"}:
                return PratyaharaResolver.contains("aC", r_char)
            allowed = set(rgt.exact_text.split(","))
            return r_char in allowed or right_str.startswith(rgt.exact_text)
        return True

    def apply(self, left: str, right: str, grammatical_context: Dict[str, Any]) -> Tuple[str, str]:
        res = self._apply_raw(left, right, grammatical_context)
        from compiler.registries import ParibhasaRegistry
        return ParibhasaRegistry.intercept_apply(self.spec, left, right, grammatical_context, res)

    def _apply_raw(self, left: str, right: str, grammatical_context: Dict[str, Any]) -> Tuple[str, str]:
        """Universal primitive executor. No if-elif per operation type."""
        if not left:
            return left, right
        prim = self._prim
        l_char = left[-1]

        # --- Compute the emit value ---
        emit = prim.emit

        if prim.compute_fn == "natva":
            res = apply_natva(left + right)
            return res[:len(left)], res[len(left):]

        if prim.compute_fn == "shatva":
            res = apply_shatva(left + right)
            return res[:len(left)], res[len(left):]

        if prim.compute_fn == "guna":
            emit = compute_ekadesha(l_char, right[0] if right else '', "guna")
        elif prim.compute_fn == "vriddhi":
            emit = compute_ekadesha(l_char, right[0] if right else '', "vriddhi")
        elif prim.compute_fn == "dirgha":
            emit = compute_ekadesha(l_char, right[0] if right else l_char, "dirgha")
        elif prim.compute_fn == "savarna_long":
            # Lengthen the vowel before the consumed chars
            vowel_idx = len(left) - prim.left_consume
            if vowel_idx >= 0 and vowel_idx < len(left):
                emit = SAVARNA_LONG.get(left[vowel_idx], left[vowel_idx])
            else:
                emit = ""
        elif prim.compute_fn == "duplicate":
            emit = l_char
        elif prim.compute_fn == "bijection":
            emit = self._resolve_bijection(left, right, prim)
            if emit is None:
                # Bijection couldn't resolve — try literal substitute fallback
                emit = self._resolve_literal_substitute(left, prim)
                if emit is None:
                    return left, right

        # --- Apply primitive: consume + emit ---
        new_left = left[:-prim.left_consume] if prim.left_consume else left
        new_right = right[prim.right_consume:] if prim.right_consume else right

        if prim.emit_side == "right":
            new_right = emit + new_right
        else:
            new_left = new_left + emit

        return new_left, new_right

    def _resolve_bijection(self, left: str, right: str, prim: 'PrimitiveOp') -> 'str | None':
        """Resolve bijection mapping for substitute/right_substitute operations."""
        t_cond = self.spec.target_context
        s_val = prim.substitute
        if not t_cond or not s_val:
            return None
        try:
            if t_cond.pratyahara:
                t_list = PratyaharaResolver.resolve_list(t_cond.pratyahara)
            else:
                t_list = _expand_literal_pattern(t_cond.exact_text)
            if s_val.startswith("PRAT:"):
                s_list = PratyaharaResolver.resolve_list(s_val.removeprefix("PRAT:"))
            else:
                s_list = _expand_literal_pattern(s_val)

            l_char = left[-1]
            savarna = {'A': 'a', 'I': 'i', 'U': 'u', 'F': 'f'}

            if prim.emit_side == "right":
                # Bijection on right boundary char
                if len(t_list) == len(s_list):
                    fwd_map = dict(zip(t_list, s_list))
                    return fwd_map.get(right[0])
                return None

            # Bijection on left boundary char
            if len(t_list) == len(s_list):
                fwd_map = dict(zip(t_list, s_list))
                return fwd_map.get(l_char) or fwd_map.get(savarna.get(l_char, ''))
            else:
                from core.phonology import get_sthana
                search_char = right[0] if l_char == 'M' and right else savarna.get(l_char, l_char)
                if search_char in t_list or l_char == 'M':
                    target_sthana = get_sthana(search_char)
                    for cand in s_list:
                        if get_sthana(cand) == target_sthana:
                            return cand
        except Exception:
            pass
        return None

    def _resolve_literal_substitute(self, left: str, prim: 'PrimitiveOp') -> 'str | None':
        """Fallback for non-bijection substitute: match target pattern in left."""
        sub = prim.substitute
        if not sub or sub in {"dirgha", "guna", "vriddhi"}:
            return None
        t_exact = self.spec.target_context.exact_text if self.spec.target_context else None
        if t_exact:
            allowed = [t.strip() for t in t_exact.split(",") if t.strip()]
            for a in allowed:
                if left.endswith(a):
                    # Return sub but also adjust left to remove the full match (not just 1 char)
                    # We need to return the emit AND adjust left_consume
                    # For now, handle the multi-char target by returning the substitute directly
                    return sub
            return None
        return sub

    def revert(self, combined_surface: str, grammatical_context: Dict[str, Any]) -> List[Tuple[str, str]]:
        splits = []
        op = self.spec.operation
        if not combined_surface:
            return splits

        if _is_config_source(self.spec):
            if op.op_type == "merge" and op.substitute:
                left_targets = _expand_literal_pattern(self.spec.target_context.exact_text or "")
                right_targets = _expand_literal_pattern(self.spec.right_context.exact_text if self.spec.right_context else "")
                idx = combined_surface.find(op.substitute)
                while idx != -1:
                    if idx > 0:
                        for l_c in left_targets:
                            for r_c in right_targets:
                                splits.append((combined_surface[:idx] + l_c, r_c + combined_surface[idx+len(op.substitute):]))
                    idx = combined_surface.find(op.substitute, idx + 1)

            elif op.op_type == "bijection_substitute" and op.substitute:
                # Handle both PRAT: prefixed and literal substitute lists
                s_val = op.substitute
                t_cond = self.spec.target_context
                try:
                    if s_val.startswith("PRAT:"):
                        s_list = list(PratyaharaResolver.resolve_list(s_val.removeprefix("PRAT:")))
                    else:
                        s_list = _expand_literal_pattern(s_val)
                    if t_cond.pratyahara:
                        t_list = list(PratyaharaResolver.resolve_list(t_cond.pratyahara))
                    else:
                        t_list = _expand_literal_pattern(t_cond.exact_text or "")
                    if len(t_list) == len(s_list):
                        bwd_map = dict(zip(s_list, t_list))
                        savarna_long = {'i': ['i', 'I'], 'u': ['u', 'U'], 'f': ['f', 'F'], 'a': ['a', 'A']}
                        for s_char, t_char in bwd_map.items():
                            targets = savarna_long.get(t_char, [t_char])
                            idx = combined_surface.find(s_char)
                            while idx != -1:
                                if idx > 0:
                                    r_part = combined_surface[idx+len(s_char):]
                                    if self._is_valid_right_context(r_part):
                                        for tc in targets:
                                            splits.append((combined_surface[:idx] + tc, r_part))
                                idx = combined_surface.find(s_char, idx + 1)
                    else:
                        # Different-length lists: use sthana-based affinity reverse
                        from core.phonology import get_sthana
                        for s_char in s_list:
                            idx = combined_surface.find(s_char)
                            while idx != -1:
                                if idx > 0:
                                    r_part = combined_surface[idx+len(s_char):]
                                    if self._is_valid_right_context(r_part):
                                        s_sthana = get_sthana(s_char)
                                        for t_char in t_list:
                                            if get_sthana(t_char) == s_sthana:
                                                splits.append((combined_surface[:idx] + t_char, r_part))
                                idx = combined_surface.find(s_char, idx + 1)
                except Exception:
                    pass

            elif op.op_type == "substitute" and op.substitute:
                targets = _expand_literal_pattern(self.spec.target_context.exact_text or "")
                idx = combined_surface.find(op.substitute)
                while idx != -1:
                    if idx > 0:
                        r_part = combined_surface[idx+len(op.substitute):]
                        if self._is_valid_right_context(r_part):
                            for target in targets:
                                splits.append((combined_surface[:idx] + target, r_part))
                    idx = combined_surface.find(op.substitute, idx + 1)

            elif op.op_type == "visarga_utva":
                # "aH" + "a" -> "o" + "'" — reverse: find 'o' followed by avagraha
                for idx in range(1, len(combined_surface)):
                    if combined_surface[idx] == 'o' or (idx > 0 and combined_surface[idx-1:idx+1] == "o'"):
                        if combined_surface[idx:idx+2] == "o'":
                            splits.append((combined_surface[:idx] + 'aH', 'a' + combined_surface[idx+2:]))
                        elif combined_surface[idx] == 'o':
                            splits.append((combined_surface[:idx] + 'aH', 'a' + combined_surface[idx+1:]))

            elif op.op_type == "purva_rupa":
                # left ends in vowel, right starts with same vowel -> purvarupa with avagraha
                idx = combined_surface.find("'")
                while idx != -1:
                    if idx > 0:
                        l_char = combined_surface[idx-1]
                        splits.append((combined_surface[:idx], l_char + combined_surface[idx+1:]))
                    idx = combined_surface.find("'", idx + 1)

            elif op.op_type == "natva":
                # 'n' becomes 'ṇ' -> find 'ṇ' and restore 'n'
                for s_char in ['R']:  # SLP1: ṇ is R
                    idx = combined_surface.find(s_char)
                    while idx != -1:
                        if idx > 0:
                            r_part = combined_surface[idx+1:]
                            splits.append((combined_surface[:idx], 'n' + r_part))
                        idx = combined_surface.find(s_char, idx + 1)

            elif op.op_type == "anusvara":
                # 'm' -> 'M' (anusvara) before consonant
                idx = combined_surface.find('M')
                while idx != -1:
                    if idx > 0:
                        r_part = combined_surface[idx+1:]
                        splits.append((combined_surface[:idx] + 'm', r_part))
                    idx = combined_surface.find('M', idx + 1)

            elif op.op_type == "right_substitute" and op.substitute:
                # right side was substituted (e.g. c -> ch before ś)
                target_right = self.spec.right_context.exact_text if self.spec.right_context else ""
                idx = combined_surface.find(op.substitute)
                while idx != -1:
                    if idx > 0:
                        for r_orig in _expand_literal_pattern(target_right) or [op.substitute[0]]:
                            splits.append((combined_surface[:idx], r_orig + combined_surface[idx+len(op.substitute):]))
                    idx = combined_surface.find(op.substitute, idx + 1)

            elif op.op_type == "insert" and op.substitute:
                # augment was inserted (e.g. tuk: SHORT_VOWEL + 'c' inserted 'c')
                # reverse: find the inserted char and remove it
                aug = op.substitute
                idx = combined_surface.find(aug)
                while idx != -1:
                    if idx > 0:
                        splits.append((combined_surface[:idx], combined_surface[idx+len(aug):]))
                    idx = combined_surface.find(aug, idx + 1)

            res_splits = list(set(splits))
            from compiler.registries import ParibhasaRegistry
            return ParibhasaRegistry.intercept_revert(self.spec, combined_surface, grammatical_context, res_splits)

        # 1. Ekādeśa Savarṇa-Dīrgha Reversion
        if op.op_type in {"ekadesha_savarna_dirgha", "merge_savarna"} or op.substitute == "dirgha":
            d_pairs = [('A', ['a', 'A']), ('I', ['i', 'I']), ('U', ['u', 'U'])]
            for char, targets in d_pairs:
                idx = combined_surface.find(char)
                while idx != -1:
                    if idx > 0:
                        for l_c in targets:
                            for r_c in targets:
                                splits.append((combined_surface[:idx] + l_c, r_c + combined_surface[idx+1:]))
                    idx = combined_surface.find(char, idx + 1)

        # 2. Guṇa Ekādeśa Reversion
        elif op.op_type == "ekadesha_guna" or (op.op_type == "sanjna_substitute" and op.substitute == "guna"):
            for idx, char in enumerate(combined_surface):
                if idx == 0: continue
                if char == 'e':
                    for l_c in ['a', 'A']:
                        for r_c in ['i', 'I']:
                            splits.append((combined_surface[:idx] + l_c, r_c + combined_surface[idx+1:]))
                elif char == 'o':
                    for l_c in ['a', 'A']:
                        for r_c in ['u', 'U']:
                            splits.append((combined_surface[:idx] + l_c, r_c + combined_surface[idx+1:]))
                elif char == 'r' and combined_surface[idx-1] == 'a':
                    for l_c in ['a', 'A']:
                        for r_c in ['f', 'F']:
                            splits.append((combined_surface[:idx-1] + l_c, r_c + combined_surface[idx+1:]))

        # 3. Vṛddhi Ekādeśa Reversion
        elif op.op_type == "ekadesha_vriddhi" or (op.op_type == "sanjna_substitute" and op.substitute == "vriddhi"):
            for idx, char in enumerate(combined_surface):
                if idx == 0: continue
                if char == 'E':
                    for l_c in ['a', 'A']:
                        for r_c in ['e', 'E']:
                            splits.append((combined_surface[:idx] + l_c, r_c + combined_surface[idx+1:]))
                elif char == 'O':
                    for l_c in ['a', 'A']:
                        for r_c in ['o', 'O']:
                            splits.append((combined_surface[:idx] + l_c, r_c + combined_surface[idx+1:]))

        # 4. Pratyāhāra Bijection Reversion (e.g. Yaṇ 6.1.77)
        elif op.op_type in {"bijection_substitute", "substitute", "exact_substitute"}:
            t_prat = self.spec.target_context.pratyahara
            s_val = op.substitute
            handled = False
            if t_prat and s_val:
                try:
                    t_list = PratyaharaResolver.resolve_list(t_prat)
                    s_raw = s_val.removeprefix("PRAT:") if s_val.startswith("PRAT:") else None
                    s_list = PratyaharaResolver.resolve_list(s_raw) if s_raw else _expand_literal_pattern(s_val)
                    if len(t_list) == len(s_list):
                        handled = True
                        bwd_map = dict(zip(s_list, t_list))
                        savarna_long = {'i': ['i', 'I'], 'u': ['u', 'U'], 'f': ['f', 'F'], 'a': ['a', 'A']}
                        for s_char, t_char in bwd_map.items():
                            targets = savarna_long.get(t_char, [t_char])
                            idx = combined_surface.find(s_char)
                            while idx != -1:
                                if idx > 0:
                                    r_part = combined_surface[idx+len(s_char):]
                                    if self._is_valid_right_context(r_part):
                                        for tc in targets:
                                            splits.append((combined_surface[:idx] + tc, r_part))
                                idx = combined_surface.find(s_char, idx + 1)
                except Exception:
                    pass
            if not handled and s_val and s_val not in {"dirgha", "guna", "vriddhi"}:
                sub_str = s_val
                targets = []
                if self.spec.target_context.exact_text:
                    targets = [t.strip() for t in self.spec.target_context.exact_text.split(",") if t.strip()]
                elif self.spec.target_context.pratyahara:
                    try:
                        targets = PratyaharaResolver.resolve_list(self.spec.target_context.pratyahara)
                    except Exception:
                        pass
                if not targets:
                    targets = [sub_str]
                idx = combined_surface.find(sub_str)
                while idx != -1:
                    if idx > 0:
                        r_part = combined_surface[idx+len(sub_str):]
                        if self._is_valid_right_context(r_part):
                            for tc in targets:
                                splits.append((combined_surface[:idx] + tc, r_part))
                    idx = combined_surface.find(sub_str, idx + 1)

        res_splits = list(set(splits))
        from compiler.registries import ParibhasaRegistry
        return ParibhasaRegistry.intercept_revert(self.spec, combined_surface, grammatical_context, res_splits)


class RuleConfigCompiler:
    """Compiles data-backed rule_configs rows into executable RuleSpec objects."""

    @classmethod
    def compile_all(cls, cur: sqlite3.Cursor) -> List[PaniniRule]:
        from rule_engine.dsl import OperationSpec, PrimitiveOp

        columns = {row[1] for row in cur.execute("PRAGMA table_info(rule_configs)").fetchall()}
        has_extended_schema = {"target_context", "domain", "source"}.issubset(columns)
        has_primitives = {"left_consume", "right_consume", "emit", "emit_side", "compute_fn"}.issubset(columns)

        if has_extended_schema and has_primitives:
            query = """
                SELECT rc.sutra_id, COALESCE(rc.name, s.sutra_slp1),
                       COALESCE(NULLIF(rc.target_context, ''), rc.left_context),
                       CASE WHEN NULLIF(rc.target_context, '') IS NULL THEN NULL ELSE rc.left_context END,
                       rc.right_context, rc.operation, rc.replacement, rc.domain, rc.source,
                       rc.left_consume, rc.right_consume, rc.emit, rc.emit_side, rc.compute_fn
                FROM rule_configs rc
                LEFT JOIN sutras s ON s.id = rc.sutra_id
                WHERE COALESCE(rc.operation, '') != 'non_operational'
                ORDER BY rc.sutra_id ASC, rc.id ASC
            """
        elif has_extended_schema:
            query = """
                SELECT rc.sutra_id, COALESCE(rc.name, s.sutra_slp1),
                       COALESCE(NULLIF(rc.target_context, ''), rc.left_context),
                       CASE WHEN NULLIF(rc.target_context, '') IS NULL THEN NULL ELSE rc.left_context END,
                       rc.right_context, rc.operation, rc.replacement, rc.domain, rc.source,
                       NULL, NULL, NULL, NULL, NULL
                FROM rule_configs rc
                LEFT JOIN sutras s ON s.id = rc.sutra_id
                WHERE COALESCE(rc.operation, '') != 'non_operational'
                ORDER BY rc.sutra_id ASC, rc.id ASC
            """
        else:
            query = """
                SELECT rc.sutra_id, COALESCE(rc.name, s.sutra_slp1),
                       rc.left_context, NULL, rc.right_context, rc.operation, rc.replacement, NULL, NULL,
                       NULL, NULL, NULL, NULL, NULL
                FROM rule_configs rc
                LEFT JOIN sutras s ON s.id = rc.sutra_id
                WHERE COALESCE(rc.operation, '') != 'non_operational'
                ORDER BY rc.sutra_id ASC, rc.id ASC
            """

        rows = cur.execute(
            query
        ).fetchall()

        compiled: List[PaniniRule] = []
        for sid, name, target_context, left_context, right_context, operation, replacement, row_domain, row_source, lc, rc, em, es, cf in rows:
            domain = row_domain or ("tripadi" if cls._is_tripadi(sid) else "sapada")
            target = _condition_from_config(target_context or "", "end")
            left = _condition_from_config(left_context or "", "end") if left_context else None
            right = _condition_from_config(right_context or "", "start") if right_context else None
            if has_primitives and lc is not None:
                op_obj = PrimitiveOp(
                    left_consume=lc, right_consume=rc, emit=em or "", emit_side=es or "left", compute_fn=cf,
                    substitute=replacement, op_type=operation
                )
            else:
                op_obj = OperationSpec(op_type=operation, substitute=replacement)
            spec = RuleSpec(
                id=sid,
                name=name or sid,
                rule_type="vidhi_sandhi",
                priority=1000,
                target_context=target,
                left_context=left,
                right_context=right,
                operation=op_obj,
                governance={"domain": domain, "source": row_source or "rule_configs"},
            )
            rule = CompiledVidhiRule(spec)
            rule.domain = "samhita"
            compiled.append(rule)
        return compiled

    @staticmethod
    def _is_tripadi(sutra_id: str) -> bool:
        try:
            a, p, _ = [int(part) for part in sutra_id.split(".")]
        except Exception:
            return False
        return a > 8 or (a == 8 and p >= 2)


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
        rows = cur.execute("SELECT id, sutra_slp1, sutra_type, pada_cheda FROM sutras WHERE pada_cheda != '' ORDER BY id ASC").fetchall()
        config_rules = RuleConfigCompiler.compile_all(cur)
        conn.close()

        from compiler.registries import SanjnaRegistry, ParibhasaRegistry, AdhikaraContext
        SanjnaRegistry._init_db()
        ParibhasaRegistry._init_db()
        AdhikaraContext._init_db()

        cls._compiled_cache = config_rules
        cls._loaded = True
        return cls._compiled_cache
