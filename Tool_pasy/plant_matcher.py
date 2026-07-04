import openpyxl
import re
import unicodedata
from collections import defaultdict
from typing import List, Optional
from thefuzz import fuzz, process


class PlantMatcher:
    """
    Páruje názvy rostlin z faktur s kódy ze šarže — víceúrovňově (recall-first).

    Pořadí (nejspecifičtější vyhrává):
      1) Přesná shoda na plném normalizovaném názvu           -> exact
      2) Přesná shoda nezávislá na pořadí tokenů (hybridy)     -> exact
      3) Autonym (var./ssp. epiteton == druhové epiteton)      -> exact
      4) Shoda na úrovni druhu (binom) – nižší rank není v DB  -> návrh (suggestion)
      5) Shoda na úrovni rodu (rod je samostatně v DB)         -> návrh
      6) Fuzzy (token_set_ratio)                               -> návrh
      7) Nic nad prahem                                        -> none

    Každý dotaz vrací seřazený seznam `candidates` (pro výběr uživatelem)
    a `best` (nejlepší kandidát) plus `reason` proč.
    """

    # Fuzzy: nad HIGH a s odstupem od druhého => auto-návrh; jinak nabídnout seznam.
    FUZZY_SUGGEST_FLOOR = 70    # minimum pro zobrazení ve výběru
    FUZZY_AUTO_FLOOR    = 88    # nad tím jednoznačný návrh
    MAX_CANDIDATES      = 6

    # Rank markery a ne-taxonomická slova (rozpoznávaná jako tokeny po normalizaci).
    _RANK_TOKENS = {'var', 'subsp', 'ssp', 'f', 'cv', 'forma', 'hybr', 'sp', 'spp', 'odr', 'odrudy', 'odruda'}

    # Ne-taxonomické popisy (semena/balení/množství) – česky, po fold+lower.
    _DESC_RE = [
        re.compile(r'\bdle\s+vyberu\b'),
        re.compile(r'\d+\s*semen\w*'),        # "50 semen", "8 semena"
        re.compile(r'\bsemenac\w*'),          # "semenáče" -> "semenace"
        re.compile(r'\bsemen\w*'),            # "semen", "semeno"
        re.compile(r'\bplod\w*\s+rostlin\w*'),# "plodící rostliny"
        re.compile(r'\bsazenic\w*'),
        re.compile(r'\brostlin\w*'),
        re.compile(r'\bkultivar\w*'),
        re.compile(r'\bmrazuvzdorn\w*'),
        re.compile(r'\bodr\w*\.'),            # "odr."
    ]

    _SPLIT_SEPS = [' - ', ' \u2013 ', ' \u2014 ', ' / ']

    def __init__(self, sarze_path: str):
        self.entries: List[dict] = []
        self._by_exact    = defaultdict(list)   # klíč: plný norm název
        self._by_tokenset = defaultdict(list)   # klíč: frozenset tokenů (hybridy nezávisle na pořadí)
        self._by_species  = defaultdict(list)   # klíč: binom (rod + druh)
        self._by_genus    = defaultdict(list)   # klíč: rod (jen pro samostatné rodové položky)
        self.duplicates: List[dict] = []
        self._load_sarze(sarze_path)

    # ── Načtení šarže ─────────────────────────────────────────────
    def _load_sarze(self, path: str):
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        ws = wb.active
        for row in ws.iter_rows(min_row=2, values_only=True):
            if not row or not row[0]:
                continue
            name    = str(row[0]).strip()
            code    = str(row[1]).strip() if len(row) > 1 and row[1] else ""
            country = str(row[2]).strip() if len(row) > 2 and row[2] else "CZ"
            if not name or not code:
                continue
            key   = self._normalize(name)
            if not key:
                continue
            binom = self._binomial(key)
            entry = {
                'name': name, 'code': code, 'country': country,
                'key': key, 'binomial': binom,
            }
            self.entries.append(entry)

        for e in self.entries:
            self._by_exact[e['key']].append(e)
            self._by_tokenset[frozenset(e['key'].split())].append(e)
            self._by_species[e['binomial']].append(e)
            if ' ' not in e['key']:              # jen samostatné rodové (jednoslovné) položky
                self._by_genus[e['key']].append(e)

        # zaznamenej duplicity (stejný klíč, různé kódy)
        for key, group in self._by_exact.items():
            codes = sorted({g['code'] for g in group})
            if len(codes) > 1:
                self.duplicates.append({'key': key, 'names': [g['name'] for g in group], 'codes': codes})
        wb.close()

    # ── Normalizace ───────────────────────────────────────────────
    def _fold(self, s: str) -> str:
        s = unicodedata.normalize('NFKD', s)
        return ''.join(c for c in s if not unicodedata.combining(c))

    def _normalize(self, name: str) -> str:
        """Sdílený normalizátor pro DB i dotazy (musí být symetrický)."""
        s = self._fold(name).lower()
        s = s.replace('\u00d7', 'x').replace('×', 'x')
        s = re.sub(r'[\'"\u2018\u2019\u201c\u201d\u00b4`]', ' ', s)   # uvozovky kultivarů
        s = s.replace('\u00ae', '').replace('\u2122', '')            # (R) (TM)
        s = re.sub(r'\([^)]*\)', ' ', s)                             # závorky vč. (=synonym)
        # rozměry: 50/80 cm, 40x60 cm, 100-150 cm, 1.5 m, 40 cm
        s = re.sub(r'\d+\s*[-/x]\s*\d+(?:\s*[-/x]\s*\d+)?\s*cm', ' ', s)
        s = re.sub(r'\d+(?:[.,]\d+)?\s*(?:cm|m)\b', ' ', s)
        # kontejnery: c2, p9, t10 (samostatné tokeny)
        s = re.sub(r'\b[cpt]\d+\b', ' ', s)
        # ne-taxonomické popisy (semena/balení)
        for rx in self._DESC_RE:
            s = rx.sub(' ', s)
        # ostatní interpunkci na mezery, ale zachovej tečku u rank markerů dočasně? -> ne, řešíme tokeny
        s = re.sub(r'[^\w\s]', ' ', s)
        # osamocená čísla
        s = re.sub(r'\b\d+\b', ' ', s)
        return re.sub(r'\s+', ' ', s).strip()

    def _binomial(self, norm_s: str) -> str:
        """Rod + druhové epiteton (hybrid-aware), rank markery přeskočeny."""
        toks = norm_s.split()
        if not toks:
            return ''
        if toks[0] == 'x' and len(toks) > 1:
            genus, rest = 'x ' + toks[1], toks[2:]
        else:
            genus, rest = toks[0], toks[1:]
        i = 0
        while i < len(rest) and rest[i] in self._RANK_TOKENS:
            i += 1
        if i >= len(rest):
            return genus
        if rest[i] == 'x' and i + 1 < len(rest):
            return genus + ' x ' + rest[i + 1]
        return genus + ' ' + rest[i]

    def _species_epithet(self, binom: str) -> str:
        parts = binom.split()
        if len(parts) >= 3 and parts[1] == 'x':   # rod x epiteton
            return parts[2]
        return parts[1] if len(parts) >= 2 else ''

    def _classify_extra(self, norm_s: str, binom: str) -> str:
        """Co dotaz nese nad rámec binomu:
          'none'    – jen binom (+rank šum) → existují jen kultivary bez holého druhu
          'autonym' – navíc jen infra-epiteton == druhové epiteton (X y var. y)
          'extra'   – navíc skutečný taxon (kultivar/varieta) mimo autonym
        Používá odečtení po výskytech (multiset), aby zopakované epiteton nezmizelo."""
        toks = list(norm_s.split())
        for bt in binom.split():
            if bt in toks:
                toks.remove(bt)                      # odeber jeden výskyt
        rem = [t for t in toks if t not in self._RANK_TOKENS and t != 'x']
        if not rem:
            return 'none'
        sp = self._species_epithet(binom)
        if sp and all(t == sp for t in rem):
            return 'autonym'
        return 'extra'

    # ── Kandidátní řetězce z dotazu ───────────────────────────────
    def _candidate_strings(self, name: str) -> List[str]:
        cands, seen = [], set()

        def add(raw):
            c = self._normalize(raw)
            if c and c not in seen:
                seen.add(c)
                cands.append(c)

        add(name)
        for sep in self._SPLIT_SEPS:
            if sep in name:
                for part in name.split(sep):
                    add(part)
                break
        if ',' in name:
            add(name.split(',')[0])
        return cands

    # ── Veřejné API ───────────────────────────────────────────────
    def match_plant(self, invoice_name: str) -> dict:
        cands = self._candidate_strings(invoice_name)
        hits = []   # (priority, confidence, level, reason, entry)  – nižší priority = lepší

        for c in cands:
            ctoks = frozenset(c.split())
            # 1) plný přesný
            for e in self._by_exact.get(c, []):
                hits.append((0, 100, 'exact', 'Přesná shoda', e))
            # 2) token-set přesný (hybridy nezávisle na pořadí)
            if c not in self._by_exact:
                for e in self._by_tokenset.get(ctoks, []):
                    hits.append((1, 100, 'exact', 'Přesná shoda (pořadí tokenů)', e))
            # 3/4) binom
            if c not in self._by_exact:
                b = self._binomial(c)
                if b:
                    entries = self._by_species.get(b, [])
                    if entries:
                        kind = self._classify_extra(c, b)
                        if kind == 'autonym':
                            for e in entries:
                                hits.append((2, 100, 'exact', 'Autonym → druh', e))
                        elif kind == 'extra':
                            for e in entries:
                                hits.append((4, 90, 'species',
                                             'Shoda na úrovni druhu — nižší taxon není v šarži', e))
                        else:
                            # c je čistě binom, ale není v _by_exact => existují jen kultivary
                            for e in entries:
                                hits.append((5, 85, 'species',
                                             f'Shoda na úrovni druhu ({b})', e))
                    # 5) rod
                    genus = b.split()[0] if b else ''
                    for e in self._by_genus.get(genus, []):
                        hits.append((6, 80, 'genus', f'Shoda na úrovni rodu ({genus})', e))

        # 6) fuzzy – vždy dopočítej pro obohacení výběru
        fuzzy_hits = self._fuzzy(cands)
        hits.extend(fuzzy_hits)

        return self._assemble(hits)

    def search_by_name(self, query: str) -> dict:
        return self.match_plant(query)

    def match_invoice_plants(self, plants: list) -> list:
        results = []
        for plant in plants:
            m = self.match_plant(plant['name'])
            m['invoice_name'] = plant['name']
            m['quantity']     = plant.get('quantity', 1)
            results.append(m)
        return results

    def get_all_sarze_names(self) -> List[str]:
        return [e['name'] for e in self.entries]

    # ── Fuzzy ─────────────────────────────────────────────────────
    def _fuzzy(self, cands: List[str]) -> list:
        best_by_code = {}
        for c in cands:
            for name, score in process.extract(
                    c, self._by_species.keys(),
                    scorer=fuzz.token_set_ratio, limit=self.MAX_CANDIDATES):
                if score < self.FUZZY_SUGGEST_FLOOR:
                    continue
                for e in self._by_species.get(name, []):
                    prev = best_by_code.get(e['code'])
                    if prev is None or score > prev[1]:
                        best_by_code[e['code']] = (7, score, 'fuzzy',
                                                   f'Fuzzy shoda ({score} %)', e)
        return list(best_by_code.values())

    # ── Sestavení výsledku ────────────────────────────────────────
    def _assemble(self, hits: list) -> dict:
        if not hits:
            return self._none()

        # nejlepší záznam na kód: nejnižší priority, pak nejvyšší confidence
        best_per_code = {}
        for prio, conf, level, reason, e in hits:
            key = e['code']
            cur = best_per_code.get(key)
            if cur is None or (prio, -conf) < (cur[0], -cur[1]):
                best_per_code[key] = (prio, conf, level, reason, e)

        ordered = sorted(best_per_code.values(), key=lambda h: (h[0], -h[1], h[4]['name']))
        top_prio = ordered[0][0]

        candidates = []
        for prio, conf, level, reason, e in ordered[:self.MAX_CANDIDATES]:
            candidates.append({
                'passport_name': e['name'], 'sarze_name': e['name'],
                'code': e['code'], 'country': e['country'],
                'confidence': conf, 'level': level, 'reason': reason,
            })

        best = candidates[0]
        # status: exact jen pokud nejlepší je exact-úroveň a jednoznačný
        exact_codes = [c for c in candidates if c['level'] == 'exact']
        if best['level'] == 'exact':
            match_type = 'exact' if len(exact_codes) == 1 else 'fuzzy'  # víc exact kódů => uživatel vybere
        else:
            match_type = 'fuzzy'

        return {
            'match_type':    match_type,
            'confidence':    best['confidence'],
            'reason':        best['reason'],
            'passport_name': best['passport_name'],
            'sarze_name':    best['sarze_name'],
            'code':          best['code'],
            'country':       best['country'],
            'candidates':    candidates,
        }

    def _none(self) -> dict:
        return {
            'match_type': 'none', 'confidence': 0, 'reason': 'Nenalezeno',
            'passport_name': None, 'sarze_name': None, 'code': '', 'country': 'CZ',
            'candidates': [],
        }
