"""
Anuvṛtti Context Inheritance Engine.

Resolves carried-over sūtra terms ('an') and governing headers ('ad')
by querying the historical Pada-cheda tags of earlier sūtras.
"""

from typing import Dict, List
from compiler.pada_cheda import PadaToken, PadaChedaParser


class AnuvrittiResolver:
    """Resolves carried over sūtra terms into active PadaToken lists."""

    def __init__(self, sutra_db: Dict[str, List[PadaToken]]):
        """
        :param sutra_db: Map of Sūtra ID (e.g. '11003') -> List[PadaToken]
        """
        self.sutra_db = sutra_db

    def resolve(self, current_tokens: List[PadaToken], anuvritti_raw: str) -> List[PadaToken]:
        """
        Combines current sūtra tokens with carried over Anuvṛtti tokens.
        If a carried over term exists in current_tokens (overridden), active sūtra wins.
        """
        active_tokens = list(current_tokens)
        if not anuvritti_raw or anuvritti_raw.strip() == "":
            return active_tokens

        # Parse anuvritti string e.g. "इकः$11003##गुण-वृद्धी$11003"
        chunks = anuvritti_raw.split("##")
        for chunk in chunks:
            chunk = chunk.strip()
            if not chunk or "$" not in chunk:
                continue

            parts = chunk.split("$")
            word_surface = parts[0].strip()
            source_id = parts[1].strip()

            # Look up word_surface in source sūtra's pada_cheda
            source_tokens = self.sutra_db.get(source_id, [])
            found_token = None
            for t in source_tokens:
                if t.devanagari == word_surface or word_surface in t.devanagari:
                    found_token = t
                    break

            if found_token:
                # Check if current sūtra already specifies a token of the same case (Utsarga override)
                case_exists = any(t.case == found_token.case for t in current_tokens if t.case in {1, 5, 6, 7})
                if not case_exists:
                    active_tokens.append(found_token)

        return active_tokens
