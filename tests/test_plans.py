"""Planungsvarianten Z, K, G, O und O ohne Schichtstruktur: Ordnung, eingefrorene Instanzen, z-Suche, Determinismus."""

import pytest

import sgt_constants as C
import sgt_cover as V
import sgt_pipeline as PL
import sgt_plans as P
import sgt_results as R
from sgt_erlang import Problem
from sgt_rng import SplitMix64, seed_from

CATALOG = (6, 8, 10)
BASE = dict(size="mittel", aht=240, goal=80, catalog="6/8/10")


def live_plans(profile, seed, with_o=True):
    s = PL.Settings(profile=profile, seed=seed, **BASE)
    prob, plans, _ = PL.stage1(s)
    if with_o:
        o, _ = PL.stage2(s, prob, plans)
        plans["O"] = o
    return s, prob, plans


@pytest.mark.parametrize("profile", C.PROFILE_ORDER)
def test_ordering_of_costs_on_fixed_instances(profile):
    for seed in (0, 1):
        s, prob, p = live_plans(profile, seed)
        # Untergrenze ohne Schichtstruktur <= O <= K <= Z; O <= G (G ist für O zulässig); alle Pläne halten das Ziel im Modell
        assert p["ODP"].cost <= p["O"].cost <= p["K"].cost <= p["Z"].cost
        assert p["O"].cost <= p["G"].cost
        for key in ("Z", "K", "G", "O", "ODP"):
            assert p[key].day_sl >= 0.8 - 1e-9, (profile, seed, key)
            assert p[key].vsum == prob.v_sum(p[key].n)
            assert sum(p[key].n) == p[key].cost
        assert p["G"].day_sl >= p["K"].day_sl - 1e-12                      # G liefert mindestens die Qualität von K
        assert all(prob.sl_at(t, p["G"].n[t]) >= 0.5 - 1e-12 for t in range(24))   # Mindestwert gehalten
        assert all(p["Z"].n[t] >= c for t, c in enumerate(prob.c_target(0.8)))      # Z überdeckt c_t


def test_frozen_instances_match_the_stored_costs_of_the_messreihe():
    """Drei Zufalls-Seeds je Profil der Basiszelle: Z, K (Kosten und z), G und die Untergrenze gleich den gespeicherten Werten."""
    for profile in C.PROFILE_ORDER:
        for seed in (0, 1, 2):
            row = next(r for r in R.rows("base", profile) if r["i"] == seed)
            s, prob, p = live_plans(profile, seed, with_o=False)
            assert p["Z"].cost == R.get(row, "A", "cost")
            assert abs(p["Z"].day_sl - R.get(row, "A", "sl")) < 2e-5
            assert p["K"].cost == R.get(row, "Az", "cost")
            assert p["K"].z == pytest.approx(R.get(row, "Az", "z"))
            assert p["G"].cost == R.get(row, "BFz", "cost")
            assert p["ODP"].cost == R.get(row, "B", "dp")


def test_pipeline_is_deterministic_for_the_same_seed():
    a = live_plans("zwei_spitzen", 3, with_o=False)[2]
    b = live_plans("zwei_spitzen", 3, with_o=False)[2]
    for key in ("Z", "K", "G", "ODP"):
        assert (a[key].cost, a[key].n, a[key].z) == (b[key].cost, b[key].n, b[key].z)


def test_z_search_is_not_worse_than_the_full_grid_without_patience():
    """Vollständige Suche über das z-Raster (ohne Geduld, jedes z einzeln gelöst): K darf nicht schlechter sein."""
    for profile, seed in (("zwei_spitzen", 0), ("flach", 1), ("morgenspitze", 2)):
        s = PL.Settings(profile=profile, seed=seed, **BASE)
        prob = PL.build_problem(s)
        rhs = prob.rhs_goal(0.8)
        grid_best = None
        k = 0
        while 0.8 - k * 0.01 >= 0.30 - 1e-9:
            z = 0.8 - k * 0.01
            k += 1
            res = V.solve(prob, CATALOG, prob.c_target(z), None, time_limit=10.0)
            if res.status in ("optimal", "feasible") and res.vsum >= rhs:
                grid_best = res.cost if grid_best is None else min(grid_best, res.cost)
        live = P.plan_k(prob, CATALOG, 0.8)
        assert live.cost <= grid_best


def test_z_search_stops_after_three_failures_in_a_row_and_keeps_the_best():
    s = PL.Settings(profile="zwei_spitzen", seed=2, **BASE)
    prob = PL.build_problem(s)
    k = P.plan_k(prob, CATALOG, 0.8)
    assert 0.30 <= k.z <= 0.8
    assert k.day_sl >= 0.8 - 1e-9
    # kleineres z als das gewählte, mit den Kosten von K oder darunter, gäbe es nicht: das nächste z darunter hält das Ziel nicht bei diesen Kosten
    lb = prob.c_target(round(k.z - 0.01, 4))
    res = V.solve(prob, CATALOG, lb, None, time_limit=10.0)
    assert res.cost >= k.cost or res.vsum < prob.rhs_goal(0.8)


