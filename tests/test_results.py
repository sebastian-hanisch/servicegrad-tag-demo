"""Vorgerechnete Ergebnisse: Aufbau der Dateien, Hilfsfunktionen und ehrliche Zählung des Beweisstatus."""

import pytest

import sgt_constants as C
import sgt_results as R


def test_the_file_has_thirteen_cells_and_5400_instances():
    data = R.load()
    assert len(data["cells"]) == 13 and list(data["cells"]) == data["meta"]["order"]
    assert sum(len(c["rows"]) for c in data["cells"].values()) == 5400
    assert data["meta"]["per_cell_profile"] == 100
    for name, c in data["cells"].items():
        assert c["size"] in C.SIZES and c["goal"] in C.GOAL_OPTIONS and c["aht"] in C.AHT_OPTIONS and c["catalog"] in C.CATALOGS
        assert len(c["rows"]) == 100 * len(c["profiles"]), name


def test_every_row_has_the_always_present_variants_and_consistent_fields():
    f = R.FIELD
    for name in R.cell_names():
        for r in R.rows(name):
            for v in ("A", "Az", "B", "BF", "Beq"):
                x = r["v"][v]
                assert len(x) == len(R.FIELDS)
                assert x[f["cost"]] > 0 and 0.0 <= x[f["sl"]] <= 1.0
            assert r["v"]["A"][f["cost"]] >= r["v"]["Az"][f["cost"]]


def test_replaced_entries_are_listed_and_never_counted_as_proven():
    meta = R.load()["meta"]["replaced"]
    assert meta == {"base:B": 4, "base:B1": 5, "base:Beq": 4, "kat468:Beq": 1, "kat8:B": 35, "kat8:Beq": 20}
    for key, count in meta.items():
        cell, v = key.split(":")
        rows = R.rows(cell)
        assert sum(1 for r in rows if r["v"][v][R.FIELD["replaced"]] == 1) == count
        assert all(r["v"][v][R.FIELD["opt"]] == 0 for r in rows if r["v"][v][R.FIELD["replaced"]] == 1)
    assert round(R.proven_share(R.rows("base"), "B"), 1) == 88.6
    assert round(R.proven_share(R.rows("kat8"), "B"), 1) == 80.5


def test_saving_is_positive_for_a_cheaper_variant_and_paired():
    base = R.rows("base")
    m, s, n = R.saving(base, "B")
    assert n == 500 and m > 0 and s > 0
    h, hs = R.hours_saved(base, "B")
    mean_cost = R.mean(R.get(r, "A", "cost") for r in base)
    assert round(m, 1) == 13.0 and round(h, 1) == 24.3 and round(mean_cost, 1) == 207.6
    # Mittel der Prozentwerte je Instanz (13,0 %) und Verhältnis der Mittel (24,3 von 207,6 h = 11,7 %) sind verschiedene Zahlen: kleine Instanzen sparen mehr
    assert round(100 * h / mean_cost, 1) == 11.7


def test_percentile_and_se_helpers():
    assert R.percentile([1, 2, 3, 4, 5], 0.5) == 3
    assert R.percentile([1, 2, 3, 4], 0.5) == 2.5
    assert R.percentile([10], 0.9) == 10
    assert R.se([1.0, 3.0]) == pytest.approx(1.0)
    assert R.se([5.0]) != R.se([5.0])                                # NaN bei einem Wert


def test_cell_lookup_matches_only_exact_settings():
    assert R.cell_for("mittel", 80, 240, "6/8/10") == "base"
    assert R.cell_for("klein", 80, 240, "6/8/10") == "klein"
    assert R.cell_for("mittel", 80, 240, "3/4") is None
    assert R.cell_for("mittel", 95, 240, "3/4") == "hart"


def test_tables_have_one_row_per_cell_and_the_documented_columns():
    cells = R.cells_table()
    assert len(cells) == 13 and {"Zelle", "O spart (%)", "K spart (%)", "K in der Messreihe (Raster 0,05)", "O bewiesen (%)"} <= set(cells[0])
    assert len(R.profile_table("base")) == 5
    dec = R.decomposition("base")
    assert dec[-1]["Profil"] == "alle" and len(dec) == 6
    proof = R.proof_table()
    assert len(proof) == 13 and any(p["Marke"] == "unter 80 %" for p in proof)
    q = R.quantile_table()
    assert {"Zelle", "Variante", "Median", "P10", "P90"} <= set(q[0])


def test_proven_share_never_counts_replaced_entries_even_if_their_flag_says_proven():
    f = R.FIELD

    def entry(opt, replaced):
        x = [0] * len(R.FIELDS)
        x[f["opt"]], x[f["replaced"]] = opt, replaced
        return {"v": {"B": x}}

    rows = [entry(1, 0), entry(1, 1), entry(0, 0), entry(1, 0)]
    assert R.proven_share(rows, "B") == 50.0


def test_the_two_long_catalog_cells_differ_in_8_of_400_instances_only():
    a = {(r["art"], r["i"]): r for r in R.rows("kat345")}
    b = {(r["art"], r["i"]): r for r in R.rows("kat3bis12")}
    assert len(a) == 400
    assert sum(1 for k in a if any(R.get(a[k], v, "cost") != R.get(b[k], v, "cost") for v in ("A", "Az", "BF", "B", "Beq"))) == 8
