"""Schichtüberdeckung als ganzzahliges Modell (HiGHS über scipy.optimize.milp), in kleinen Einheiten.

Unbekannte: x_j = Zahl der Schichten vom Typ j (Start, Länge, zyklisch über Mitternacht), Besetzung n_t = Summe der Schichten über der
Stunde t. Der Servicegrad je Stunde ist über die ganzzahligen Wertetabellen V_t[n] eingebunden:

  * ab der Untergrenze lb_t ist V_t konkav, wenn die Zuwächse nichtsteigend sind (gemessen für lb_t = c_t(z), z >= 0,5; zur Laufzeit je
    Stunde geprüft): dann genügen kontinuierliche Zuwachs-Variablen l_tk in [0, 1] mit sum_k l_tk <= n_t - lb_t,
  * sonst (S-förmige Kurve ab 0, oder z < 0,5) unäre Binärkette l_tk, l_t,k+1 <= l_tk.

Jede Einheit ist eine eigene Funktion; `solve` setzt sie nur zusammen. Rechenzeiten und Zeitlimit-Status gehören zum Ergebnis.
"""

import time
from dataclasses import dataclass, field

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import coo_matrix

import sgt_constants as C

MIN_STAGE2_S = 0.05   # kürzer lohnt die zweite Stufe nicht
V_SCALE = 1000.0   # Wertezeile in Tausendstel-Einheiten: Toleranz 1e-6 entspricht unter einer ganzen Einheit der ganzzahligen Werte


@dataclass
class CoverResult:
    n: list = field(default_factory=list)       # Besetzung je Stunde
    x: list = field(default_factory=list)       # Schichten je Typ
    cost: int = 0
    vsum: int = 0
    status: str = "none"                         # optimal | feasible | infeasible | none
    bound: int = 0                               # bewiesene untere Schranke der Kosten
    seconds: float = 0.0
    nodes: int = 0


def shift_types(catalog, tlen=C.T):
    """Alle Schichttypen (Start, Länge, abgedeckte Stunden) des Katalogs; zyklisch, Längen über tlen entfallen."""
    out = []
    for length in sorted(set(catalog)):
        if length > tlen:
            continue
        for s in range(tlen):
            out.append((s, length, tuple((s + k) % tlen for k in range(length))))
    return out


def concave_hours(prob, lb):
    """Stunden, in denen die Zuwächse von V_t ab lb_t nichtsteigend sind (kontinuierliche Fassung zulässig)."""
    ok = []
    for t in range(prob.tlen):
        d = [prob.v[t][k] - prob.v[t][k - 1] for k in range(lb[t] + 1, prob.cap[t] + 1)]
        ok.append(all(d[i + 1] <= d[i] for i in range(len(d) - 1)))
    return ok


def build_model(prob, shifts, lb, with_value, rhs, cost_cap, cost_floor, objective, force_binary=False):
    """Baut (c, A, row_lo, row_hi, integrality, bounds) und das Spaltenverzeichnis der Zuwachs-Variablen.

    objective: "cost" (min sum L x) oder "value" (max sum Delta l). with_value legt die Zuwachs-Variablen an."""
    tl = prob.tlen
    J = len(shifts)
    conc = concave_hours(prob, lb) if with_value else [True] * tl
    cols = J
    inc_cols = []            # je Stunde die Spaltenindizes der Zuwächse k = lb+1 .. cap
    binary_hour = [False] * tl
    if with_value:
        for t in range(tl):
            idx = list(range(cols, cols + max(0, prob.cap[t] - lb[t])))
            cols += len(idx)
            inc_cols.append(idx)
            binary_hour[t] = force_binary or not conc[t]
    rows, cidx, vals = [], [], []
    row_lo, row_hi = [], []
    r = 0
    for t in range(tl):    # Überdeckung und Besetzung: sum_j x_j - sum_k l_tk >= lb_t
        for j, s in enumerate(shifts):
            if t in s[2]:
                rows.append(r)
                cidx.append(j)
                vals.append(1.0)
        if with_value:
            for c in inc_cols[t]:
                rows.append(r)
                cidx.append(c)
                vals.append(-1.0)
        row_lo.append(float(lb[t]))
        row_hi.append(np.inf)
        r += 1
    obj = np.zeros(cols)
    delta = {}
    if with_value:
        for t in range(tl):
            for i, c in enumerate(inc_cols[t]):
                k = lb[t] + 1 + i
                delta[c] = prob.v[t][k] - prob.v[t][k - 1]
        if objective == "value":
            for c, dv in delta.items():
                obj[c] = -dv / V_SCALE
        if rhs is not None:
            base = sum(prob.v[t][lb[t]] for t in range(tl))
            need = (rhs - base) / V_SCALE
            if need > 0:
                for c, dv in delta.items():
                    rows.append(r)
                    cidx.append(c)
                    vals.append(dv / V_SCALE)
                row_lo.append(need)
                row_hi.append(np.inf)
                r += 1
        for t in range(tl):    # Binärkette: l_t,k+1 <= l_tk
            if binary_hour[t]:
                for a, b in zip(inc_cols[t][:-1], inc_cols[t][1:]):
                    rows.extend([r, r])
                    cidx.extend([b, a])
                    vals.extend([1.0, -1.0])
                    row_lo.append(-np.inf)
                    row_hi.append(0.0)
                    r += 1
    if objective == "cost":
        for j, s in enumerate(shifts):
            obj[j] = float(s[1])
    if cost_cap is not None or cost_floor is not None:
        for j, s in enumerate(shifts):
            rows.append(r)
            cidx.append(j)
            vals.append(float(s[1]))
        row_lo.append(float(cost_floor) if cost_floor is not None else -np.inf)
        row_hi.append(float(cost_cap) if cost_cap is not None else np.inf)
        r += 1
    A = coo_matrix((vals, (rows, cidx)), shape=(r, cols)).tocsr()
    integrality = np.zeros(cols, dtype=int)
    integrality[:J] = 1
    ub = np.full(cols, np.inf)
    lbv = np.zeros(cols)
    if with_value:
        for t in range(tl):
            for c in inc_cols[t]:
                ub[c] = 1.0
                if binary_hour[t]:
                    integrality[c] = 1
    return obj, A, np.array(row_lo), np.array(row_hi), integrality, Bounds(lbv, ub)