def test_k_equals_z_when_the_lowering_cannot_help():
    """Katalog nur 8 h, Ziel 95 %: K darf nie teurer sein als Z; z liegt zwischen Untergrenze und Ziel."""
    s = PL.Settings(profile="flach", seed=0, size="mittel", aht=240, goal=95, catalog="8")
    prob, plans, _ = PL.stage1(s)
    assert plans["K"].cost <= plans["Z"].cost
    assert C.Z_LOWER - 1e-9 <= plans["K"].z <= 0.95


def test_o_without_shift_structure_is_a_lower_bound_for_every_catalog():
    for catalog in ("8", "3/4", "3 bis 12"):
        s = PL.Settings(profile="zwei_spitzen", seed=1, size="klein", aht=240, goal=80, catalog=catalog)
        prob, plans, _ = PL.stage1(s)
        o, _ = PL.stage2(s, prob, plans)
        assert plans["ODP"].cost <= o.cost
        assert o.bound >= plans["ODP"].cost
        assert o.status in ("optimal", "feasible")
        if o.status == "optimal":
            assert o.cost == o.bound


def test_plan_o_falls_back_to_a_known_feasible_candidate_when_the_limit_is_tiny():
    s = PL.Settings(profile="flach", seed=0, size="mittel", aht=240, goal=70, catalog="6/8/10")
    prob, plans, _ = PL.stage1(s)
    o = P.plan_o(prob, s.shifts, 0.7, candidates=(plans["K"], plans["G"]), time_limit=0.1)
    assert o is not None and o.vsum >= prob.rhs_goal(0.7)
    assert o.cost <= plans["K"].cost and o.cost <= plans["G"].cost       # nie schlechter als der bekannte Fund
    assert o.status in ("optimal", "feasible")


def test_o_status_is_never_optimal_when_the_bound_is_below_the_cost():
    s = PL.Settings(profile="flach", seed=0, size="mittel", aht=480, goal=80, catalog="6/8/10")
    prob, plans, _ = PL.stage1(s)
    o = P.plan_o(prob, s.shifts, 0.8, candidates=(plans["K"],), time_limit=0.3)
    assert (o.status == "optimal") == (o.cost <= o.bound)


def test_time_limit_follows_the_peak_load():
    small = Problem([800] * 24, 240, 20)
    big = Problem([2500] * 24, 240, 20)
    assert P.time_limit_for(small) == C.TIME_LIMIT_S
    assert P.time_limit_for(big) == C.TIME_LIMIT_BIG_S


def test_shift_list_matches_the_staffing():
    s, prob, p = live_plans("zwei_spitzen", 2, with_o=True)
    for key in ("Z", "K", "G", "O"):
        n = [0] * 24
        for start, length, cnt in p[key].shifts:
            for h in range(length):
                n[(start + h) % 24] += cnt
        assert n == p[key].n, key


def test_the_z_search_gives_up_after_exactly_three_failures_in_a_row():
    """Ziel 70 %, Zwei Spitzen, Zufalls-Seed 52: nach drei Fehlschlägen bricht die Suche bei 180 Personenstunden ab; eine vierte Geduld fände 176 (z = 0,44).
    Das ist die Definition der Messreihe (drei Fehlschläge in Folge) und der Grund, warum K im feinen Raster in seltenen Fällen teurer ist als im groben."""
    s = PL.Settings(profile="zwei_spitzen", size="mittel", aht=240, goal=70, catalog="6/8/10", seed=52)
    prob = PL.build_problem(s)
    k3 = P.plan_k(prob, s.shifts, 0.7)
    assert (k3.cost, round(k3.z, 2)) == (180, 0.5)
    assert P.plan_k(prob, s.shifts, 0.7, patience=C.Z_PATIENCE + 1).cost == 176
    assert P.plan_k(prob, s.shifts, 0.7, patience=1).cost == 180


def test_a_fallback_candidate_that_meets_the_lower_bound_is_reported_as_proven():
    s = PL.Settings(profile="zwei_spitzen", seed=0, goal=95, catalog="3/4")
    prob, plans, _ = PL.stage1(s)
    o = P.plan_o(prob, s.shifts, 0.95, candidates=(plans["K"], plans["G"]), time_limit=0.0001)
    assert o.cost == plans["ODP"].cost == o.bound
    assert o.status == "optimal"


def test_plan_o_ignores_candidates_that_miss_the_daily_target():
    s = PL.Settings(profile="zwei_spitzen", seed=1, size="klein")
    prob, plans, _ = PL.stage1(s)
    fake = P.Plan(key="K", n=[0] * 24, cost=1, vsum=0, day_sl=0.0)           # billig, aber das Ziel verfehlt
    o = P.plan_o(prob, s.shifts, 0.8, candidates=(fake, plans["K"]), time_limit=0.0001)
    assert o.cost > 1 and o.vsum >= prob.rhs_goal(0.8)
