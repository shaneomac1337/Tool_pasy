"""Centrální umístění souborů projektu.

Jediný modul, který zná adresářovou strukturu. Ostatní moduly importují
pojmenované cesty odtud místo ručního `Path(__file__).parent` — přesun
souborů se pak řeší na jednom místě.
"""
from pathlib import Path

# Kořen aplikace: o úroveň výš než src/ (kde leží tento soubor).
ROOT = Path(__file__).resolve().parent.parent

DATA_DIR = ROOT / 'data'          # sarze.xlsx (katalog šarží)
ASSETS_DIR = ROOT / 'assets'      # eu_flag.png
OUTPUT_DIR = ROOT / 'výstupy'     # generované výstupy (pasy_{datum})

# Google Drive konfigurace (mimo git, v kořeni aplikace)
CREDENTIALS_PATH = ROOT / 'credentials.json'
TOKEN_PATH = ROOT / 'token.json'
CONFIG_PATH = ROOT / 'drive_config.json'
