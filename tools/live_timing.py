"""Zeitmessung je Stufe der Live-Rechnung (AP 0 e): Median, 90. Perzentil und Maximum, eine Zeile je Einstellung.

Aufruf (Python mit vollem Pfad, auf einem ruhigen Rechner, ein Prozess):
    python tools/live_timing.py [--seeds 3] [--out <Pfad>/live_timing.json]

Stufe 1: Z, K, G und O ohne Schichtstruktur; Stufe 2: O mit Schichten (HiGHS, Zeitlimit wie live); Stufe 3: Simulation der vier Pläne
(Anrufbudget wie live). Gemessen wird auf diesem Gerät; Streamlit Cloud ist langsamer (nicht gemessen).
"""

import argparse
import json
import pathlib
import statistics as st
import sys
import time

sys.dont_write_bytecode = True
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import sgt_constants as C  # noqa: E402
import sgt_pipeline as PL  # noqa: E402

LABELS = [
    ("Basis (mittel, 80 %, 240 s, 6/8/10)", dict()),
    ("Größe klein", dict(size="klein")),
    ("Größe groß", dict(size="gross")),
    ("Ziel 70 %", dict(goal=70)),
    ("Ziel 95 %", dict(goal=95)),
    ("Katalog nur 8 h", dict(catalog="8")),
    ("Katalog 3 bis 12 h", dict(catalog="3 bis 12")),
    ("Stresszelle (3/4 h, 95 %)", dict(goal=95, catalog="3/4")),
    ("Bediendauer 120 s", dict(aht=120)),
    ("Bediendauer 480 s", dict(aht=480)),
]


def pct(xs, q):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(round(q * (len(xs) - 1))))]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=3)
    ap.add_argument("--out", default="")
    args = ap.parse_args()
    out = {}
    all_total = []
    print(f"{'Einstellung':38s} {'n':>3s} {'Stufe 1':>14s} {'Stufe 2':>14s} {'Stufe 3':>14s} {'gesamt (Med/P90/Max)':>24s}  O bewiesen")
    for label, kw in LABELS:
        s1, s2, s3, tot, proven = [], [], [], [], 0
        profiles = C.PROFILE_ORDER if label.startswith(("Basis", "Stresszelle")) else C.PROFILE_ORDER[:4]
        for prof in profiles:
            for seed in range(args.seeds):
                s = PL.Settings(profile=prof, seed=seed, **kw)
                t0 = time.perf_counter()
                live = PL.run_live(s, with_sim=True)
                tot.append(time.perf_counter() - t0)
                s1.append(live.seconds["stage1"])
                s2.append(live.seconds["stage2"])
                s3.append(live.seconds["stage3"])
                proven += 1 if live.plans["O"].status == "optimal" else 0
        all_total += tot
        row = {"n": len(tot), "s1": (st.median(s1), max(s1)), "s2": (st.median(s2), max(s2)), "s3": (st.median(s3), max(s3)),
               "total": (st.median(tot), pct(tot, 0.9), max(tot)), "proven": proven}
        out[label] = row
        print(f"{label:38s} {row['n']:3d} {row['s1'][0]:6.2f}/{row['s1'][1]:5.2f} {row['s2'][0]:6.2f}/{row['s2'][1]:5.2f} {row['s3'][0]:6.2f}/{row['s3'][1]:5.2f} "
              f"{row['total'][0]:8.2f}/{row['total'][1]:5.2f}/{row['total'][2]:5.2f}  {proven}/{row['n']}", flush=True)
    out["_all"] = {"n": len(all_total), "median": st.median(all_total), "p90": pct(all_total, 0.9), "max": max(all_total)}
    print(f"gesamt über {len(all_total)} Läufe: Median {out['_all']['median']:.2f} s, P90 {out['_all']['p90']:.2f} s, Maximum {out['_all']['max']:.2f} s")
    if args.out:
        pathlib.Path(args.out).write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
