import pdfplumber
import re
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class PlantItem:
    name: str
    quantity: int = 1
    unit_price: float = 0.0
    raw_name: str = ""

    def to_dict(self):
        return {
            'name': self.name,
            'quantity': self.quantity,
            'unit_price': self.unit_price,
            'raw_name': self.raw_name
        }


@dataclass
class Invoice:
    number: str
    date: str = ""
    customer: str = ""
    plants: List[PlantItem] = field(default_factory=list)
    source_file: str = ""
    source_page: int = 0
    email: str = ""
    source_pages: List[int] = field(default_factory=list)

    def to_dict(self):
        return {
            'number': self.number,
            'date': self.date,
            'customer': self.customer,
            'plants': [p.to_dict() for p in self.plants],
            'plant_count': len(self.plants),
            'source_file': self.source_file,
            'source_page': self.source_page,
            'email': self.email,
            'source_pages': self.source_pages
        }


class PDFParser:
    NON_PLANT_KEYWORDS = [
        'ppl', 'česká pošta', 'poštovné', 'doprava', 'balné',
        'přepravné', 'záloha', 'sleva', 'shipping', 'delivery',
        'expedice', 'dobírka', 'přidaný produkt', 'dle výběru',
        'dárkový poukaz',
    ]

    def parse_files(self, file_paths: List[str],
                    progress_callback=None) -> List[Invoice]:
        all_invoices = []
        total = len(file_paths)
        for i, path in enumerate(file_paths):
            if progress_callback:
                progress_callback(i / total, f"Čtu: {Path(path).name}")
            try:
                invoices = self._parse_pdf(Path(path))
                all_invoices.extend(invoices)
            except Exception as e:
                print(f"Chyba v {path}: {e}")
        all_invoices.sort(
            key=lambda inv: int(inv.number) if inv.number.isdigit() else 0
        )
        return all_invoices

    def _parse_pdf(self, pdf_path: Path) -> List[Invoice]:
        invoices = []
        current: Optional[Invoice] = None
        with pdfplumber.open(pdf_path) as pdf:
            for page_num, page in enumerate(pdf.pages):
                try:
                    text = page.extract_text() or ""
                    if re.search(r'Faktura\s+č\.\s*[:\s]*(\d+)', text,
                                 re.IGNORECASE):
                        inv = self._parse_page(page, pdf_path.name,
                                               page_num + 1)
                        if inv:
                            inv.source_pages = [page_num + 1]
                            invoices.append(inv)
                            current = inv
                    elif current is not None:
                        # Continuation page: extra items, no customer block
                        current.source_pages.append(page_num + 1)
                        for table in page.extract_tables():
                            current.plants.extend(self._parse_items(table))
                    # else: cover/blank page before first invoice — skip
                except Exception as e:
                    print(f"  Stránka {page_num+1}: {e}")
        return invoices

    def _parse_page(self, page, source_file: str,
                    page_num: int) -> Optional[Invoice]:
        text = page.extract_text() or ""
        tables = page.extract_tables()

        m = re.search(r'Faktura\s+č\.\s*[:\s]*(\d+)', text, re.IGNORECASE)
        if not m:
            return None

        date = ""
        dm = re.search(r'(\d{2}\.\d{2}\.\d{4})', text)
        if dm:
            date = dm.group(1)

        customer = self._get_customer(tables)

        em = re.search(r'(?i)E-mail:\s*([\w.+\-]+@[\w.\-]+\.\w+)', text)
        email = em.group(1) if em else ""

        plants = []
        if len(tables) >= 2:
            plants = self._parse_items(tables[1])
        elif len(tables) == 1:
            plants = self._parse_items(tables[0])

        return Invoice(
            number=m.group(1),
            date=date,
            customer=customer,
            plants=plants,
            source_file=source_file,
            source_page=page_num,
            email=email
        )

    def _get_customer(self, tables: list) -> str:
        if not tables or not tables[0]:
            return ""
        row = tables[0][0] if tables[0] else []
        for col_idx in [1, 0]:
            if col_idx < len(row) and row[col_idx]:
                cell = str(row[col_idx])
                for line in cell.split('\n'):
                    line = line.strip()
                    if line and not re.search(
                            r'Odběratel|Dodavatel', line, re.IGNORECASE):
                        if len(line) > 3:
                            return line
        return ""

    def _parse_items(self, table: list) -> List[PlantItem]:
        """
        Struktura tabulky (4 sloupce):
          row[0] = "() Název rostliny ..."  — kód a název dohromady
          row[1] = množství (Ks)
          row[2] = cena / ks
          row[3] = celkem
        Rostlinné řádky začínají row[0] řetězcem "() ".
        """
        plants = []
        for row in table:
            if not row or len(row) < 2:
                continue

            col0 = str(row[0]).strip() if row[0] else ''

            # Přijmeme pouze řádky, kde první sloupec začíná "()"
            if not col0.startswith('()'):
                continue

            # Odtrhneme prefix "() " a získáme čistý název
            raw_name = re.sub(r'^\(\)\s*', '', col0).strip()
            if not raw_name or len(raw_name) < 3:
                continue

            if self._is_non_plant(raw_name):
                continue

            clean = self._clean_name(raw_name)
            if not clean or len(clean) < 3:
                continue

            # Množství — row[1]
            qty = 1
            if len(row) > 1 and row[1]:
                qty_str = str(row[1]).strip()
                try:
                    qty = int(qty_str)
                except ValueError:
                    pass

            # Cena / ks — row[2]
            price = 0.0
            if len(row) > 2 and row[2]:
                pm = re.search(r'([\d\s]+(?:,\d+)?)', str(row[2]))
                if pm:
                    try:
                        price = float(
                            pm.group(1)
                            .replace('\xa0', '').replace(' ', '')
                            .replace(',', '.')
                        )
                    except ValueError:
                        pass

            plants.append(PlantItem(
                name=clean, quantity=qty,
                unit_price=price, raw_name=raw_name
            ))
        return plants

    def _is_non_plant(self, name: str) -> bool:
        nl = name.lower()
        return any(kw in nl for kw in self.NON_PLANT_KEYWORDS)

    def _clean_name(self, name: str) -> str:
        name = re.sub(r'\s+', ' ', name).strip()
        name = re.sub(r'\s+\d+[-/x]\d+\s*cm\s*$', '', name,
                      flags=re.IGNORECASE).strip()
        name = re.sub(r'\s+\d+(?:[,\.]\d+)?\s*(?:cm|m)\s*$', '', name,
                      flags=re.IGNORECASE).strip()
        return name
