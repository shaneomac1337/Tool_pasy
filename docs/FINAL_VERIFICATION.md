# Final Verification — All Updates Complete

## Files Updated

### 1. plant_matcher.py (6.5 KB)
Location: `/sessions/zealous-pensive-ramanujan/mnt/Tool_pasy/plant_matcher.py`

**Key code snippet — Split-name handling:**
```python
def _build_candidates(self, invoice_name: str) -> List[str]:
    """From "Orixa japonská - Orixa japonica" creates:
    ["orixa japonská - orixa japonica", "orixa japonská", "orixa japonica"]"""
    clean_full = self._clean(invoice_name)
    candidates = [clean_full]
    
    for sep in [' - ', ' – ', ' / ']:
        if sep in invoice_name:
            parts = invoice_name.split(sep)
            for part in parts:
                c = self._clean(part.strip())
                if c and c not in candidates:
                    candidates.append(c)
            break
    return candidates
```

**Key code snippet — Always return ŠARŽE name:**
```python
def match_plant(self, invoice_name: str) -> dict:
    """Returns dict with 'passport_name' = name from ŠARŽE (not from invoice)"""
    candidates = self._build_candidates(invoice_name)
    best = None
    
    for candidate in candidates:
        result = self._try_match(candidate)
        if result['match_type'] == 'exact':
            return result  # Exact match found
        if result['match_type'] == 'fuzzy':
            if best is None or result['confidence'] > best['confidence']:
                best = result
    
    return best or {
        'match_type': 'none',
        'confidence': 0,
        'passport_name': None,  # Returns ŠARŽE name (or None if not found)
        'sarze_name': None,
        'code': '',
        'country': 'CZ',
    }
```

---

### 2. app.py (3.0 KB)
Location: `/sessions/zealous-pensive-ramanujan/mnt/Tool_pasy/app.py`

**New endpoint — /api/search-plant:**
```python
@app.route('/api/search-plant', methods=['POST'])
def search_plant():
    """Ruční vyhledávání: uživatel zadá název, vrátí shodu ze šarže."""
    data  = request.get_json()
    query = (data or {}).get('query', '').strip()
    if not query:
        return jsonify({'error': 'Prázdný dotaz'}), 400

    result = matcher.search_by_name(query)
    return jsonify(result)
```

Example request/response:
```
POST /api/search-plant
Content-Type: application/json

{"query": "Orixa japonica"}

Response (200 OK):
{
  "match_type": "exact",
  "confidence": 100,
  "passport_name": "Orixa japonica",
  "sarze_name": "Orixa japonica",
  "code": "25-Ro883",
  "country": "CZ"
}
```

---

### 3. app.js (16 KB)
Location: `/sessions/zealous-pensive-ramanujan/mnt/Tool_pasy/static/app.js`

**Manual search UI generation:**
```javascript
function buildManualSearch(invNum, idx, prefill) {
  return `
    <div class="manual-search" id="msearch-${invNum}-${idx}">
      <input  type="text"
              class="manual-input"
              placeholder="Zadej název ze šarže…"
              value="${esc(prefill || '')}"
              id="minput-${invNum}-${idx}" />
      <button class="btn-search"
              onclick="doManualSearch('${invNum}', ${idx})">
        Hledat
      </button>
      <div class="search-result" id="sresult-${invNum}-${idx}"></div>
    </div>`;
}
```

**Manual search API call:**
```javascript
async function doManualSearch(invNum, idx) {
  const input   = document.getElementById(`minput-${invNum}-${idx}`);
  const resultEl = document.getElementById(`sresult-${invNum}-${idx}`);
  const query   = input.value.trim();
  if (!query) { resultEl.innerHTML = '<span class="srError">Zadej název.</span>'; return; }

  resultEl.innerHTML = '<span class="srLoading">Hledám…</span>';

  try {
    const res  = await fetch('/api/search-plant', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query })
    });
    const data = await res.json();

    if (data.match_type === 'none') {
      resultEl.innerHTML = `<span class="srError">✗ Nenalezeno v šarži. Zkus jiný název.</span>`;
    } else {
      const conf = data.match_type === 'exact' ? '' : ` (${data.confidence}%)`;
      resultEl.innerHTML = `
        <div class="sr-found">
          <span class="sr-name">✓ Nalezeno${conf}: <strong>${data.passport_name}</strong> — <code>${data.code}</code></span>
          <button class="btn-accept-found"
                  onclick="acceptManual('${invNum}', ${idx}, '${esc(data.passport_name)}', '${esc(data.code)}', '${esc(data.country)}')">
            Použít
          </button>
        </div>`;
    }
  } catch (e) {
    resultEl.innerHTML = `<span class="srError">Chyba: ${e.message}</span>`;
  }
}
```

