# Step 2 Code Snippets Reference

## Backend (Python)

### plant_matcher.py - Import and Usage

```python
from plant_matcher import PlantMatcher

# Initialize at app startup
matcher = PlantMatcher('data/sarze.xlsx')
print(f"Loaded {len(matcher.entries)} plants")

# Match single plant
result = matcher.match_plant("Cephalotaxus fortunei")
# Returns: {
#   'match_type': 'exact',
#   'confidence': 100,
#   'sarze_name': 'Cephalotaxus fortunei',
#   'code': '25-Ro290',
#   'country': 'CZ'
# }

# Match batch of plants from invoice
plants = [
    {'name': 'Cephalotaxus fortunei', 'quantity': '5 ks'},
    {'name': 'Amelanchier lamarckii', 'quantity': '10 ks'}
]
matched = matcher.match_invoice_plants(plants)
```

### app.py - New Endpoint

```python
@app.route('/api/match', methods=['POST'])
def match_plants():
    """Spáruje rostliny ze všech faktur s kódy ze šarže"""
    global _session_invoices

    if not _session_invoices:
        return jsonify({'error': 'Nejdřív nahraj faktury'}), 400

    result = []
    stats = {'exact': 0, 'fuzzy': 0, 'none': 0}

    for inv in _session_invoices:
        plants_raw = [p.to_dict() for p in inv.plants]
        matched_plants = matcher.match_invoice_plants(plants_raw)

        for p in matched_plants:
            stats[p['match_type']] += 1

        result.append({
            'number': inv.number,
            'date': inv.date,
            'customer': inv.customer,
            'source_file': inv.source_file,
            'plants': matched_plants
        })

    return jsonify({
        'invoices': result,
        'stats': stats,
        'sarze_names': matcher.get_all_sarze_names()
    })
```

## Frontend (JavaScript)

### Step 2 UI Initialization

```javascript
// Get DOM elements
const sectionMatch  = document.getElementById('section-match');
const matchLoading  = document.getElementById('match-loading');
const matchInvoices = document.getElementById('match-invoices');
const btnToStep2    = document.getElementById('btn-to-step2');
const btnBackTo1    = document.getElementById('btn-back-to-1');

// Listen for Step 2 button
btnToStep2.addEventListener('click', () => {
  sectionMatch.classList.remove('hidden');
  sectionMatch.scrollIntoView({ behavior: 'smooth' });
  loadMatching();
});
```

### Load Matching Results

```javascript
async function loadMatching() {
  matchLoading.style.display = 'flex';
  matchInvoices.classList.add('hidden');

  try {
    const res = await fetch('/api/match', { method: 'POST' });
    if (!res.ok) throw new Error('Error matching plants');
    const data = await res.json();

    matchLoading.style.display = 'none';
    renderMatchResults(data);

  } catch (err) {
    matchLoading.style.display = 'none';
    alert(`Error: ${err.message}`);
  }
}
```

### Render Match Results

```javascript
function renderMatchResults(data) {
  // Update statistics
  statExact.textContent = `${data.stats.exact} exact`;
  statFuzzy.textContent = `${data.stats.fuzzy} suggestions`;
  statNone.textContent = `${data.stats.none} not found`;
  matchStats.classList.remove('hidden');

  // Render invoices
  matchInvoices.innerHTML = '';

  data.invoices.forEach(inv => {
    const block = document.createElement('div');
    block.className = 'invoice-block';

    // Count unmatched plants
    const noneCount = inv.plants.filter(p => p.match_type === 'none').length;
    const statusBadge = noneCount > 0
      ? `<span class="badge badge-none">⚠ ${noneCount} not found</span>`
      : `<span class="badge badge-exact">✓ OK</span>`;

    block.innerHTML = `
      <div class="invoice-block-header">
        <div>
          <span class="invoice-block-title">Invoice ${inv.number}</span>
          <span class="invoice-block-meta"> · ${inv.customer} · ${inv.date}</span>
        </div>
        ${statusBadge}
      </div>
      <table class="match-table">
        <thead>
          <tr>
            <th>Plant Name</th>
            <th>Qty</th>
            <th>Status</th>
            <th>Sarze Name</th>
            <th>Code</th>
          </tr>
        </thead>
        <tbody id="tbody-${inv.number}"></tbody>
      </table>
    `;
    matchInvoices.appendChild(block);

    // Add plant rows
    const tbody = document.getElementById(`tbody-${inv.number}`);
    inv.plants.forEach(plant => {
      const tr = document.createElement('tr');
      
      const badge = matchBadge(plant.match_type, plant.confidence);
      const codeClass = plant.match_type === 'none' ? 'code-input missing' : 'code-input';

      tr.innerHTML = `
        <td>${plant.name}</td>
        <td>${plant.quantity}</td>
        <td>${badge}</td>
        <td>${plant.sarze_name || '—'}</td>
        <td>
          <input class="${codeClass}"
                 type="text"
                 value="${plant.code || ''}"
                 onchange="onCodeChange(this)" />
        </td>
      `;
      tbody.appendChild(tr);
    });
  });

  matchInvoices.classList.remove('hidden');
  checkStep2Ready();
}
```

### Match Badge Helper

```javascript
function matchBadge(type, confidence) {
  if (type === 'exact') 
    return `<span class="badge badge-exact">✓ Exact</span>`;
  if (type === 'fuzzy') 
    return `<span class="badge badge-fuzzy">~ Suggestion (${confidence}%)</span>`;
  return `<span class="badge badge-none">✗ Not found</span>`;
}
```

### Handle Fuzzy Suggestions

