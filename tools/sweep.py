"""Abdeckung (AP 0): alle 216 Kombinationen (Größe x Ziel x Bediendauer x Katalog) x 5 Profile x 20 Instanzen mit der Live-Pipeline.

Aufruf (Python mit vollem Pfad, mehrere Prozesse):
    python tools/sweep.py --workers 10 --raw <Pfad>/sweep_raw.jsonl            # Rohläufe (eine Zeile je Instanz, fortsetzbar)
    python tools/sweep.py --aggregate --raw <Pfad>/sweep_raw.jsonl             # schreibt data/sgt_coverage.json

Je Lauf: Z, K, G, O (HiGHS mit Zeitlimit wie live), O ohne Schichtstruktur und die Simulation der vier Pläne (Anrufbudget wie live).
Instanzen sind die Zufalls-Seeds 0 bis 19 je Profil. Die Aggregation fasst je (Kombination, Profil) Mittel und Standardfehler zusammen
und legt die vier Aussagen des Plans fest (gilt, unklar, gilt nicht) mit den hier stehenden Schwellen.
"""

import argparse
import itertools
import json
import math
import os
import pathlib
import statistics as st
import sys
import time
from concurrent.futures import ProcessPoolExecutor

sys.dont_write_bytecode = True
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import sgt_constants as C  # noqa: E402
import sgt_pipeline as PL  # noqa: E402

N_INSTANCES = 20
STATUS_CODE = {"optimal": 0, "feasible": 1, "exact": 0}

# Schwellen der vier Aussagen (vorab festgelegt, im README genannt)
OVER_YES, OVER_NO = 1.0, 0.5          # Übererfüllung: Z liefert mehr als Ziel + 1 Punkt (gilt) / weniger als Ziel + 0,5 Punkte (gilt nicht)
EMPTY_YES, EMPTY_NO = 1.0, 0.5        # leere Stunden von O: Mittel >= 1 / < 0,5
DROP_YES_POINTS, DROP_NO_POINTS = -3.0, -1.0   # Einbruch: Mittel < -3 Punkte und unter -2 SE (gilt) / >= -1 Punkt (gilt nicht)
COUPLE_YES_H, COUPLE_NO_H = 1.0, 0.5  # G gegen K: Mittel >= 1 Personenstunde / < 0,5


def combos():
    return list(itertools.product(C.SIZE_ORDER, C.GOAL_OPTIONS, C.AHT_OPTIONS, C.CATALOG_ORDER))


def one_run(task):
    size, goal, aht, catalog, profile, seed = task
    s = PL.Settings(profile=profile, size=size, aht=aht, goal=goal, catalog=catalog, seed=seed)
    live = PL.run_live(s, with_sim=True)
    rec = {"size": size, "goal": goal, "aht": aht, "catalog": catalog, "profile": profile, "seed": seed,
           "sec": [round(live.seconds[k], 3) for k in ("stage1", "stage2", "stage3")], "peak": max(live.prob.a)}
    for key in ("Z", "K", "G", "O", "ODP"):
        p = live.plans.get(key)
        if p is None:
            rec[key] = None
            continue
        f = p.figures
        sim = live.sims.get(key)
        rec[key] = {"cost": p.cost, "sl": round(p.day_sl, 5), "bound": p.bound, "status": STATUS_CODE.get(p.status, 2), "z": p.z,
                    "empty": f["empty"], "nbelow": f["n_hours_below"], "callsbelow": round(f["calls_below"], 4), "slmin": round(f["sl_min"], 4),
                    "sim": None if sim is None else round(sim.sl, 5), "se": None if sim is None else round(sim.se, 5),
                    "days": None if sim is None else sim.days}
    return rec


def run_sweep(args):
    raw = pathlib.Path(args.raw)
    done = set()
    if raw.exists():
        for line in raw.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                done.add((r["size"], r["goal"], r["aht"], r["catalog"], r["profile"], r["seed"]))
    tasks = []
    for size, goal, aht, catalog in combos():
        if args.only and f"{size},{goal},{aht},{catalog}" not in args.only:
            continue
        for profile in C.PROFILE_ORDER:
            for seed in range(args.n):
                t = (size, goal, aht, catalog, profile, seed)
                if t not in done:
                    tasks.append(t)
    print(f"{len(tasks)} Läufe offen, {len(done)} schon da, {args.workers} Prozesse", flush=True)
    t0 = time.time()
    with ProcessPoolExecutor(max_workers=args.workers) as ex, open(raw, "a", encoding="utf-8", newline="\n") as f:
        for k, rec in enumerate(ex.map(one_run, tasks, chunksize=2)):
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            if (k + 1) % 200 == 0:
                f.flush()
                print(f"  {k + 1}/{len(tasks)} nach {time.time() - t0:.0f} s", flush=True)
    print(f"fertig nach {time.time() - t0:.0f} s", flush=True)


def mean_se(xs):
    xs = [x for x in xs if x is not None]
    if not xs:
        return None, None
    m = sum(xs) / len(xs)
    if len(xs) < 2:
        return m, 0.0
    return m, math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1) / len(xs))


def verdict_high(mean, yes, no):
    """gilt: Mittel >= yes; gilt nicht: Mittel < no; sonst unklar (Aussagen der Form "es gibt mehr als ...")."""
    return "gilt" if mean >= yes else "gilt nicht" if mean < no else "unklar"


def verdict_drop(mean, se):
    if mean < DROP_YES_POINTS and mean + DROP_SE_FACTOR * se < 0:
        return "gilt"
    return "gilt nicht" if mean >= DROP_NO_POINTS else "unklar"


DROP_SE_FACTOR = 2.0


