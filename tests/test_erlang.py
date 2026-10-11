"""Erlang C je Stunde: Handwerte, Tabellen, kleinste Besetzung, Tages-Servicegrad, Kennzahlen (Mini-Instanz von Hand)."""

import math

import pytest

import sgt_constants as C
from sgt_erlang import Problem, erlang_b, erlang_c, key_figures, service_level, sl_table


def test_erlang_b_hand_values():
    assert erlang_b(1, 1.0) == pytest.approx(0.5)          # B(1, a) = a / (1 + a)
    assert erlang_b(2, 1.0) == pytest.approx(0.2)          # (1/2) / (1 + 1 + 1/2) = 0,2
    assert erlang_b(0, 3.0) == 1.0


def test_erlang_c_hand_values():
    assert erlang_c(1, 0.5) == pytest.approx(0.5)          # M/M/1: C = a
    assert erlang_c(2, 1.0) == pytest.approx(1.0 / 3.0)    # M/M/2, a = 1
    assert erlang_c(3, 3.0) == 1.0 and erlang_c(2, 3.0) == 1.0   # n <= a: kein stationäres Gleichgewicht


def test_service_level_hand_values():
    # M/M/1, a = 0,5, Bediendauer 4 min, Servicezeit 1 min: SL = 1 - 0,5 * exp(-(1 - 0,5) * 1/4 * 1)
    assert service_level(1, 0.5, 4.0, 1.0) == pytest.approx(1 - 0.5 * math.exp(-0.125))
    assert service_level(3, 3.0, 4.0, 0.5) == 0.0 and service_level(2, 3.0, 4.0, 0.5) == 0.0
    assert service_level(0, 0.2, 4.0, 0.5) == 0.0


def test_service_level_equals_one_minus_wait_probability_for_zero_service_time():
    # s = 0: SL = 1 - C(n, a), die Wahrscheinlichkeit, nicht warten zu müssen
    assert service_level(2, 1.0, 4.0, 0.0) == pytest.approx(1 - 1.0 / 3.0)


def test_table_is_monotone_starts_at_zero_and_ends_at_one(mini):
    for t in range(mini.tlen):
        tab = mini.tab[t]
        assert tab[0] == 0.0
        assert all(tab[i] <= tab[i + 1] + 1e-15 for i in range(len(tab) - 1))
        assert tab[-1] >= 1 - 1e-7
        assert all(tab[n] == 0.0 for n in range(0, int(mini.a[t]) + 1))


def test_c_target_is_the_smallest_staffing_reaching_the_goal(mini):
    for goal in (0.5, 0.8, 0.95):
        c = mini.c_target(goal)
        for t in range(mini.tlen):
            assert mini.sl_at(t, c[t]) >= goal - 1e-12
            assert c[t] == 0 or mini.sl_at(t, c[t] - 1) < goal


def test_v_table_is_the_floored_scaled_service_level(mini):
    for t in range(mini.tlen):
        for n in range(mini.cap[t] + 1):
            assert mini.v[t][n] == math.floor(mini.a_cent[t] * mini.tab[t][n] * C.SKALA + 1e-9)
            assert mini.v[t][n] <= mini.a_cent[t] * mini.tab[t][n] * C.SKALA + 1e-6


def test_day_service_level_is_the_arrival_weighted_mean(mini):
    n = [2, 3, 1, 2]
    expect = sum(mini.a_cent[t] * mini.sl_at(t, n[t]) for t in range(4)) / sum(mini.a_cent)
    assert mini.day_sl(n) == pytest.approx(expect)
    assert mini.day_sl([0, 0, 0, 0]) == 0.0


def test_rhs_goal_is_rounded_up_and_reached_only_by_a_plan_meeting_the_goal(mini):
    rhs = mini.rhs_goal(0.8)
    assert rhs == math.ceil(0.8 * sum(mini.a_cent) * C.SKALA - 1e-9)
    n_ok = mini.c_target(0.8)
    assert mini.v_sum(n_ok) >= rhs
    assert mini.day_sl(n_ok) >= 0.8


def test_key_figures_count_hours_below_half_and_empty_hours(mini):
    f = key_figures(mini, [0, 3, 0, 1])
    assert f["cost"] == 4
    assert f["empty"] == 2
    assert f["sl_min"] == 0.0
    below = [t for t in range(4) if mini.sl_at(t, [0, 3, 0, 1][t]) < 0.5]
    assert f["n_hours_below"] == len(below)
    assert f["hours_below"] == pytest.approx(len(below) / 4)
    assert f["calls_below"] == pytest.approx(sum(mini.a_cent[t] for t in below) / sum(mini.a_cent))


def test_sl_table_ends_exactly_when_the_service_level_is_one_to_1e7():
    tab = sl_table(1.0, 4.0, 1.0 / 3.0)
    assert tab[-1] >= 1 - 1e-7 and tab[-2] < 1 - 1e-7


def test_problem_scales_load_with_aht_and_keeps_call_counts():
    base = Problem([100, 200], aht_s=240)
    long = Problem([200, 400], aht_s=480)
    assert long.a == [2 * x for x in base.a]
    assert long.aht == 2 * base.aht


def test_mini_instance_hand_value(mini):
    # Stunde 0: a = 0,6, ein Bediener: C = 0,6, SL = 1 - 0,6 * exp(-(1 - 0,6) * (20 s / 240 s)) = 1 - 0,6 * exp(-1/30)
    assert mini.sl_at(0, 1) == pytest.approx(1 - 0.6 * math.exp(-1.0 / 30.0))
    assert mini.sl_at(0, 0) == 0.0


def test_rhs_goal_is_never_below_the_exact_integer_value_and_at_most_one_unit_above():
    """goal * Σa * SKALA ist für 70, 80, 90 und 95 % eine ganze Zahl; Gleitkommarauschen darf höchstens um eine Werteeinheit aufrunden
    (so rechnet die Messreihe, die Reproduktion bleibt gleich), nie darunter: abgerundete rechte Seiten ließen Pläne unter dem Ziel zu."""
    for goal in (0.7, 0.8, 0.9, 0.95):
        exact_per_unit = round(goal * 100) * 1000
        for w in range(100, 400):
            prob = Problem([w], 240, 20)
            assert exact_per_unit * w <= prob.rhs_goal(goal) <= exact_per_unit * w + 1
