# -*- coding: utf-8 -*-
"""Testy pro session.ParseSession, pdf_generator.zip_outputs a validaci rout.

Kontrakt pod ochranou:
- ParseSession.save: faktury NAHRAZUJE, file_paths SLUČUJE (akumulace přes
  více uploadů — pozdější generate musí najít i dříve nahrané soubory;
  opakovaný upload téhož jména ukazuje na novou cestu, ne na starou).
- index_by_number: klíčuje podle invoice.number; clear: vyprázdní obojí.
- zip_outputs: ZIP_DEFLATED archiv, arcname = holé jméno souboru (bez cest),
  vrácený buffer má pozici 0 (jinak send_file pošle prázdno); obsah
  přežije round-trip.
- POST /api/generate-pdf i /api/generate-excel: JSON null / chybějící klíč
  'invoices' → 400 'Chybí data faktur'; prázdný seznam faktur
  → 400 'Žádné faktury k exportu'. (Chybějící content-type → 415 a rozbitý
  JSON → HTML 400 jsou defaulty Flasku, ne náš kontrakt — netestují se.)
"""
import io
import sys
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest

APP_DIR = Path(__file__).resolve().parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from session import ParseSession  # noqa: E402
from pdf_generator import zip_outputs  # noqa: E402


# ---------------------------------------------------------------- ParseSession

def _inv(number):
    return SimpleNamespace(number=number)


@pytest.fixture
def sess():
    return ParseSession()


def test_save_replaces_invoices(sess):
    second = [_inv('333')]
    sess.save([_inv('111'), _inv('112')], {})
    sess.save(second, {})
    assert sess.invoices() == second


def test_save_merges_file_paths_across_calls(sess):
    sess.save([_inv('111')], {'a.pdf': '/tmp/a1.pdf'})
    sess.save([_inv('222')], {'b.pdf': '/tmp/b2.pdf'})
    assert sess.file_paths() == {'a.pdf': '/tmp/a1.pdf',
                                 'b.pdf': '/tmp/b2.pdf'}


def test_save_reupload_same_name_wins_over_stale_path(sess):
    sess.save([], {'a.pdf': '/tmp/old.pdf'})
    sess.save([], {'a.pdf': '/tmp/new.pdf'})
    assert sess.file_paths()['a.pdf'] == '/tmp/new.pdf'


def test_index_by_number(sess):
    inv1, inv2 = _inv('111'), _inv('112')
    sess.save([inv1, inv2], {})
    assert sess.index_by_number() == {'111': inv1, '112': inv2}


def test_clear_empties_invoices_and_file_paths(sess):
    sess.save([_inv('111')], {'a.pdf': '/tmp/a.pdf'})
    sess.clear()
    assert sess.invoices() == []
    assert sess.file_paths() == {}
    assert sess.index_by_number() == {}


# ---------------------------------------------------------------- zip_outputs

def test_zip_outputs_roundtrip(tmp_path):
    # Soubory ve DVOU různých adresářích: arcname musí být holé jméno,
    # ne relativní/absolutní cesta.
    dir_a = tmp_path / 'da'
    dir_b = tmp_path / 'db'
    dir_a.mkdir()
    dir_b.mkdir()
    pdf = dir_a / '111.pdf'
    xlsx = dir_b / 'recipients.xlsx'
    pdf.write_bytes(b'obsah faktury 111')
    xlsx.write_bytes(b'xlsx bajty')

    buf = zip_outputs([pdf, xlsx])

    assert buf.tell() == 0  # send_file jinak posílá prázdný stream
    with zipfile.ZipFile(buf) as zf:
        assert sorted(zf.namelist()) == ['111.pdf', 'recipients.xlsx']
        assert zf.read('111.pdf') == b'obsah faktury 111'
        assert zf.read('recipients.xlsx') == b'xlsx bajty'
        assert all(i.compress_type == zipfile.ZIP_DEFLATED
                   for i in zf.infolist())


# ---------------------------------------------------------------- Flask routy

GENERATE_ROUTES = ['/api/generate-pdf', '/api/generate-excel']


@pytest.fixture(scope='module')
def client():
    import app as app_module
    app_module.app.config['TESTING'] = True
    with app_module.app.test_client() as c:
        yield c


@pytest.mark.parametrize('route', GENERATE_ROUTES)
def test_generate_null_json_body(client, route):
    resp = client.post(route, data='null',
                       content_type='application/json')
    assert resp.status_code == 400
    assert resp.get_json() == {'error': 'Chybí data faktur'}


@pytest.mark.parametrize('route', GENERATE_ROUTES)
def test_generate_missing_invoices_key(client, route):
    resp = client.post(route, json={'neco': 'jineho'})
    assert resp.status_code == 400
    assert resp.get_json() == {'error': 'Chybí data faktur'}


@pytest.mark.parametrize('route', GENERATE_ROUTES)
def test_generate_empty_invoices(client, route):
    resp = client.post(route, json={'invoices': []})
    assert resp.status_code == 400
    assert resp.get_json() == {'error': 'Žádné faktury k exportu'}
