# Code Changes Reference Guide

## 1. plant_matcher.py Changes

### Key Methods:

#### `_build_candidates(invoice_name)` — NEW LOGIC
Splits names by " - " or " – " to create multiple search candidates:

```python
def _build_candidates(self, invoice_name: str) -> List[str]:
    # Input:  "Orixa japonská - Orixa japonica"
    # Output: ["orixa japonská - orixa japonica", 
    #          "orixa japonská", 
    #          "orixa japonica"]
```

#### `_try_match(clean_query)` — PRIORITY ORDER
1. Try exact match against all entries
2. If none, try fuzzy match with token_sort_ratio scorer
3. If confidence >= 65%, return fuzzy result
4. Otherwise, return 'none'

#### `_clean(name)` — IMPROVED
- Normalizes whitespace
- Strips size indicators: "50/80 cm", "40/60 cm"
- Converts to lowercase
- Example: "Sophora japonica 40/60 cm" → "sophora japonica"

#### Return Value — ALWAYS passport_name
```python
{
    'match_type':    'exact'|'fuzzy'|'none',
    'confidence':    0-100,
    'passport_name': entry['name'],      # NAME FROM ŠARŽE
    'sarze_name':    entry['name'],      # SAME AS passport_name
    'code':          entry['code'],
    'country':       entry['country'],
}
```

---

## 2. app.py Changes

### New Endpoint:

```python
@app.route('/api/search-plant', methods=['POST'])
def search_plant():
    """Manual search triggered by user in UI"""
    data = request.get_json()
    query = (data or {}).get('query', '').strip()
    if not query:
        return jsonify({'error': 'Prázdný dotaz'}), 400
    
    result = matcher.search_by_name(query)
    return jsonify(result)
```

### Usage Flow:
1. User enters name in manual search input
2. Clicks "Hledat" button
3. Frontend calls `POST /api/search-plant` with `{"query": "Orixa japonica"}`
4. Backend returns matching result
5. Frontend updates row with plant data

---

## 3. app.js Changes

### Manual Search Functions:

#### `buildManualSearch(invNum, idx, prefill)`
Generates HTML for manual search UI when plant not found:
```html
<div class="manual-search">
  <input type="text" class="manual-input" placeholder="Zadej název ze šarže…" />
  <button class="btn-search" onclick="doManualSearch(...)">Hledat</button>
  <div class="search-result"></div>
</div>
```

#### `doManualSearch(invNum, idx)`
- Gets input value
- Calls `POST /api/search-plant`
- Shows loading state: "Hledám…"
- On success: Shows result with "Použít" button
- On failure: Shows "✗ Nenalezeno v šarži. Zkus jiný název."

#### `acceptManual(invNum, idx, passportName, code, country)`
- Updates row cells with new passport_name and code
- Changes status badge to "✓ Doplněno ručně"
- Re-checks if Step 3 can be enabled

#### `acceptFuzzy(invNum, idx)` & `rejectFuzzy(...)`
- Accept: Confirm fuzzy match, hide suggestion buttons
- Reject: Switch to manual search input instead

#### `checkStep2Ready()`
Checks if all `.code-value` inputs have values:
```javascript
const allCodes = document.querySelectorAll('.code-value');
btnToStep3.disabled = Array.from(allCodes).some(inp => !inp.value.trim());
```

#### `updateInvoiceHeaderBadge(invNum)`
Recalculates status badge:
- All codes filled: "✓ OK" (green)
- Some empty: "⚠ N nenalezeno" (red)

---

## 4. style.css Changes

### Color Scheme:
- Forest green: `#1e4a1e` (passport names, codes, buttons)
- Light red: `#e07070`, `#fff5f5` (unfound plants)
- Light green: `#f0f7f0`, `#b0d4b0` (found results)

### Key Classes:

| Class | Purpose | Color |
|-------|---------|-------|
| `.passport-name` | Plant name in passport | Italic green |
| `.code-display` | Tracking code | Monospace green |
| `.missing-code` | Unfilled code | Light gray |
| `.fuzzy-code` | Fuzzy match code | Brown |
| `.manual-input` | Manual search input | Light red background |
| `.btn-search` | Search button | Forest green |
| `.sr-found` | Search result box | Light green background |
| `.btn-accept-found` | Accept button | Forest green |

---

## Data Flow Diagram

```
User uploads PDF
         ↓
[/api/parse] → Extract plants from invoices
         ↓
[/api/match] → Auto-match with plant_matcher
         ↓
Render results:
  - Exact match (✓) → Show passport_name + code
  - Fuzzy match (~) → Show passport_name + code + buttons
  - Not found (✗) → Show manual search input
         ↓
User action on NOT FOUND:
  - Types name → Clicks "Hledat"
         ↓
[/api/search-plant] → Manual re-search
         ↓
  - Found → User clicks "Použít" → Update row
  - Not found → User retypes → Try again
         ↓
[Step 3] → Enabled only when all codes filled
```

---

## Testing Examples

### Test 1: Split name matching
```python
m.match_plant("Jerlín japonský - Sophora japonica")
# Returns: match_type='exact', passport_name='Sophora japonica'
```

### Test 2: Size stripping
```python
m.match_plant("Sophora japonica 40/60 cm")
# Cleans to "sophora japonica", finds exact match
```

### Test 3: Fuzzy matching
```python
m.match_plant("Albizia julibrissin")
# Returns: match_type='fuzzy', confidence=80+
```

### Test 4: Manual search
```
POST /api/search-plant
Body: {"query": "Orixa japonica"}
Response: {match_type='exact', passport_name='Orixa japonica', code='25-Ro883'}
```

---

## Integration Checklist

- [x] plant_matcher.py — Split-name logic + passport_name guarantee
- [x] app.py — POST /api/search-plant endpoint
- [x] app.js — Manual search UI + workflow
- [x] style.css — Visual styling for new elements
- [x] Testing on Invoice 527 — All 4 plants match correctly
- [x] Backward compatibility — No breaking changes

