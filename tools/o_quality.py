"""Qualität von O mit Schichten gegen den Bestwert der Messreihe je Zelle (Bau-Gate des Plans, AP 0 a).

Aufruf (Python mit vollem Pfad): python tools/o_quality.py --cells ziel70,aht480,gross --every 4 --workers 3

Je Zelle werden die Instanzen mit der Nummer 0, `every`, 2·`every` ... (alle Profile) mit der Live-Pipeline (Zeitlimit wie live) gerechnet und die Kosten von O mit
dem gespeicherten Wert verglichen. Gate des Plans: höchstens 5 % der Läufe je Zelle um mehr als 2 Personenstunden schlechter. Das Ergebnis hängt von der
verfügbaren Rechenzeit ab (HiGHS startet je Prozess mehrere Threads): wenige Prozesse, ruhiger Rechner.
"""

import argparse
import pathlib
import sys
import time
from concurrent.futures import ProcessPoolExecutor

sys.dont_write_bytecode = True
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import sgt_pipeline as PL  # noqa: E402
import sgt_plans as P  # noqa: E402
import sgt_results as R  # noqa: E402


def run(task):
    name, art, i, limit = task
    cell = R.cell(name)
    s = PL.Settings(profile=art, size=cell["size"], aht=cell["aht"], goal=cell["goal"], catalog=cell["catalog"], seed=i)
    prob, plans, _ = PL.stage1(s)
    row = next(r for r in R.rows(name, art) if r["i"] == i)
    t0 = time.perf_counter()
    o = P.plan_o(prob, s.shifts, s.goal_fraction, candidates=(plans["K"], plans["G"]), time_limit=limit)
    return name, art, i, o.cost - R.get(row, "B", "cost"), o.status, time.perf_counter() - t0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cells", default="ziel70,aht480,gross")
    ap.add_argument("--every", type=int, default=4)
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--limit", type=float, default=None, help="Zeitlimit in Sekunden (Vorgabe: wie live, 5 s bzw. 8 s ab 20 Erlang)")
    args = ap.parse_args()
    cells = args.cells.split(",")
    tasks = [(c, a, i, args.limit) for c in cells for a in R.cell(c)["profiles"] for i in range(0, 100, args.every)]
    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        res = list(ex.map(run, tasks, chunksize=3))
    for c in cells:
        rr = [r for r in res if r[0] == c]
        gt2 = sum(1 for r in rr if r[3] > 2)
        print(f"{c}: n={len(rr)}, Zeitlimit {args.limit if args.limit else 'live'}, um mehr als 2 Personenstunden schlechter {gt2} ({100 * gt2 / len(rr):.1f} %), schlechter überhaupt {sum(1 for r in rr if r[3] > 0)}, "
              f"besser {sum(1 for r in rr if r[3] < 0)}, bewiesen {sum(1 for r in rr if r[4] == 'optimal')}, mittlere Zeit {sum(r[5] for r in rr) / len(rr):.1f} s, "
              f"größte Abweichung {max(r[3] for r in rr)}")


if __name__ == "__main__":
    main()
