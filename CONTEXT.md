# Tool_pasy — domain glossary

Sales-documentation tool: generates plant passports (rostlinolékařské pasy) as customer-facing documents for sold plants. Not a biology tool — botanical names are catalog data for matching and printing.

## Terms

- **Invoice (faktura)** — one customer order parsed from an uploaded invoice PDF; identified by `Faktura č.` number; owns its plant items and its source page run.
- **Plant item** — one line of an invoice that is a plant (non-plant lines like shipping are filtered by keyword).
- **Šarže** — the batch catalog (`data/sarze.xlsx`): passport name ↔ traceability code ↔ country. The authority plant items are matched against.
- **Match** — the link from a plant item to a šarže entry; `exact` / `fuzzy` (best candidate pre-filled, user confirms) / `none` (manual search).
- **Passport (pas)** — the printable plant-passport document for one invoice: EU flag, `Rostlinolékařský pas / Plant Passport`, `B: CZ - 0550`, and the A:/C:/D: table of matched plants. Rendered by two adapters: xlsx (`passport_generator`) and PDF (`pdf_generator`).
- **Vzor** — the reference layout the passport must visually match (legacy sample `100.pdf`).
- **ParseSession** — the current upload session: the invoices parsed from the last upload plus the uploaded files' temp paths. **Memory-only by decision (2026-07-04)**: a server restart between parse and generate degrades PDF output to passport-only + `varovani.txt` — deliberate, tested contingency. Persistence, if ever wanted, is an implementation swap behind the same interface.
- **Outputs (výstupy)** — the per-day deliverables `výstupy/pasy_{date}/`: one merged `{number}.pdf` per invoice (passport page + original invoice pages), `recipients.xlsx` (Email | Attachment), optional `varovani.txt`. Delivered as ZIP download and Drive upload (`Rostlinné pasy/{year}/pdfka/{date}/` for the day's files, the daily Excel to `Rostlinné pasy/{year}/`; loose files, update-in-place).
