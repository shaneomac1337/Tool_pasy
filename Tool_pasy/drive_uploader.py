"""
Nahrávání výstupů (pasy + faktury) na Google Drive.

OAuth installed-app flow s osobním Google účtem, scope pouze drive.file.
Soubory credentials.json / token.json / drive_config.json leží vedle app.py.
Import modulu nikdy nesmí selhat ani mít vedlejší efekty (síť, zápis souborů)
— Google knihovny se importují líně uvnitř funkcí.
"""
import json
from pathlib import Path

CREDENTIALS_PATH = Path(__file__).parent / 'credentials.json'
TOKEN_PATH = Path(__file__).parent / 'token.json'
CONFIG_PATH = Path(__file__).parent / 'drive_config.json'
SCOPES = ['https://www.googleapis.com/auth/drive.file']
OUTPUT_BASE = Path(__file__).parent / 'výstupy'

_MIMETYPES = {
    '.pdf': 'application/pdf',
    '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    '.txt': 'text/plain',
}


def get_status() -> dict:
    """Stav napojení na Drive — jen existence souborů, žádná síť."""
    token_ok = False
    if TOKEN_PATH.exists():
        try:
            token_ok = isinstance(json.loads(
                TOKEN_PATH.read_text(encoding='utf-8')), dict)
        except (json.JSONDecodeError, OSError):
            token_ok = False
    return {
        'credentials': CREDENTIALS_PATH.exists(),
        'token': token_ok,
    }


def get_service():
    """Vrátí Drive v3 service; podle potřeby obnoví token nebo spustí OAuth flow."""
    if not CREDENTIALS_PATH.exists():
        raise RuntimeError(
            'Chybí credentials.json — vytvořte OAuth klienta v Google Cloud Console')

    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    creds = None
    if TOKEN_PATH.exists():
        try:
            creds = Credentials.from_authorized_user_file(
                str(TOKEN_PATH), SCOPES)
        except (ValueError, json.JSONDecodeError):
            creds = None  # poškozený token — projde znovu OAuth flow

    if creds and creds.valid:
        pass
    elif creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        TOKEN_PATH.write_text(creds.to_json(), encoding='utf-8')
    else:
        flow = InstalledAppFlow.from_client_secrets_file(
            str(CREDENTIALS_PATH), SCOPES)
        creds = flow.run_local_server(port=0)
        TOKEN_PATH.write_text(creds.to_json(), encoding='utf-8')

    return build('drive', 'v3', credentials=creds)


def ensure_folder(service, name: str, parent_id=None) -> str:
    """Najde složku podle jména (a rodiče), jinak ji vytvoří. Vrací id."""
    safe = name.replace("'", "\\'")
    q = (f"name='{safe}' and mimeType='application/vnd.google-apps.folder'"
         " and trashed=false")
    if parent_id:
        q += f" and '{parent_id}' in parents"
    res = service.files().list(
        q=q, spaces='drive', fields='files(id)', pageSize=10).execute()
    files = res.get('files', [])
    if files:
        return files[0]['id']

    body = {'name': name, 'mimeType': 'application/vnd.google-apps.folder'}
    if parent_id:
        body['parents'] = [parent_id]
    created = service.files().create(body=body, fields='id').execute()
    return created['id']


def _get_pasy_folder_id(service) -> str:
    """Id kořenové složky 'Pasy' — cache v drive_config.json, ověřená get()."""
    config = {}
    if CONFIG_PATH.exists():
        try:
            config = json.loads(CONFIG_PATH.read_text(encoding='utf-8'))
            if not isinstance(config, dict):
                config = {}
        except (json.JSONDecodeError, OSError):
            config = {}

    cached = config.get('pasy_folder_id')
    if cached:
        try:
            meta = service.files().get(
                fileId=cached, fields='id,trashed').execute()
            if not meta.get('trashed'):
                return cached
        except Exception:
            pass  # neplatné/smazané id — vytvoří se znovu

    folder_id = ensure_folder(service, 'Pasy', None)
    config['pasy_folder_id'] = folder_id
    CONFIG_PATH.write_text(
        json.dumps(config, ensure_ascii=False, indent=2), encoding='utf-8')
    return folder_id


def upload_outputs(date_str: str) -> dict:
    """
    Nahraje soubory z výstupy/pasy_{date_str}/ do Drive složky Pasy/{date_str}/.
    Stejnojmenné soubory přepíše (update), nové vytvoří. Vrací odkazy.
    """
    out_dir = OUTPUT_BASE / f'pasy_{date_str}'
    local_files = (
        sorted(p for p in out_dir.iterdir() if p.is_file())
        if out_dir.is_dir() else []
    )
    if not local_files:
        raise RuntimeError('Složka výstupů neexistuje — nejprve vygenerujte PDF')

    from googleapiclient.http import MediaFileUpload

    service = get_service()
    pasy_id = _get_pasy_folder_id(service)
    folder_id = ensure_folder(service, date_str, pasy_id)

    uploaded = []
    for path in local_files:
        mimetype = _MIMETYPES.get(path.suffix.lower(),
                                  'application/octet-stream')
        media = MediaFileUpload(str(path), mimetype=mimetype)

        safe = path.name.replace("'", "\\'")
        q = f"name='{safe}' and '{folder_id}' in parents and trashed=false"
        res = service.files().list(
            q=q, spaces='drive', fields='files(id)', pageSize=1).execute()
        existing = res.get('files', [])

        if existing:
            info = service.files().update(
                fileId=existing[0]['id'], media_body=media,
                fields='id,webViewLink').execute()
            updated = True
        else:
            info = service.files().create(
                body={'name': path.name, 'parents': [folder_id]},
                media_body=media, fields='id,webViewLink').execute()
            updated = False

        uploaded.append({
            'name': path.name,
            'link': info.get('webViewLink', ''),
            'updated': updated,
        })

    return {
        'folder_link': f'https://drive.google.com/drive/folders/{folder_id}',
        'files': uploaded,
    }