def aggregate_group(recs):
    """Statistik einer Gruppe von Läufen (eine Kombination und ein Profil, 20 Instanzen)."""
    goal = recs[0]["goal"]
    out = {"n": len(recs)}

    def col(f):
        return [f(r) for r in recs]

    out["over"] = mean_se(col(lambda r: 100 * r["Z"]["sl"] - goal))
    out["k_save_pct"] = mean_se(col(lambda r: 100.0 * (r["Z"]["cost"] - r["K"]["cost"]) / r["Z"]["cost"]))
    out["k_save_h"] = mean_se(col(lambda r: r["Z"]["cost"] - r["K"]["cost"]))
    gk = [r for r in recs if r["G"] is not None]
    out["g_vs_k_pct"] = mean_se([100.0 * (r["K"]["cost"] - r["G"]["cost"]) / r["K"]["cost"] for r in gk])
    out["g_vs_k_h"] = mean_se([r["K"]["cost"] - r["G"]["cost"] for r in gk])
    out["g_missing"] = len(recs) - len(gk)
    out["o_save_pct"] = mean_se(col(lambda r: 100.0 * (r["Z"]["cost"] - r["O"]["cost"]) / r["Z"]["cost"]))
    out["o_save_h"] = mean_se(col(lambda r: r["Z"]["cost"] - r["O"]["cost"]))
    out["odp_pct"] = mean_se(col(lambda r: 100.0 * (r["Z"]["cost"] - r["ODP"]["cost"]) / r["Z"]["cost"]))
    out["o_empty"] = mean_se(col(lambda r: r["O"]["empty"]))
    out["o_below"] = mean_se(col(lambda r: r["O"]["nbelow"]))
    out["o_calls_below"] = mean_se(col(lambda r: 100 * r["O"]["callsbelow"]))
    out["o_any_below"] = sum(1 for r in recs if r["O"]["nbelow"] > 0) / len(recs)
    for key in ("Z", "K", "G", "O"):
        rr = [r for r in recs if r[key] is not None and r[key]["sim"] is not None]
        out[f"d_{key}"] = mean_se([100 * (r[key]["sim"] - r[key]["sl"]) for r in rr])
        out[f"sim_{key}"] = mean_se([100 * r[key]["sim"] for r in rr])[0]
        out[f"hold_{key}"] = (sum(1 for r in rr if r[key]["sim"] >= goal / 100.0 - C.HOLD_TOLERANCE) / len(rr)) if rr else None
        out[f"model_{key}"] = mean_se([100 * r[key]["sl"] for r in rr])[0]
    out["se_sim_O"] = mean_se([100 * r["O"]["se"] for r in recs if r["O"]["se"] is not None])[0]
    out["z_mean"] = mean_se([r["K"]["z"] for r in recs if r["K"]["z"] is not None])[0]
    out["o_status"] = [sum(1 for r in recs if r["O"]["status"] == s) for s in (0, 1, 2)]
    out["o_gap_h"] = mean_se(col(lambda r: r["O"]["cost"] - r["O"]["bound"]))
    out["sec"] = [st.median(r["sec"][i] for r in recs) for i in range(3)]
    out["sec_max"] = max(sum(r["sec"]) for r in recs)
    out["verdict"] = {
        "over": verdict_high(out["over"][0], OVER_YES, OVER_NO),
        "empty": verdict_high(out["o_empty"][0], EMPTY_YES, EMPTY_NO),
        "drop": verdict_drop(out["d_O"][0], out["d_O"][1]),
        "couple": verdict_high(out["g_vs_k_h"][0], COUPLE_YES_H, COUPLE_NO_H) if gk else "unklar",
    }
    return out


def aggregate(args):
    raw = pathlib.Path(args.raw)
    groups = {}
    n_runs = 0
    for line in raw.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        key = (r["size"], r["goal"], r["aht"], r["catalog"])
        groups.setdefault(key, {}).setdefault(r["profile"], []).append(r)
        n_runs += 1
    out = {"meta": {"runs": n_runs, "instances_per_profile": N_INSTANCES, "seeds": [0, N_INSTANCES - 1], "combinations": len(groups),
                    "thresholds": {"over_yes": OVER_YES, "over_no": OVER_NO, "empty_yes": EMPTY_YES, "empty_no": EMPTY_NO,
                                   "drop_yes_points": DROP_YES_POINTS, "drop_no_points": DROP_NO_POINTS, "drop_se_factor": DROP_SE_FACTOR,
                                   "couple_yes_h": COUPLE_YES_H, "couple_no_h": COUPLE_NO_H},
                    "workers": args.workers, "wall_s": args.wall},
           "cells": {}}
    for key, profs in sorted(groups.items()):
        name = "|".join(str(x) for x in key)
        out["cells"][name] = {p: aggregate_group(rr) for p, rr in sorted(profs.items())}
    path = pathlib.Path(args.out)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8", newline="\n")
    print(f"{path}: {n_runs} Läufe, {len(groups)} Kombinationen")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", required=True)
    ap.add_argument("--workers", type=int, default=min(10, max(1, (os.cpu_count() or 2) - 4)))
    ap.add_argument("--n", type=int, default=N_INSTANCES)
    ap.add_argument("--only", nargs="*", default=[], help="Kombinationen als 'mittel,80,240,6/8/10'")
    ap.add_argument("--aggregate", action="store_true")
    ap.add_argument("--wall", type=float, default=None, help="gemessene Gesamtdauer des Sweeps in Sekunden (nur für die Meta-Angabe)")
    ap.add_argument("--out", default=str(ROOT / "data" / "sgt_coverage.json"))
    args = ap.parse_args()
    if args.aggregate:
        aggregate(args)
    else:
        run_sweep(args)


if __name__ == "__main__":
    main()