def _run(model, time_limit):
    obj, A, lo, hi, integrality, bounds = model
    t0 = time.perf_counter()
    res = milp(obj, constraints=LinearConstraint(A, lo, hi), integrality=integrality, bounds=bounds,
               options={"time_limit": float(time_limit), "mip_rel_gap": 0.0, "disp": False})
    return res, time.perf_counter() - t0


def _extract(res, shifts, tlen):
    """Besetzung und Schichten aus dem Lösungsvektor (None, wenn der Löser nichts Zulässiges fand)."""
    if res.x is None:
        return None
    x = [int(round(float(v))) for v in res.x[:len(shifts)]]
    n = [0] * tlen
    for j, s in enumerate(shifts):
        if x[j]:
            for t in s[2]:
                n[t] += x[j]
    return n, x


def _valid(prob, n, lb, rhs):
    """Unabhängige Zulässigkeitsprüfung gegen Untergrenzen und Tageszeile (auf den ganzzahligen Werten)."""
    if any(n[t] < lb[t] for t in range(prob.tlen)):
        return False
    return rhs is None or prob.v_sum(n) >= rhs


def min_cost(prob, catalog, lb, rhs=None, time_limit=C.TIME_LIMIT_S, cost_floor=None, cost_cap=None, force_binary=False):
    """Stufe 1: kleinste Kosten mit n_t >= lb_t und (falls rhs gegeben) Wertesumme >= rhs.

    `cost_floor`: gültige untere Schranke der Kosten (Schnitt, z. B. aus der Rechnung ohne Schichtstruktur). `cost_cap`: Obergrenze der
    Kosten (ein bekannter Fund: ist das Modell mit der Obergrenze unzulässig, ist der Fund optimal, Status "infeasible").
    Status: "optimal" (bewiesen), "feasible" (Zeitlimit, Fund ohne Beweis), "infeasible", "none" (nichts gefunden)."""
    shifts = shift_types(catalog, prob.tlen)
    res, sec = _run(build_model(prob, shifts, lb, rhs is not None, rhs, cost_cap, cost_floor, "cost", force_binary), time_limit)
    out = CoverResult(seconds=sec, nodes=int(getattr(res, "mip_node_count", 0) or 0), bound=int(cost_floor or 0))
    if res.status == 2:
        out.status = "infeasible"
        return out
    dual = getattr(res, "mip_dual_bound", None)
    if dual is not None and np.isfinite(dual):
        out.bound = max(out.bound, int(np.ceil(dual - 1e-3)))   # Kosten sind ganzzahlig; die Dualschranke trägt Rauschen (Toleranz 1e-6 relativ)
    got = _extract(res, shifts, prob.tlen)
    if got is None or not _valid(prob, got[0], lb, rhs):
        out.status = "none"
        return out
    out.n, out.x = got
    out.cost = sum(s[1] * out.x[j] for j, s in enumerate(shifts))
    out.vsum = prob.v_sum(out.n)
    out.status = "optimal" if res.status == 0 else "feasible"
    if out.status == "optimal":
        out.bound = out.cost
    return out


def improve_value(prob, catalog, lb, rhs, current, time_limit, force_binary=False):
    """Stufe 2: bei den Kosten von `current` die größte Wertesumme (bester Tages-Servicegrad). Gibt `current` zurück, wenn nichts Besseres
    gefunden wird; ändert die Kosten nie."""
    if time_limit < MIN_STAGE2_S or not current.n:
        return current
    shifts = shift_types(catalog, prob.tlen)
    t0 = time.perf_counter()
    res, _ = _run(build_model(prob, shifts, lb, True, rhs, current.cost, None, "value", force_binary), time_limit)
    got = _extract(res, shifts, prob.tlen)
    out = current
    if got is not None and _valid(prob, got[0], lb, rhs):
        n2, x2 = got
        c2 = sum(s[1] * x2[j] for j, s in enumerate(shifts))
        if c2 <= current.cost and prob.v_sum(n2) > current.vsum:
            out = CoverResult(n=n2, x=x2, cost=c2, vsum=prob.v_sum(n2), status=current.status, bound=current.bound,
                              seconds=current.seconds, nodes=current.nodes)
    out.seconds = current.seconds + (time.perf_counter() - t0)
    return out


def solve(prob, catalog, lb, rhs=None, time_limit=C.TIME_LIMIT_S, stage2=True, stage2_limit=C.TIME_LIMIT_STAGE2_S,
          cost_floor=None, force_binary=False):
    """Stufe 1 und 2 zusammen: kleinste Kosten, danach bei gleichen Kosten die größte Wertesumme. Die zweite Stufe teilt sich das
    Zeitlimit mit der ersten (höchstens `stage2_limit`, höchstens der Rest)."""
    t_all = time.perf_counter()
    out = min_cost(prob, catalog, lb, rhs, time_limit, cost_floor, None, force_binary)
    if stage2 and out.status in ("optimal", "feasible"):
        left = min(stage2_limit, time_limit - (time.perf_counter() - t_all))
        out = improve_value(prob, catalog, lb, rhs, out, left, force_binary)
    out.seconds = time.perf_counter() - t_all
    return out

