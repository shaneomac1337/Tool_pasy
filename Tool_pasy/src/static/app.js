// ── Elementy Krok 1 ────────────────────────────────────────
const dropZone       = document.getElementById('drop-zone');
const fileInput      = document.getElementById('file-input');
const fileListEl     = document.getElementById('file-list');
const progressWrap   = document.getElementById('progress-wrap');
const progressBar    = document.getElementById('progress-bar');
const progressText   = document.getElementById('progress-text');
const invoiceResults = document.getElementById('invoice-results');
const pillInvoices   = document.getElementById('pill-invoices');
const pillPlants     = document.getElementById('pill-plants');
const invoiceTbody   = document.getElementById('invoice-tbody');
const btnReset       = document.getElementById('btn-reset');
const btnToStep2     = document.getElementById('btn-to-step2');

// ── Elementy Krok 3 ────────────────────────────────────────
const sectionGenerate  = document.getElementById('section-generate');
const generateSummary  = document.getElementById('generate-summary');
const generateLoading  = document.getElementById('generate-loading');
const generateResult   = document.getElementById('generate-result');
const btnBackTo2       = document.getElementById('btn-back-to-2');
const btnGenerateExcel = document.getElementById('btn-generate-excel');
const btnGeneratePdf   = document.getElementById('btn-generate-pdf');
const btnUploadDrive   = document.getElementById('btn-upload-drive');

// ── Elementy Krok 2 ────────────────────────────────────────
const sectionMatch  = document.getElementById('section-match');
const matchLoading  = document.getElementById('match-loading');
const matchInvoices = document.getElementById('match-invoices');
const matchStats    = document.getElementById('match-stats');
const statExact     = document.getElementById('stat-exact');
const statFuzzy     = document.getElementById('stat-fuzzy');
const statNone      = document.getElementById('stat-none');
const btnBackTo1    = document.getElementById('btn-back-to-1');
const btnDedup      = document.getElementById('btn-dedup');
const btnAssignAll  = document.getElementById('btn-assign-all');
const btnToStep3    = document.getElementById('btn-to-step3');

let currentInvoices  = [];
let currentInvoiceMeta = {};   // číslo → { customer, date }

// ══════════════════════════════════════════════════════════
// KROK 1 — Upload PDF
// ══════════════════════════════════════════════════════════
dropZone.addEventListener('dragover', e => { e.preventDefault(); dropZone.classList.add('dragging'); });
dropZone.addEventListener('dragleave', () => dropZone.classList.remove('dragging'));
dropZone.addEventListener('drop', e => {
  e.preventDefault(); dropZone.classList.remove('dragging');
  const files = Array.from(e.dataTransfer.files).filter(f => f.name.toLowerCase().endsWith('.pdf'));
  if (files.length) handleFiles(files);
});
fileInput.addEventListener('change', () => {
  if (fileInput.files.length) handleFiles(Array.from(fileInput.files));
});

function handleFiles(files) {
  fileListEl.classList.remove('hidden');
  fileListEl.innerHTML = '';
  files.forEach(f => {
    const chip = document.createElement('div');
    chip.className = 'file-chip';
    chip.innerHTML = `📄 ${f.name}`;
    fileListEl.appendChild(chip);
  });
  uploadAndParse(files);
}

async function uploadAndParse(files) {
  progressWrap.classList.remove('hidden');
  invoiceResults.classList.add('hidden');
  setProgress(10, 'Nahrávám soubory…');

  const formData = new FormData();
  files.forEach(f => formData.append('files', f));

  try {
    setProgress(40, 'Zpracovávám faktury…');
    const res = await fetch('/api/parse', { method: 'POST', body: formData });
    setProgress(85, 'Načítám výsledky…');

    if (!res.ok) { const e = await res.json(); throw new Error(e.error || 'Chyba'); }

    const data = await res.json();
    currentInvoices = data.invoices;
    // Ulož metadata faktur (číslo → customer, date) pro Krok 3
    currentInvoiceMeta = {};
    data.invoices.forEach(inv => {
      currentInvoiceMeta[inv.number] = { customer: inv.customer, date: inv.date };
    });

    setProgress(100, `✓ Načteno ${data.total_invoices} faktur`);
    setTimeout(() => {
      progressWrap.classList.add('hidden');
      showInvoiceTable(data);
    }, 500);

  } catch (err) {
    progressWrap.classList.add('hidden');
    alert(`Chyba: ${err.message}`);
  }
}

