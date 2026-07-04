# -*- coding: utf-8 -*-
"""Testy pro drive_uploader — mockovaná Drive služba, žádná síť ani OAuth.

Kontrakt pod ochranou:
- get_status: hlásí stav credentials/token podle souborů vedle modulu.
- get_service: bez credentials.json srozumitelně selže (a nesahá na síť).
- ensure_folder: existující složku najde bez vytváření; chybějící vytvoří
  se správným jménem, mimeType a rodičem.
- upload_outputs: chybějící/prázdné výstupy → česká RuntimeError PŘED
  autentizací; stejnojmenný soubor v Drive → update, nový → create;
  správné mimetypes; folder_link míří na složku dne; kořen Pasy se kešuje.
- Flask: GET /api/drive-status a POST /api/upload-drive mapují totéž na HTTP.
"""
import json
import re
import sys
import threading
import time
from pathlib import Path

import pytest

APP_DIR = Path(__file__).resolve().parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

import drive_uploader as du  # noqa: E402

DATE = '2000-12-31'
FOLDER_MIME = 'application/vnd.google-apps.folder'
XLSX_MIME = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'


# ---------------------------------------------------------------- fake Drive

class _FakeRequest:
    def __init__(self, result):
        self._result = result

    def execute(self):
        return self._result


def _view_link(fid):
    return f'https://drive.google.com/file/d/{fid}/view'


class _FakeFiles:
    """In-memory náhrada za service.files(): list/get/create/update.

    ``list`` odpovídá podle dotazu q — složky (mimeType=folder) hledá
    v ``folders`` (jméno → id), soubory v ``existing`` (jméno → id).
    Všechna volání zaznamenává, aby testy mohly ověřit create vs. update.
    """

    def __init__(self, folders=None, existing=None):
        self.folders = dict(folders or {})
        self.existing = dict(existing or {})
        self.queries = []
        self.folder_creates = []
        self.file_creates = []
        self.updates = []
        self._seq = 0
        self._lock = threading.Lock()

    def list(self, q='', **kwargs):
        with self._lock:
            self.queries.append(q)
            m = re.search(r"name\s*=\s*'((?:[^'\\]|\\.)*)'", q)
            name = m.group(1).replace("\\'", "'") if m else None
            pool = self.folders if FOLDER_MIME in q else self.existing
            hits = [{'id': pool[name]}] if name in pool else []
        return _FakeRequest({'files': hits})

    def get(self, fileId=None, **kwargs):
        return _FakeRequest({'id': fileId, 'trashed': False})

    def create(self, body=None, media_body=None, **kwargs):
        body = body or {}
        with self._lock:
            self._seq += 1
            if body.get('mimeType') == FOLDER_MIME:
                fid = f'folder-{self._seq}'
                self.folder_creates.append({'body': body, 'id': fid})
                self.folders[body['name']] = fid
            else:
                fid = f'file-{self._seq}'
                self.file_creates.append(
                    {'body': body, 'media_body': media_body, 'id': fid})
        return _FakeRequest({'id': fid, 'webViewLink': _view_link(fid)})

    def update(self, fileId=None, media_body=None, **kwargs):
        with self._lock:
            self.updates.append({'fileId': fileId, 'media_body': media_body})
        return _FakeRequest({'id': fileId, 'webViewLink': _view_link(fileId)})


class _FakeService:
    def __init__(self, files_resource):
        self._files = files_resource

    def files(self):
        return self._files


def _fail_get_service():
    raise AssertionError(
        'upload_outputs sáhl na autentizaci před kontrolou výstupní složky')


# ---------------------------------------------------------------- fixtures

@pytest.fixture
def paths(tmp_path, monkeypatch):
    """Přesměruje všechny souborové konstanty modulu do tmp_path."""
    monkeypatch.setattr(du, 'CREDENTIALS_PATH', tmp_path / 'credentials.json')
    monkeypatch.setattr(du, 'TOKEN_PATH', tmp_path / 'token.json')
    monkeypatch.setattr(du, 'CONFIG_PATH', tmp_path / 'drive_config.json')
    monkeypatch.setattr(du, 'OUTPUT_BASE', tmp_path / 'výstupy')
    return tmp_path


@pytest.fixture
def outputs_dir(paths):
    """Výstupní složka dne se dvěma soubory k nahrání."""
    day = paths / 'výstupy' / f'pasy_{DATE}'
    day.mkdir(parents=True)
    (day / 'a.pdf').write_bytes(b'%PDF-1.4 test')
    (day / 'recipients.xlsx').write_bytes(b'PK\x03\x04 test')
    return day


