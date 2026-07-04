"""Paměťová session parsovaných faktur.

Jediné místo, které drží stav mezi /api/parse a navazujícími kroky.
Žádná persistence — restart serveru session zahodí (záměrné chování).
"""


class ParseSession:
    """Výsledek posledního parsování + cesty k nahraným PDF.

    - Faktury se každým parsováním NAHRAZUJÍ.
    - Cesty k souborům se SLUČUJÍ (akumulují se přes více uploadů).
    """

    def __init__(self) -> None:
        self._invoices: list = []
        self._file_paths: dict = {}

    def save(self, invoices, file_paths: dict) -> None:
        """Nahradí faktury a přimíchá cesty k nahraným souborům."""
        self._invoices = invoices
        self._file_paths.update(file_paths)

    def invoices(self) -> list:
        return self._invoices

    def file_paths(self) -> dict:
        """Mapování název souboru → uložená cesta."""
        return self._file_paths

    def index_by_number(self) -> dict:
        """Mapování číslo faktury → Invoice (pro slučování PDF)."""
        return {inv.number: inv for inv in self._invoices}

    def clear(self) -> None:
        self._invoices = []
        self._file_paths.clear()


session = ParseSession()
