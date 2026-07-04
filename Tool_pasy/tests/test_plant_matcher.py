"""Regression suite for the recall-first tiered plant-name matcher.

Guards the behavioral contract of ``plant_matcher.PlantMatcher`` so future edits
cannot silently regress recall (round-trip), precision (cultivar landmines), or
the real-invoice normalization (junk stripping, bilingual split, diacritics).

Run from the app dir:  python -m pytest test_plant_matcher.py -q
The ``matcher`` fixture chdir's into the app dir itself, so the relative
``data/sarze.xlsx`` path resolves regardless of pytest's invocation cwd.
"""

import os
import random
import sys
import unicodedata
from pathlib import Path

import pytest

APP_DIR = Path(__file__).resolve().parent
# Make ``plant_matcher`` importable no matter where pytest is invoked from.
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from plant_matcher import PlantMatcher  # noqa: E402
from paths import DATA_DIR  # noqa: E402


# ── Fixtures ──────────────────────────────────────────────────────────────
@pytest.fixture(scope="module")
def matcher():
    """One matcher for the whole module, built against the real shipped DB."""
    return PlantMatcher(str(DATA_DIR / "sarze.xlsx"))


# ── Helpers ───────────────────────────────────────────────────────────────
def candidate_codes(result):
    return [c["code"] for c in result["candidates"]]


def top_code(result):
    return result["candidates"][0]["code"] if result["candidates"] else None


def code_for_name(matcher, name):
    """Latin/DB name -> code via case-insensitive exact name lookup.

    Keeps the expected codes data-driven off the shipped DB instead of
    hardcoding possibly-stale numbers.
    """
    key = name.strip().lower()
    hits = [e["code"] for e in matcher.entries if e["name"].strip().lower() == key]
    assert hits, f"DB has no entry named {name!r} to anchor the test against"
    return hits


def fold(s):
    """Strip combining diacritics (mirrors the matcher's own folding)."""
    return "".join(
        c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c)
    )


def with_diacritics(s):
    """Inject a combining acute accent after each vowel; folds back to ``s``."""
    out = []
    for ch in s:
        out.append(ch)
        if ch.lower() in "aeiou":
            out.append("\u0301")
    return "".join(out)


# ── Contract shape ────────────────────────────────────────────────────────
def test_db_loaded_and_entry_shape(matcher):
    assert len(matcher.entries) > 1000, "DB failed to load a plausible number of rows"
    for e in matcher.entries[:50]:
        assert {"name", "code", "country"} <= e.keys()
        assert e["name"] and e["code"]


def test_result_shape(matcher):
    r = matcher.match_plant("Acer palmatum")
    assert r["match_type"] in {"exact", "fuzzy", "none"}
    assert isinstance(r["confidence"], int)
    assert isinstance(r["reason"], str)
    for key in ("passport_name", "sarze_name", "code", "country", "candidates"):
        assert key in r
    for c in r["candidates"]:
        assert {"passport_name", "code", "country", "confidence", "level", "reason"} <= c.keys()
        assert c["level"] in {"exact", "species", "genus", "fuzzy"}


def test_search_by_name_is_match_plant(matcher):
    assert matcher.search_by_name("Acer palmatum") == matcher.match_plant("Acer palmatum")


# ── 1) DB self round-trip — the primary recall regression guard ───────────
def test_db_self_round_trip(matcher):
    """Every DB entry must recover its OWN code when queried by its own name:
    either an unambiguous exact match, or at minimum present among candidates
    (duplicates normalize to the same key -> match_type 'fuzzy' with several
    exact-level codes, which is acceptable as long as the code is surfaced)."""
    failures = []
    for e in matcher.entries:
        r = matcher.match_plant(e["name"])
        exact_hit = r["match_type"] == "exact" and r["code"] == e["code"]
        in_candidates = e["code"] in candidate_codes(r)
        if not (exact_hit or in_candidates):
            failures.append((e["name"], e["code"], r["match_type"], r["code"],
                             candidate_codes(r)))
    assert not failures, (
        f"{len(failures)}/{len(matcher.entries)} entries did not recover their own "
        f"code. First few: {failures[:5]}"
    )


# ── 2) Autonym collapse ───────────────────────────────────────────────────
def test_autonym_collapses_to_species(matcher):
    # var. epithet == species epithet -> treated as the bare species (exact).
    r = matcher.match_plant("Agave parryi var. parryi")
    assert r["match_type"] == "exact"
    assert r["code"] == "25-Ro59"


def test_unknown_variety_suggests_species_not_exact(matcher):
    # A variety NOT in the DB must not masquerade as exact; the bare species
    # 'Agave parryi' (25-Ro59) must be the top suggestion.
    r = matcher.match_plant("Agave parryi var. truncata")
    assert r["match_type"] != "exact"
    assert top_code(r) == "25-Ro59"


# ── 3) Cultivar landmine — precision must not collapse to species ─────────
def test_known_cultivar_keeps_its_own_code(matcher):
    r = matcher.match_plant("Acer palmatum Atropurpureum")
    assert r["match_type"] == "exact"
    assert r["code"] == "25-Ro33"          # its OWN code
    assert r["code"] != "25-Ro32"          # must NOT collapse to the species


