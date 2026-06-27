import sys, os
sys.path.insert(0, os.path.abspath('.'))
from compiler.pipeline import MasterCompilerPipeline
from core.shiva_sutras import PratyaharaResolver

rules = MasterCompilerPipeline.compile_all()
for r in rules:
    if r.sutra_id == "8.2.39":
        print(f"Rule: {r.sutra_id} - {r.name}")
        print(f"Target: {r.spec.target_context.pratyahara} | {r.spec.target_context.exact_text}")
        print(f"Op: {r.spec.operation.op_type} | {r.spec.operation.substitute}")
        t_list = PratyaharaResolver.resolve_list(r.spec.target_context.pratyahara) if r.spec.target_context.pratyahara else []
        s_list = PratyaharaResolver.resolve_list(r.spec.operation.substitute) if r.spec.operation.substitute else []
        print(f"T-list: {t_list}")
        print(f"S-list: {s_list}")
