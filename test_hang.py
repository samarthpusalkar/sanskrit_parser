import sys, threading, _thread

def dump_stack():
    import traceback, threading
    print("\nTIMEOUT! Dumping stacks:")
    for thread in threading.enumerate():
        frame = sys._current_frames().get(thread.ident)
        if frame:
            traceback.print_stack(f=frame)
    _thread.interrupt_main()

from tensor.vectorizer import TensorVectorizer
from tensor.detokenizer import TensorDetokenizer

tests = [
    ("devālayaḥ", ["deva", "ālayaḥ"]),
    ("sūryodayaḥ", ["sūrya", "udayaḥ"]),
    ("rāmaḥ gacchati", ["rāmaḥ", "gacchati"]),
    ("so'pi", ["saḥ", "api"]),
    ("jagannāthaḥ", ["jagat", "nāthaḥ"]),
    ("sukhaduḥkhe", ["sukha", "duḥkhe"]),
    ("dharmakṣetre", ["dharma", "kṣetre"]),
    ("nāstyeva", ["na", "asti", "eva"]),
    ("tacchrutvā", ["tat", "śrutvā"]),
    ("rāmaśca", ["rāmaḥ", "ca"]),
    ("pītāmbaraḥ", ["pīta", "ambaraḥ"]),
    ("karmaṇyevādhikāraste", ["karmaṇi", "eva", "adhikāraḥ", "te"]),
    ("kṣetrakṣetrajñayorjñānam", ["kṣetra", "kṣetrajñayoḥ", "jñānam"]),
    ("vāgarthāviva", ["vāk", "arthau", "iva"]),
    ("saṅgostvakarmaṇi", ["saṅgaḥ", "astu", "akarmaṇi"]),
]

passed = 0
for txt, expected in tests:
    timer = threading.Timer(2.0, dump_stack)
    timer.start()
    try:
        vecs = TensorVectorizer.vectorize(txt)
        tokens = TensorDetokenizer.detokenize_to_tokens(vecs)
        status = "✅" if tokens == expected else "❌"
        if tokens == expected:
            passed += 1
        print(f"{status} '{txt}': got {tokens}, expected {expected}")
    except KeyboardInterrupt:
        print(f"⏱️ HUNG on '{txt}'")
        break
    finally:
        timer.cancel()

print(f"\n{passed}/{len(tests)} passed")
