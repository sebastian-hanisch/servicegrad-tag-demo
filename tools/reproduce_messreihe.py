"""Selbst-Reproduktion (AP 0 a): die Live-Funktionen auf den Instanzen der Vorab-Messreihe gegen data/sgt_results.json.

Aufruf (Python mit vollem Pfad):
    python tools/reproduce_messreihe.py --workers 10 --out <Pfad>/reproduktion.json [--cells base,kat8] [--n 100]

Je Instanz (Zelle, Profil, Nummer) wird die Live-Pipeline (Z, K, G, O ohne Schichtstruktur, O mit Schichten) gerechnet und verglichen:
  A  (Z): Kosten gleich (und Tages-Servicegrad bis auf die fünf gespeicherten Nachkommastellen),
  Az (K): Kosten höchstens gleich (die Messreihe rechnet in neun Zellen mit Raster 0,05; mit 0,01 gleich),
  BFz (G): wo gespeichert (Basis, Stresszelle): Kosten höchstens gleich,
  DP (O ohne Schichtstruktur): gleich der gespeicherten Schranke (ersetzte Einträge der Messreihe ausgenommen: dort steht die Schranke
          der engeren Variante nicht in der Datei, die gespeicherte DP-Schranke gehört dem Eintrag selbst und gilt weiter),
  B  (O): Kosten gegen den Bestwert der Messreihe: gleich, besser, schlechter und um wie viele Stunden.
"""

import argparse
import json
import os
import pathlib
import sys
import time
from concurrent.futures import ProcessPoolExecutor

sys.dont_write_bytecode = True
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import sgt_constants as C  # noqa: E402
import sgt_instance as I  # noqa: E402
import sgt_pipeline as PL  # noqa: E402
import sgt_results as R  # noqa: E402

CELL_GEOM = {name: C.SIZES[c["size"]] for name, c in R.load()["cells"].items()}


def one(task):
    name, art, i = task
    cell = R.load()["cells"][name]
    row = next(r for r in cell["rows"] if r["art"] == art and r["i"] == i)
    lo, hi = C.SIZES[cell["size"]]
    a_cent = I.a_cent_at(I.make_instance(art, lo, hi, i), cell["aht"])
    s = PL.Settings(profile=art, size=cell["size"], aht=cell["aht"], goal=cell["goal"], catalog=cell["catalog"], seed=i)
    t0 = time.perf_counter()
    prob, plans, s1 = PL.stage1(s)
    o, s2 = PL.stage2(s, prob, plans)
    v = row["v"]
    f = R.FIELD
    out = {"cell": name, "art": art, "i": i, "t1": round(s1, 3), "t2": round(s2, 3), "peak": max(prob.a),
           "a_cent_ok": ("a_cent" not in row) or row["a_cent"] == a_cent}
    out["A"] = [plans["Z"].cost, v["A"][f["cost"]], round(plans["Z"].day_sl, 5), v["A"][f["sl"]]]
    out["Az"] = [plans["K"].cost, v["Az"][f["cost"]], plans["K"].z, v["Az"][f["z"]]]
    if "BFz" in v and "G" in plans:
        out["BFz"] = [plans["G"].cost, v["BFz"][f["cost"]]]
    out["DP"] = [plans["ODP"].cost, v["B"][f["dp"]]]
    out["B"] = [None if o is None else o.cost, v["B"][f["cost"]], v["B"][f["replaced"]], v["B"][f["opt"]],
                None if o is None else (o.status, o.bound)]
    out["wall"] = round(time.perf_counter() - t0, 3)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--cells", default="")
    ap.add_argument("--n", type=int, default=100)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    data = R.load()
    names = [c for c in args.cells.split(",") if c] or data["meta"]["order"]
    tasks = [(n, r["art"], r["i"]) for n in names for r in data["cells"][n]["rows"] if r["i"] < args.n]
    print(f"{len(tasks)} Instanzen, {args.workers} Prozesse", flush=True)
    t0 = time.time()
    res = []
    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        for k, r in enumerate(ex.map(one, tasks, chunksize=4)):
            res.append(r)
            if (k + 1) % 250 == 0:
                print(f"  {k + 1}/{len(tasks)} nach {time.time() - t0:.0f} s", flush=True)
    text = json.dumps({"wall_s": round(time.time() - t0), "results": res}, ensure_ascii=False)
    pathlib.Path(args.out).write_text(text, encoding="utf-8", newline="\n")
    summarize(res)
    print("fertig", round(time.time() - t0), "s", flush=True)


def summarize(res):
    cells = {}
    for r in res:
        cells.setdefault(r["cell"], []).append(r)
    print(f"{'Zelle':10s} {'n':>4s} {'A=':>5s} {'sl':>4s} {'Az<':>4s} {'Az=':>4s} {'Az>':>4s} {'BFz>':>5s} {'DP=':>5s} {'B<':>4s} {'B=':>4s} {'B>':>4s} {'B>+2':>5s} {'maxB':>5s}")
    for name, rr in cells.items():
        n = len(rr)
        a_eq = sum(1 for r in rr if r["A"][0] == r["A"][1])
        sl_ok = sum(1 for r in rr if abs(r["A"][2] - r["A"][3]) < 2e-5)
        az_lt = sum(1 for r in rr if r["Az"][0] < r["Az"][1])
        az_eq = sum(1 for r in rr if r["Az"][0] == r["Az"][1])
        az_gt = sum(1 for r in rr if r["Az"][0] > r["Az"][1])
        bfz_gt = sum(1 for r in rr if "BFz" in r and r["BFz"][0] > r["BFz"][1])
        dp_eq = sum(1 for r in rr if r["DP"][0] == r["DP"][1])
        b = [r["B"][0] - r["B"][1] for r in rr if r["B"][0] is not None]
        print(f"{name:10s} {n:4d} {a_eq:5d} {sl_ok:4d} {az_lt:4d} {az_eq:4d} {az_gt:4d} {bfz_gt:5d} {dp_eq:5d} "
              f"{sum(1 for x in b if x < 0):4d} {sum(1 for x in b if x == 0):4d} {sum(1 for x in b if x > 0):4d} {sum(1 for x in b if x > 2):5d} {max(b):5d}")


if __name__ == "__main__":
    main()
