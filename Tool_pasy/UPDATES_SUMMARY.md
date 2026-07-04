# Plant Matching Logic Updates — Summary

**Date:** 2026-03-07

## Overview
Enhanced plant matching system to handle complex naming patterns (Czech name - Latin name) and support manual search/override workflow.

---

## 1. plant_matcher.py — Enhanced Matching Logic

### Key Changes:
- **Split-name handling:** When matching "Jerlín japonský - Sophora japonica", the system now:
  1. Tries matching the full name
  2. If no exact match, tries each part separated by " - " or " – "
  
- **ŠARŽE name as passport_name:** The system now ALWAYS returns the name from ŠARŽE (`passport_name`), never the invoice name. This ensures passport data always reflects the official plant database.

- **Improved cleaning:** The `_clean()` method strips:
  - Whitespace normalization
  - Size indicators (e.g., "50/80 cm", "40/60 cm")
  
- **Candidates builder:** `_build_candidates()` creates a list of all possible search terms from a single invoice name.

### Test Results (Invoice 527):
```
✓ [exact] Orixa japonská - Orixa japonica
         → PAS: Orixa japonica          KÓD: 25-Ro883

✓ [exact] Jerlín japonský - Sophora japonica
         → PAS: Sophora japonica        KÓD: 25-Ro1326

✓ [exact] Pouštní lebeda - Atriplex canescens
         → PAS: Atriplex canescens      KÓD: 25-Ro138

~ [fuzzy] Albizia julibrissin "Ombrella" - kapinice...
         → PAS: Albizia julibrissin     KÓD: 25-Ro68 (confidence: 74%)
```

---

## 2. app.py — New /api/search-plant Endpoint

### Changes:
- **POST /api/search-plant** — Manual plant search endpoint
  - Input: `{ "query": "user entered name" }`
  - Output: Same match result as `match_plant()` but called explicitly by user
  - Used when initial matching fails and user wants to manually search

### Endpoint Response:
```json
{
  "match_type": "exact|fuzzy|none",
  "confidence": 0-100,
  "passport_name": "Orixa japonica",
  "sarze_name": "Orixa japonica",
  "code": "25-Ro883",
  "country": "CZ"
}
```

---

## 3. app.js — Manual Search UI & Workflow

### Key Features:

#### For plants NOT found (match_type='none'):
1. **Manual search input** appears with:
   - Prefilled with invoice name (as suggestion)
   - Placeholder: "Zadej název ze šarže…"
   - "Hledat" button triggers `/api/search-plant`

2. **Search workflow:**
   ```
   User types name → Clicks "Hledat" 
   → API searches  
   → If found: Show "✓ Nalezeno (confidence%): NAME — CODE" + "Použít" button
   → If not found: Show "✗ Nenalezeno v šarži. Zkus jiný název."
   ```

3. **Accept manual result:**
   - Updates row with new passport_name and code
   - Changes status to "✓ Doplněno ručně"
   - Re-enables Step 3 button if all codes now filled

#### For fuzzy matches (match_type='fuzzy'):
- Shows suggestion with confidence percentage
- Two options:
  - "✓ Potvrdit" — Accept the fuzzy match
  - "✗ Zadat jiný" — Switch to manual search instead

#### For exact matches (match_type='exact'):
- Green "✓ Přesná shoda" badge
- No intervention needed

### Helper Functions:
- `doManualSearch(invNum, idx)` — Calls /api/search-plant and renders result
- `acceptManual()` — Updates row with found plant
- `acceptFuzzy()` — Accepts fuzzy suggestion
- `rejectFuzzy()` — Switches fuzzy to manual search
- `checkStep2Ready()` — Enables Step 3 only when all codes filled
- `updateInvoiceHeaderBadge()` — Shows count of remaining unfilled codes

---

## 4. style.css — Visual Styling

### New Styles Added:

#### Passport name display:
```css
.passport-name {
  font-style: italic;
  color: #1e4a1e;  /* Forest green */
  font-size: 13px;
}
```

#### Tracking codes:
```css
.code-display {
  font-family: monospace;
  font-size: 13px;
  color: #1e4a1e;
  font-weight: 600;
}
.missing-code { color: #ccc; }      /* Unfilled codes */
.fuzzy-code { color: #7a5800; }     /* Fuzzy match codes */
```

#### Manual search input/button:
```css
.manual-input {
  border: 1px solid #e07070;  /* Light red border */
  background: #fff5f5;         /* Light red background */
}

.manual-input:focus {
  border-color: #2a5f2a;  /* Forest green on focus */
  background: white;
}

.btn-search {
  background: #2a5f2a;  /* Forest green */
  color: white;
  border-radius: 6px;
  padding: 6px 12px;
}
```

#### Search result feedback:
```css
.sr-found {
  background: #f0f7f0;         /* Very light green */
  border: 1px solid #b0d4b0;   /* Light green border */
}

.btn-accept-found {
  background: #2a5f2a;
  font-size: 12px;
}
```

#### Fuzzy match buttons:
```css
.btn-fuzzy-accept { color: #2a7a2a; }  /* Green */
.btn-fuzzy-reject { color: #c0392b; }  /* Red */
```

---

## File Locations:
- `/sessions/zealous-pensive-ramanujan/mnt/Tool_pasy/plant_matcher.py` (6.5 KB)
- `/sessions/zealous-pensive-ramanujan/mnt/Tool_pasy/app.py` (3.0 KB)
- `/sessions/zealous-pensive-ramanujan/mnt/Tool_pasy/static/app.js` (16 KB)
- `/sessions/zealous-pensive-ramanujan/mnt/Tool_pasy/static/style.css` (13 KB)

---

## Testing:
All changes tested with invoice 527. The matching logic correctly:
1. Splits "Czech - Latin" names and tries each part
2. Returns ŠARŽE names (not invoice names) as passport_name
3. Handles size indicators and special characters
4. Provides fuzzy matching with confidence scores
5. Falls back to manual search when no match found

---

## Backward Compatibility:
✓ Existing exact/fuzzy match endpoints remain unchanged
✓ New /api/search-plant endpoint is additive (no breaking changes)
✓ Frontend gracefully handles all three match types
