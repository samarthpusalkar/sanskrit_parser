import os
import sys

# Add the project root to sys.path so that 'benchmarks' and other 
# top-level packages can be imported by pytest.
root_path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if root_path not in sys.path:
    sys.path.insert(0, root_path)
