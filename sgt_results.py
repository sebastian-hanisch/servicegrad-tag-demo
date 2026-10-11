"""Vorgerechnete Ergebnisse: die 13 Zellen der Vorab-Messreihe (data/sgt_results.json) und die Abdeckung aller 216 Kombinationen
(data/sgt_coverage.json). Nichts davon wird im Browser gerechnet; die Dateien erzeugen tools/build_results.py und tools/sweep.py.

Konvention: Ersparnisse immer in Prozent der Kosten der Bezugsvariante derselben Instanz (gepaart), Mittel mit Standardfehler.
Kürzel der Messreihe: A = Z, Az = K, BFz = G, B = O; dazu Beq, BF, B1, Bz (nur vorgerechnet).
"""

import functools
import json
import math
import pathlib

import sgt_constants as C

DATA = pathlib.Path(__file__).resolve().parent / "data"
FIELDS = ["cost", "sl", "int50", "anr50", "slmin", "empty", "opt", "replaced", "sim", "z", "dp", "gap"]
FIELD = {name: i for i, name in enumerate(FIELDS)}
MESS_TO_APP = {"A": "Z", "Az": "K", "BFz": "G", "B": "O"}


@functools.lru_cache(maxsize=1)
def load():
    return json.loads((DATA / "sgt_results.json").read_text(encoding="utf-8"))


@functools.lru_cache(maxsize=1)
def load_coverage():
    p = DATA / "sgt_coverage.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def mean(xs):
    xs = list(xs)
    return sum(xs) / len(xs) if xs else float("nan")


def se(xs):
    xs = list(xs)
    if len(xs) < 2:
        return float("nan")
    m = mean(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1) / len(xs))


def cell_names():
    return list(load()["meta"]["order"])


def cell(name):
    return load()["cells"][name]


def rows(name, art=None):
    return [r for r in cell(name)["rows"] if art is None or r["art"] == art]


def get(row, variant, field):
    v = row["v"].get(variant)
    return None if v is None else v[FIELD[field]]


def has(rows_, *variants):
    return [r for r in rows_ if all(r["v"].get(v) for v in variants)]


def saving(rows_, variant, ref="A"):
    """Mittlere Kostenersparnis von `variant` gegenüber `ref` in Prozent (gepaart je Instanz), Standardfehler, Zahl der Instanzen."""
    use = has(rows_, variant, ref)
    q = [100.0 * (get(r, ref, "cost") - get(r, variant, "cost")) / get(r, ref, "cost") for r in use]
    return mean(q), se(q), len(q)


def k_cost(row):
    """Kosten von K im Raster 0,01: in den neun Zellen mit grobem Raster der live nachgerechnete Wert (`kfine`), sonst der gespeicherte."""
    return row["kfine"][0] if "kfine" in row else get(row, "Az", "cost")


def saving_k(rows_):
    """Ersparnis von K gegenüber Z im Raster 0,01 (Mittel, Standardfehler, n); die Messreihe selbst rechnete in neun Zellen mit 0,05."""
    q = [100.0 * (get(r, "A", "cost") - k_cost(r)) / get(r, "A", "cost") for r in rows_ if r["v"].get("Az")]
    return mean(q), se(q), len(q)


def hours_saved(rows_, variant, ref="A"):
    use = has(rows_, variant, ref)
    q = [get(r, ref, "cost") - get(r, variant, "cost") for r in use]
    return mean(q), se(q)


def field_mean(rows_, variant, field, scale=1.0):
    use = [r for r in rows_ if r["v"].get(variant)]
    return scale * mean(get(r, variant, field) for r in use)


def share(rows_, variant, pred):
    use = [r for r in rows_ if r["v"].get(variant)]
    return 100.0 * sum(1 for r in use if pred(r["v"][variant])) / len(use) if use else float("nan")


def proven_share(rows_, variant):
    """Anteil bewiesener Optima der Kosten in Prozent; ersetzte Einträge zählen nicht als bewiesen (anders als die Auswertung der Messreihe)."""
    return share(rows_, variant, lambda v: v[FIELD["opt"]] == 1 and v[FIELD["replaced"]] == 0)


def sim_rows(rows_):
    """Instanzen mit Simulation (Basiszelle, Nummern 0 bis 19 je Profil)."""
    return [r for r in rows_ if r["v"].get("A") and r["v"]["A"][FIELD["sim"]] is not None]


def sim_delta(rows_, variant):
    """Simulation minus Modell des Tages-Servicegrads in Punkten (Mittel, Standardfehler, n)."""
    use = [r for r in rows_ if r["v"].get(variant) and r["v"][variant][FIELD["sim"]] is not None]
    d = [100 * (get(r, variant, "sim") - get(r, variant, "sl")) for r in use]
    return mean(d), se(d), len(d)


def hold_share(rows_, variant, goal):
    use = [r for r in rows_ if r["v"].get(variant) and r["v"][variant][FIELD["sim"]] is not None]
    return 100.0 * sum(1 for r in use if get(r, variant, "sim") >= goal / 100.0 - C.HOLD_TOLERANCE) / len(use) if use else float("nan")


def cell_for(size, goal, aht, catalog):
    """Name der Messreihen-Zelle, die genau dieser Einstellung entspricht, sonst None."""
    for name in cell_names():
        c = cell(name)
        if (c["size"], c["goal"], c["aht"], c["catalog"]) == (size, goal, aht, catalog):
            return name
    return None


def combo_key(size, goal, aht, catalog):
    return f"{size}|{goal}|{aht}|{catalog}"


def coverage_for(size, goal, aht, catalog, profile):
    """Statistik der Abdeckung (20 Instanzen) für Einstellung und Profil, oder None."""
    cov = load_coverage()
    if cov is None:
        return None
    return cov["cells"].get(combo_key(size, goal, aht, catalog), {}).get(profile)


