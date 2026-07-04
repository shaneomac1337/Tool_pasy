"""Zpřístupní moduly z src/ pro pytest bez ohledu na to, odkud se spouští."""
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / 'src'
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