function showInvoiceTable(data) {
  // Souhrn
  pillInvoices.textContent = `${data.total_invoices} faktur`;
  pillPlants.textContent   = `${data.total_plants} rostlin`;

  // Tabulka
  invoiceTbody.innerHTML = '';

  if (data.invoices.length === 0) {
    invoiceTbody.innerHTML = `<tr><td colspan="5" style="text-align:center;color:#c0392b;padding:20px">
      Žádné faktury nenalezeny. Zkontroluj nahrané soubory.
    </td></tr>`;
  } else {
    data.invoices.forEach(inv => {
      const tr = document.createElement('tr');
      const countOk    = inv.plant_count > 0;
      const countClass = countOk ? 'td-count' : 'td-count zero';
      const countText  = countOk ? `${inv.plant_count} ks` : '⚠ 0';
      const fileName   = inv.source_file.length > 22
        ? inv.source_file.substring(0, 20) + '…'
        : inv.source_file;

      tr.innerHTML = `
        <td class="td-num">Faktura ${inv.number}</td>
        <td class="td-customer">${inv.customer || '—'}</td>
        <td>${inv.date || '—'}</td>
        <td class="${countClass}">${countText}</td>
        <td class="td-file">${fileName}</td>`;
      invoiceTbody.appendChild(tr);
    });
  }

  invoiceResults.classList.remove('hidden');
}

function setProgress(pct, text) {
  progressBar.style.width = pct + '%';
  if (text) progressText.textContent = text;
}

btnReset.addEventListener('click', () => {
  currentInvoices = [];
  fileListEl.innerHTML = ''; fileListEl.classList.add('hidden');
  invoiceResults.classList.add('hidden');
  progressWrap.classList.add('hidden');
  fileInput.value = '';
  sectionMatch.classList.add('hidden');
  setNavStep(1);
});

// ══════════════════════════════════════════════════════════
// KROK 2 — Párování rostlin
// ══════════════════════════════════════════════════════════
btnToStep2.addEventListener('click', () => {
  sectionMatch.classList.remove('hidden');
  sectionMatch.scrollIntoView({ behavior: 'smooth' });
  setNavStep(2);
  loadMatching();
});

btnBackTo1.addEventListener('click', () => {
  sectionMatch.classList.add('hidden');
  setNavStep(1);
});

async function loadMatching() {
  matchLoading.style.display = 'flex';
  matchInvoices.classList.add('hidden');
  matchStats.classList.add('hidden');
  btnToStep3.disabled = true;
  try {
    const res = await fetch('/api/match', { method: 'POST' });
    if (!res.ok) throw new Error('Chyba při párování');
    const data = await res.json();
    matchLoading.style.display = 'none';
    renderMatchResults(data);
  } catch (err) {
    matchLoading.style.display = 'none';
    alert(`Chyba: ${err.message}`);
  }
}

function renderMatchResults(data) {
  const s = data.stats;
  statExact.textContent = `${s.exact} přesných`;
  statFuzzy.textContent = `${s.fuzzy} návrhů`;
  statNone.textContent  = `${s.none} nenalezeno`;
  matchStats.classList.remove('hidden');

  matchInvoices.innerHTML = '';

  data.invoices.forEach(inv => {
    const block = document.createElement('div');
    block.className = 'invoice-block';

    const noneCount = inv.plants.filter(p => p.match_type === 'none').length;
    const statusBadge = noneCount > 0
      ? `<span class="badge badge-none">⚠ ${noneCount} nenalezeno</span>`
      : `<span class="badge badge-exact">✓ OK</span>`;

    block.innerHTML = `
      <div class="invoice-block-header">
        <div>
          <span class="invoice-block-title">Faktura ${inv.number}</span>
          <span class="invoice-block-meta"> · ${inv.customer || '—'} · ${inv.date || '—'}</span>
        </div>
        ${statusBadge}
      </div>
      <table class="match-table">
        <thead>
          <tr>
            <th>Název z faktury</th>
            <th>Ks</th>
            <th>Stav</th>
            <th>Název v pasu (ze šarže)</th>
            <th>Kód vysledovatelnosti</th>
          </tr>
        </thead>
        <tbody id="tbody-${inv.number}"></tbody>
      </table>`;
    matchInvoices.appendChild(block);

    const tbody = document.getElementById(`tbody-${inv.number}`);
    inv.plants.forEach((plant, idx) => {
      tbody.appendChild(renderPlantRow(inv.number, idx, plant));
    });
  });

  matchInvoices.classList.remove('hidden');
  checkStep2Ready();
}

