"""Schichtüberdeckung (HiGHS): Schichttypen, jede Nebenbedingungsfamilie einzeln, Vollaufzählung auf T = 4."""

import itertools

import numpy as np
import pytest
from scipy.sparse import issparse

import sgt_cover as V
from sgt_erlang import Problem
from sgt_rng import SplitMix64, seed_from

CATALOG = (2, 3)


def test_shift_types_are_cyclic_and_skip_too_long_shifts():
    s = V.shift_types((2, 3), 4)
    assert len(s) == 8
    assert (3, 2, (3, 0)) in s                      # Schicht von 3 bis 1 Uhr, über die Tagesgrenze
    assert V.shift_types((5,), 4) == []
    assert [x[1] for x in V.shift_types((3, 2), 4)] == [2, 2, 2, 2, 3, 3, 3, 3]


def full_vector(prob, shifts, lb, x, binary_force=False):
    """Spaltenvektor des Modells (Schichten, dann Zuwachs-Variablen je Stunde) für die Schichtzahlen x: die ersten (n_t - lb_t) Zuwächse auf 1."""
    n = [0] * prob.tlen
    for j, s in enumerate(shifts):
        for t in s[2]:
            n[t] += x[j]
    vec = list(x)
    for t in range(prob.tlen):
        k_count = max(0, prob.cap[t] - lb[t])
        use = max(0, n[t] - lb[t])
        vec += [1.0 if i < use else 0.0 for i in range(k_count)]
    return np.array(vec, dtype=float), n


def rows_ok(model, vec):
    obj, A, lo, hi, integrality, bounds = model
    r = A @ vec
    return bool(np.all(r >= lo - 1e-9) and np.all(r <= hi + 1e-9)), r


def test_cover_family_a_feasible_cover_passes_and_an_uncovered_hour_is_rejected(mini):
    shifts = V.shift_types(CATALOG, 4)
    lb = [1, 1, 1, 1]
    model = V.build_model(mini, shifts, lb, with_value=True, rhs=None, cost_cap=None, cost_floor=None, objective="cost")
    x = [0] * len(shifts)
    x[0] = 1; x[2] = 1                      # Schichten (0,2) und (2,2) decken alle vier Stunden einmal
    vec, n = full_vector(mini, shifts, lb, x)
    assert n == [1, 1, 1, 1]
    assert rows_ok(model, vec)[0]
    x[2] = 0                                 # Stunden 2 und 3 unbesetzt: Überdeckungszeile verletzt
    vec2, _ = full_vector(mini, shifts, lb, x)
    assert not rows_ok(model, vec2)[0]


def test_cover_family_value_row_accepts_enough_value_and_rejects_too_little(mini):
    shifts = V.shift_types(CATALOG, 4)
    lb = [0, 0, 0, 0]
    rhs = mini.rhs_goal(0.8)
    model = V.build_model(mini, shifts, lb, True, rhs, None, None, "cost")
    good = mini.c_target(0.8)
    # Besetzung gut = c_target; als Schichten mit Länge 2 und 3 darstellbar? Benutze viele Schichten: jede Stunde mit einer Länge-3-Schicht abdecken
    x = [0] * len(shifts)
    for j, s in enumerate(shifts):
        if s[1] == 3:
            x[j] = max(good)                 # alle Länge-3-Schichten max(good)-mal: jede Stunde dreifach gedeckt mal max(good)
    vec, n = full_vector(mini, shifts, lb, x)
    assert mini.v_sum(n) >= rhs and rows_ok(model, vec)[0]
    vec_bad, n_bad = full_vector(mini, shifts, lb, [0] * len(shifts))
    assert mini.v_sum(n_bad) < rhs and not rows_ok(model, vec_bad)[0]


def test_cover_family_binary_chain_orders_the_increments(mini):
    shifts = V.shift_types(CATALOG, 4)
    lb = [0, 0, 0, 0]
    model = V.build_model(mini, shifts, lb, True, None, None, None, "cost", force_binary=True)
    obj, A, lo, hi, integrality, bounds = model
    assert integrality[len(shifts):].min() == 1       # alle Zuwächse binär
    x = [1] + [0] * (len(shifts) - 1)
    vec, n = full_vector(mini, shifts, lb, x)
    assert rows_ok(model, vec)[0]
    # Kette verletzen: ein späterer Zuwachs ohne den früheren
    start = len(shifts)
    broken = vec.copy()
    t_hour = next(t for t in range(4) if n[t] >= 1)
    offset = start + sum(max(0, mini.cap[u] - lb[u]) for u in range(t_hour))
    broken[offset] = 0.0
    broken[offset + 1] = 1.0
    assert not rows_ok(model, broken)[0]


def test_cover_family_cost_cap_and_floor(mini):
    shifts = V.shift_types(CATALOG, 4)
    lb = [1, 1, 1, 1]
    x = [0] * len(shifts)
    x[0] = 1
    x[2] = 1                                  # Kosten 4
    vec, _ = full_vector(mini, shifts, lb, x)
    assert rows_ok(V.build_model(mini, shifts, lb, True, None, 4, None, "cost"), vec)[0]
    assert not rows_ok(V.build_model(mini, shifts, lb, True, None, 3, None, "cost"), vec)[0]     # Obergrenze 3 < 4
    assert rows_ok(V.build_model(mini, shifts, lb, True, None, None, 4, "cost"), vec)[0]
    assert not rows_ok(V.build_model(mini, shifts, lb, True, None, None, 5, "cost"), vec)[0]     # Untergrenze 5 > 4


