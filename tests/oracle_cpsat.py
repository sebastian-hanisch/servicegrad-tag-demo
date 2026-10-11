"""CP-SAT-Orakel für die Schichtüberdeckung: dasselbe Modell in anderer Bauweise und mit einem anderen Löser (OR-Tools).

Unäre Kodierung des Servicegrads (Stufenliterale mit den ganzzahligen Zuwächsen der Wertetabelle), Zeitlimit, fester Zufalls-Seed
und genau ein Suchprozess (nie mehr Worker als Kerne, reproduzierbar). Verglichen werden nur Kosten und Status, nie die Pläne selbst:
HiGHS und CP-SAT lösen Gleichstände der Kosten verschieden auf.
"""

import sgt_cover as V


def solve_cpsat(prob, catalog, lb, rhs=None, time_limit=20.0, seed=7):
    """Rückgabe (status, kosten, untere Schranke, n) mit status in {"optimal", "feasible", "infeasible", "unknown"}."""
    from ortools.sat.python import cp_model

    tl = prob.tlen
    shifts = V.shift_types(catalog, tl)
    m = cp_model.CpModel()
    cap_max = max(prob.cap)
    x = [m.NewIntVar(0, cap_max + 2, f"x{j}") for j in range(len(shifts))]
    n = []
    for t in range(tl):
        nt = m.NewIntVar(0, 4 * (cap_max + 2), f"n{t}")
        m.Add(nt == sum(x[j] for j, s in enumerate(shifts) if t in s[2]))
        if lb[t] > 0:
            m.Add(nt >= lb[t])
        n.append(nt)
    if rhs is not None:
        parts = []
        for t in range(tl):
            lits = [m.NewBoolVar(f"l{t}_{k}") for k in range(1, prob.cap[t] + 1)]
            for k in range(len(lits) - 1):
                m.AddImplication(lits[k + 1], lits[k])
            m.Add(sum(lits) <= n[t])
            parts.append(sum((prob.v[t][k] - prob.v[t][k - 1]) * lit for k, lit in enumerate(lits, start=1)))
        m.Add(sum(parts) >= rhs)
    m.Minimize(sum(s[1] * x[j] for j, s in enumerate(shifts)))
    sv = cp_model.CpSolver()
    sv.parameters.num_search_workers = 1
    sv.parameters.random_seed = seed
    sv.parameters.max_time_in_seconds = float(time_limit)
    st = sv.Solve(m)
    if st == cp_model.OPTIMAL:
        return "optimal", int(round(sv.ObjectiveValue())), int(round(sv.ObjectiveValue())), [sv.Value(v) for v in n]
    if st == cp_model.FEASIBLE:
        return "feasible", int(round(sv.ObjectiveValue())), int(sv.BestObjectiveBound() + 1 - 1e-9), [sv.Value(v) for v in n]
    return ("infeasible" if st == cp_model.INFEASIBLE else "unknown"), None, None, None