function renderPlantRow(invNum, idx, plant) {
  const tr = document.createElement('tr');
  tr.id = `row-${invNum}-${idx}`;
  tr.dataset.invoiceName = plant.invoice_name;  // pro globální propagaci

  const passportName = plant.passport_name || plant.sarze_name || '';
  const code         = plant.code || '';

  let statusCell = '', passportCell = '', codeCell = '';

  if (plant.match_type === 'exact') {
    statusCell   = `<span class="badge badge-exact">✓ Přesná shoda</span>`;
    passportCell = `<span class="passport-name">${passportName}</span>`;
    codeCell     = `<span class="code-display">${code}</span>
                    <input type="hidden" class="code-value" value="${code}" />`;

  } else if (plant.match_type === 'fuzzy') {
    const cands = plant.candidates || [];
    statusCell   = `<span class="badge badge-fuzzy">~ Návrh (${plant.confidence}%)</span>`;
    passportCell = `<span class="passport-name">${passportName}</span>
                    <div class="fuzzy-suggestion">
                      <span class="reason">${plant.reason || 'Zkontroluj název v pasu'}</span>
                      <button class="btn-fuzzy-accept" onclick="acceptFuzzy('${invNum}',${idx})">✓ Potvrdit</button>
                      <button class="btn-fuzzy-reject" onclick="rejectFuzzy('${invNum}',${idx},'${esc(plant.invoice_name)}')">✗ Zadat jiný</button>
                    </div>
                    ${renderCandidateList(invNum, idx, cands)}`;
    codeCell     = `<span class="code-display fuzzy-code">${code}</span>
                    <input type="hidden" class="code-value" value="${code}" />`;

  } else {
    statusCell   = `<span class="badge badge-none">✗ Nenalezeno</span>`;
    passportCell = buildManualSearch(invNum, idx, plant.invoice_name);
    codeCell     = `<span class="code-display missing-code">—</span>
                    <input type="hidden" class="code-value" value="" data-missing="true" />`;
  }

  tr.innerHTML = `
    <td class="td-invoice-name">${plant.invoice_name}</td>
    <td>${plant.quantity}</td>
    <td>${statusCell}</td>
    <td class="td-passport-name">${passportCell}</td>
    <td class="td-code">${codeCell}</td>`;
  return tr;
}

function buildManualSearch(invNum, idx, prefill) {
  return `
    <div class="manual-search" id="msearch-${invNum}-${idx}">
      <input type="text" class="manual-input"
             placeholder="Zadej název ze šarže…"
             value="${esc(prefill || '')}"
             id="minput-${invNum}-${idx}" />
      <button class="btn-search" onclick="doManualSearch('${invNum}',${idx})">🔍 Hledat</button>
      <div class="search-result" id="sresult-${invNum}-${idx}"></div>
    </div>`;
}

const LEVEL_LABEL = { exact: 'přesná', species: 'druh', genus: 'rod', fuzzy: 'fuzzy' };
function levelLabel(l) { return LEVEL_LABEL[l] || l || ''; }

/** Seznam kandidátů k výběru (pro návrhy i ruční hledání). */
function renderCandidateList(invNum, idx, cands) {
  if (!cands || cands.length <= 1) return '';
  const items = cands.map(c => `
    <li class="cand">
      <button class="btn-cand"
              onclick="acceptCandidate('${invNum}',${idx},'${esc(c.passport_name)}','${esc(c.code)}','${esc(c.country)}')">Použít</button>
      <span class="cand-name">${c.passport_name}</span>
      <code class="cand-code">${c.code}</code>
      <span class="cand-meta">${c.confidence}% ${levelLabel(c.level)}</span>
    </li>`).join('');
  return `<ul class="cand-list">${items}</ul>`;
}

