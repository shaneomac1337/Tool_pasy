import os
import io
import tempfile
import zipfile
from datetime import date
from pathlib import Path
from flask import Flask, render_template, request, jsonify, send_file
from pdf_parser import PDFParser
from plant_matcher import PlantMatcher
from passport_generator import generate_excel
from pdf_generator import build_outputs
from drive_uploader import get_status, upload_outputs

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 200 * 1024 * 1024

parser = PDFParser()

SARZE_PATH = Path(__file__).parent / 'data' / 'sarze.xlsx'
matcher = PlantMatcher(str(SARZE_PATH))
print(f"✓ Šarže načtena: {len(matcher.entries)} rostlin")

UPLOAD_TMP = Path(tempfile.gettempdir()) / "rl_pasy_uploads"
UPLOAD_TMP.mkdir(exist_ok=True)

_session_invoices = []
_session_file_paths: dict = {}


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/parse', methods=['POST'])
def parse_pdfs():
    global _session_invoices
    if 'files' not in request.files:
        return jsonify({'error': 'Žádné soubory nebyly nahrány'}), 400

    files = request.files.getlist('files')
    pdf_files = [f for f in files if f.filename.lower().endswith('.pdf')]
    if not pdf_files:
        return jsonify({'error': 'Žádné PDF soubory nenalezeny'}), 400

    saved_paths = []
    for f in pdf_files:
        tmp_path = UPLOAD_TMP / f.filename
        f.save(str(tmp_path))
        saved_paths.append(str(tmp_path))
        _session_file_paths[f.filename] = str(tmp_path)

    invoices = parser.parse_files(saved_paths)
    _session_invoices = invoices

    return jsonify({
        'invoices':         [inv.to_dict() for inv in invoices],
        'total_invoices':   len(invoices),
        'total_plants':     sum(len(inv.plants) for inv in invoices),
        'files_processed':  len(saved_paths)
    })


@app.route('/api/match', methods=['POST'])
def match_plants():
    global _session_invoices
    if not _session_invoices:
        return jsonify({'error': 'Nejdřív nahraj faktury'}), 400

    result = []
    stats = {'exact': 0, 'fuzzy': 0, 'none': 0}

    for inv in _session_invoices:
        plants_raw = [p.to_dict() for p in inv.plants]
        matched    = matcher.match_invoice_plants(plants_raw)
        for p in matched:
            stats[p['match_type']] += 1
        result.append({
            'number':      inv.number,
            'date':        inv.date,
            'customer':    inv.customer,
            'source_file': inv.source_file,
            'plants':      matched,
        })

    return jsonify({
        'invoices':    result,
        'stats':       stats,
        'sarze_names': matcher.get_all_sarze_names(),
    })


@app.route('/api/search-plant', methods=['POST'])
def search_plant():
    """Ruční vyhledávání: uživatel zadá název, vrátí shodu ze šarže."""
    data  = request.get_json()
    query = (data or {}).get('query', '').strip()
    if not query:
        return jsonify({'error': 'Prázdný dotaz'}), 400

    result = matcher.search_by_name(query)
    return jsonify(result)


@app.route('/api/generate-excel', methods=['POST'])
def generate_excel_route():
    """
    Přijme finální data z frontendu a vygeneruje Excel s pasy.
    Body: { "invoices": [ { "number", "customer", "date", "plants": [...] } ] }
    """
    data = request.get_json()
    if not data or 'invoices' not in data:
        return jsonify({'error': 'Chybí data faktur'}), 400

    invoices = data['invoices']
    if not invoices:
        return jsonify({'error': 'Žádné faktury k exportu'}), 400

    output_dir = Path(__file__).parent / 'výstupy'
    try:
        excel_path = generate_excel(invoices, output_dir)
    except Exception as e:
        return jsonify({'error': f'Chyba při generování: {e}'}), 500

    return send_file(
        str(excel_path),
        as_attachment=True,
        download_name=excel_path.name,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )


@app.route('/api/generate-pdf', methods=['POST'])
def generate_pdf_route():
    """
    Přijme finální data a vygeneruje ZIP: pas + faktura per PDF,
    recipients.xlsx. Kopie zůstává ve výstupy/pasy_{datum}/.
    Body: { "invoices": [ { "number", "customer", "date", "plants": [...] } ] }
    """
    data = request.get_json()
    if not data or 'invoices' not in data:
        return jsonify({'error': 'Chybí data faktur'}), 400

    invoices = data['invoices']
    if not invoices:
        return jsonify({'error': 'Žádné faktury k exportu'}), 400

    out_dir = (Path(__file__).parent / 'výstupy'
               / f"pasy_{date.today().isoformat()}")
    try:
        result = build_outputs(
            invoices,
            {inv.number: inv for inv in _session_invoices},
            _session_file_paths,
            out_dir
        )
    except Exception as e:
        return jsonify({'error': f'Chyba při generování: {e}'}), 500

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        for path in result['files']:
            zf.write(path, arcname=path.name)
    buf.seek(0)

    return send_file(
        buf,
        as_attachment=True,
        download_name=f"pasy_{date.today().isoformat()}.zip",
        mimetype='application/zip'
    )


@app.route('/api/drive-status', methods=['GET'])
def drive_status_route():
    """Stav napojení na Google Drive (credentials + token)."""
    return jsonify(get_status())


@app.route('/api/upload-drive', methods=['POST'])
def upload_drive_route():
    """
    Nahraje výstupy dne na Google Drive do složky Pasy/{datum}/.
    Body (volitelné): { "date": "YYYY-MM-DD" } — výchozí dnešek.
    """
    data = request.get_json(silent=True) or {}
    date_str = data.get('date') or date.today().isoformat()

    try:
        result = upload_outputs(date_str)
    except RuntimeError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': f'Chyba při nahrávání na Drive: {e}'}), 500

    return jsonify(result)


@app.route('/api/debug-tables', methods=['POST'])
def debug_tables():
    """Debug endpoint — vrátí surová data tabulek z prvního PDF."""
    import pdfplumber
    if 'file' not in request.files:
        return jsonify({'error': 'Žádný soubor'}), 400
    f = request.files['file']
    tmp_path = UPLOAD_TMP / f.filename
    f.save(str(tmp_path))

    pages_data = []
    with pdfplumber.open(str(tmp_path)) as pdf:
        for page_num, page in enumerate(pdf.pages[:3]):  # max 3 stránky
            tables = page.extract_tables()
            tables_data = []
            for t_idx, table in enumerate(tables):
                rows_data = []
                for r_idx, row in enumerate(table[:15]):  # max 15 řádků
                    rows_data.append({
                        'row_index': r_idx,
                        'cells': [str(c) if c is not None else 'None' for c in row]
                    })
                tables_data.append({
                    'table_index': t_idx,
                    'num_rows': len(table),
                    'num_cols': len(table[0]) if table else 0,
                    'rows': rows_data
                })
            pages_data.append({
                'page': page_num + 1,
                'num_tables': len(tables),
                'tables': tables_data
            })

    return jsonify({'pages': pages_data})


if __name__ == '__main__':
    print("\n🌿 Rostlinolékařské pasy — spouštím server...")
    print("👉  Otevři prohlížeč na: http://localhost:5001\n")
    app.run(debug=True, port=5001)
