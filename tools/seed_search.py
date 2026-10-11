"""Standard-Zufalls-Seed je Preset: die typischste Instanz einer (Zelle, Profil)-Gruppe der Messreihe.

Typisch heißt hier: kleinster standardisierter euklidischer Abstand der Kennzahlen der Instanz zu den Mitteln der Gruppe. Kennzahlen,
soweit in der Zelle gemessen: Ersparnis von K und O gegenüber Z (Prozent), leere Stunden von O, Tages-Servicegrad von Z, simulierter
minus Modell-Tages-Servicegrad von O (nur Basiszelle, Nummern 0 bis 19), G gegenüber K (nur Basis und Stresszelle).

Aufruf: python tools/seed_search.py [--cell base --profile zwei_spitzen --top 5]
"""

import argparse
import math
import pathlib
import statistics as st
import sys

sys.dont_write_bytecode = True
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import sgt_results as R  # noqa: E402


def figures(r):
    cost = lambda v: R.get(r, v, "cost")  # noqa: E731
    out = {"az": 100.0 * (cost("A") - cost("Az")) / cost("A"), "b": 100.0 * (cost("A") - cost("B")) / cost("A"),
           "leer": R.get(r, "B", "empty"), "asl": 100 * R.get(r, "A", "sl")}
    if R.get(r, "B", "sim") is not None:
        out["dsim"] = 100 * (R.get(r, "B", "sim") - R.get(r, "B", "sl"))
    if r["v"].get("BFz") and r["v"].get("Az"):
        out["g"] = 100.0 * (cost("Az") - cost("BFz")) / cost("Az")
    return out


def search(cell, profile, top=5):
    rows = [r for r in R.rows(cell, profile)]
    if any(R.get(r, "B", "sim") is not None for r in rows):
        rows = [r for r in rows if R.get(r, "B", "sim") is not None]
    fig = [(r["i"], figures(r)) for r in rows]
    keys = [k for k in fig[0][1] if all(k in f for _, f in fig)]
    mu = {k: st.mean(f[k] for _, f in fig) for k in keys}
    sd = {k: st.pstdev([f[k] for _, f in fig]) or 1.0 for k in keys}
    ranked = sorted(((math.sqrt(sum(((f[k] - mu[k]) / sd[k]) ** 2 for k in keys)), i, f) for i, f in fig), key=lambda x: x[0])
    return ranked[:top], mu, keys, len(fig)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cell", default="base")
    ap.add_argument("--profile", default="zwei_spitzen")
    ap.add_argument("--top", type=int, default=5)
    a = ap.parse_args()
    ranked, mu, keys, n = search(a.cell, a.profile, a.top)
    print(f"{a.cell} / {a.profile}: {n} Instanzen, Kennzahlen {keys}")
    print("Mittel:", {k: round(v, 2) for k, v in mu.items()})
    for dist, i, f in ranked:
        print(f"  Zufalls-Seed {i:2d}  Abstand {dist:.2f}  " + "  ".join(f"{k} {v:.1f}" for k, v in f.items()))


if __name__ == "__main__":
    main()