/** Uživatel vybral jednoho kandidáta ze seznamu. */
function acceptCandidate(invNum, idx, passportName, code, country) {
  const tr = document.getElementById(`row-${invNum}-${idx}`);
  if (!tr) return;
  applyAccepted(tr, passportName, code, 'Vybráno');
  const propagated = propagateToMatchingRows(tr, passportName, code, 'Vybráno');
  if (propagated > 0) showPropagationNotice(tr, propagated);
  checkStep2Ready();
  updateInvoiceHeaderBadge(invNum);
}

async function doManualSearch(invNum, idx) {
  const input    = document.getElementById(`minput-${invNum}-${idx}`);
  const resultEl = document.getElementById(`sresult-${invNum}-${idx}`);
  const query    = input.value.trim();
  if (!query) { resultEl.innerHTML = '<span class="srError">Zadej název.</span>'; return; }

  resultEl.innerHTML = '<span class="srLoading">Hledám…</span>';
  try {
    const res  = await fetch('/api/search-plant', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query })
    });
    const data = await res.json();

    const cands = data.candidates || [];
    if (data.match_type === 'none' || cands.length === 0) {
      resultEl.innerHTML = `<span class="srError">✗ Nenalezeno. Zkus jiný název.</span>`;
    } else {
      resultEl.innerHTML = cands.map(c => `
        <div class="sr-found">
          <span class="sr-name"><strong>${c.passport_name}</strong> — <code>${c.code}</code>
            <span class="cand-meta">${c.confidence}% ${levelLabel(c.level)}</span></span>
          <button class="btn-accept-found"
                  onclick="acceptManual('${invNum}',${idx},'${esc(c.passport_name)}','${esc(c.code)}','${esc(c.country)}')">
            Použít
          </button>
        </div>`).join('');
    }
  } catch (e) {
    resultEl.innerHTML = `<span class="srError">Chyba: ${e.message}</span>`;
  }
}

// ── Pomocné funkce pro aplikování shody ────────────────────

/** Aplikuje potvrzený výsledek na jeden řádek tabulky. */
function applyAccepted(tr, passportName, code, label) {
  tr.cells[2].innerHTML = `<span class="badge badge-exact">✓ ${label}</span>`;
  tr.cells[3].innerHTML = `<span class="passport-name">${passportName}</span>`;
  tr.cells[4].innerHTML = `<span class="code-display">${code}</span>
                            <input type="hidden" class="code-value" value="${code}" />`;
}

/**
 * Propaguje opravu na všechny ostatní řádky se stejným názvem z faktury.
 * Vrátí počet aktualizovaných řádků.
 */
function propagateToMatchingRows(sourceRow, passportName, code, label) {
  const invoiceName = sourceRow.dataset.invoiceName;
  if (!invoiceName) return 0;
  let count = 0;
  document.querySelectorAll('tr[data-invoice-name]').forEach(tr => {
    if (tr !== sourceRow && tr.dataset.invoiceName === invoiceName) {
      applyAccepted(tr, passportName, code, label);
      const tbody = tr.closest('tbody');
      if (tbody) updateInvoiceHeaderBadge(tbody.id.replace('tbody-', ''));
      count++;
    }
  });
  return count;
}

function acceptManual(invNum, idx, passportName, code, country) {
  const tr = document.getElementById(`row-${invNum}-${idx}`);
  if (!tr) return;
  applyAccepted(tr, passportName, code, 'Doplněno ručně');
  const propagated = propagateToMatchingRows(tr, passportName, code, 'Doplněno ručně');
  if (propagated > 0) {
    showPropagationNotice(tr, propagated);
  }
  checkStep2Ready();
  updateInvoiceHeaderBadge(invNum);
}

function acceptFuzzy(invNum, idx) {
  const tr = document.getElementById(`row-${invNum}-${idx}`);
  if (!tr) return;
  const pn      = tr.cells[3].querySelector('.passport-name');
  const codeVal = tr.cells[4].querySelector('.code-value');
  const passportName = pn ? pn.textContent : '';
  const code         = codeVal ? codeVal.value : '';
  applyAccepted(tr, passportName, code, 'Potvrzeno');
  const propagated = propagateToMatchingRows(tr, passportName, code, 'Potvrzeno');
  if (propagated > 0) {
    showPropagationNotice(tr, propagated);
  }
  checkStep2Ready();
  updateInvoiceHeaderBadge(invNum);
}

