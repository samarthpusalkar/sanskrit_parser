import sys, os
sys.path.insert(0, os.path.abspath('.'))
from core.phonology import get_sthana, Sthana

nasals = ['N', 'Y', 'R', 'n', 'm']
for r_char in ['k', 'c', 'w', 't', 'p', 'y']:
    st = get_sthana(r_char)
    matched = next((n for n in nasals if get_sthana(n) == st), 'M')
    print(f"{r_char} ({st}) -> {matched}")
