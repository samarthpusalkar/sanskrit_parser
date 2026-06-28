import sys
import os

# Add parent directory to sys.path so paninian_engine can be imported reliably
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