/** Hromadně potvrdí nejlepší návrh u všech nepotvrzených fuzzy shod. */
function acceptAllFuzzy() {
  const buttons = Array.from(document.querySelectorAll('.btn-fuzzy-accept'));
  buttons.forEach(btn => {
    if (document.body.contains(btn)) btn.click();
  });
  checkStep2Ready();
}

/** Zobrazí malou notifikaci vedle řádku o propagaci. */
function showPropagationNotice(tr, count) {
  // Odeber starý notice, pokud existuje
  const existing = tr.querySelector('.propagation-notice');
  if (existing) existing.remove();
  const notice = document.createElement('div');
  notice.className = 'propagation-notice';
  notice.textContent = `↕ Aplikováno na ${count} další${count > 1 ? 'ch' : ''} faktur${count > 1 ? 'ách' : 'e'}`;
  tr.cells[3].appendChild(notice);
  setTimeout(() => notice.remove(), 5000);
}

function rejectFuzzy(invNum, idx, invoiceName) {
  const tr = document.getElementById(`row-${invNum}-${idx}`);
  if (!tr) return;
  tr.cells[2].innerHTML = `<span class="badge badge-none">✗ Nenalezeno</span>`;
  tr.cells[3].innerHTML = buildManualSearch(invNum, idx, invoiceName);
  tr.cells[4].innerHTML = `<span class="code-display missing-code">—</span>
                            <input type="hidden" class="code-value" value="" data-missing="true" />`;
  checkStep2Ready();
  updateInvoiceHeaderBadge(invNum);
}

function checkStep2Ready() {
  const allCodes = document.querySelectorAll('.code-value');
  const anyEmpty = Array.from(allCodes).some(inp => !inp.value.trim());
  const hasRows  = allCodes.length > 0;
  btnToStep3.disabled = anyEmpty || !hasRows;
  btnDedup.disabled   = !hasRows;
  btnAssignAll.disabled = document.querySelectorAll('.btn-fuzzy-accept').length === 0;
}

// ── Odebrat duplicity ───────────────────────────────────────
btnDedup.addEventListener('click', removeDuplicates);

// ── Přiřadit vše ────────────────────────────────────────────
btnAssignAll.addEventListener('click', acceptAllFuzzy);

function removeDuplicates() {
  let totalRemoved = 0;

  document.querySelectorAll('.invoice-block').forEach(block => {
    const tbody = block.querySelector('tbody');
    if (!tbody) return;

    const rows = Array.from(tbody.querySelectorAll('tr'));
    const seen = new Set();
    let removedInBlock = 0;

    rows.forEach(tr => {
      if (!tr.cells || tr.cells.length < 4) return;

      // Klíč = NÁZEV V PASU (sloupec 3), normalizovaný
      // Různé varianty "Asimina triloba, odr. X" → stejný pas "Asimina triloba" → duplicita
      const passportEl = tr.cells[3].querySelector('.passport-name');
      if (!passportEl) return; // přeskoč řádky bez přiřazeného pasu (nenalezeno)

      const key = passportEl.textContent.toLowerCase().replace(/\s+/g, ' ').trim();
      if (!key) return;

      if (seen.has(key)) {
        tr.remove();
        removedInBlock++;
        totalRemoved++;
      } else {
        seen.add(key);
      }
    });

    if (removedInBlock > 0) {
      const invNum = tbody.id.replace('tbody-', '');
      updateInvoiceHeaderBadge(invNum);
      const header = block.querySelector('.invoice-block-header');
      if (header) {
        let notice = header.querySelector('.dedup-notice');
        if (!notice) {
          notice = document.createElement('span');
          notice.className = 'dedup-notice';
          header.appendChild(notice);
        }
        notice.textContent = `−${removedInBlock} duplikát${removedInBlock > 1 ? 'ů' : ''}`;
      }
    }
  });

  checkStep2Ready();

  if (totalRemoved > 0) {
    btnDedup.textContent = `✓ Odebráno ${totalRemoved} duplikátů`;
    btnDedup.disabled = true;
  } else {
    btnDedup.textContent = '✓ Žádné duplicity';
    btnDedup.disabled = true;
  }
}

