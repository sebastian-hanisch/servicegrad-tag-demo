"""Die Planungsvarianten Z, K, G, O und O ohne Schichtstruktur, je als eine Funktion mit ausdrücklichen Ein- und Ausgaben.

Z (Messreihe: A)   zweistufig: n_t >= c_t(Ziel), Schichten kostenminimal darüber.
K (Messreihe: Az)  wie Z mit einheitlichem Stundenziel z <= Ziel, so weit abgesenkt, wie der Tages-Servicegrad noch das Ziel hält.
G (Messreihe: BFz) gemeinsam, jede Stunde mindestens `FLOOR`, Tages-Servicegrad mindestens der von K (gleiche gelieferte Qualität).
O (Messreihe: B)   gemeinsam, nur der Tages-Servicegrad zählt (kein Mindestwert, leere Stunden erlaubt).
ODP                O ohne Schichtstruktur: jedes Besetzungsmuster erlaubt (exakte Rucksack-Rechnung), die Untergrenze der Kosten von O.
"""

import time
from dataclasses import dataclass, field

import sgt_constants as C
import sgt_cover as V
import sgt_dp as D
from sgt_erlang import key_figures


@dataclass
class Plan:
    key: str
    n: list
    cost: int
    vsum: int
    day_sl: float
    figures: dict = field(default_factory=dict)
    status: str = "optimal"      # optimal | feasible (Zeitlimit) | fallback (nur aus K/G bekannt) | exact (DP)
    bound: int = 0               # bewiesene untere Schranke der Kosten (bei optimal gleich cost)
    z: float | None = None       # K: einheitliches Stundenziel
    seconds: float = 0.0
    note: str = ""
    shifts: list = field(default_factory=list)   # (Start, Länge, Anzahl) je benutztem Schichttyp


def shift_list(catalog, x, tlen=C.T):
    """Gewählte Schichten als (Start, Länge, Anzahl), nach Start und Länge sortiert."""
    return [(s[0], s[1], x[j]) for j, s in enumerate(V.shift_types(catalog, tlen)) if j < len(x) and x[j] > 0]


def _plan_from_cover(prob, key, res, catalog, z=None, note=""):
    return Plan(key=key, n=list(res.n), cost=res.cost, vsum=res.vsum, day_sl=prob.day_sl(res.n), figures=key_figures(prob, res.n),
                status=res.status, bound=res.bound, z=z, seconds=res.seconds, note=note, shifts=shift_list(catalog, res.x))


def plan_z(prob, catalog, goal):
    """Z: Tagesziel als Stundenziel. Kleinste Besetzung je Stunde mit SL_t >= Ziel, Schichten kostenminimal, bei gleichen Kosten bester Tages-SL."""
    res = V.solve(prob, catalog, prob.c_target(goal), rhs=None, time_limit=C.TIME_LIMIT_S)
    return _plan_from_cover(prob, "Z", res, catalog)


def evaluate_z_level(prob, catalog, z, rhs, cache):
    """Eine Stufe der z-Suche: kostenminimale Überdeckung zur Untergrenze c_t(z); bester Tages-Wert bei gleichen Kosten nur, wenn nötig.

    Zwischenspeicher je Untergrenzen-Vektor (viele z liefern denselben). Rückgabe: das Ergebnis der Überdeckung oder None."""
    lb = tuple(prob.c_target(z))
    if lb in cache:
        return cache[lb]
    res = V.solve(prob, catalog, list(lb), rhs=None, time_limit=C.TIME_LIMIT_S, stage2=False)
    if res.status in ("optimal", "feasible") and res.vsum < rhs:
        res = V.solve(prob, catalog, list(lb), rhs=None, time_limit=C.TIME_LIMIT_S, stage2=True)
    cache[lb] = res if res.status in ("optimal", "feasible") else None
    return cache[lb]


def plan_k(prob, catalog, goal, z_step=C.Z_STEP, z_lower=C.Z_LOWER, patience=C.Z_PATIENCE):
    """K: von z = Ziel in Schritten `z_step` nach unten; gewählt wird das z mit den kleinsten Kosten, dessen Tages-SL noch das Ziel hält
    (bei Gleichstand das kleinere z). Abbruch nach `patience` Fehlschlägen in Folge. Rückgabe: Plan oder None, wenn schon z = Ziel scheitert."""
    rhs = prob.rhs_goal(goal)
    cache = {}
    best = None
    fails = 0
    k = 0
    while True:
        z = goal - k * z_step
        if z < z_lower - 1e-9:
            break
        k += 1
        res = evaluate_z_level(prob, catalog, z, rhs, cache)
        if res is None or res.vsum < rhs:
            fails += 1
            if fails >= patience:
                break
            continue
        fails = 0
        if best is None or res.cost <= best[1].cost:
            best = (round(z, 4), res)
    if best is None:
        return None
    z, res = best
    # Zweite Stufe für das gewählte z: bester Tages-Servicegrad bei den Kosten (aus dem Zwischenspeicher, falls schon gerechnet)
    final = V.solve(prob, catalog, prob.c_target(z), rhs=None, time_limit=C.TIME_LIMIT_S, stage2=True)
    if final.status in ("optimal", "feasible") and final.cost <= res.cost and final.vsum >= res.vsum:
        res = final
    return _plan_from_cover(prob, "K", res, catalog, z=z)


