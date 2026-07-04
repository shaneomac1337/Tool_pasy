# Rostlinolékařské pasy (Plant Passport Generator)

A complete Flask web application for generating plant passports (Rostlinolékařské pasy) from invoice PDFs.

## Project Structure

```
Tool_pasy/
├── app.py                      # Flask application server
├── pdf_parser.py               # PDF parsing and invoice extraction logic
├── data/
│   └── sarze.xlsx              # Plant batch reference data
├── output/                      # Generated passports output directory
├── static/
│   ├── app.js                  # Frontend JavaScript (drag-drop, upload)
│   └── style.css               # UI styling (green theme)
├── templates/
│   └── index.html              # HTML template (Czech language)
└── README.md                    # This file
```

## Features

### Backend (Python/Flask)
- **PDF Parser (`pdf_parser.py`)**
  - Extracts invoice data from PDF files
  - Identifies plant items from invoice tables
  - Cleans plant names (removes dimensions, shipping info)
  - Returns structured data (Invoice, PlantItem objects)
  - Filters out non-plant items (shipping, fees, etc.)

- **Flask API (`app.py`)**
  - `/` - Main landing page
  - `/api/parse` - POST endpoint for PDF file processing
  - Handles multi-file uploads (max 200MB)
  - Returns JSON with parsed invoices and plant data

### Frontend (HTML/CSS/JavaScript)
- **HTML Template** (Czech language)
  - 4-step process UI (Load → Assign → Generate → Upload)
  - Drag-and-drop file upload zone
  - Results table with invoice summary

- **Styling** (`style.css`)
  - Green theme matching plant/nature concept
  - Responsive design (mobile-friendly)
  - Card-based layout
  - Progress bar visualization

- **Interactivity** (`app.js`)
  - Drag-and-drop file handling
  - File upload with progress tracking
  - Real-time results display
  - Table generation from parsed data

## Installation & Setup

### Prerequisites
- Python 3.8+
- pip

### Install Dependencies
```bash
pip3 install flask pdfplumber --break-system-packages
```

### Run Application
```bash
cd /sessions/zealous-pensive-ramanujan/mnt/Tool_pasy
python3 app.py
```

Server starts at: **http://localhost:5001**

## Usage

1. **Load PDFs** (Step 1)
   - Drag and drop PDF files or click "Select files"
   - PDFs are automatically uploaded and parsed

2. **View Results**
   - Table shows extracted invoices with:
     - Invoice number
     - Customer name
     - Date
     - Plant count
     - Source file

3. **Continue** (Step 2-4)
   - Assign plant codes
   - Generate passports
   - Upload to Google Drive

## Data Classes

### PlantItem
```python
name: str           # Cleaned plant name
quantity: int       # Number of plants
unit_price: float   # Price per unit
raw_name: str       # Original text from PDF
```

### Invoice
```python
number: str         # Invoice number
date: str          # Invoice date (DD.MM.YYYY)
customer: str      # Customer name
plants: List[PlantItem]
source_file: str   # PDF filename
source_page: int   # Page number in PDF
```

## PDF Parsing Logic

The parser uses `pdfplumber` to:
1. Extract text and tables from each page
2. Find invoice number with regex: `Faktura č. (\d+)`
3. Extract customer from first table
4. Parse items from second table (name, quantity, price)
5. Clean plant names (remove dimensions like "40x50 cm")
6. Filter non-plants: shipping, fees, postal services, etc.

## Testing

Test the parser with sample invoice:
```bash
cd /sessions/zealous-pensive-ramanujan/mnt/Tool_pasy

python3 -c "
from pdf_parser import PDFParser
parser = PDFParser()
invoices = parser.parse_files(['/path/to/invoice.pdf'])
for inv in invoices:
    print(f'Invoice {inv.number}: {len(inv.plants)} plants')
    for plant in inv.plants:
        print(f'  - {plant.name} ({plant.quantity}x)')
"
```

## Test Results

Parsing `faktury 6.3. 2026.pdf`:
- 35 invoices extracted
- 200 plants total
- Sample invoices:
  - Invoice 527 (Daniel Kadlec): 4 plants
  - Invoice 543 (Luci Kuzilkova): 3 plants
  - Invoice 547 (Adéla Schneiderová): 2 plants

## Configuration

Edit `app.py` to modify:
- Port: `app.run(debug=True, port=5001)`
- Max upload size: `app.config['MAX_CONTENT_LENGTH']`
- Temporary upload directory: `UPLOAD_TMP`

## Notes

- Language: Czech (Čeština)
- Theme: Green (#2a5f2a primary color)
- Responsive design works on mobile/tablet
- All files are UTF-8 encoded
- No external dependencies for UI (vanilla JS/CSS)

## Files Overview

| File | Purpose | Lines |
|------|---------|-------|
| `pdf_parser.py` | Core parsing logic | 180 |
| `app.py` | Flask server & API | 45 |
| `templates/index.html` | Main UI template | 120 |
| `static/style.css` | Complete styling | 280 |
| `static/app.js` | Frontend logic | 130 |

---

Generated: 2026-03-07
