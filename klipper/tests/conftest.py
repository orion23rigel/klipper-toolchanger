import os
import sys

_EXTRAS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "extras")
if _EXTRAS_DIR not in sys.path:
    sys.path.insert(0, _EXTRAS_DIR)
