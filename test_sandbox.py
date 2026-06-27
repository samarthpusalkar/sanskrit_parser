import sys
import os
sys.path.insert(0, os.path.abspath('.'))
from rules.engine import UniversalRuleEngine
from core.phonology import iast_to_slp1, slp1_to_iast
import json

engine = UniversalRuleEngine.get_instance()
with open('tests/forward_parser_test.json', 'r') as f:
    cases = json.load(f)

for case in cases:
    tokens = [iast_to_slp1(t) for t in case["input_tokens"]]
    expected = case["expected_string"]
    
    result = tokens[0]
    for i in range(1, len(tokens)):
        result, right_rem = engine.dispatch_forward(result, tokens[i])
        result += right_rem
        
    result_iast = slp1_to_iast(result)
    if result_iast == expected:
        print(f"✅ {case['id']}")
    else:
        print(f"❌ {case['id']}: {result_iast} (Expected: {expected})")
