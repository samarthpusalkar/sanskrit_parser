import sys
import threading
import _thread

def quit_function(fn_name):
    print(f"{fn_name} took too long", file=sys.stderr)
    import traceback
    traceback.print_stack()
    sys.stderr.flush() # flush stderr
    _thread.interrupt_main() # raises KeyboardInterrupt

def exit_after(s):
    def outer(fn):
        def inner(*args, **kwargs):
            timer = threading.Timer(s, quit_function, args=[fn.__name__])
            timer.start()
            try:
                result = fn(*args, **kwargs)
            finally:
                timer.cancel()
            return result
        return inner
    return outer

@exit_after(5.0)
def run_test():
    import subprocess
    subprocess.run(["python", "tests/test_grammar_dataset.py", "--dataset", "tests/basic_grammar_test.json"])

run_test()
