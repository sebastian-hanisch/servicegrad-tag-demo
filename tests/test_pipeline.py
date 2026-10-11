"""Live-Pipeline: Einstellungen, Stufen, Simulationsseeds, Statusangaben."""

import pytest

import sgt_constants as C
import sgt_pipeline as PL
import sgt_plans as P
from sgt_erlang import Problem
from sgt_rng import seed_from


def test_settings_are_a_frozen_keyword_dataclass_with_catalog_lookup():
    s = PL.Settings(profile="flach", size="gross", aht=120, goal=95, catalog="3 bis 12", seed=7)
    assert s.shifts == tuple(range(3, 13)) and s.goal_fraction == 0.95
    with pytest.raises(Exception):
        s.goal = 80                                   # eingefroren
    assert PL.Settings() == PL.Settings(profile=C.DEFAULT_PROFILE, size=C.DEFAULT_SIZE, aht=C.DEFAULT_AHT, goal=C.DEFAULT_GOAL,
                                        catalog=C.DEFAULT_CATALOG, seed=C.DEFAULT_SEED)


def test_sim_seed_follows_the_naming_of_the_messreihe_and_separates_plans_and_instances():
    s = PL.Settings(profile="zwei_spitzen", seed=2)
    assert PL.sim_seed(s, "Z") == seed_from("sim", "zwei_spitzen", 2, "A")
    assert PL.sim_seed(s, "K") == seed_from("sim", "zwei_spitzen", 2, "Az")
    assert PL.sim_seed(s, "G") == seed_from("sim", "zwei_spitzen", 2, "BFz")
    assert PL.sim_seed(s, "O") == seed_from("sim", "zwei_spitzen", 2, "B")
    assert len({PL.sim_seed(s, k) for k in C.PLAN_KEYS}) == 4
    assert PL.sim_seed(s, "Z") != PL.sim_seed(PL.Settings(profile="zwei_spitzen", seed=3), "Z")


def test_the_three_stages_return_what_run_live_assembles():
    s = PL.Settings(profile="flach", size="klein", seed=3)
    prob, plans, s1 = PL.stage1(s)
    assert set(plans) >= {"Z", "K", "G", "ODP"} and s1 > 0
    o, s2 = PL.stage2(s, prob, plans)
    assert o.key == "O"
    plans["O"] = o
    sims, s3 = PL.stage3(s, prob, plans)
    assert set(sims) == {"Z", "K", "G", "O"}
    for sim in sims.values():
        assert 0.0 <= sim.sl <= 1.0 and sim.se >= 0 and sim.days >= C.SIM_DAYS_MIN
        assert len(sim.hours_sl) == 24 and sum(sim.hours_calls) == sim.calls
    live = PL.run_live(s, with_sim=True)
    assert live.plans["Z"].cost == plans["Z"].cost and live.plans["K"].cost == plans["K"].cost
    assert live.sims["Z"].sl == sims["Z"].sl                    # gleiche Simulationsseeds und Tageszahl: gleiches Ergebnis


def test_o_status_is_optimal_when_the_cost_meets_the_bound():
    """Stresszelle (Katalog 3/4 h, Ziel 95 %): O fällt auf die Untergrenze ohne Schichtstruktur, der Beweis ist die Gleichheit der Kosten."""
    s = PL.Settings(profile="zwei_spitzen", seed=0, goal=95, catalog="3/4")
    prob, plans, _ = PL.stage1(s)
    o, _ = PL.stage2(s, prob, plans)
    assert o.cost == plans["ODP"].cost and o.status == "optimal" and o.bound == o.cost


def test_k_reaches_the_lower_bound_of_the_z_search_with_8_hour_shifts():
    """Katalog nur 8 h: die Schichtlänge erzwingt die Übererfüllung, das Stundenziel sinkt bis zur Untergrenze 0,30 der Suche."""
    s = PL.Settings(profile="nachtgrund", seed=0, catalog="8")
    prob, plans, _ = PL.stage1(s)
    assert plans["K"].z == pytest.approx(C.Z_LOWER)
    assert plans["K"].cost == 232 and plans["Z"].cost == 296      # gespeicherte Werte der Messreihe (Zelle Katalog nur 8 h)


def test_problem_scales_with_the_aht_setting_and_keeps_call_counts():
    base = PL.build_problem(PL.Settings(aht=240, seed=4))
    long = PL.build_problem(PL.Settings(aht=480, seed=4))
    assert long.aht_s == 480 and base.aht_s == 240
    assert long.a_cent == [2 * x for x in base.a_cent]


def test_time_limit_follows_the_peak_not_the_mean():
    spike = Problem([100] * 23 + [2500], 240, 20)                 # Spitze 25 Erlang, Mittel klein
    assert P.time_limit_for(spike) == C.TIME_LIMIT_BIG_S
    assert P.time_limit_for(Problem([1900] * 24, 240, 20)) == C.TIME_LIMIT_S


def test_stage3_counts_after_the_warm_up_days_and_with_the_plan_specific_stream():
    import sgt_sim as S
    s = PL.Settings(profile="flach", size="klein", seed=2)
    prob, plans, _ = PL.stage1(s)
    sims, _ = PL.stage3(s, prob, plans, keys=("Z",))
    days = S.days_for_budget(prob)
    direct = S.simulate(prob, plans["Z"].n, days=days, warm=C.SIM_WARM_DAYS, seed=PL.sim_seed(s, "Z"))
    assert sims["Z"].sl == direct["sl_day"] and sims["Z"].calls == direct["n"] and sims["Z"].days == days
    no_warm = S.simulate(prob, plans["Z"].n, days=days, warm=0, seed=PL.sim_seed(s, "Z"))
    assert no_warm["sl_day"] != direct["sl_day"] or no_warm["calls_day"] != direct["calls_day"]
