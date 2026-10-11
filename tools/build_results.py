"""Erzeugt data/sgt_results.json aus den Rohdaten der Vorab-Messreihe (sweep_data.json, 13 Zellen, 5.400 Instanzen).

Aufruf (Python mit vollem Pfad):
    python tools/build_results.py --source "<Pfad>/messreihe_bedarf_plan/sweep_data.json"

Die Rohdatei hat je Instanz und Variante Kosten, Tages-Servicegrad, Anteile unter 50 %, kleinsten Stunden-Servicegrad, leere Stunden,
Beweisstatus und (in der Basis, 20 Instanzen je Profil) den simulierten Tages-Servicegrad. Hier wird sie verdichtet und dabei eine
bekannte Unschärfe der Auswertung der Messreihe behoben: Hat der Löser im Zeitlimit für eine weitere Variante etwas Schlechteres
gefunden als die bekannte Lösung einer engeren (ein zulässiger Fund der engeren ist auch für die weitere zulässig), gilt "bestbekannt".
Solche ersetzten Einträge erbten in der Auswertung der Messreihe das Beweis-Flag der engeren Variante und galten fälschlich als
bewiesen; hier steht `replaced = 1` und `opt = 0`.

Zeilenformat je Variante: [cost, sl, int50, anr50, slmin, empty, opt, replaced, sim, z, dp, gap]
(sim, z, dp nur, wo vorhanden, sonst null; gap = Kosten minus bewiesene untere Schranke des Lösers).

Mit `--k-fine <reproduktion.json>` (Ausgabe von tools/reproduce_messreihe.py) trägt jede Instanz der neun Zellen mit dem groben z-Raster 0,05 zusätzlich
`kfine = [Kosten, z]` von K im Raster 0,01 (AP 0 c): die Spalte K der Messreihe in diesen Zellen ist sonst nur eine Untergrenze der Ersparnis.
"""

import argparse
import json
import pathlib

FIELDS = ["cost", "sl", "int50", "anr50", "slmin", "empty", "opt", "replaced", "sim", "z", "dp", "gap"]
SIZE_OF = {(300, 600): "klein", (800, 1500): "mittel", (2500, 4000): "gross"}
CAT_OF = {(8,): "8", (6, 8, 10): "6/8/10", (4, 6, 8): "4/6/8", (3, 4, 5): "3/4/5", tuple(range(3, 13)): "3 bis 12", (3, 4): "3/4"}
LABELS = {"ziel70": "Ziel 70 %", "base": "Basis (Ziel 80 %)", "ziel90": "Ziel 90 %", "ziel95": "Ziel 95 %", "kat8": "Katalog nur 8 h",
          "kat468": "Katalog 4/6/8 h", "kat345": "Katalog 3/4/5 h", "kat3bis12": "Katalog 3 bis 12 h", "aht120": "Bediendauer 120 s",
          "aht480": "Bediendauer 480 s", "klein": "Größe klein", "gross": "Größe groß", "hart": "Stresszelle (Katalog 3/4 h, Ziel 95 %)"}
ORDER = ["ziel70", "base", "ziel90", "ziel95", "kat8", "kat468", "kat345", "kat3bis12", "aht120", "aht480", "klein", "gross", "hart"]
# von eng nach weit: eine zulässige Lösung der engeren Variante ist auch für die weitere zulässig
FEASIBLE_FROM = {"BFz": ("Az",), "Bz": ("BFz",), "Beq": ("A",), "BF": ("A", "BFz", "Az"), "B1": ("BF", "A", "Az", "BFz"),
                 "B": ("B1", "BF", "Beq", "A", "Az", "BFz", "Bz")}


def refine(cells):
    """Bestbekannt-Regel; Rückgabe: Anzahl ersetzter Einträge je (Zelle, Variante)."""
    count = {}
    for name, blk in cells.items():
        for r in blk["instanzen"]:
            for v, sources in FEASIBLE_FROM.items():
                for q in sources:
                    if not r.get(v) or not r.get(q):
                        continue
                    if q == "Az" and v in ("BF", "BFz") and r["Az"].get("z", 0) < 0.5:
                        continue   # K mit z < 0,5 darf Stunden unter dem Mindestwert haben: für BF nicht zulässig
                    if r[q]["kosten"] < r[v]["kosten"]:
                        count[(name, v)] = count.get((name, v), 0) + 1
                        r[v] = dict(r[q], ersetzt_durch=q, opt=False)
    return count


def row_of(x):
    gap = x.get("luecke")
    replaced = 1 if x.get("ersetzt_durch") else 0
    return [x["kosten"], x["sl"], x["int50"], x["anr50"], x["slmin"], x["leer"], 0 if replaced else int(x.get("opt") or 0), replaced,
            x.get("sim"), x.get("z"), x.get("dp"), gap]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", required=True)
    ap.add_argument("--k-fine", default="", help="Reproduktionslauf mit den Kosten von K im Raster 0,01 (nur Zellen mit Raster 0,05)")
    ap.add_argument("--out", default=str(pathlib.Path(__file__).resolve().parent.parent / "data" / "sgt_results.json"))
    args = ap.parse_args()
    raw = json.loads(pathlib.Path(args.source).read_text(encoding="utf-8"))
    cells = raw["zellen"]
    replaced = refine(cells)
    fine = {}
    if args.k_fine:
        for r in json.loads(pathlib.Path(args.k_fine).read_text(encoding="utf-8"))["results"]:
            fine[(r["cell"], r["art"], r["i"])] = [r["Az"][0], r["Az"][2]]
    out = {"meta": {"source": "messreihe_bedarf_plan/sweep_data.json (Vorab-Messreihe, 2026-10-10)", "per_cell_profile": raw["n_je_zelle_profil"],
                    "duration_s": raw["dauer_s"], "fields": FIELDS, "order": ORDER,
                    "replaced": {f"{k[0]}:{k[1]}": v for k, v in sorted(replaced.items())}},
           "cells": {}}
    for name in ORDER:
        blk = cells[name]
        z = blk["zelle"]
        rows = []
        for r in blk["instanzen"]:
            row = {"art": r["art"], "i": r["i"], "sec": r.get("sek"), "v": {}}
            for v in ("A", "Az", "B", "B1", "BF", "Beq", "BFz", "Bz"):
                if r.get(v):
                    row["v"][v] = row_of(r[v])
            if (name, r["art"], r["i"]) in fine and (z.get("az_schritt") or 0.05) == 0.05:
                row["kfine"] = fine[(name, r["art"], r["i"])]
            if "plaene" in r and "a_cent" in r:
                row["plans"] = r["plaene"]
                row["a_cent"] = r["a_cent"]
            rows.append(row)
        out["cells"][name] = {"label": LABELS[name], "size": SIZE_OF[tuple(z["groesse"])], "goal": round(100 * z["ziel"]), "aht": z["aht"],
                              "catalog": CAT_OF[tuple(z["katalog"])], "profiles": z["profile"], "az_step": z.get("az_schritt") or 0.05,
                              "n_sim": z.get("n_sim", 0), "variants": z["varianten"], "rows": rows}
    p = pathlib.Path(args.out)
    p.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(out, ensure_ascii=False, separators=(",", ":"))
    p.write_text(text, encoding="utf-8", newline="\n")
    print(f"{p}: {len(text) / 1e6:.2f} MB, {sum(len(c['rows']) for c in out['cells'].values())} Instanzen, ersetzt: {out['meta']['replaced']}")


if __name__ == "__main__":
    main()
