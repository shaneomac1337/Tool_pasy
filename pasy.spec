# -*- mode: python ; coding: utf-8 -*-
# pasy.spec — PyInstaller 6.x onedir spec pro Rostlinolékařské pasy (Windows + macOS).
# Build:  pyinstaller pasy.spec
#   Windows -> dist/Pasy/Pasy.exe   (+ dist/Pasy/_internal/)
#   macOS   -> dist/Pasy/Pasy       (unixový spustitelný soubor, + dist/Pasy/_internal/)
# ponytail: JEDEN cross-platform spec — žádná větev na sys.platform, žádný BUNDLE.
#   PyInstaller sám řeší rozdíly OS (přípona .exe, bootloader). BUNDLE bychom
#   přidali jen kdybychom chtěli .app — to ale rozbije 'data vedle spustitelného
#   souboru' model (viz src/paths.py, docs/shipping_plan.md §1.1) a schová konzoli.
#   onedir SLOŽKA => data leží vedle spustitelného souboru na obou OS a
#   console=True ukáže log (Windows konzole / macOS Terminal po dvojkliku).
# target_arch=None => host arch (na macos-latest = arm64 / Apple Silicon).

from PyInstaller.utils.hooks import collect_data_files

datas = [
    ('src/templates', 'templates'),   # Flask hledá šablony vedle app modulu (frozen root = _internal)
    ('src/static', 'static'),
    ('assets/eu_flag.png', 'assets'),  # passport_generator má i base64 zálohu
    ('assets/DejaVuSans.ttf', 'assets'),       # font s českou diakritikou (vendored)
    ('assets/DejaVuSans-Bold.ttf', 'assets'),
]
# DejaVu font (čeština) přibalujeme z assets/ výše — reportlab žádný DejaVu nemá
# (jen Vera bez ě/ř/ů). collect_data_files sebere jen vlastní data reportlabu.
datas += collect_data_files('reportlab')
# googleapiclient statické discovery dokumenty (discovery_cache/documents/*.json)
datas += collect_data_files('googleapiclient')

hiddenimports = [
    'pdfminer',                          # pdfplumber -> pdfminer.six
    'PIL',                               # vkládání obrázků (reportlab/pdfplumber)
    'google.auth.transport.requests',    # lazy importy v drive_uploader.py
    'google.oauth2.credentials',
    'google_auth_oauthlib.flow',
    'googleapiclient.discovery',
    'googleapiclient.http',
]

a = Analysis(
    ['run.py'],
    pathex=['src'],          # aby 'from app import app' a sourozenci našli moduly
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,   # onedir: knihovny jdou do COLLECT
    name='Pasy',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,               # bez UPX — méně false-positive u antiviru
    console=True,            # Windows: konzole s logem; macOS (onedir složka): Terminal po dvojkliku
    disable_windowed_traceback=False,
    argv_emulation=False,    # jen pro .app file-drop; tady nepotřebné
    target_arch=None,        # host arch; macos-latest = arm64. NE universal2 (viz plán §7.4)
    codesign_identity=None,  # unsigned; PyInstaller na arm64 auto ad-hoc podepíše (viz §6.3)
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='Pasy',
)
# ŽÁDNÝ BUNDLE(...) — záměrně onedir SLOŽKA, ne .app (viz hlavička a §1.1).