# --- Tabellen für die Seite ---------------------------------------------------------------------------------------------------------------

def de1(x, d=1):
    return f"{x:.{d}f}".replace(".", ",")


def percentile(xs, q):
    xs = sorted(xs)
    if not xs:
        return float("nan")
    pos = (len(xs) - 1) * q
    lo = int(math.floor(pos))
    hi = min(lo + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (pos - lo)


def cells_table():
    """Die 13 Zellen: Ersparnis gegenüber Z je Variante (alle Profile gemittelt), was Z liefert, Raster von K, Anteil bewiesener Optima von O."""
    out = []
    for name in cell_names():
        c = cell(name)
        rows_ = rows(name)
        row = {"Zelle": c["label"], "Instanzen": len(rows_), "Z liefert (%)": de1(field_mean(rows_, "A", "sl", 100))}
        for v, label in (("B", "O spart (%)"), ("BF", "BF spart (%)"), ("Az", "K spart (%)"), ("Beq", "Beq spart (%)")):
            row[label] = de1(saving_k(rows_)[0] if v == "Az" else saving(rows_, v)[0]) if has(rows_, v) else "-"
        row["K in der Messreihe (Raster 0,05)"] = de1(saving(rows_, "Az")[0]) if c["az_step"] == 0.05 else "-"
        row["O bewiesen (%)"] = de1(proven_share(rows_, "B"), 0)
        out.append(row)
    return out


def profile_table(name="base"):
    """Je Profil der Zelle: Ersparnis von O und K, leere Stunden, simulierter minus Modell-Servicegrad (20 Instanzen), Anteil gehaltenes Ziel."""
    c = cell(name)
    out = []
    for art in c["profiles"]:
        rows_ = rows(name, art)
        sim = sim_rows(rows_)
        out.append({"Profil": C.PROFILE_LABELS[art], "O spart (%)": de1(saving(rows_, "B")[0]), "K spart (%)": de1(saving(rows_, "Az")[0]),
                    "leere Stunden (O)": de1(field_mean(rows_, "B", "empty")),
                    "Simulation minus Modell (Punkte)": de1(sim_delta(sim, "B")[0]) if sim else "-",
                    "Ziel gehalten (%)": de1(hold_share(sim, "B", c["goal"]), 0) if sim else "-"})
    return out


def decomposition(name="base"):
    """Anteil der Ersparnis von O (in Personenstunden), den K, Beq, BF und B1 schon erreichen; je Profil und alle."""
    c = cell(name)
    out = []
    for art in list(c["profiles"]) + [None]:
        rows_ = rows(name, art)
        tot = mean(get(r, "A", "cost") - get(r, "B", "cost") for r in rows_)
        row = {"Profil": C.PROFILE_LABELS[art] if art else "alle", "O spart (h)": de1(tot)}
        for v, label in (("Az", "K"), ("Beq", "Beq"), ("BF", "BF"), ("B1", "B1")):
            use = has(rows_, v)
            row[label + " erreicht (%)"] = de1(100 * mean(get(r, "A", "cost") - get(r, v, "cost") for r in use) / tot, 0) if use and tot else "-"
        out.append(row)
    return out


def proof_table():
    """Beweisstatus der Kosten je Zelle (O): bewiesen ohne ersetzte Einträge, ersetzte Einträge, Marke unter 80 %."""
    out = []
    for name in cell_names():
        rows_ = rows(name)
        n_rep = sum(1 for r in rows_ if r["v"]["B"][FIELD["replaced"]] == 1)
        p = proven_share(rows_, "B")
        out.append({"Zelle": cell(name)["label"], "O bewiesen (%)": de1(p, 1), "ersetzt": n_rep, "Instanzen": len(rows_), "Marke": "unter 80 %" if p < 80 else ""})
    return out


def quantile_table():
    """Median, 10. und 90. Perzentil der Ersparnis je Zelle und Variante (Prozent der Personenstunden), mit Instanzzahl."""
    out = []
    for name in cell_names():
        rows_ = rows(name)
        for v, label in (("B", "O"), ("BF", "BF"), ("Az", "K"), ("Beq", "Beq")):
            use = has(rows_, v)
            if not use:
                continue
            cost = k_cost if v == "Az" else (lambda r, v=v: get(r, v, "cost"))
            q = [100.0 * (get(r, "A", "cost") - cost(r)) / get(r, "A", "cost") for r in use]
            out.append({"Zelle": cell(name)["label"], "Variante": label, "Instanzen": len(q), "Median": de1(percentile(q, 0.5)),
                        "P10": de1(percentile(q, 0.1)), "P90": de1(percentile(q, 0.9)), "Mittel": de1(mean(q))})
    return out


def coverage_counts():
    """Zählung der Abdeckung: je Aussage (over, empty, drop, couple) die Zahl der (Kombination, Profil)-Zeilen mit gilt, unklar, gilt nicht,
    insgesamt und je Tagesziel; dazu die Zahl der Zeilen und der Läufe."""
    cov = load_coverage()
    if cov is None:
        return None
    out = {"rows": 0, "runs": cov["meta"]["runs"], "total": {}, "by_goal": {}}
    for key, profs in cov["cells"].items():
        goal = int(key.split("|")[1])
        for s in profs.values():
            out["rows"] += 1
            for stm, v in s["verdict"].items():
                out["total"].setdefault(stm, {"gilt": 0, "unklar": 0, "gilt nicht": 0})[v] += 1
                out["by_goal"].setdefault(goal, {}).setdefault(stm, {"gilt": 0, "unklar": 0, "gilt nicht": 0})[v] += 1
    return out