function updateInvoiceHeaderBadge(invNum) {
  const block = document.querySelector(`#tbody-${invNum}`)?.closest('.invoice-block');
  if (!block) return;
  const emptyCount = Array.from(block.querySelectorAll('.code-value')).filter(i => !i.value.trim()).length;
  const badgeEl = block.querySelector('.invoice-block-header .badge');
  if (!badgeEl) return;
  if (emptyCount === 0) {
    badgeEl.className   = 'badge badge-exact';
    badgeEl.textContent = '✓ OK';
  } else {
    badgeEl.className   = 'badge badge-none';
    badgeEl.textContent = `⚠ ${emptyCount} nenalezeno`;
  }
}

// ══════════════════════════════════════════════════════════
// KROK 3 — Generovat Excel
// ══════════════════════════════════════════════════════════
btnToStep3.addEventListener('click', () => {
  sectionGenerate.classList.remove('hidden');
  sectionGenerate.scrollIntoView({ behavior: 'smooth' });
  setNavStep(3);
  renderGenerateSummary();
});

btnBackTo2.addEventListener('click', () => {
  sectionGenerate.classList.add('hidden');
  setNavStep(2);
});

/** Sebere finální data z tabulky Kroku 2 */
function collectFinalData() {
  const invoices = [];
  document.querySelectorAll('.invoice-block').forEach(block => {
    const tbody = block.querySelector('tbody');
    if (!tbody) return;
    const invNum = tbody.id.replace('tbody-', '');
    const meta   = currentInvoiceMeta[invNum] || {};
    const plants = [];

    tbody.querySelectorAll('tr').forEach(tr => {
      if (!tr.cells || tr.cells.length < 5) return;
      const passportEl = tr.cells[3].querySelector('.passport-name');
      const codeEl     = tr.cells[4].querySelector('.code-value');
      const passportName = passportEl ? passportEl.textContent.trim() : '';
      const code         = codeEl     ? codeEl.value.trim()           : '';
      if (passportName && code) {
        plants.push({ passport_name: passportName, code, country: 'CZ' });
      }
    });

    if (plants.length > 0) {
      invoices.push({
        number:   invNum,
        customer: meta.customer || '',
        date:     meta.date     || '',
        plants
      });
    }
  });
  return invoices;
}

function renderGenerateSummary() {
  const invoices = collectFinalData();
  generateResult.classList.add('hidden');
  generateResult.innerHTML = '';

  if (invoices.length === 0) {
    generateSummary.innerHTML = `<p class="hint" style="color:#c0392b">
      Žádná data k exportu. Vrať se a zkontroluj přiřazení kódů.</p>`;
    btnGenerateExcel.disabled = true;
    return;
  }

  const totalPlants = invoices.reduce((s, i) => s + i.plants.length, 0);
  let html = `<div class="gen-stats">
    <span class="pill green">${invoices.length} faktur</span>
    <span class="pill blue">${totalPlants} rostlin</span>
  </div>
  <table class="gen-table">
    <thead><tr><th>Faktura</th><th>Zákazník</th><th>Datum</th><th>Rostlin</th></tr></thead>
    <tbody>`;
  invoices.forEach(inv => {
    html += `<tr>
      <td><strong>${inv.number}</strong></td>
      <td>${inv.customer || '—'}</td>
      <td>${inv.date     || '—'}</td>
      <td>${inv.plants.length}</td>
    </tr>`;
  });
  html += '</tbody></table>';
  generateSummary.innerHTML = html;
  btnGenerateExcel.disabled = false;
  btnGeneratePdf.disabled = false;
}

