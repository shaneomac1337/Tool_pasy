"""Generování PDF pasů a sloučených faktur.

Vykreslí rostlinolékařský pas (reportlab) a sloučí ho před stránky
původní faktury (pypdf). Výstup: {číslo}.pdf per faktura + recipients.xlsx.
"""
import io
import sys
import zipfile
from pathlib import Path

import openpyxl
from pypdf import PdfReader, PdfWriter
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader

from passport_generator import _get_flag_image_path


# Přibalený DejaVu font (čeština) — hledán ve frozen bundlu (sys._MEIPASS)
# i ve vývoji (assets/ v kořeni). reportlab žádný DejaVu nemá (jen Vera bez
# ě/ř/ů/ť/ň), proto ho přibalujeme sami — funguje na Windows i macOS.
_BUNDLE_ASSETS = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent.parent)) / 'assets'


def _register_fonts() -> None:
    """Registruje font s českou diakritikou. Nikdy nespadne na Helveticu."""
    candidates = [
        (r'C:\Windows\Fonts\arial.ttf', r'C:\Windows\Fonts\arialbd.ttf'),   # Windows
        (str(_BUNDLE_ASSETS / 'DejaVuSans.ttf'),
         str(_BUNDLE_ASSETS / 'DejaVuSans-Bold.ttf')),                       # přibalený (macOS aj.)
    ]
    for regular, bold in candidates:
        if Path(regular).exists() and Path(bold).exists():
            pdfmetrics.registerFont(TTFont('Arial', regular))
            pdfmetrics.registerFont(TTFont('Arial-Bold', bold))
            return
    raise RuntimeError('Chybí font s českou diakritikou')


_register_fonts()

# Rozměry bloku pasu (viz _write_passport_sheet ve passport_generator.py)
_LEFT = 2.0 * cm
_TOP_MARGIN = 2.0 * cm
_BOTTOM_MARGIN = 2.0 * cm
_HEADER_H = 3.0 * cm
_FLAG_CELL_W = 5.0 * cm
_COL_WIDTHS = [9.0 * cm, 4.0 * cm, 4.5 * cm]
_TABLE_W = sum(_COL_WIDTHS)          # 17.5 cm = šířka hlavičky
_ROW_H = 0.55 * cm
_LINE_W = 0.5                        # pt


def _draw_header(c, top_y: float) -> float:
    """Nakreslí hlavičku pasu (vlajka + názvy). Vrací y spodní hrany."""
    band_bottom = top_y - _HEADER_H

    # EU vlajka — zachovat poměr stran, cíl ≈ 3.4 × 2.0 cm, svisle centrovaná
    try:
        img = ImageReader(_get_flag_image_path())
        iw, ih = img.getSize()
        max_w = _FLAG_CELL_W - 2 * 0.25 * cm
        max_h = _HEADER_H - 2 * 0.25 * cm
        target_w, target_h = 3.4 * cm, 2.0 * cm
        scale = min(target_w / iw, target_h / ih, max_w / iw, max_h / ih)
        fw, fh = iw * scale, ih * scale
        fx = _LEFT + (_FLAG_CELL_W - fw) / 2
        fy = band_bottom + (_HEADER_H - fh) / 2
        c.drawImage(img, fx, fy, fw, fh)
    except Exception as e:
        print(f"Varování: Nelze vložit vlajku: {e!r}")

    # Texty vpravo od vlajky
    tx = _LEFT + _FLAG_CELL_W + 0.3 * cm
    ty = top_y - 1.0 * cm
    c.setFont('Arial-Bold', 14)
    c.drawString(tx, ty, 'Rostlinolékařský pas / Plant Passport')
    c.drawString(tx, ty - 0.8 * cm, 'B: CZ - 0550')

    # Rámeček hlavičky + předěl vlajka | texty
    c.setLineWidth(_LINE_W)
    c.rect(_LEFT, band_bottom, _TABLE_W, _HEADER_H)
    c.line(_LEFT + _FLAG_CELL_W, band_bottom,
           _LEFT + _FLAG_CELL_W, top_y)
    return band_bottom


def _draw_table_row(c, y_top: float, values, bold: bool, centered: bool):
    """Jeden řádek tabulky s mřížkou. Vrací y spodní hrany."""
    y_bot = y_top - _ROW_H
    c.setLineWidth(_LINE_W)
    x = _LEFT
    for w, val in zip(_COL_WIDTHS, values):
        c.rect(x, y_bot, w, _ROW_H)
        if val:
            c.setFont('Arial-Bold' if bold else 'Arial', 11 if bold else 10)
            baseline = y_bot + (_ROW_H - (11 if bold else 10) * 0.72) / 2 + 1
            if centered:
                c.drawCentredString(x + w / 2, baseline, val)
            else:
                c.drawString(x + 0.1 * cm, baseline, val)
        x += w
    return y_bot


