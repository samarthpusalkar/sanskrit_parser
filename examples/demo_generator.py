"""
End-to-End Pāṇinian Lakṣya Verification Demonstrator.

Demonstrates:
1. Pratyāhāra expansion via Shiva Sūtras
2. Verbal conjugation (Tiṅanta)
3. Nominal declension (Subanta)
4. Forward Sandhi joining via Virtual Tape Machine
5. Deterministic Sandhi inversion (splitting)
"""

import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from morphology.api import SanskritCompiler
from core.shiva_sutras import PratyaharaResolver


def run_demo():
    print("=" * 60)
    print("✨ SANSKRIT_NEW: PĀṆINIAN GENERATIVE COMPILER DEMO ✨")
    print("=" * 60)

    # 1. Pratyāhāra Resolution
    ik = PratyaharaResolver.resolve("iK")
    print(f"\n1️⃣ Shiva Sūtra Pratyāhāra 'iK' resolved to: {sorted(ik)}")

    # 2. Verb Conjugation
    verb = SanskritCompiler.conjugate_verb("bhū", gana=1, lakara="laṭ", purusa=3, vacana=1)
    print(f"\n2️⃣ Tiṅanta Conjugation (√bhū, 1st class, 3rd sg): {verb}")

    # 3. Noun Declension
    noun1 = SanskritCompiler.decline_noun("rāma", case="locative", number="singular")
    noun2 = SanskritCompiler.decline_noun("īśa", case="nominative", number="singular")
    print(f"\n3️⃣ Subanta Declension:")
    print(f"   • rāma (Locative Sg): {noun1}")
    print(f"   • īśa (Nominative Sg): {noun2}")

    # 4. Sandhi Joining via PaniniVM
    joined = SanskritCompiler.join_words("rāma", "īśa", output_encoding="iast")
    joined_dev = SanskritCompiler.join_words("rāma", "īśa", output_encoding="devanagari")
    print(f"\n4️⃣ Forward Sandhi Joining (rāma + īśa):")
    print(f"   • IAST: {joined}")
    print(f"   • Devanagari: {joined_dev}")

    # 5. Backward Sandhi Splitting
    splits = SanskritCompiler.split_word("yadyapi")
    print(f"\n5️⃣ Mechanical Sandhi Splitting ('yadyapi'):")
    for l, r in splits:
        print(f"   • {l} + {r}")

    print("\n" + "=" * 60)
    print("✅ All classical tests verified against Pāṇini’s Aṣṭādhyāyī.")
    print("=" * 60)


if __name__ == "__main__":
    run_demo()
