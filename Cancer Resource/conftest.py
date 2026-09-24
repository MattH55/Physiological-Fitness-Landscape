"""
Pytest bootstrap for the Combinatorial Fitness Landscape module.

Sets an isolated SQLite database BEFORE any synlethality module is imported
(the engine is created at import time), and makes the package importable.
"""

import os
import sys
import tempfile

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

_TMP_DIR = tempfile.mkdtemp(prefix="synlethality_test_")
os.environ["SYNLETHALITY_DATABASE_URL"] = f"sqlite:///{os.path.join(_TMP_DIR, 'test.db')}"