def test_absent_cultivar_falls_back_to_species(matcher):
    # 'Dissectum' cultivar is not in the DB -> not exact, species is top.
    r = matcher.match_plant("Acer palmatum Dissectum")
    assert r["match_type"] != "exact"
    assert top_code(r) == "25-Ro32"


# ── 4) Non-taxonomic junk stripping (real-invoice pain) ───────────────────
@pytest.mark.parametrize(
    "query, latin",
    [
        ("Bez kanadský - Sambucus canadensis, 50 semen", "Sambucus canadensis"),
        ("Zmarlika čínská - Cercis chinensis, 20 semen", "Cercis chinensis"),
    ],
)
def test_junk_and_seed_counts_dont_block_species(matcher, query, latin):
    expected = code_for_name(matcher, latin)
    r = matcher.match_plant(query)
    assert top_code(r) in expected, (
        f"{query!r} should resolve to {latin} {expected}, got {top_code(r)}"
    )


def test_cultivar_suffix_and_dimensions_dont_block(matcher):
    # 'odr.'/'odrůdy' markers + 'cm' dimensions must be stripped, leaving the
    # bare species to match.
    base = "Acer palmatum"
    expected = code_for_name(matcher, base)
    for query in (f"{base} odr. 40/60 cm", f"{base} odrůdy 100-150 cm"):
        r = matcher.match_plant(query)
        assert top_code(r) in expected, f"{query!r} -> {top_code(r)}"


# ── 5) Bilingual 'Czech - Latin' split ────────────────────────────────────
def test_bilingual_resolves_via_latin_part(matcher):
    latin = "Asimina triloba"
    expected = code_for_name(matcher, latin)          # 25-Ro132
    r = matcher.match_plant(f"Pawpaw muďoul - {latin}")
    assert r["match_type"] == "exact"
    assert r["code"] in expected


# ── 6) Token-set (order-independent) hybrid exact ─────────────────────────
def test_hybrid_token_order_is_exact(matcher):
    # DB stores 'Trachycarpus wagnerianus x fortunei'; the reversed order query
    # must still be an exact hit on the same code.
    r = matcher.match_plant("Trachycarpus fortunei x wagnerianus")
    assert r["match_type"] == "exact"
    assert r["code"] == "25-Ro1410"


# ── 7) Diacritics folding ─────────────────────────────────────────────────
def test_added_diacritics_still_match(matcher):
    # A clean binomial with injected Czech-style accents must fold back and
    # resolve to the same code.
    base = "Acer palmatum"
    expected = code_for_name(matcher, base)
    query = with_diacritics(base)
    assert query != base                              # accents really added
    r = matcher.match_plant(query)
    assert r["match_type"] == "exact"
    assert r["code"] in expected


def test_folded_query_matches_diacritic_db_name(matcher):
    # Reverse direction: a DB name that contains diacritics must still be found
    # when queried with its ASCII-folded form.
    diac = next(
        (e for e in matcher.entries
         if any(unicodedata.combining(c) for c in unicodedata.normalize("NFKD", e["name"]))),
        None,
    )
    assert diac is not None, "expected at least one DB name with diacritics"
    r = matcher.match_plant(fold(diac["name"]))
    assert diac["code"] in candidate_codes(r)


# ── 8) Non-plant / no match ───────────────────────────────────────────────
def test_non_plant_yields_none(matcher):
    r = matcher.match_plant("Přidaný produkt (Semena dle výběru)")
    assert r["match_type"] == "none"
    assert r["candidates"] == []
    assert r["code"] == ""


# ── 9) Duplicate surfacing — nothing silently dropped ─────────────────────
def test_duplicates_are_detected(matcher):
    assert matcher.duplicates, "expected the DB to contain normalize-collision duplicates"
    for d in matcher.duplicates:
        assert len(d["codes"]) > 1
        assert set(d["names"]) and d["key"]


def test_duplicate_name_surfaces_all_codes(matcher):
    # 'Bouea macrophylla' has two distinct codes; both must appear so the user
    # can disambiguate rather than one being silently dropped.
    dup = next((d for d in matcher.duplicates if d["key"] == "bouea macrophylla"), None)
    assert dup is not None, "expected 'bouea macrophylla' among detected duplicates"
    assert set(dup["codes"]) == {"25-Ro171", "25-Ro1540"}
    r = matcher.match_plant("Bouea macrophylla")
    codes = candidate_codes(r)
    for code in ("25-Ro171", "25-Ro1540"):
        assert code in codes, f"{code} dropped from candidates: {codes}"


# ── 10) Synthetic mutation robustness ─────────────────────────────────────
def test_synthetic_mutations_keep_own_code(matcher):
    rng = random.Random(1234)
    sample = rng.sample(matcher.entries, min(100, len(matcher.entries)))
    failures = []
    for e in sample:
        for suffix in (" 40/60 cm", ", 10 semen"):
            r = matcher.match_plant(e["name"] + suffix)
            if e["code"] not in candidate_codes(r):
                failures.append((e["name"] + suffix, e["code"], candidate_codes(r)))
    assert not failures, f"{len(failures)} mutated queries lost their code: {failures[:5]}"
