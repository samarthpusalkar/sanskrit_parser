import re

with open("compiler/pipeline.py", "r") as f:
    content = f.read()

# 1. Remove hardcoded dictionaries
content = re.sub(r'VOICED_EQUIVALENTS = \{.*?\n\}\n*', '', content, flags=re.DOTALL)
content = re.sub(r'NASAL_BY_STHANA = \{.*?\n\}\n*', '', content, flags=re.DOTALL)
content = re.sub(r'SCU_EQUIVALENTS = \{.*?\n\}\n*', '', content, flags=re.DOTALL)
content = re.sub(r'SCU_TRIGGERS = .*?\n*', '', content)

# 2. Update data_ops
content = content.replace('"palatalize", "purva_rupa", "visarga_utva", "ro_ri_dirgha",\n            "anusvara", "parasavarna", "natva"', '"purva_rupa", "visarga_utva", "ro_ri_dirgha",\n            "anusvara", "natva"')
content = content.replace('"bijection_substitute", "elide", "dirgha", "voice", "nasalize",', '"bijection_substitute", "elide", "dirgha",')

# 3. Update bijection_substitute to support lists
new_bijection = '''        elif op.op_type in {"bijection_substitute", "substitute", "exact_substitute"}:
            t_cond = self.spec.target_context
            s_val = op.substitute
            if t_cond and s_val:
                try:
                    if t_cond.pratyahara:
                        t_list = PratyaharaResolver.resolve_list(t_cond.pratyahara)
                    else:
                        t_list = _expand_literal_pattern(t_cond.exact_text)
                        
                    if s_val.startswith("PRAT:"):
                        s_list = PratyaharaResolver.resolve_list(s_val.removeprefix("PRAT:"))
                    else:
                        s_list = _expand_literal_pattern(s_val)
                        
                    savarna = {'A': 'a', 'I': 'i', 'U': 'u', 'F': 'f'}
                    lookup = None
                    
                    if len(t_list) == len(s_list):
                        fwd_map = dict(zip(t_list, s_list))
                        lookup = fwd_map.get(l_char) or fwd_map.get(savarna.get(l_char, ''))
                    else:
                        from core.phonology import get_sthana
                        search_char = savarna.get(l_char, l_char)
                        if search_char in t_list:
                            target_sthana = get_sthana(search_char)
                            for cand in s_list:
                                if get_sthana(cand) == target_sthana:
                                    lookup = cand
                                    break
                                    
                    if lookup:
                        return left[:-1] + lookup, right
                except Exception:
                    pass'''

content = re.sub(
    r'        elif op.op_type in \{"bijection_substitute", "substitute", "exact_substitute"\}:.*?(?=            if op.substitute and op.substitute not in \{"dirgha", "guna", "vriddhi"\}:)',
    new_bijection + '\n',
    content,
    flags=re.DOTALL
)

# 4. Remove voice, parasavarna, palatalize, nasalize from apply_raw
content = re.sub(r'        elif op.op_type == "voice":.*?return left\[:-1\] \+ VOICED_EQUIVALENTS\.get\(l_char, l_char\), right\n\n', '', content, flags=re.DOTALL)
content = re.sub(r'        elif op.op_type == "parasavarna":.*?return left\[:-1\] \+ NASAL_BY_STHANA\.get\(right\[0\], \'M\'\), right\n\n', '', content, flags=re.DOTALL)
content = re.sub(r'        elif op.op_type == "palatalize":.*?return left\[:-1\] \+ SCU_EQUIVALENTS\.get\(l_char, l_char\), right\n\n', '', content, flags=re.DOTALL)
content = re.sub(r'        elif op.op_type == "nasalize":.*?return left\[:-1\] \+ NASAL_BY_STHANA\.get\(right\[0\], right\[0\]\), right\n\n', '', content, flags=re.DOTALL)

with open("compiler/pipeline.py", "w") as f:
    f.write(content)
