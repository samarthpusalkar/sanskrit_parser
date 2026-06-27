import re

with open("data/db_compiler.py", "r") as f:
    content = f.read()

new_seeds = """        ("6.1.78", "eco_yavāyāvaḥ_O", "O", "VOWEL", "substitute", "Av"),
        ("6.1.78", "eco_yavāyāvaḥ_E", "E", "VOWEL", "substitute", "Ay"),
        ("6.1.78", "eco_yavāyāvaḥ_o", "o", "VOWEL_NON_A", "substitute", "av"),
        ("6.1.78", "eco_yavāyāvaḥ_e", "e", "VOWEL_NON_A", "substitute", "ay"),
        ("6.1.101", "akaḥ_savarṇe_dīrghaḥ_a", "a|A", "a|A", "merge", "A"),
        ("6.1.101", "akaḥ_savarṇe_dīrghaḥ_i", "i|I", "i|I", "merge", "I"),
        ("6.1.101", "akaḥ_savarṇe_dīrghaḥ_u", "u|U", "u|U", "merge", "U"),
        ("6.1.87", "ād_guṇaḥ_i", "a|A", "i|I", "merge", "e"),
        ("6.1.87", "ād_guṇaḥ_u", "a|A", "u|U", "merge", "o"),
        ("6.1.87", "ād_guṇaḥ_f", "a|A", "f|F", "merge", "ar"),
        ("6.1.88", "vṛddhireci_e", "a|A", "e|E", "merge", "E"),
        ("6.1.88", "vṛddhireci_o", "a|A", "o|O", "merge", "O"),
        ("6.1.77", "iko_yaṇ_aci", "PRAT:iK", "VOWEL", "bijection_substitute", "PRAT:yaR"),
        ("6.1.73", "che_ca_tuk", "SHORT_VOWEL", "C", "insert", "c"),
        ("8.4.40", "stoḥ_ścunā_ścuḥ", "s|t|T|d|D|n", "S|c|C|j|J|Y", "bijection_substitute", "S|c|C|j|J|Y"),
        ("8.2.39", "jhalāṃ_jaśo_nte", "PRAT:JaL", "PAUSE_OR_VOICED", "bijection_substitute", "PRAT:jaS"),
        ("8.4.45", "yaro_nunāsike", "PRAT:yaR", "NASAL", "bijection_substitute", "N|Y|R|n|m"),
        ("6.1.109", "eṅaḥ_padāntād_ati", "e|o", "a", "purva_rupa", ""),
        ("6.1.113", "ato_ror_aplutād_aplute", "aH", "a", "visarga_utva", "o"),
        ("8.2.77", "hali_ca_external_block", "VOWEL", "CONSONANT", "external_block", ""),
        ("8.3.14", "ro_ri", "r", "r", "ro_ri_dirgha", ""),
        ("8.3.23", "mo_nusvāraḥ", "m", "CONSONANT", "anusvara", "M"),
        ("8.4.1", "raṣābhyāṃ_no_ṇaḥ", "n", "VOWEL", "natva", "R"),
        ("8.4.59", "anusvārasya_yayi_parasavarṇaḥ", "M", "CONSONANT", "bijection_substitute", "N|Y|R|n|m"),
        ("8.4.63", "śaścho_ṭi", "c|C", "S", "right_substitute", "C"),
        ("8.3.34", "visarga_sibilant", "H", "c|C", "substitute", "S"),
        ("8.3.34", "visarga_retroflex", "H", "w|W", "substitute", "z"),
        ("8.3.34", "visarga_dental", "H", "t|T", "substitute", "s")"""

content = re.sub(
    r'        \("6\.1\.78".*?\("8\.3\.34", "visarga_dental", "H", "t\|T", "substitute", "s"\)',
    new_seeds,
    content,
    flags=re.DOTALL
)

with open("data/db_compiler.py", "w") as f:
    f.write(content)
