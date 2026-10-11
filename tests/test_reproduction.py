"""Selbst-Reproduktion der Messreihe (kleine Stichprobe; der volle Lauf über 5.400 Instanzen ist tools/reproduce_messreihe.py).

Die Live-Funktionen werden auf Instanzen der gespeicherten Zellen gerechnet und gegen data/sgt_results.json gelegt: Z gleich, K höchstens gleich
(neun Zellen rechneten mit Raster 0,05, live gilt überall 0,01), G höchstens gleich, die Untergrenze ohne Schichtstruktur gleich (ersetzte Einträge
tragen die Schranke der engeren Variante und fallen aus dem Vergleich), O gleich, wenn beide Seiten bewiesen sind, sonst nie unter der Untergrenze.
Kein Vergleich mit einem Zeitlimit-Ergebnis des Lösers auf Gleichheit (plattform- und lastabhängig).
"""

import pytest

import sgt_constants as C
import sgt_instance as I
import sgt_pipeline as PL
import sgt_results as R

F = R.FIELD
SAMPLE = [(name, art, i) for name in R.cell_names() for art in R.cell(name)["profiles"][1:3] for i in (0, 1)]   # Zwei Spitzen und Morgenspitze


def live_for(name, art, i):
    cell = R.cell(name)
    s = PL.Settings(profile=art, size=cell["size"], aht=cell["aht"], goal=cell["goal"], catalog=cell["catalog"], seed=i)
    prob, plans, _ = PL.stage1(s)
    return s, prob, plans


@pytest.mark.parametrize("name", R.cell_names())
def test_live_functions_reproduce_the_stored_costs(name):
    for _, art, i in [t for t in SAMPLE if t[0] == name]:
        row = next(r for r in R.rows(name, art) if r["i"] == i)
        s, prob, plans = live_for(name, art, i)
        assert plans["Z"].cost == R.get(row, "A", "cost")
        assert abs(plans["Z"].day_sl - R.get(row, "A", "sl")) < 2e-5
        assert plans["K"].cost <= R.get(row, "Az", "cost")
        cell = R.cell(name)
        if cell["az_step"] == 0.01:
            assert plans["K"].cost == R.get(row, "Az", "cost")
        if "BFz" in row["v"]:
            assert plans["G"].cost <= R.get(row, "BFz", "cost")
        if R.get(row, "B", "replaced") == 0:
            assert plans["ODP"].cost == R.get(row, "B", "dp")
        assert plans["ODP"].cost <= R.get(row, "B", "cost")


def test_proven_live_and_proven_stored_costs_of_o_agree():
    checked = 0
    for name, art, i in [t for t in SAMPLE if t[0] in ("base", "hart", "ziel90", "kat468")]:
        row = next(r for r in R.rows(name, art) if r["i"] == i)
        s, prob, plans = live_for(name, art, i)
        o, _ = PL.stage2(s, prob, plans)
        assert o.cost >= plans["ODP"].cost and o.cost <= min(plans["K"].cost, plans["G"].cost)
        stored_proven = R.get(row, "B", "opt") == 1 and R.get(row, "B", "replaced") == 0
        if o.status == "optimal" and stored_proven:
            assert o.cost == R.get(row, "B", "cost"), (name, art, i)
            checked += 1
        if o.status == "optimal" and not stored_proven:
            assert o.cost <= R.get(row, "B", "cost")           # live bewiesen, gespeichert nur bester Fund: nie schlechter
    assert checked >= 3
