import json
import os
import sys

# Ensure module path is correct
sys.path.insert(0, os.path.abspath('.'))

from rules.engine import UniversalRuleEngine

def test_forward_parser():
    engine = UniversalRuleEngine.get_instance()
    
    with open('tests/forward_parser_test.json', 'r') as f:
        cases = json.load(f)
        
    print(f"Loaded {len(cases)} test cases.")
    
    passed = 0
    failed = 0
    
    for case in cases:
        tokens = case["input_tokens"]
        expected = case["expected_string"]
        
        # Sequentially apply forward rules
        result = tokens[0]
        for i in range(1, len(tokens)):
            result, right_rem = engine.dispatch_forward(result, tokens[i])
            result += right_rem
            
        if result == expected:
            print(f"✅ {case['id']}: '{' + '.join(tokens)}' -> {result}")
            passed += 1
        else:
            print(f"❌ {case['id']}: '{' + '.join(tokens)}' -> {result} (Expected: {expected})")
            failed += 1
            
    print(f"\nTotal: {len(cases)}, Passed: {passed}, Failed: {failed}")
    if failed > 0:
        sys.exit(1)

if __name__ == '__main__':
    test_forward_parser()