```javascript
function acceptFuzzy(btn, sarzeName, code) {
  const td = btn.closest('td');
  const input = td.querySelector('.code-input');
  const row = btn.closest('tr');

  input.value = code;
  input.classList.remove('missing');
  
  // Update sarze name cell
  const sarzeCell = row.querySelector('.sarze-name-cell');
  sarzeCell.textContent = sarzeName;

  // Update badge
  const badgeTd = row.cells[2];
  badgeTd.innerHTML = `<span class="badge badge-exact">✓ Accepted</span>`;

  // Remove suggestion
  td.querySelector('.fuzzy-suggestion')?.remove();

  checkStep2Ready();
}

function rejectFuzzy(btn) {
  const td = btn.closest('td');
  const input = td.querySelector('.code-input');
  
  input.value = '';
  input.classList.add('missing');
  
  const row = btn.closest('tr');
  const badgeTd = row.cells[2];
  badgeTd.innerHTML = `<span class="badge badge-none">✗ Not found</span>`;

  td.querySelector('.fuzzy-suggestion')?.remove();

  checkStep2Ready();
}
```

### Handle Manual Code Changes

```javascript
function onCodeChange(input) {
  if (input.value.trim()) {
    input.classList.remove('missing');
    const row = input.closest('tr');
    const badgeTd = row.cells[2];
    if (badgeTd.querySelector('.badge-none')) {
      badgeTd.innerHTML = `<span class="badge badge-exact">✓ Manual</span>`;
    }
  } else {
    input.classList.add('missing');
  }
  checkStep2Ready();
}

function checkStep2Ready() {
  const missing = document.querySelectorAll('.code-input.missing');
  btnToStep3.disabled = missing.length > 0;
}
```

## Frontend (HTML)

### Invoice Block Structure

```html
<div class="invoice-block">
  <div class="invoice-block-header">
    <div>
      <span class="invoice-block-title">Invoice INV-2025-001</span>
      <span class="invoice-block-meta"> · Customer Name · 2025-03-07</span>
    </div>
    <span class="badge badge-exact">✓ OK</span>
  </div>
  
  <table class="match-table">
    <thead>
      <tr>
        <th>Plant Name</th>
        <th>Qty</th>
        <th>Status</th>
        <th>Sarze Name</th>
        <th>Code</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td>Cephalotaxus fortunei</td>
        <td>5 ks</td>
        <td><span class="badge badge-exact">✓ Exact</span></td>
        <td>Cephalotaxus fortunei</td>
        <td><input class="code-input" type="text" value="25-Ro290" /></td>
      </tr>
    </tbody>
  </table>
</div>
```

### Loading Spinner

```html
<div id="match-loading" class="loading-state">
  <div class="spinner"></div>
  <span>Matching plants...</span>
</div>
```

## Frontend (CSS)

### Invoice Block Styling

```css
.invoice-block {
  border: 1px solid #e0e8e0;
  border-radius: 10px;
  margin-bottom: 16px;
  overflow: hidden;
}

.invoice-block-header {
  background: #f0f7f0;
  padding: 10px 16px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.invoice-block-title {
  font-weight: 700;
  font-size: 14px;
  color: #1e4a1e;
}
```

### Match Table Styling

```css
.match-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

.match-table th {
  background: #f8fbf8;
  color: #2a5f2a;
  font-weight: 700;
  padding: 8px 12px;
  text-align: left;
  border-bottom: 1px solid #e0e8e0;
}

.match-table td {
  padding: 9px 12px;
  border-bottom: 1px solid #f4f4f4;
  vertical-align: middle;
}
```

### Badge Styling

```css
.badge {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 10px;
  font-size: 11px;
  font-weight: 600;
}

.badge-exact { background: #e0f4e0; color: #1e6a1e; }
.badge-fuzzy { background: #fff3cd; color: #7a5800; }
.badge-none  { background: #fde8e8; color: #8b1a1a; }
```

### Code Input Styling

```css
.code-input {
  border: 1px solid #cce0cc;
  border-radius: 6px;
  padding: 5px 10px;
  font-size: 13px;
  width: 130px;
  font-family: monospace;
  color: #1e4a1e;
  background: #f9fbf9;
}

.code-input:focus {
  outline: none;
  border-color: #2a5f2a;
  background: white;
}

.code-input.missing {
  border-color: #e07070;
  background: #fff5f5;
}
```

### Loading Spinner

```css
.spinner {
  width: 22px;
  height: 22px;
  border: 3px solid #d0e8d0;
  border-top-color: #2a5f2a;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
```

## Configuration

### Matching Thresholds (plant_matcher.py)

```python
class PlantMatcher:
    EXACT_THRESHOLD = 95    # Score for "exact" match (currently unused)
    FUZZY_THRESHOLD = 65    # Minimum score for fuzzy suggestion
```

Adjust these values based on your accuracy requirements:
- Higher FUZZY_THRESHOLD = stricter matching (fewer suggestions)
- Lower FUZZY_THRESHOLD = looser matching (more suggestions)

## Testing

### Python Test

```python
from plant_matcher import PlantMatcher

matcher = PlantMatcher('data/sarze.xlsx')

test_cases = [
    "Cephalotaxus fortunei",        # exact
    "cephalotaxus fortunei",        # exact (case)
    "Cephalotaxus fortunei 60cm",   # exact (size)
    "Cephalotaxus fortuneii",       # fuzzy
    "Unknown Plant",                # none
]

for plant in test_cases:
    result = matcher.match_plant(plant)
    print(f"{result['match_type']:6s} {result['confidence']:3d}% - {result['code']}")
```

### API Test with curl

```bash
curl -X POST http://localhost:5001/api/match \
  -H "Content-Type: application/json" \
  -d '{}'
```

Expected response:
```json
{
  "invoices": [...],
  "stats": {
    "exact": 42,
    "fuzzy": 5,
    "none": 2
  },
  "sarze_names": [...]
}
```

