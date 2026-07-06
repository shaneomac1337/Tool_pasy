# Rostlinolékařské pasy — Plant Passport Tool

A sales-documentation tool for a plant nursery. It reads customer **invoice PDFs**
(faktury), matches each plant against the batch catalog (**šarže**), and produces
the **plant passports** (rostlinolékařské pasy) needed to ship the order — as an
Excel workbook, as merged per-invoice PDFs, and optionally uploaded straight to
Google Drive.

> This is a **documentation / sales tool**, not a biology application. The
> botanical names are catalog data used for matching and printing — nothing more.

---

## What it does

Three steps in the browser (`http://localhost:5001`):

1. **Upload** — drop one or more invoice PDFs. Each `Faktura č.` starts a new
   invoice; continuation pages are grouped onto it. Non-plant lines (shipping,
   *Přidaný produkt*, *Dárkový poukaz*, …) are filtered out automatically.
2. **Match** — every plant line is matched against `data/sarze.xlsx`:
   - `exact` — one confident hit, code assigned.
   - `fuzzy` — best candidate pre-filled; confirm with **✓ Potvrdit**, or accept
     them all at once with **✓ Přiřadit vše**.
   - `none` — not found; search manually.
3. **Generate** — produce the deliverables:
   - **Generovat Excel** — one `.xlsx` with a passport sheet per invoice.
   - **Generovat PDF (ZIP)** — one merged `{number}.pdf` per invoice (passport
     page first, original invoice pages after) + `recipients.xlsx`, streamed as a
     ZIP and saved under `výstupy/pasy_{date}/`.
   - **☁ Nahrát na Drive** — upload that day's output folder to Google Drive
     (see [Google Drive](#google-drive-upload)).

---

## Repository layout

```
Tool_pasy/
├── run.py                  # dev-server entry point: python run.py
├── requirements.txt
├── src/
│   ├── app.py              # Flask routes
│   ├── paths.py            # SINGLE source of truth for file locations
│   ├── session.py          # ParseSession — in-memory upload session
│   ├── pdf_parser.py       # invoice PDF -> Invoice objects
│   ├── plant_matcher.py    # name -> šarže match (7-tier pipeline)
│   ├── passport_generator.py  # Excel passport renderer
│   ├── pdf_generator.py    # PDF passport renderer + merge + ZIP
│   ├── drive_uploader.py   # Google Drive upload
│   ├── templates/index.html
│   └── static/app.js, style.css
├── data/sarze.xlsx         # the šarže catalog (input data)
├── assets/eu_flag.png      # EU flag drawn on every passport
├── tests/                  # pytest suite (conftest puts src/ on the path)
├── scripts/report_anomalies.py
├── docs/                   # historical notes
└── výstupy/                # generated output (gitignored)
```

All modules resolve their file locations through `src/paths.py` (`DATA_DIR`,
`ASSETS_DIR`, `OUTPUT_DIR`, and the three Drive config paths). If you ever move the
project, that one file is the only place that knows the layout.

---

## Setup

Requires **Python 3.10+**.

```bash
pip install -r requirements.txt
python run.py
```

Then open **http://localhost:5001**. The server runs in debug mode (auto-reload)
on port 5001.

> `thefuzz` prints a warning if `python-Levenshtein` isn't installed; matching
> still works, just a little slower. `pip install python-Levenshtein` to silence it.

---

## Output files

Every generation writes to `výstupy/pasy_{YYYY-MM-DD}/`:

| File | Contents |
|------|----------|
| `{number}.pdf` | Merged passport page + the original invoice pages, one per invoice. |
| `recipients.xlsx` | Two columns — `Email` \| `Attachment` (`{number}.pdf`) — one row per generated PDF. |
| `varovani.txt` | Only if something degraded (e.g. a source invoice PDF was missing). |

Re-running on the same day **overwrites** the same folder. Invoices with no
matched plants (voucher-only orders) produce no PDF.

---

## Google Drive upload

The **☁ Nahrát na Drive** button uploads the current day's outputs to your
Google Drive, organised by year. The day's passport Excel goes into the year
folder; the PDFs land in `pdfka/{date}/` — no ZIPs on Drive:

```
Můj disk/
└── Rostlinné pasy/             # root folder, created once
    └── 2026/                   # one folder per year
        ├── pasy_2026-07-04.xlsx    # passport Excel (if generated that day)
        └── pdfka/
            └── 2026-07-04/     # one folder per generation day
                ├── 637.pdf
                ├── 662.pdf
                ├── …
                └── recipients.xlsx
```

Re-uploading the same day **updates the existing files in place** (same Drive file
IDs) — it never creates duplicates.

### How it works

- OAuth **installed-app flow** against your personal Google account.
- Scope is **`drive.file` only** — the app can see *only* the files and folders it
  creates, nothing else in your Drive.
- The first upload opens a Google login page in your browser; approve once and the
  token is cached and refreshed automatically forever after.
- Upload is a **separate step** from generation (its own `POST /api/upload-drive`),
  so it's retryable and never blocks the ZIP download.
- The Drive step now shows upload progress (file count + current file) instead
  of looking frozen during larger batches.
- Files are uploaded concurrently, up to 4 at a time; re-uploading the same date
  still updates existing Drive files in place.

### One-time Google Cloud setup

You only do this once; the resulting `credentials.json` is the app registration
everyone reuses.

1. Go to <https://console.cloud.google.com> and create a project (e.g. `pasy`).
2. **APIs & Services → Library** → enable **Google Drive API**.
3. **APIs & Services → OAuth consent screen**:
   - User type **External**, fill in app name + your email.
   - **Publish the app** (move it from "Testing" to "In production").
     This is important — see [token lifetime](#token-lifetime) below.
4. **APIs & Services → Credentials → Create credentials → OAuth client ID**:
   - Application type **Desktop app**.
   - Download the JSON and save it as **`credentials.json`** in the repo root
     (next to `run.py`).
5. Start the app, walk to step 3, click **☁ Nahrát na Drive**. A browser window
   opens for consent; approve it. Done — from now on it's fully automatic.

### Token lifetime

While the OAuth app is in **"Testing"** mode, Google expires the refresh token
after **7 days**, forcing you to re-consent weekly. **Publishing the app** (step 3
above) makes the token permanent. No Google verification is needed because the
`drive.file` scope is *non-sensitive*.

---

## Configuration files

Three files in the repo root control the Drive integration. **All three are
gitignored** — they hold secrets or machine-local state and must never be
committed. Their locations are defined in `src/paths.py`.

| File | What it is | How it's created | Notes |
|------|-----------|------------------|-------|
| **`credentials.json`** | Your OAuth **client secret** (the app registration downloaded from Google Cloud). | You place it there manually (Cloud setup step 4). | Required. Without it the app shows *"Google Drive není nastaven — chybí credentials.json"* and the upload button explains what's missing. |
| **`token.json`** | The cached **access + refresh token** for your Google account. | Created automatically after the first successful consent. | Delete this file to force re-authentication (e.g. to switch Google accounts). Refreshed silently while valid. |
| **`drive_config.json`** | Cache of the **`Pasy` root folder ID** on your Drive. | Created automatically on the first upload. | See below. |

### `drive_config.json` and the folder ID

```json
{
  "root_folder_id": "1AbCdEfGhIjKlMnOpQrStUvWxYz012345"
}
```

- `root_folder_id` is the Drive ID of the top-level **`Rostlinné pasy`** folder
  that all year folders go into.
- On each upload the app validates this ID (a `files.get` call). If the folder
  was deleted, trashed, or the ID is invalid, it **transparently recreates**
  `Rostlinné pasy` and rewrites the config — you don't have to do anything.
- **To point the tool at a different Drive folder**, put that folder's ID here
  (the long string in its URL: `drive.google.com/drive/folders/<THIS_ID>`). The
  next upload will nest the year folders inside it. Note: with the `drive.file`
  scope the app can only write to folders **it created**, so an arbitrary
  pre-existing folder may not be writable — the safe reset is to **delete
  `drive_config.json`** and let the app create a fresh `Rostlinné pasy` folder.
  If you already have a manually created `Rostlinné pasy` folder on Drive, let
  the app create its own and move your old year folders into it (the app only
  needs write access to folders it creates; old content sitting next to it is
  fine).

### Drive-related endpoints

| Endpoint | Purpose |
|----------|---------|
| `GET /api/drive-status` | Reports `{ "credentials": bool, "token": bool }` (pure file check, no network). Drives the button's tooltip. |
| `POST /api/upload-drive` | Body `{ "date": "YYYY-MM-DD" }` (defaults to today). Uploads `výstupy/pasy_{date}/`. Returns `{ folder_link, files: [{ name, link, updated }] }`. |

---

## Session behavior

Parsed invoices and uploaded file paths live in an **in-memory** `ParseSession`
(`src/session.py`). If the server restarts between uploading invoices and
generating PDFs, the original invoice files can no longer be merged — the tool
falls back to **passport-only PDFs** and writes a `varovani.txt` explaining which
invoices were affected. This is deliberate; there is no on-disk session state.

---

## Testing

```bash
python -m pytest -q
```

The suite (52 tests) covers plant matching, PDF parsing/generation, the merge and
ZIP packaging, the session, and the Drive uploader (fully mocked — no network, no
real OAuth). `tests/conftest.py` puts `src/` on the path, so tests run from the
repo root.

---

## Notes

- Passport layout (`B: CZ - 0550`, the EU flag, the A:/C:/D: table) is rendered by
  two independent adapters — Excel (`passport_generator.py`) and PDF
  (`pdf_generator.py`) — kept visually consistent against the reference sample.
- Czech diacritics require a real TrueType font; the PDF renderer registers Windows
  Arial (falling back to DejaVu) and never silently drops to a glyph-less font.
