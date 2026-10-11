"""Ereignissimulation M_t/M/n_t: stündlich konstante Rate, zyklischer Plan, exponentielle Bedienzeit, unendliche Geduld, FIFO.

Der Kern ist die Simulation der Vorab-Messreihe (modell.simuliere), Zufallsströme und Ereignisfolge unverändert (bitgleich getestet);
neu ist nur die Zählung je Tag, aus der der Standardfehler kommt. Sinkt n_t, beenden laufende Anrufe ihre Bedienung (Bediener gehen
erst danach). Gezählt wird jede Ankunft in den Zähltagen; ein noch unbedienter Anruf gilt als nicht rechtzeitig (die erste Fassung
zählte nur bediente Anrufe und verzerrte Pläne mit Dauerrückstau nach oben). Einschwingzeit: `warm` ungezählte Tage, danach
`days` gezählte Tage und ein Auslauftag.
"""

import math
from collections import deque
from heapq import heappop, heappush

import sgt_constants as C
from sgt_rng import SplitMix64, seed_from


def simulate(prob, n_plan, days=40, warm=C.SIM_WARM_DAYS, seed=1):
    """Simuliert `n_plan` (Besetzung je Stunde) über warm + days + 1 Tage; Rückgabe mit Zählern je Stunde und je Tag."""
    tl = prob.tlen
    ra = SplitMix64(seed_from("sim_a", seed))
    rs = SplitMix64(seed_from("sim_s", seed))
    aht = prob.aht
    s_min = prob.s_min
    eps = 1e-12
    total_days = warm + days + 1
    count_h = [0] * tl
    ok_h = [0] * tl
    count_d = [0] * days
    ok_d = [0] * days
    deps = []
    queue = deque()   # (Ankunftszeit, Stunde im Tag, gezählter Tag oder -1)
    busy = 0
    log = math.log

    def start_service(t_start, arrival, hour, day):
        nonlocal busy
        busy += 1
        heappush(deps, t_start + (-log(rs.uniform())) * aht)
        if day >= 0 and t_start - arrival <= s_min + eps:
            ok_h[hour] += 1
            ok_d[day] += 1

    for H in range(total_days * tl):
        h = H % tl
        d = H // tl
        counted = warm <= d < warm + days
        day = d - warm if counted else -1
        t0 = H * 60.0
        t1 = t0 + 60.0
        n = n_plan[h]
        while busy < n and queue:
            arrival, hh, dd = queue.popleft()
            start_service(t0, arrival, hh, dd)
        lam = prob.a[h] / aht
        t = t0
        arr = []
        while True:
            t += -log(ra.uniform()) / lam
            if t >= t1:
                break
            arr.append(t)
        if counted:
            count_h[h] += len(arr)
            count_d[day] += len(arr)
        i = 0
        na = len(arr)
        while True:
            ta = arr[i] if i < na else t1
            td = deps[0] if deps else t1
            if ta >= t1 and td >= t1:
                break
            if td <= ta:
                tt = heappop(deps)
                if busy > n:
                    busy -= 1
                elif queue:
                    arrival, hh, dd = queue.popleft()
                    start_service(tt, arrival, hh, dd)
                    busy -= 1   # start_service hat busy erhöht; der Abgang hat einen Platz frei gemacht
                else:
                    busy -= 1
            else:
                i += 1
                if busy < n:
                    start_service(ta, ta, h, day)
                else:
                    queue.append((ta, h, day))
    total = sum(count_h)
    return {"calls": count_h, "ok": ok_h, "calls_day": count_d, "ok_day": ok_d, "sl_day": sum(ok_h) / max(1, total), "n": total, "days": days}


def mean_and_se(res, block=1):
    """Mittel des simulierten Tages-Servicegrads und Standardfehler aus Tagesmitteln (block = Tage je Block, Blockmittel)."""
    sl = [o / c for o, c in zip(res["ok_day"], res["calls_day"]) if c > 0]
    if block > 1:
        sl = [sum(sl[i:i + block]) / block for i in range(0, len(sl) - block + 1, block)]
    k = len(sl)
    if k < 2:
        return res["sl_day"], float("nan")
    m = sum(sl) / k
    var = sum((x - m) ** 2 for x in sl) / (k - 1)
    return res["sl_day"], math.sqrt(var / k)


def days_for_budget(prob, call_budget=C.CALL_BUDGET, lo=C.SIM_DAYS_MIN, hi=C.SIM_DAYS_MAX):
    """Zahl der gezählten Tage nach Anrufbudget: erwartete Anrufe je Tag aus der Last, begrenzt auf [lo, hi]."""
    per_day = sum(prob.a) * 3600.0 / prob.aht_s
    return max(lo, min(hi, int(round(call_budget / max(1.0, per_day)))))