**Accept manual result:**
```javascript
function acceptManual(invNum, idx, passportName, code, country) {
  const tr = document.getElementById(`row-${invNum}-${idx}`);
  if (!tr) return;

  // Update row with new data from ŠARŽE
  tr.cells[2].innerHTML = `<span class="badge badge-exact">✓ Doplněno ručně</span>`;
  tr.cells[3].innerHTML = `<span class="passport-name">${passportName}</span>`;
  tr.cells[4].innerHTML = `<span class="code-display">${code}</span>
                            <input type="hidden" class="code-value" value="${code}" />`;
  checkStep2Ready();
  updateInvoiceHeaderBadge(invNum);
}
```

---

### 4. style.css (13 KB)
Location: `/sessions/zealous-pensive-ramanujan/mnt/Tool_pasy/static/style.css`

**New CSS styles added:**
```css
/* Passport name — always in italics, forest green */
.passport-name {
  font-style: italic;
  color: #1e4a1e;
  font-size: 13px;
}

/* Tracking codes — monospace, bold green */
.code-display {
  font-family: monospace;
  font-size: 13px;
  color: #1e4a1e;
  font-weight: 600;
}
.fuzzy-code { color: #7a5800; }
.missing-code { color: #ccc; }

/* Manual search input — light red background */
.manual-input {
  border: 1px solid #e07070;
  border-radius: 6px;
  padding: 6px 10px;
  font-size: 13px;
  width: 100%;
  background: #fff5f5;
  color: #333;
}

.manual-input:focus {
  outline: none;
  border-color: #2a5f2a;
  background: white;
}

/* Search button — forest green */
.btn-search {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  background: #2a5f2a;
  color: white;
  border: none;
  border-radius: 6px;
  padding: 6px 12px;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  width: fit-content;
  transition: background .15s;
}
.btn-search:hover { background: #1e4a1e; }

/* Search result found — light green background */
.sr-found {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  background: #f0f7f0;
  border: 1px solid #b0d4b0;
  border-radius: 6px;
  padding: 6px 10px;
}

.btn-accept-found {
  background: #2a5f2a;
  color: white;
  border: none;
  border-radius: 5px;
  padding: 4px 10px;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
}
.btn-accept-found:hover { background: #1e4a1e; }
```

---

## Test Results — Invoice 527

All 4 plants matched correctly:

```
PASS 1 ✓ [exact] () Orixa japonská - Orixa japonica
       Passport: Orixa japonica    Code: 25-Ro883

PASS 2 ~ [fuzzy] () Albizia julibrissin "Ombrella" - kapinice
       Passport: Albizia julibrissin    Code: 25-Ro68    Confidence: 74%

PASS 3 ✓ [exact] () Jerlín japonský - Sophora japonica
       Passport: Sophora japonica    Code: 25-Ro1326

PASS 4 ✓ [exact] () Pouštní lebeda - Atriplex canescens
       Passport: Atriplex canescens    Code: 25-Ro138
```

---

## Features Implemented

### 1. Plant Matching Logic (plant_matcher.py)
- [x] Split "Czech - Latin" names by " - " separator
- [x] Try matching each part individually
- [x] Return ŠARŽE name (not invoice name) as passport_name
- [x] Strip size indicators (50/80 cm, etc.)
- [x] Normalize whitespace and case
- [x] Provide exact and fuzzy matching

### 2. Backend API (app.py)
- [x] Add POST /api/search-plant endpoint
- [x] Accept {"query": "plant name"} JSON
- [x] Return match result with passport_name + code
- [x] Handle empty query gracefully

### 3. Frontend UI (app.js)
- [x] Show manual search input for plants not found
- [x] Prefill with invoice name as suggestion
- [x] "Hledat" button to trigger API
- [x] Display search results with "Použít" button
- [x] Show error if plant not found in ŠARŽE
- [x] Update row with found plant data
- [x] Support fuzzy match accept/reject workflow
- [x] Re-check Step 3 enablement after update

### 4. Visual Styling (style.css)
- [x] Style passport name (italic, green)
- [x] Style tracking codes (monospace, green)
- [x] Style manual search input (red border, light red bg)
- [x] Style search button (green, hover effect)
- [x] Style search result box (light green, border)
- [x] Style accept button (green, hover effect)
- [x] Style fuzzy match buttons (green/red text)

---

## Backward Compatibility

All changes are backward compatible:
- Existing `/api/parse` unchanged
- Existing `/api/match` unchanged
- New `/api/search-plant` is additive only
- Frontend handles all three match types correctly
- No breaking changes to data structures

---

## Ready for Deployment

All files have been successfully updated and tested. The system is ready for:
1. User testing with real plant invoices
2. Integration with production database
3. Multi-language support if needed
4. Additional plant matching rules as discovered

