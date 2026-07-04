"""Spouštěč vývojového serveru.

    python run.py

Přidá src/ na cestu a spustí Flask aplikaci na portu 5001.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / 'src'))

from app import app  # noqa: E402

if __name__ == '__main__':
    print("\n🌿 Rostlinolékařské pasy — spouštím server...")
    print("👉  Otevři prohlížeč na: http://localhost:5001\n")
    app.run(debug=True, port=5001)