btnGenerateExcel.addEventListener('click', async () => {
  const invoices = collectFinalData();
  if (!invoices.length) return;

  generateLoading.style.display = 'flex';
  btnGenerateExcel.disabled = true;
  generateResult.classList.add('hidden');

  try {
    const res = await fetch('/api/generate-excel', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ invoices })
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.error || 'Chyba serveru');
    }

    // Stažení souboru
    const blob        = await res.blob();
    const disposition = res.headers.get('Content-Disposition') || '';
    const nameMatch   = disposition.match(/filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/);
    const filename    = nameMatch ? nameMatch[1].replace(/['"]/g, '') : 'pasy.xlsx';

    const url  = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href  = url;
    link.download = filename;
    link.click();
    URL.revokeObjectURL(url);

    generateResult.innerHTML = `
      <div class="gen-success">
        ✓ Excel úspěšně vygenerován a stažen: <strong>${filename}</strong><br>
        <small>Soubor je také uložen ve složce <code>Tool_pasy/výstupy/</code></small>
      </div>`;
    generateResult.classList.remove('hidden');
    btnUploadDrive.disabled = false;

  } catch (e) {
    generateResult.innerHTML = `<div class="gen-error">✗ Chyba: ${e.message}</div>`;
    generateResult.classList.remove('hidden');
    btnGenerateExcel.disabled = false;
  } finally {
    generateLoading.style.display = 'none';
  }
});

btnGeneratePdf.addEventListener('click', async () => {
  const invoices = collectFinalData();
  if (!invoices.length) return;

  generateLoading.style.display = 'flex';
  btnGeneratePdf.disabled = true;
  generateResult.classList.add('hidden');

  try {
    const res = await fetch('/api/generate-pdf', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ invoices })
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.error || 'Chyba serveru');
    }

    // Stažení ZIPu
    const blob        = await res.blob();
    const disposition = res.headers.get('Content-Disposition') || '';
    const nameMatch   = disposition.match(/filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/);
    const filename    = nameMatch ? nameMatch[1].replace(/['"]/g, '') : 'pasy.zip';

    const url  = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href  = url;
    link.download = filename;
    link.click();
    URL.revokeObjectURL(url);

    generateResult.innerHTML = `
      <div class="gen-success">
        ✓ PDF pasy úspěšně vygenerovány a staženy: <strong>${filename}</strong><br>
        <small>Soubory jsou také uloženy ve složce <code>Tool_pasy/výstupy/</code></small>
      </div>`;
    generateResult.classList.remove('hidden');
    btnUploadDrive.disabled = false;

  } catch (e) {
    generateResult.innerHTML = `<div class="gen-error">✗ Chyba: ${e.message}</div>`;
    generateResult.classList.remove('hidden');
  } finally {
    btnGeneratePdf.disabled = false;
    generateLoading.style.display = 'none';
  }
});

btnUploadDrive.addEventListener('click', async () => {
  generateLoading.style.display = 'flex';
  btnUploadDrive.disabled = true;
  generateResult.classList.add('hidden');

  try {
    const res = await fetch('/api/upload-drive', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({})
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.error || 'Chyba serveru');
    }

    const data = await res.json();
    const fileItems = (data.files || []).map(f =>
      `<li><a href="${f.link}" target="_blank">${esc(f.name)}</a></li>`
    ).join('');

    generateResult.innerHTML = `
      <div class="gen-success">
        ✓ Nahráno na Google Drive —
        <a href="${data.folder_link}" target="_blank">Otevřít složku</a>
        <ul class="drive-file-list">${fileItems}</ul>
      </div>`;
    generateResult.classList.remove('hidden');

  } catch (e) {
    generateResult.innerHTML = `<div class="gen-error">✗ ${e.message}</div>`;
    generateResult.classList.remove('hidden');
  } finally {
    btnUploadDrive.disabled = false;
    generateLoading.style.display = 'none';
  }
});

function setNavStep(num) {
  for (let i = 1; i <= 4; i++) {
    const el = document.getElementById(`step-nav-${i}`);
    if (!el) continue;
    el.classList.remove('active', 'done');
    if (i < num) el.classList.add('done');
    else if (i === num) el.classList.add('active');
  }
}

function esc(s) {
  return (s || '').replace(/\\/g, '\\\\').replace(/'/g, "\\'").replace(/"/g, '&quot;');
}

// ── Stav Google Drive (vylepšení tooltipu) ─────────────────
fetch('/api/drive-status')
  .then(res => res.ok ? res.json() : null)
  .then(status => {
    if (status && !status.credentials) {
      btnUploadDrive.title = 'Google Drive není nastaven — chybí credentials.json';
    }
  })
  .catch(() => {});
