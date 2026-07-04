# Krok 2 - Přiřazení kódů vysledovatelnosti

## Přehled

Step 2 přidává funkčnost pro **fuzzy párování jmen rostlin** z faktur s kódy ze šarže Excel souboru.

## Nové soubory

### 1. plant_matcher.py
Jádro párování - třída `PlantMatcher`

**Klíčové metody:**
- `_load_sarze(path)` - Načte Excel soubor se šarží (název, kód, země)
- `_clean(name)` - Normalizuje názvy (lowercase, whitespace, odstranění velikostí)
- `match_plant(plant_name)` - Páruje jednu rostlinu
  - Vrátí `match_type`: 'exact', 'fuzzy', nebo 'none'
  - Vrátí `confidence` (0-100%)
  - Vrátí `sarze_name`, `code`, `country`

**Algoritmus párování:**
1. **Přesná shoda** - po normalizaci
2. **Fuzzy shoda** - token_sort_ratio >= 65%
3. **Nenalezeno** - vrátí prázdný kód

### 2. Aktualizace app.py

Nový endpoint:
```
POST /api/match
```
- Spáruje všechny rostliny ze všech nahraných faktur
- Vrátí seznam faktur s obohacenými rostlinami
- Vrátí statistiky: počty přesných, fuzzy a nenalezených shod

Inicializace při startu:
```python
matcher = PlantMatcher(str(SARZE_PATH))
```

### 3. Aktualizace templates/index.html

Nový formulář (Section 2):
- "Krok 2 — Přiřazení kódů vysledovatelnosti"
- Výpis všech faktur v tabulkovém formátu
- Pro každou rostlinu: název, ks, stav párování, kód
- Možnost ručně editovat nebo přijmout/odmítnout fuzzy návrhy

Navigace (steps):
```
1 → 2 → 3 → 4
```

### 4. Aktualizace static/style.css

Nové CSS třídy:
- `.invoice-block` - stylizace bloku faktury
- `.match-table` - tabulka párování
- `.badge-exact`, `.badge-fuzzy`, `.badge-none` - stavové indikátory
- `.code-input` - textové pole pro kód (normální + .missing varianta)
- `.spinner`, `@keyframes spin` - loading animace
- `.fuzzy-suggestion` - zobrazení návrhů fuzzy shod

### 5. Aktualizace static/app.js

**Nové funkce:**
- `loadMatching()` - Zavolá `/api/match` a načte výsledky
- `renderMatchResults(data)` - Vykresí faktury a tabulky v HTML
- `matchBadge(type, confidence)` - Vrátí HTML badge (✓/~/✗)
- `acceptFuzzy(btn, sarzeName, code)` - Přijmout fuzzy návrh
- `rejectFuzzy(btn)` - Odmítnout fuzzy návrh
- `onCodeChange(input)` - Handler pro ruční editaci kódu
- `checkStep2Ready()` - Kontrola, zda je všechno vyplněno

**Event listenery:**
- `btnToStep2.click` - Přechod do Step 2 + spuštění `loadMatching()`
- `btnBackTo1.click` - Zpět na Step 1

## Datové struktury

### Vstup: Invoice.plants
```json
[
  { "name": "Cephalotaxus fortunei", "quantity": "5 ks" },
  { "name": "Amelanchier lamarckii", "quantity": "10 ks" }
]
```

### Výstup: /api/match
```json
{
  "invoices": [
    {
      "number": "2025-001",
      "date": "2025-03-07",
      "customer": "Zahrada s.r.o.",
      "plants": [
        {
          "name": "Cephalotaxus fortunei",
          "quantity": "5 ks",
          "match_type": "exact",
          "confidence": 100,
          "sarze_name": "Cephalotaxus fortunei",
          "code": "25-Ro290",
          "country": "CZ"
        }
      ]
    }
  ],
  "stats": {
    "exact": 42,
    "fuzzy": 5,
    "none": 2
  },
  "sarze_names": [...]
}
```

## Uživatelské interakce

### Step 2 Flow:
1. Klikni "Přiřadit kódy →"
2. Systém načte faktury a páruje rostliny (loading spinner)
3. Zobrazí tabulku s výsledky:
   - ✓ Přesná shoda - automaticky vyplněno
   - ~ Návrh (X%) - fuzzy shoda s tlačítky přijmout/odmítnout
   - ✗ Nenalezeno - prázdné pole pro ruční zadání
4. Edituj dle potřeby
5. Když jsou všechny kódy vyplněné → tlačítko "Generovat pasy" se aktivuje

## Konfigurace

V `plant_matcher.py`:
```python
EXACT_THRESHOLD = 95    # % shoda pro "přesné" párování
FUZZY_THRESHOLD = 65    # minimální % pro návrh fuzzy
```

V `app.py`:
```python
SARZE_PATH = Path(__file__).parent / 'data' / 'sarze.xlsx'
```

## Testování

```bash
cd /sessions/zealous-pensive-ramanujan/mnt/Tool_pasy
python3 -c "
from plant_matcher import PlantMatcher
m = PlantMatcher('data/sarze.xlsx')
r = m.match_plant('Cephalotaxus fortunei')
print(f'Výsledek: {r}')
"
```

## To-do pro další kroky

- Step 3: Generování PDF pasů
- Step 4: Integrace s Google Drive
- Možnost exportu párování do CSV
- Validace vstupních dat