def render_passport_pdf(plants: list, buf) -> None:
    """Vykreslí pas do bufferu jako A4 PDF (portrét)."""
    c = canvas.Canvas(buf, pagesize=A4)
    page_h = A4[1]
    top_y = page_h - _TOP_MARGIN

    y = _draw_header(c, top_y)
    y = _draw_table_row(c, y, ['A:', 'C:', 'D:'], bold=True, centered=True)

    rows = [
        (p.get('passport_name', ''), p.get('code', ''),
         p.get('country') or 'CZ')
        for p in plants
    ]
    rows.append(('', '', ''))  # prázdný závěrečný řádek (parita se vzorem)

    for name, code, country in rows:
        if y - _ROW_H < _BOTTOM_MARGIN:
            c.showPage()
            y = page_h - _TOP_MARGIN
            y = _draw_table_row(c, y, ['A:', 'C:', 'D:'],
                                bold=True, centered=True)
        y = _draw_table_row(c, y, [name, code, country],
                            bold=False, centered=False)

    c.showPage()
    c.save()


def build_outputs(final_invoices: list, parsed_index: dict,
                  source_paths: dict, output_dir: Path) -> dict:
    """Vygeneruje sloučené PDF per faktura + recipients.xlsx.

    Vrací {'dir': Path, 'files': [Path], 'warnings': [str]}.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    files = []
    warnings = []
    recipients = []  # (email, attachment)

    for inv_data in final_invoices:
        number = str(inv_data.get('number', ''))
        plants = inv_data.get('plants') or []
        if not plants:
            continue  # objednávka bez rostlin — žádný pas (parita se starým)

        buf = io.BytesIO()
        render_passport_pdf(plants, buf)
        buf.seek(0)

        writer = PdfWriter()
        for page in PdfReader(buf).pages:
            writer.add_page(page)

        parsed = parsed_index.get(number)
        src_path = (source_paths.get(parsed.source_file)
                    if parsed is not None else None)
        if parsed is not None and src_path and Path(src_path).exists():
            try:
                reader = PdfReader(src_path)
                pages = parsed.source_pages or [parsed.source_page]
                for p in pages:
                    writer.add_page(reader.pages[p - 1])
            except Exception as e:
                warnings.append(
                    f"{number}: chyba při čtení zdrojové faktury ({e}), "
                    f"vygenerován pouze pas")
        else:
            warnings.append(
                f"{number}: chybí zdrojová faktura, vygenerován pouze pas")

        out_path = output_dir / f"{number}.pdf"
        with open(out_path, 'wb') as f:
            writer.write(f)
        files.append(out_path)
        recipients.append((parsed.email if parsed else '', f"{number}.pdf"))

    # recipients.xlsx — parita se starým nástrojem
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(['Email', 'Attachment'])
    ws.column_dimensions['A'].width = 30
    ws.column_dimensions['B'].width = 11
    for email, attachment in recipients:
        ws.append([email or '', attachment])
    rec_path = output_dir / 'recipients.xlsx'
    wb.save(rec_path)
    files.append(rec_path)

    if warnings:
        warn_path = output_dir / 'varovani.txt'
        warn_path.write_text('\n'.join(warnings), encoding='utf-8')
        files.append(warn_path)

    # vyrazeno.txt — audit řádků vyřazených filtrem nerostlinných položek.
    # Když frontend pošle klíč 'excluded', platí JEHO stav (uživatel mohl
    # položky vrátit na pas); bez klíče se bere stav z parseru.
    excluded_lines = []
    for inv_data in final_invoices:
        number = str(inv_data.get('number', ''))
        if 'excluded' in inv_data:
            items = inv_data['excluded'] or []
        else:
            parsed = parsed_index.get(number)
            items = parsed.excluded if parsed is not None else []
        for item in items:
            excluded_lines.append(f"Faktura {number}: {item['text']}")
    if excluded_lines:
        exc_path = output_dir / 'vyrazeno.txt'
        exc_path.write_text('\n'.join(excluded_lines), encoding='utf-8')
        files.append(exc_path)

    return {'dir': output_dir, 'files': files, 'warnings': warnings}


def zip_outputs(files: list) -> io.BytesIO:
    """Zabalí vygenerované soubory do ZIP v paměti (buffer na pozici 0)."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        for path in files:
            zf.write(path, arcname=path.name)
    buf.seek(0)
    return buf
