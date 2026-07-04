"""Report anomálií v šarži (data/sarze.xlsx) k ruční opravě.

Spusť z adresáře Tool_pasy:  python report_anomalies.py
Zapíše přehled do výstupy/sarze_anomalie.txt a vypíše souhrn.
"""
import openpyxl
from pathlib import Path
from plant_matcher import PlantMatcher

SARZE = 'data/sarze.xlsx'
OUT   = Path('výstupy') / 'sarze_anomalie.txt'


def main():
    m = PlantMatcher(SARZE)
    lines = []

    # 1) Duplicity: stejný normalizovaný název, různé kódy
    lines.append(f"=== Duplicitní názvy (stejná rostlina, více kódů): {len(m.duplicates)} ===")
    for d in sorted(m.duplicates, key=lambda x: x['key']):
        lines.append(f"  '{d['key']}'  kódy: {', '.join(d['codes'])}")
        for n in d['names']:
            lines.append(f"       ← {n}")

    # 2) Řádky bez kódu / bez názvu (přeskočené při načítání)
    wb = openpyxl.load_workbook(SARZE, read_only=True, data_only=True)
    ws = wb.active
    empty_code, empty_name = [], []
    for i, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
        if not row:
            continue
        name = str(row[0]).strip() if row[0] else ''
        code = str(row[1]).strip() if len(row) > 1 and row[1] else ''
        if name and not code:
            empty_code.append((i, name))
        if code and not name:
            empty_name.append((i, code))
    wb.close()

    lines.append(f"\n=== Řádky s názvem ale bez kódu: {len(empty_code)} ===")
    for r, n in empty_code:
        lines.append(f"  řádek {r}: {n}")
    lines.append(f"\n=== Řádky s kódem ale bez názvu: {len(empty_name)} ===")
    for r, c in empty_name:
        lines.append(f"  řádek {r}: {c}")

    lines.append(f"\nNačteno platných položek: {len(m.entries)}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text('\n'.join(lines), encoding='utf-8')
    print('\n'.join(lines))
    print(f"\n→ Report uložen do {OUT}")


if __name__ == '__main__':
    main()
