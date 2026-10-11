"""Rucksack-Rechnung ohne Schichtstruktur gegen die Aufzählung aller Besetzungsmuster."""

import itertools

import pytest

from sgt_dp import dp_no_shifts, unit_best_table
from sgt_erlang import Problem
from sgt_rng import SplitMix64, seed_from


def enumerate_best(prob, lb, rhs):
    """Aufzählung aller Muster n_t in [lb_t, cap_t]: kleinste Kosten mit Wertesumme >= rhs, dabei größte Wertesumme."""
    ranges = [range(lb[t], prob.cap[t] + 1) for t in range(prob.tlen)]
    best = None
    for n in itertools.product(*ranges):
        v = sum(prob.v[t][n[t]] for t in range(prob.tlen))
        if v < rhs:
            continue
        key = (sum(n), -v)
        if best is None or key < best[0]:
            best = (key, list(n))
    return None if best is None else (best[0][0], -best[0][1], best[1])


def random_problem(rng, tlen=5):
    return Problem([rng.randint(15, 120) for _ in range(tlen)], 240, 20)


def test_dp_matches_enumeration_on_random_small_instances():
    rng = SplitMix64(seed_from("dp-enum"))
    n_checked = 0
    for i in range(30):
        prob = random_problem(rng)
        goal = (0.5, 0.7, 0.8, 0.9)[i % 4]
        lb = [0] * 5 if i % 3 else prob.c_target(0.5)
        rhs = prob.rhs_goal(goal)
        brute = enumerate_best(prob, lb, rhs)
        got = dp_no_shifts(prob, lb, rhs)
        assert (got is None) == (brute is None)
        if brute is None:
            continue
        cost, n, vsum = got
        assert cost == brute[0], i
        assert vsum == brute[1], i                   # zweite Stufe: bester Wert bei gleichen Kosten
        assert sum(n) == cost and prob.v_sum(n) == vsum >= rhs
        assert all(n[t] >= lb[t] for t in range(5))
        n_checked += 1
    assert n_checked >= 25


def test_dp_hand_example_with_one_hour(mini):
    """Eine Stunde, a = 0,6: das kleinste n mit SL >= 0,8 ist das Ergebnis der Rechnung (ein Tag aus einer Stunde)."""
    one = Problem([60], 240, 20)
    cost, n, _ = dp_no_shifts(one, [0], one.rhs_goal(0.8))
    assert n == one.c_target(0.8) and cost == n[0]


def test_dp_respects_lower_bounds_and_reports_unreachable_targets(mini):
    lb = [2, 2, 2, 2]
    cost, n, _ = dp_no_shifts(mini, lb, 0)
    assert n == lb and cost == 8
    assert dp_no_shifts(mini, [0, 0, 0, 0], sum(mini.v_at(t, 10**6) for t in range(4)) + 1) is None


def test_dp_cost_is_a_lower_bound_for_any_pattern_meeting_the_target(mini):
    rhs = mini.rhs_goal(0.8)
    cost = dp_no_shifts(mini, [0] * 4, rhs)[0]
    for n in itertools.product(range(0, 6), repeat=4):
        if mini.v_sum(n) >= rhs:
            assert sum(n) >= cost


def test_unit_best_table_first_hour_equals_the_value_table(mini):
    kmax = sum(mini.cap) + 1
    best, choices = unit_best_table(Problem([60], 240, 20), [0], kmax)
    one = Problem([60], 240, 20)
    for c in range(0, one.cap[0] + 1):
        assert best[c] == one.v[0][c]
    assert best[one.cap[0] + 1] == -1