def test_concave_hours_flags_the_s_shape_from_zero_and_accepts_it_from_the_target(mini):
    from_zero = V.concave_hours(mini, [0] * 4)
    assert not all(from_zero)                           # S-Kurve ab 0: Zuwächse 0, ..., 0, groß, kleiner
    from_target = V.concave_hours(mini, mini.c_target(0.8))
    assert all(from_target)


def brute_force(prob, tlen, lb, rhs, xmax=3):
    """Alle Schichtzahlen 0..xmax je Typ: kleinste Kosten mit n_t >= lb_t und Wertesumme >= rhs, dabei größte Wertesumme."""
    shifts = V.shift_types(CATALOG, tlen)
    A = np.zeros((len(shifts), tlen), dtype=np.int32)
    L = np.zeros(len(shifts), dtype=np.int32)
    for j, s in enumerate(shifts):
        for t in s[2]:
            A[j, t] = 1
        L[j] = s[1]
    X = np.indices((xmax + 1,) * len(shifts), dtype=np.int8).reshape(len(shifts), -1).T.astype(np.int32)
    N = X @ A
    cost = X @ L
    ok = np.ones(N.shape[0], dtype=bool)
    for t in range(tlen):
        ok &= N[:, t] >= lb[t]
    vs = np.zeros(N.shape[0], dtype=np.int64)
    for t in range(tlen):
        tab = np.array(prob.v[t] + [prob.v[t][-1]] * (int(N[:, t].max()) + 2), dtype=np.int64)
        vs += tab[np.minimum(N[:, t], len(tab) - 1)]
    if rhs is not None:
        ok &= vs >= rhs
    if not ok.any():
        return None
    cmin = int(cost[ok].min())
    sel = ok & (cost == cmin)
    return cmin, int(vs[sel].max()), int(X[sel].max())


def test_highs_matches_full_enumeration_for_z_g_and_o_type_models():
    rng = SplitMix64(seed_from("cover-brute"))
    compared = 0
    for i in range(24):
        prob = Problem([rng.randint(15, 110) for _ in range(4)], 240, 20)
        goal = (0.7, 0.8, 0.9)[i % 3]
        cases = {"Z": (prob.c_target(goal), None), "G": (prob.c_target(0.5), prob.rhs_goal(goal)), "O": ([0] * 4, prob.rhs_goal(goal))}
        for name, (lb, rhs) in cases.items():
            bf = brute_force(prob, 4, lb, rhs)
            res = V.solve(prob, CATALOG, lb, rhs, time_limit=20.0, stage2=True, stage2_limit=20.0)
            if bf is None or bf[2] >= 3:        # unzulässig oder an der Aufzählungsgrenze: nicht vergleichbar
                continue
            assert res.status == "optimal", (i, name)
            assert res.cost == bf[0], (i, name)
            assert res.vsum == bf[1], (i, name)
            assert all(res.n[t] >= lb[t] for t in range(4))
            compared += 1
    assert compared >= 50


def test_solution_vector_is_integral_and_cost_equals_sum_of_shift_lengths(mini):
    lb = mini.c_target(0.8)
    res = V.solve(mini, CATALOG, lb, None, time_limit=10.0)
    shifts = V.shift_types(CATALOG, 4)
    assert res.cost == sum(s[1] * res.x[j] for j, s in enumerate(shifts)) == sum(res.n)
    assert all(isinstance(v, int) and v >= 0 for v in res.x)


def test_catalog_with_a_length_one_shift_reaches_the_pattern_cost(mini5):
    """Mit Länge 1 im Katalog ist jedes Muster darstellbar: die Kosten sind die Summe der Besetzung, also das DP-Ergebnis."""
    from sgt_dp import dp_no_shifts
    rhs = mini5.rhs_goal(0.8)
    dp = dp_no_shifts(mini5, [0] * 5, rhs)
    res = V.solve(mini5, (1, 2, 3), [0] * 5, rhs, time_limit=20.0, cost_floor=dp[0])
    assert res.status == "optimal" and res.cost == dp[0]


def test_infeasible_cap_is_reported_as_infeasible(mini):
    lb = mini.c_target(0.8)
    res = V.min_cost(mini, CATALOG, lb, None, time_limit=10.0, cost_cap=1)
    assert res.status == "infeasible"


def test_model_matrix_is_sparse(mini):
    shifts = V.shift_types(CATALOG, 4)
    obj, A, lo, hi, integ, bounds = V.build_model(mini, shifts, [0] * 4, True, mini.rhs_goal(0.8), None, None, "cost")
    assert issparse(A) and A.shape[1] == len(obj) == len(integ)


def test_a_shift_as_long_as_the_day_is_allowed():
    assert len(V.shift_types((4,), 4)) == 4


def test_validity_guard_rejects_lower_bound_violations_and_a_missing_value_sum(mini):
    lb = mini.c_target(0.8)
    rhs = mini.rhs_goal(0.8)
    assert V._valid(mini, list(lb), lb, rhs)
    assert not V._valid(mini, [lb[0] - 1] + list(lb[1:]), lb, None)          # Untergrenze verletzt
    assert not V._valid(mini, [0, 0, 0, 0], [0, 0, 0, 0], rhs)               # Wertesumme zu klein
    assert V._valid(mini, [0, 0, 0, 0], [0, 0, 0, 0], None)
