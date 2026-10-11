"""Orakel-Tests: die Kernroutinen gegen einen anderen Rechenweg (DEMO-PLAYBOOK §12, ORACLE-PLAYBOOK §2: Warteschlangen, Scheduling, LP).

  Erlang C         gegen die Lehrbuchsumme in Brüchen (fractions) und den Servicegrad gegen die abgeschnittene Markow-Kette mit Wartezeit
                   über die Poisson-Verteilung (scipy), unabhängig von der geschlossenen Formel
  c_t(z)           gegen Brute Force über n und die Monotonie des Servicegrads
  Konkavität       Zuwächse ab c_t(z) nichtsteigend für z >= 0,5 (Test, kein Beweis), Gegenbeispiel bei z = 0,3
  Überdeckung      HiGHS gegen CP-SAT (OR-Tools, anderer Löser, eigene Modellbauweise): Kosten gleich, wenn beide beweisen; Schranke nie über dem
                   CP-SAT-Optimum (die Dualschranke trug einmal Rauschen und lag um eins zu hoch)
  Aufzählung       Vollaufzählung der Schichtüberdeckung (T = 4) und aller Besetzungsmuster (DP): tests/test_cover.py, tests/test_dp.py
  Simulation       gegen Erlang C und die Rückstau-Rechnung: tests/test_sim.py
"""

import math
from fractions import Fraction

import numpy as np
import pytest
from scipy.stats import poisson

import sgt_cover as V
import sgt_dp as D
from sgt_erlang import Problem, erlang_c, service_level
from sgt_rng import SplitMix64, seed_from


def erlang_c_fraction(c, a):
    """Lehrbuchsumme: C = (a^c / c! * c / (c - a)) / (sum_{k<c} a^k / k! + a^c / c! * c / (c - a)) in exakten Brüchen."""
    a = Fraction(a).limit_denominator(10**6)
    term, s = Fraction(1), Fraction(0)
    for k in range(c):
        s += term
        term = term * a / (k + 1)
    top = term * c / (c - a)
    return float(top / (s + top))


def service_level_chain(c, a, mu, s):
    """P(W <= s) über die Zahl der Anrufe im System (PASTA): abgeschnittene Kette, W bedingt auf n >= c als Poisson-Verteilung (Erlang)."""
    nmax = c + 4000
    logs = [0.0]
    for n in range(1, nmax + 1):
        logs.append(logs[-1] + math.log(a * mu) - math.log(min(n, c) * mu))
    w = np.exp(np.array(logs) - max(logs))
    pi = w / w.sum()
    ns = np.arange(c, nmax + 1)
    return 1.0 - float(np.sum(pi[c:] * poisson.cdf(ns - c, c * mu * s)))


def test_erlang_c_against_the_textbook_sum_in_fractions():
    rng = SplitMix64(seed_from("erlang-fraction"))
    worst = 0.0
    n = 0
    for _ in range(300):
        c = rng.randint(1, 60)
        a = round(min(rng.randint(1, 100 * c - 1) / 100.0 * 0.999, c - 0.02), 2)
        if a <= 0 or a >= c:
            continue
        worst = max(worst, abs(erlang_c(c, a) - erlang_c_fraction(c, a)))
        n += 1
    assert n >= 250 and worst < 1e-9


def test_service_level_against_the_truncated_markov_chain():
    rng = SplitMix64(seed_from("erlang-chain"))
    worst = 0.0
    for _ in range(40):
        c = rng.randint(1, 40)
        a = round(min(rng.randint(10, 100 * c - 20) / 100.0, c - 0.05), 2)
        aht = rng.randint(60, 600) / 60.0
        s = rng.randint(5, 90) / 60.0
        worst = max(worst, abs(service_level(c, a, aht, s) - service_level_chain(c, a, 1.0 / aht, s)))
    assert worst < 1e-7


def test_c_target_against_brute_force_over_n():
    rng = SplitMix64(seed_from("c-target"))
    for _ in range(40):
        prob = Problem([rng.randint(10, 4000) for _ in range(6)], 240, 20)
        for goal in (0.5, 0.8, 0.95):
            c = prob.c_target(goal)
            for t in range(6):
                direct = next(n for n in range(0, 10**4) if service_level(n, prob.a[t], prob.aht, prob.s_min) >= goal - 1e-12)
                assert c[t] == direct