def plan_g(prob, catalog, k_plan, goal, floor=C.FLOOR, time_limit=None):
    """G: Mindestwert je Stunde, Tages-Servicegrad mindestens der von K. Kosten minimal, danach bester Tages-Wert."""
    lb = prob.c_target(floor)
    rhs = k_plan.vsum if k_plan is not None else prob.rhs_goal(goal)
    cut = D.dp_no_shifts(prob, lb, rhs)
    res = V.solve(prob, catalog, lb, rhs=rhs, time_limit=time_limit or time_limit_for(prob), cost_floor=cut[0] if cut else None)
    if res.status not in ("optimal", "feasible"):
        return None
    return _plan_from_cover(prob, "G", res, catalog)


def plan_o_dp(prob, goal):
    """O ohne Schichtstruktur: exakt, jedes Besetzungsmuster erlaubt (Untergrenze der Kosten von O)."""
    t0 = time.perf_counter()
    cut = D.dp_no_shifts(prob, [0] * prob.tlen, prob.rhs_goal(goal))
    c, n, vs = cut
    return Plan(key="ODP", n=list(n), cost=c, vsum=vs, day_sl=prob.day_sl(n), figures=key_figures(prob, n), status="exact", bound=c,
                seconds=time.perf_counter() - t0)


def time_limit_for(prob):
    """Zeitlimit von O mit Schichten: 8 s bei großer Last (Spitze ab BIG_LOAD_ERLANG Erlang), sonst 5 s (gemessen, AP 0)."""
    return C.TIME_LIMIT_BIG_S if max(prob.a) >= C.BIG_LOAD_ERLANG else C.TIME_LIMIT_S


def pattern_cover(prob, catalog, pattern, goal):
    """Billigste Schichtüberdeckung eines Besetzungsmusters (n_t >= pattern_t): ist für O zulässig, wenn das Muster es ist."""
    res = V.min_cost(prob, catalog, list(pattern), rhs=None, time_limit=C.TIME_LIMIT_S)
    if res.status not in ("optimal", "feasible") or res.vsum < prob.rhs_goal(goal):
        return None
    return _plan_from_cover(prob, "DP-Muster", res, catalog)


def plan_o(prob, catalog, goal, candidates=(), time_limit=None):
    """O mit Schichten: kostenminimal bei Tages-Servicegrad >= Ziel, ohne Mindestwert. HiGHS mit DP-Schnitt (Kosten >= Untergrenze ohne
    Schichtstruktur) und Zeitlimit. Bekannte zulässige Funde (K, G, die billigste Überdeckung des DP-Musters) sind der Rückfall: gewählt
    wird der billigste zulässige Fund. Der Status benennt, ob Optimalität bewiesen ist (sonst Zeitlimit, Untergrenze gleich dem
    besseren aus DP-Schranke und HiGHS-Dualschranke).

    Gemessen: eine Obergrenze aus den bekannten Funden im Modell verschlechterte die Funde im Zeitlimit (flache Last, 12 Instanzen), deshalb nicht."""
    limit = time_limit if time_limit is not None else time_limit_for(prob)
    t0 = time.perf_counter()
    rhs = prob.rhs_goal(goal)
    cut = D.dp_no_shifts(prob, [0] * prob.tlen, rhs)
    floor = cut[0]
    res = V.min_cost(prob, catalog, [0] * prob.tlen, rhs=rhs, time_limit=limit, cost_floor=floor)
    plan = None
    if res.status in ("optimal", "feasible"):
        left = min(C.TIME_LIMIT_STAGE2_S, limit - (time.perf_counter() - t0))
        res = V.improve_value(prob, catalog, [0] * prob.tlen, rhs, res, left)
        plan = _plan_from_cover(prob, "O", res, catalog)
    cands = [c for c in candidates if c is not None and c.vsum >= rhs]
    cover = pattern_cover(prob, catalog, cut[1], goal)
    if cover is not None:
        cands.append(cover)
    for cand in cands:
        if plan is None or cand.cost < plan.cost:
            origin = "des DP-Musters" if cand.key == "DP-Muster" else f"von {cand.key}"
            plan = Plan(key="O", n=list(cand.n), cost=cand.cost, vsum=cand.vsum, day_sl=cand.day_sl, figures=dict(cand.figures),
                        status="feasible", bound=max(floor, res.bound), shifts=list(cand.shifts),
                        note=f"Überdeckung {origin} übernommen (der Löser fand im Zeitlimit nichts Besseres)")
    if plan is None:
        return None
    plan.bound = max(plan.bound, floor)
    if plan.cost <= plan.bound:
        plan.status = "optimal"
    plan.seconds = time.perf_counter() - t0
    return plan