# ---------------------------------------------------------------- get_status

def test_get_status_nothing_connected(paths):
    assert du.get_status() == {'credentials': False, 'token': False}


def test_get_status_both_present(paths):
    (paths / 'credentials.json').write_text('{"installed": {}}',
                                            encoding='utf-8')
    (paths / 'token.json').write_text('{"token": "x"}', encoding='utf-8')
    assert du.get_status() == {'credentials': True, 'token': True}


def test_get_status_keys_not_swapped(paths):
    # Jen credentials → přesně tenhle klíč True; odhalí prohozené klíče.
    (paths / 'credentials.json').write_text('{}', encoding='utf-8')
    assert du.get_status() == {'credentials': True, 'token': False}


def test_get_status_corrupt_token_not_connected(paths):
    # Rozbitý token.json nesmí UI hlásit jako funkční napojení.
    (paths / 'token.json').write_text('tohle není JSON', encoding='utf-8')
    assert du.get_status()['token'] is False


# ---------------------------------------------------------------- get_service

def test_get_service_without_credentials(paths):
    with pytest.raises(RuntimeError, match='credentials.json'):
        du.get_service()


# ---------------------------------------------------------------- ensure_folder

def test_ensure_folder_returns_existing_without_create():
    files = _FakeFiles(folders={DATE: 'existing-day-id'})
    folder_id = du.ensure_folder(_FakeService(files), DATE, 'root-id')

    assert folder_id == 'existing-day-id'
    assert files.folder_creates == []
    assert files.file_creates == []

    q = files.queries[0]
    assert re.search(rf"name\s*=\s*'{DATE}'", q)
    assert FOLDER_MIME in q
    assert re.search(r'trashed\s*=\s*false', q)
    assert "'root-id' in parents" in q


def test_ensure_folder_creates_when_absent_at_root():
    files = _FakeFiles()
    folder_id = du.ensure_folder(_FakeService(files), 'Pasy', None)

    assert folder_id == 'folder-1'
    assert len(files.folder_creates) == 1
    body = files.folder_creates[0]['body']
    assert body['name'] == 'Pasy'
    assert body['mimeType'] == FOLDER_MIME
    assert 'parents' not in body  # bez rodiče patří do kořene


def test_ensure_folder_creates_under_parent():
    files = _FakeFiles()
    folder_id = du.ensure_folder(_FakeService(files), DATE, 'root-id')

    assert folder_id == 'folder-1'
    assert files.folder_creates[0]['body']['parents'] == ['root-id']


# ---------------------------------------------------------------- upload_outputs

def test_upload_outputs_missing_dir_raises_before_auth(paths, monkeypatch):
    monkeypatch.setattr(du, 'get_service', _fail_get_service)
    with pytest.raises(RuntimeError, match=r'výstup|vygenerujte'):
        du.upload_outputs(DATE)


def test_upload_outputs_empty_dir_raises_before_auth(paths, monkeypatch):
    (paths / 'výstupy' / f'pasy_{DATE}').mkdir(parents=True)
    monkeypatch.setattr(du, 'get_service', _fail_get_service)
    with pytest.raises(RuntimeError, match=r'výstup|vygenerujte'):
        du.upload_outputs(DATE)


def test_upload_outputs_creates_new_files(paths, outputs_dir, monkeypatch):
    files = _FakeFiles(folders={'Pasy': 'root-pasy-id', DATE: 'day-folder-id'})
    monkeypatch.setattr(du, 'get_service', lambda: _FakeService(files))

    result = du.upload_outputs(DATE)

    assert result['folder_link'] == (
        'https://drive.google.com/drive/folders/day-folder-id')
    assert files.updates == []
    assert files.folder_creates == []  # obě složky existovaly

    by_name = {e['name']: e for e in result['files']}
    assert set(by_name) == {'a.pdf', 'recipients.xlsx'}
    assert all(e['updated'] is False for e in by_name.values())

    creates = {c['body']['name']: c for c in files.file_creates}
    assert set(creates) == {'a.pdf', 'recipients.xlsx'}
    for name, call in creates.items():
        assert call['body']['parents'] == ['day-folder-id']
        assert by_name[name]['link'] == _view_link(call['id'])

    assert creates['a.pdf']['media_body'].mimetype() == 'application/pdf'
    assert creates['recipients.xlsx']['media_body'].mimetype() == XLSX_MIME

    # Id kořenové složky Pasy se kešuje do drive_config.json.
    config = json.loads(
        (paths / 'drive_config.json').read_text(encoding='utf-8'))
    assert config['pasy_folder_id'] == 'root-pasy-id'

