"""Spouštěč serveru.

    python run.py            # vývoj (debug + reloader)
    Pasy.exe / ./Pasy        # frozen (PyInstaller) — debug off, otevře prohlížeč

Přidá src/ na cestu a spustí Flask aplikaci na portu 5001.
"""
import sys
import threading
import webbrowser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / 'src'))

from app import app  # noqa: E402

PORT = 5001


def _open_browser() -> None:
    webbrowser.open(f'http://localhost:{PORT}')


if __name__ == '__main__':
    frozen = getattr(sys, 'frozen', False)
    print("\n🌿 Rostlinolékařské pasy — spouštím server...")
    print(f"👉  Otevři prohlížeč na: http://localhost:{PORT}\n")
    if frozen:
        # Prohlížeč otevři až server naběhne. debug=False => žádný reloader,
        # žádný child proces, žádné dvojité otevření. Cross-platform:
        # webbrowser.open použije výchozí prohlížeč (Windows i macOS).
        # ponytail: Timer stačí, poll na port je zbytečný pro lokální server.
        threading.Timer(1.5, _open_browser).start()
    app.run(debug=not frozen, port=PORT)
