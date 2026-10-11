"""Live-Rechnung in drei Stufen für eine Instanz: Stufe 1 (Z, K, G, O ohne Schichtstruktur), Stufe 2 (O mit Schichten), Stufe 3 (Simulation).

Jede Stufe ist eine Funktion mit ausdrücklichen Ein- und Ausgaben; `run_live` ruft sie nur der Reihe nach auf. Alle Einstellungen
stecken in `Settings` (immer mit Schlüsselwörtern aufrufen, nie positional).
"""

import time
from dataclasses import dataclass, field

import sgt_constants as C
import sgt_instance as I
import sgt_plans as P
import sgt_sim as S
from sgt_erlang import Problem
from sgt_rng import seed_from


@dataclass(frozen=True)
class Settings:
    profile: str = C.DEFAULT_PROFILE
    size: str = C.DEFAULT_SIZE
    aht: int = C.DEFAULT_AHT
    goal: int = C.DEFAULT_GOAL            # Prozent
    catalog: str = C.DEFAULT_CATALOG      # Schlüssel in C.CATALOGS
    seed: int = C.DEFAULT_SEED            # Instanznummer

    @property
    def goal_fraction(self):
        return self.goal / 100.0

    @property
    def shifts(self):
        return C.CATALOGS[self.catalog]


@dataclass
class Simulated:
    sl: float            # simulierter Tages-Servicegrad
    se: float            # Standardfehler (aus Tagesmitteln)
    days: int
    calls: int
    hours_sl: list = field(default_factory=list)   # Servicegrad je Stunde (None ohne Anrufe)
    hours_calls: list = field(default_factory=list)


@dataclass
class Live:
    settings: Settings
    prob: Problem
    plans: dict = field(default_factory=dict)      # Z, K, G, O, ODP (fehlende Pläne fehlen)
    sims: dict = field(default_factory=dict)       # Z, K, G, O
    seconds: dict = field(default_factory=dict)    # stage1, stage2, stage3


def build_problem(settings):
    """Instanz und Servicegrad-Tabellen der Einstellung (die Last skaliert mit der Bediendauer, die Anrufzahlen bleiben)."""
    a_ref = I.instance_for(settings.profile, settings.size, settings.seed)
    return Problem(I.a_cent_at(a_ref, settings.aht), settings.aht, C.SERVICE_S)


def stage1(settings, prob=None):
    """Stufe 1: Z, K, G und O ohne Schichtstruktur (sofort). Rückgabe (Problem, Pläne, Sekunden)."""
    t0 = time.perf_counter()
    prob = prob or build_problem(settings)
    goal = settings.goal_fraction
    plans = {"Z": P.plan_z(prob, settings.shifts, goal)}
    k = P.plan_k(prob, settings.shifts, goal)
    plans["K"] = k if k is not None else _as_k(plans["Z"])
    g = P.plan_g(prob, settings.shifts, plans["K"], goal)
    if g is not None:
        plans["G"] = g
    plans["ODP"] = P.plan_o_dp(prob, goal)
    return prob, plans, time.perf_counter() - t0


def _as_k(z_plan):
    """Kein z hält das Ziel (kommt in der Messreihe nicht vor): K ist dann Z mit z = Ziel."""
    k = P.Plan(key="K", n=list(z_plan.n), cost=z_plan.cost, vsum=z_plan.vsum, day_sl=z_plan.day_sl, figures=dict(z_plan.figures),
               status=z_plan.status, bound=z_plan.bound, z=None, seconds=0.0, note="kein einheitliches z gefunden, K = Z", shifts=list(z_plan.shifts))
    return k


def stage2(settings, prob, plans, time_limit=None):
    """Stufe 2: O mit Schichten (HiGHS, Zeitlimit, Status). Rückgabe (Plan oder None, Sekunden)."""
    t0 = time.perf_counter()
    plan = P.plan_o(prob, settings.shifts, settings.goal_fraction, candidates=(plans.get("K"), plans.get("G")), time_limit=time_limit)
    return plan, time.perf_counter() - t0


def sim_seed(settings, key):
    """Zufalls-Seed der Simulation: aus Profil, Instanznummer und Messreihen-Kürzel des Plans (jeder Plan hat einen eigenen Strom)."""
    return seed_from("sim", settings.profile, settings.seed, C.MESS_CODE.get(key, key))


def stage3(settings, prob, plans, keys=C.PLAN_KEYS, call_budget=C.CALL_BUDGET):
    """Stufe 3: Ereignissimulation der Pläne (Tageszahl nach Anrufbudget). Rückgabe (Simulationen, Sekunden)."""
    t0 = time.perf_counter()
    days = S.days_for_budget(prob, call_budget)
    out = {}
    for key in keys:
        plan = plans.get(key)
        if plan is None:
            continue
        res = S.simulate(prob, plan.n, days=days, warm=C.SIM_WARM_DAYS, seed=sim_seed(settings, key))
        sl, se = S.mean_and_se(res)
        out[key] = Simulated(sl=sl, se=se, days=days, calls=res["n"], hours_sl=[o / c if c else None for o, c in zip(res["ok"], res["calls"])],
                             hours_calls=list(res["calls"]))
    return out, time.perf_counter() - t0


def run_live(settings, with_sim=True):
    """Alle drei Stufen hintereinander (für Tests, Messungen und die Abdeckung)."""
    prob, plans, s1 = stage1(settings)
    o, s2 = stage2(settings, prob, plans)
    if o is not None:
        plans["O"] = o
    live = Live(settings=settings, prob=prob, plans=plans, seconds={"stage1": s1, "stage2": s2})
    if with_sim:
        live.sims, live.seconds["stage3"] = stage3(settings, prob, plans)
    return live
