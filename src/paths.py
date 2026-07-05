"""Centrální umístění souborů projektu.

Jediný modul, který zná adresářovou strukturu. Ostatní moduly importují
pojmenované cesty odtud místo ručního `Path(__file__).parent` — přesun
souborů se pak řeší na jednom místě.
"""
import sys
from pathlib import Path

# Kořen aplikace:
#  - vývoj: o úroveň výš než src/ (kde leží tento soubor).
#  - frozen (PyInstaller onedir): adresář vedle spustitelného souboru.
#      Windows: vedle Pasy.exe.
#      macOS:   vedle unixového spustitelného souboru Pasy VE SLOŽCE.
#    ZÁMĚRNĚ onedir SLOŽKA, ne .app bundle — v .app by sys.executable mířil
#    DOVNITŘ (Pasy.app/Contents/MacOS/Pasy) a psali bychom do read-only bundlu.
#    Díky tomu je frozen větev na obou OS identická a data/, výstupy/,
#    credentials.json leží vedle spustitelného souboru.
# ponytail: jedna cross-platform větev — onedir SLOŽKA dělá
#           Path(sys.executable).parent shodným na Windows i macOS.
#           Viz docs/shipping_plan.md §1.1.
if getattr(sys, 'frozen', False):
    ROOT = Path(sys.executable).resolve().parent
else:
    ROOT = Path(__file__).resolve().parent.parent

DATA_DIR = ROOT / 'data'          # sarze.xlsx (katalog šarží)
ASSETS_DIR = ROOT / 'assets'      # eu_flag.png
OUTPUT_DIR = ROOT / 'výstupy'     # generované výstupy (pasy_{datum})

# Google Drive konfigurace (mimo git, v kořeni aplikace)
CREDENTIALS_PATH = ROOT / 'credentials.json'
TOKEN_PATH = ROOT / 'token.json'
CONFIG_PATH = ROOT / 'drive_config.json'