def test_increments_are_nonincreasing_from_the_target_but_not_from_zero():
    """Konkavität ab c_t(z) (gemessen, kein Beweis): für z = 0,3, 0,5 und 0,7 keine Verletzung in 60 Demo-Instanzen (klein bei 120 s, mittel bei
    240 s); ab 0 ist die Kurve S-förmig (erst Null bis zum Angebot, dann steil): dort braucht das Modell die Binärkette (Variante O)."""
    import sgt_constants as C
    import sgt_instance as I
    violations = {0.3: 0, 0.5: 0, 0.7: 0}
    s_shaped = 0
    n = 0
    for size, aht in (("klein", 120), ("mittel", 240)):
        for profile in C.PROFILE_ORDER:
            for i in range(6):
                prob = Problem(I.a_cent_at(I.instance_for(profile, size, i), aht), aht, 20)
                n += 1
                for z in violations:
                    if not all(V.concave_hours(prob, prob.c_target(z))):
                        violations[z] += 1
                if not all(V.concave_hours(prob, [0] * 24)):
                    s_shaped += 1
    assert n == 60
    assert violations == {0.3: 0, 0.5: 0, 0.7: 0}
    assert s_shaped == n


def small_problem(profile, seed):
    import sgt_pipeline as PL
    return PL.build_problem(PL.Settings(profile=profile, size="klein", seed=seed))


@pytest.mark.parametrize("profile,seed", [("zwei_spitzen", 0), ("flach", 1), ("nachtgrund", 2)])
def test_highs_against_cpsat_for_z_g_and_o_type_models(profile, seed):
    pytest.importorskip("ortools")
    from oracle_cpsat import solve_cpsat
    prob = small_problem(profile, seed)
    catalog = (6, 8, 10)
    rhs = prob.rhs_goal(0.8)
    k_rhs = prob.v_sum(prob.c_target(0.8))             # irgendein erreichbarer Wert für G
    cases = {"Z": (prob.c_target(0.8), None), "G": (prob.c_target(0.5), k_rhs), "O": ([0] * 24, rhs)}
    for name, (lb, r) in cases.items():
        cut = D.dp_no_shifts(prob, lb, r if r is not None else 0)
        hi = V.min_cost(prob, catalog, lb, r, time_limit=15.0, cost_floor=cut[0])
        status, cost, bound, _ = solve_cpsat(prob, catalog, lb, r, time_limit=30.0)
        assert status in ("optimal", "feasible"), (name, status)
        assert hi.status in ("optimal", "feasible")
        if status == "optimal":
            assert hi.bound <= cost, (name, hi.bound, cost)            # Schranke nie über dem Optimum
            assert hi.cost >= cost
            if hi.status == "optimal":
                assert hi.cost == cost, (name, hi.cost, cost)
        assert hi.cost >= cut[0]                                       # Untergrenze ohne Schichtstruktur
        assert hi.vsum == prob.v_sum(hi.n) and (r is None or hi.vsum >= r)


def test_dual_bound_never_exceeds_the_optimum_under_a_tight_time_limit():
    """Regression: die Dualschranke trägt Rauschen (402,0000001 wurde zu 403 aufgerundet und der Fund 403 als optimal gemeldet)."""
    pytest.importorskip("ortools")
    from oracle_cpsat import solve_cpsat
    import sgt_constants as C
    import sgt_instance as I
    prob = Problem(I.a_cent_at(I.make_instance("flach", *C.SIZES["mittel"], 79), 240), 240, 20)
    cat = C.CATALOGS["3/4/5"]
    rhs = prob.rhs_goal(0.8)
    optimum = solve_cpsat(prob, cat, [0] * 24, rhs, time_limit=60.0)
    assert optimum[0] == "optimal" and optimum[1] == 402
    for limit in (0.3, 0.6):
        res = V.min_cost(prob, cat, [0] * 24, rhs, time_limit=limit, cost_floor=D.dp_no_shifts(prob, [0] * 24, rhs)[0])
        assert res.bound <= 402
        assert not (res.status == "optimal" and res.cost != 402)