def test_upload_outputs_reports_progress(paths, outputs_dir, monkeypatch):
    files = _FakeFiles(folders={'Pasy': 'root-pasy-id', DATE: 'day-folder-id'})
    monkeypatch.setattr(du, 'get_service', lambda: _FakeService(files))
    events = []

    result = du.upload_outputs(DATE, progress_callback=events.append, max_workers=1)

    assert [f['name'] for f in result['files']] == ['a.pdf', 'recipients.xlsx']
    assert events[0] == {
        'stage': 'preparing',
        'done': 0,
        'total': 2,
        'current': 'Připravuji složku na Drive…',
    }
    assert events[-1] == {
        'stage': 'done',
        'done': 2,
        'total': 2,
        'current': '',
    }
    uploaded_events = [event for event in events if event['stage'] == 'uploaded']
    assert len(uploaded_events) == 2
    assert [event['done'] for event in uploaded_events] == [1, 2]
    assert {event['file']['name'] for event in uploaded_events} == {
        'a.pdf', 'recipients.xlsx'}
    assert all(event['file']['link'] for event in uploaded_events)


def test_upload_outputs_updates_existing_file(paths, outputs_dir, monkeypatch):
    files = _FakeFiles(
        folders={'Pasy': 'root-pasy-id', DATE: 'day-folder-id'},
        existing={'a.pdf': 'drive-a-id'})
    monkeypatch.setattr(du, 'get_service', lambda: _FakeService(files))

    result = du.upload_outputs(DATE)

    by_name = {e['name']: e for e in result['files']}
    assert by_name['a.pdf']['updated'] is True
    assert by_name['recipients.xlsx']['updated'] is False

    assert [u['fileId'] for u in files.updates] == ['drive-a-id']
    assert [c['body']['name'] for c in files.file_creates] == [
        'recipients.xlsx']
    assert by_name['a.pdf']['link'] == _view_link('drive-a-id')


# ---------------------------------------------------------------- Flask routy

@pytest.fixture(scope='module')
def client():
    import app as app_module
    app_module.app.config['TESTING'] = True
    with app_module.app.test_client() as c:
        yield c


def wait_upload_done(client, job_id, timeout=2.0):
    deadline = time.monotonic() + timeout
    last_state = None
    while time.monotonic() < deadline:
        resp = client.get(f'/api/upload-drive/progress/{job_id}')
        assert resp.status_code == 200
        last_state = resp.get_json()
        if last_state['status'] in {'done', 'error'}:
            return last_state
        time.sleep(0.02)
    raise AssertionError(f'Upload job did not finish: {last_state!r}')

def test_drive_status_route(client, paths):
    resp = client.get('/api/drive-status')
    assert resp.status_code == 200
    assert resp.get_json() == {'credentials': False, 'token': False}


def test_upload_drive_route_no_outputs(client, paths, monkeypatch):
    monkeypatch.setattr(du, 'get_service', _fail_get_service)
    resp = client.post('/api/upload-drive', json={'date': '1999-01-01'})
    assert resp.status_code == 400
    data = resp.get_json()
    assert re.search(r'výstup|vygenerujte', data['error'])


def test_upload_drive_route_starts_job_and_reports_done(
        client, outputs_dir, monkeypatch):
    files = _FakeFiles(folders={'Pasy': 'root-pasy-id', DATE: 'day-folder-id'})
    monkeypatch.setattr(du, 'get_service', lambda: _FakeService(files))

    resp = client.post('/api/upload-drive', json={'date': DATE})

    assert resp.status_code == 202
    started = resp.get_json()
    assert started['status'] == 'running'
    assert started['job_id']

    final = wait_upload_done(client, started['job_id'])
    assert final['status'] == 'done'
    assert final['percent'] == 100
    assert final['total'] == 2
    assert final['done'] == 2
    assert final['folder_link'] == (
        'https://drive.google.com/drive/folders/day-folder-id')
    assert {f['name'] for f in final['files']} == {'a.pdf', 'recipients.xlsx'}


def test_upload_drive_progress_unknown_job(client):
    resp = client.get('/api/upload-drive/progress/nope')

    assert resp.status_code == 404
    assert resp.get_json()['error'] == 'Upload job nenalezen'
