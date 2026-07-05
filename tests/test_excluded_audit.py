# -*- coding: utf-8 -*-
"""Testy auditu vyřazených řádků.

Řetěz kontraktů: parser (Invoice.excluded) → pdf_generator (vyrazeno.txt
ve výstupech + ZIPu) → /api/match (pole 'excluded' v odpovědi).
"""
import zipfile
from pathlib import Path

import openpyxl
import pytest

import app as app_module
import pdf_parser
from pdf_generator import build_outputs, zip_outputs
from pdf_parser import Invoice, PDFParser, PlantItem
from plant_matcher import PlantMatcher
from session import ParseSession

PLANTS = [{'passport_name': 'Dřín velkoplodý', 'code': 'CZ-123', 'country': 'CZ'}]


# ---------------------------------------------------------------- parser

def test_parse_items_splits_plants_and_excluded():
    """Řádek s klíčovým slovem skončí v excluded (s klíčovým slovem),
    NE v plants; hlavička bez '()' se nedostane nikam."""
    table = [
        ['Název', 'Ks', 'Cena/ks', 'Celkem'],   # hlavička — mimo obě skupiny
        ['() Dárkový poukaz v hodnotě 1000 Kč', '1', '1 000', '1 000'],
        ['() Agave parryi var. parryi', '3', '120', '360'],
    ]

    plants, excluded = PDFParser()._parse_items(table)

    assert [p.name for p in plants] == ['Agave parryi var. parryi']
    assert excluded == [{'text': 'Dárkový poukaz v hodnotě 1000 Kč',
                         'keyword': 'dárkový poukaz'}]


def test_parse_items_clean_table_has_no_exclusions():
    plants, excluded = PDFParser()._parse_items(
        [['() Hosta hybrid', '2', '80', '160']])

    assert [p.name for p in plants] == ['Hosta hybrid']
    assert excluded == []


@pytest.mark.parametrize('name, keyword', [
    ('Dárkový poukaz v hodnotě 1000 Kč', 'dárkový poukaz'),
    ('DÁRKOVÝ POUKAZ', 'dárkový poukaz'),        # case-insensitive
    ('Přidaný produkt', 'přidaný produkt'),
    ('Agave parryi var. parryi', None),          # rostlina projde
], ids=['voucher', 'voucher-upper', 'added-product', 'real-plant'])
def test_non_plant_keyword_returns_matched_keyword(name, keyword):
    assert PDFParser()._non_plant_keyword(name) == keyword


# Fake pdfplumber stránky: externí hranice (čtení PDF) — ruční fake,
# stejný přístup jako mocky v test_drive_uploader.py.
class _FakePage:
    def __init__(self, text, tables=()):
        self._text = text
        self._tables = list(tables)

    def extract_text(self):
        return self._text

    def extract_tables(self):
        return self._tables


class _FakePDF:
    def __init__(self, pages):
        self.pages = pages

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_multipage_invoice_merges_exclusions(monkeypatch):
    """Vyřazené řádky z pokračovací stránky se slučují do TÉŽE faktury."""
    pages = [
        _FakePage('Faktura č.: 111',
                  [[['() Acer palmatum', '2', '100', '200'],
                    ['() Přidaný produkt', '1', '50', '50']]]),
        _FakePage('Pokračování položek bez hlavičky',
                  [[['() Dárkový poukaz v hodnotě 500 Kč', '1', '500', '500'],
                    ['() Hosta hybrid', '1', '80', '80']]]),
    ]
    monkeypatch.setattr(pdf_parser.pdfplumber, 'open',
                        lambda path: _FakePDF(pages))

    invoices = PDFParser()._parse_pdf(Path('fake.pdf'))

    assert len(invoices) == 1
    inv = invoices[0]
    assert inv.number == '111'
    assert [p.name for p in inv.plants] == ['Acer palmatum', 'Hosta hybrid']
    assert inv.excluded == [
        {'text': 'Přidaný produkt', 'keyword': 'přidaný produkt'},
        {'text': 'Dárkový poukaz v hodnotě 500 Kč', 'keyword': 'dárkový poukaz'},
    ]


# ---------------------------------------------------------------- build_outputs

def test_vyrazeno_txt_content_and_zip_membership(tmp_path):
    """Formát 'Faktura {n}: {text}'; faktura s KOMPLETNĚ odfiltrovanými
    položkami nemá pas, ale v auditu je; soubor doputuje do ZIPu."""
    out_dir = tmp_path / 'out'
    result = build_outputs(
        [{'number': '111', 'customer': 'X', 'date': '', 'plants': PLANTS},
         {'number': '112', 'customer': 'Y', 'date': '', 'plants': []}],
        {'111': Invoice(number='111', excluded=[
            {'text': 'Přidaný produkt', 'keyword': 'přidaný produkt'}]),
         '112': Invoice(number='112', excluded=[
            {'text': 'Dárkový poukaz v hodnotě 500 Kč',
             'keyword': 'dárkový poukaz'}])},
        {},
        out_dir,
    )

    exc_path = out_dir / 'vyrazeno.txt'
    assert exc_path in result['files']
    assert exc_path.read_text(encoding='utf-8') == (
        'Faktura 111: Přidaný produkt\n'
        'Faktura 112: Dárkový poukaz v hodnotě 500 Kč'
    )
    # 112: vše odfiltrováno → žádný pas, přesto figuruje v auditu
    assert not (out_dir / '112.pdf').exists()
    with zipfile.ZipFile(zip_outputs(result['files'])) as zf:
        assert 'vyrazeno.txt' in zf.namelist()


def test_no_vyrazeno_txt_when_nothing_excluded(tmp_path):
    out_dir = tmp_path / 'out'
    result = build_outputs(
        [{'number': '111', 'customer': 'X', 'date': '', 'plants': PLANTS}],
        {'111': Invoice(number='111', excluded=[])},
        {},
        out_dir,
    )

    assert not (out_dir / 'vyrazeno.txt').exists()
    assert 'vyrazeno.txt' not in [p.name for p in result['files']]


# ---------------------------------------------------------------- /api/match

def test_api_match_response_carries_excluded(tmp_path, monkeypatch):
    """Každá faktura v odpovědi /api/match nese své pole 'excluded'."""
    # Seam: app drží matcher i session jako modulové globály čtené za běhu —
    # monkeypatch je nahradí testovacími instancemi a po testu vrátí originály.
    sarze = tmp_path / 'sarze.xlsx'
    wb = openpyxl.Workbook()
    wb.active.append(['Název', 'Kód', 'Země'])
    wb.active.append(['Acer palmatum', '25-T1', 'CZ'])
    wb.save(sarze)
    monkeypatch.setattr(app_module, 'matcher', PlantMatcher(str(sarze)))
    monkeypatch.setattr(app_module, 'session', ParseSession())
    monkeypatch.setitem(app_module.app.config, 'TESTING', True)

    dropped = [{'text': 'Dárkový poukaz v hodnotě 500 Kč',
                'keyword': 'dárkový poukaz'}]
    app_module.session.save([
        Invoice(number='111', plants=[PlantItem(name='Acer palmatum')],
                excluded=dropped),
        Invoice(number='112'),
    ], {})

    with app_module.app.test_client() as c:
        resp = c.post('/api/match')

    assert resp.status_code == 200
    inv111, inv112 = resp.get_json()['invoices']
    assert inv111['excluded'] == dropped
    assert inv111['plants'][0]['match_type'] == 'exact'  # matching dál funguje
    assert inv112['excluded'] == []
