"""Ereignissimulation: Bitgleichheit mit der Vorab-Messreihe, Randfälle, Zählung je Handler und Tag."""

import math

import pytest

import sgt_constants as C
import sgt_results as R
import sgt_sim as S
from sgt_erlang import Problem, service_level
from sgt_rng import seed_from


def test_bitwise_equal_to_the_stored_simulations_of_the_messreihe():
    """Pläne und a_cent der ersten zwei Instanzen je Profil der Basiszelle sind gespeichert, ebenso die simulierten Tages-Servicegrade."""
    n_checked = 0
    for row in R.rows("base"):
        if "plans" not in row or row["v"]["A"][R.FIELD["sim"]] is None:
            continue
        prob = Problem(row["a_cent"], 240, 20)
        for v in ("A", "B"):
            plan = row["plans"][v]
            res = S.simulate(prob, plan, days=40, warm=3, seed=seed_from("sim", row["art"], row["i"], v))
            assert round(res["sl_day"], 5) == row["v"][v][R.FIELD["sim"]], (row["art"], row["i"], v)
            n_checked += 1
    assert n_checked >= 10


def test_constant_plan_matches_erlang_c_within_noise():
    for a, c, aht in ((4.0, 6, 240), (10.0, 13, 240), (2.0, 3, 120)):
        prob = Problem([int(a * 100)] * 24, aht, 20)
        res = S.simulate(prob, [c] * 24, days=300, warm=3, seed=11)
        expected = service_level(c, a, prob.aht, prob.s_min)
        band = max(0.012, 3 * math.sqrt(expected * (1 - expected) / res["n"]))
        assert abs(res["sl_day"] - expected) < band, (a, c)


def test_plan_without_operators_gives_exactly_zero_and_counts_arrivals():
    prob = Problem([300] * 24, 240, 20)
    res = S.simulate(prob, [0] * 24, days=5, warm=1, seed=3)
    assert res["sl_day"] == 0.0 and res["n"] > 0


def test_huge_staffing_gives_almost_one():
    prob = Problem([300] * 24, 240, 20)
    assert S.simulate(prob, [200] * 24, days=5, warm=1, seed=3)["sl_day"] > 0.999


def test_arrival_count_matches_expectation():
    prob = Problem([300] * 24, 240, 20)
    expected = 24 * 3.0 / 4.0 * 60 * 20          # 20 Tage: 3 Erlang bei 4 min Bediendauer = 0,75 Anrufe je Minute
    res = S.simulate(prob, [10] * 24, days=20, warm=1, seed=5)
    assert abs(res["n"] - expected) < 5 * math.sqrt(expected)


def test_backlog_behind_a_closed_block_is_visible_in_the_first_open_hours():
    """Niemand in den Stunden 0 bis 11, danach 8 Bediener bei 3 Erlang: die stationäre Rechnung sagt für Stunde 12 fast 1, die Simulation fast 0."""
    prob = Problem([300] * 24, 240, 20)
    res = S.simulate(prob, [0] * 12 + [8] * 12, days=10, warm=1, seed=9)
    sl_h = [res["ok"][h] / res["calls"][h] for h in range(24)]
    assert all(sl_h[h] == 0.0 for h in range(12))
    assert service_level(8, 3.0, 4.0, 20 / 60) > 0.99
    assert sl_h[12] < 0.2
    assert sl_h[23] > 0.97


def test_every_arrival_counts_not_only_served_calls():
    """Sechs Bediener nur in Stunde 0, danach keiner: die meisten Anrufe werden nie bedient und müssen im Nenner stehen."""
    prob = Problem([300] * 24, 240, 20)
    res = S.simulate(prob, [6] + [0] * 23, days=3, warm=1, seed=2)
    assert res["n"] == sum(res["calls"])
    assert res["sl_day"] < 0.1
    assert sum(res["ok"]) < 0.1 * res["n"]


def test_day_tallies_add_up_to_the_hour_tallies():
    prob = Problem([200] * 24, 240, 20)
    res = S.simulate(prob, [5] * 24, days=7, warm=2, seed=4)
    assert sum(res["calls_day"]) == sum(res["calls"]) == res["n"]
    assert sum(res["ok_day"]) == sum(res["ok"])
    assert len(res["calls_day"]) == 7 and all(c > 0 for c in res["calls_day"])


def test_simulation_is_deterministic_per_seed_and_differs_between_seeds():
    prob = Problem([200] * 24, 240, 20)
    a = S.simulate(prob, [4] * 24, days=5, warm=1, seed=1)
    assert a == S.simulate(prob, [4] * 24, days=5, warm=1, seed=1)
    assert a != S.simulate(prob, [4] * 24, days=5, warm=1, seed=2)


def test_warm_up_removes_the_empty_start_bias_at_large_load():
    """Bei 20 Erlang und knapper Besetzung läuft ein leer gestartetes System ein; mit Einschwingzeit stimmt der Mittelwert mit Erlang C."""
    prob = Problem([2000] * 24, 240, 20)
    c = 23
    expected = service_level(c, 20.0, prob.aht, prob.s_min)
    sims = [S.simulate(prob, [c] * 24, days=10, warm=C.SIM_WARM_DAYS, seed=100 + r)["sl_day"] for r in range(8)]
    assert abs(sum(sims) / len(sims) - expected) < 0.02


def test_mean_and_se_from_day_means():
    res = {"ok_day": [8, 9, 7, 10], "calls_day": [10, 10, 10, 10], "sl_day": 0.85}
    m, se = S.mean_and_se(res)
    assert m == 0.85
    sl = [0.8, 0.9, 0.7, 1.0]
    mu = sum(sl) / 4
    sd = math.sqrt(sum((x - mu) ** 2 for x in sl) / 3)
    assert se == pytest.approx(sd / 2)


def test_days_for_budget_is_clamped_and_follows_the_load():
    small = Problem([100] * 24, 240, 20)       # 1 Erlang: 15 Anrufe je Stunde
    big = Problem([4000] * 24, 240, 20)
    assert S.days_for_budget(small) == C.SIM_DAYS_MAX
    assert S.days_for_budget(big) == C.SIM_DAYS_MIN
    mid = Problem([1000] * 24, 240, 20)        # 10 Erlang: 150 je Stunde, 3.600 je Tag
    assert S.days_for_budget(mid) == round(C.CALL_BUDGET / 3600)
