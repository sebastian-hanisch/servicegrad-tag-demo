"""Presets (alle auf gemessenen Zellen der Vorab-Messreihe), ihre Geschichten und die Abnahmekriterien, die die Tests prüfen.

Jedes Preset gibt eine Einstellung und eine Geschichte vor; die Kriterien stehen als Funktionen auf den Kennzahlen und werden in
tests/test_stories.py an der Messreihe (100 Instanzen je Profil) UND an der gezeigten Instanz geprüft. Kein Kriterium nutzt O mit
Schichten (Zeitlimit): nur Z, K, O ohne Schichtstruktur und die Simulation mit festem Zufalls-Seed.
"""

import sgt_constants as C

VIEW_OPTIONS = ("alle", "Z und K", "Z und O")
VIEW_KEYS = {"alle": ("Z", "K", "G", "O"), "Z und K": ("Z", "K"), "Z und O": ("Z", "O")}
VIEW_HELP = "Reine Anzeigewahl: welche Pläne in den Diagrammen des Methodenvergleichs stehen (keine Einstellung der Rechnung)."

_BASE = {"profile": "zwei_spitzen", "size": "mittel", "aht": 240, "goal": 80, "catalog": "6/8/10", "seed": C.DEFAULT_SEED}

PRESET_ORDER = ("Standard", "Flache Last", "Schmaler Gipfel", "Hohes Ziel", "Nur 8-Stunden-Schichten")
PRESETS = {
    "Standard": dict(_BASE),
    "Flache Last": dict(_BASE, profile="flach"),
    "Schmaler Gipfel": dict(_BASE, profile="steile_spitze"),
    "Hohes Ziel": dict(_BASE, goal=95),
    "Nur 8-Stunden-Schichten": dict(_BASE, catalog="8"),
}
PRESET_HELP = {
    "Standard": "Der Grundfall in der Reihenfolge der Fallstricke: Z liefert über dem Ziel, K holt Personenstunden zurück, O verspricht viel und fällt in der "
                "Simulation, G spart kaum etwas. Zwei Spitzen, mittlerer Betrieb, Ziel 80 %, Schichten 6, 8, 10 h.",
    "Flache Last": "Wenig zu holen, viel zu verlieren: eine kleine Scheinersparnis, aber der größte Einbruch in der Simulation, weil die wenigen leeren Stunden "
                   "in voller Last liegen.",
    "Schmaler Gipfel": "Die größte Scheinersparnis, der kleinste Einbruch: Die leeren Stunden liegen nachts, wo kaum Anrufe sind. Ohne Simulation wäre die Zahl "
                       "irreführend, mit ihr ist sie fast berechtigt.",
    "Hohes Ziel": "Bei Ziel 95 % gibt es nichts mehr aufzugeben: O fällt auf G zurück, die Fallstricke 2 und 3 verschwinden, nur die Übererfüllung bleibt.",
    "Nur 8-Stunden-Schichten": "Die Schichtstruktur erzwingt die Übererfüllung: Die Kalibrierung holt viel, die gleiche Qualität kaum, und O mit Schichten ist "
                               "hier am schwersten zu beweisen.",
}


# --- Abnahmekriterien ---------------------------------------------------------------------------------------------------------------------
# Je Kriterium: (Beschriftung, Kennzahl, Vergleich, Schwelle). Die Kennzahlen kommen in zwei Fassungen: "meas" aus der Messreihe (alle 100
# Instanzen des Profils, Simulation: 20) und "inst" aus der gezeigten Instanz (Live-Rechnung). Fehlt eine Kennzahl (None), entfällt das
# Kriterium in dieser Fassung. Kein Kriterium nutzt O mit Schichten (Zeitlimit); O steht nur als "o_pct" der Messreihe und der DP-Fassung.
#   over   Tages-Servicegrad von Z minus Ziel (Punkte)       k_pct   Ersparnis von K gegenüber Z (%)
#   o_pct  Ersparnis von O gegenüber Z (%)                    empty   leere Stunden von O (Mittel bzw. Instanz)
#   d_O    O simuliert minus Modell (Punkte)                   g_pct   G gegenüber K (%)
#   z_sl   Tages-Servicegrad von Z (%)                         beq_pct Ersparnis von Beq gegenüber Z (%)
#   o_minus_bf  O minus BF in Prozentpunkten der Ersparnis (nur Messreihe)
CRITERIA = {
    "Standard": [("Z liefert mindestens 5 Punkte über dem Ziel", "over", ">=", 5.0), ("K spart mindestens 4 %", "k_pct", ">=", 4.0),
                 ("O lässt mindestens 3 Stunden leer", "empty", ">=", 3.0), ("O liegt simuliert mindestens 5 Punkte unter dem Modell", "d_O", "<=", -5.0),
                 ("G spart höchstens 2 % gegenüber K", "g_pct", "<=", 2.0)],
    "Flache Last": [("O spart höchstens 8 %", "o_pct", "<=", 8.0), ("K spart höchstens 5 %", "k_pct", "<=", 5.0),
                    ("O lässt höchstens 3 Stunden leer", "empty", "<=", 3.0), ("O liegt simuliert mindestens 10 Punkte unter dem Modell", "d_O", "<=", -10.0)],
    "Schmaler Gipfel": [("O spart mindestens 15 %", "o_pct", ">=", 15.0), ("O liegt simuliert höchstens 5 Punkte unter dem Modell", "d_O", ">=", -5.0),
                        ("G spart höchstens 1 % gegenüber K", "g_pct", "<=", 1.0)],
    "Hohes Ziel": [("O spart höchstens 0,5 Punkte mehr als BF", "o_minus_bf", "<=", 0.5), ("O lässt im Mittel höchstens 0,5 Stunden leer", "empty", "<=", 0.5),
                   ("K spart mindestens 3 %", "k_pct", ">=", 3.0), ("Z liefert mindestens 96 %", "z_sl", ">=", 96.0)],
    "Nur 8-Stunden-Schichten": [("K spart mindestens 10 %", "k_pct", ">=", 10.0), ("Beq spart höchstens 1 %", "beq_pct", "<=", 1.0),
                                ("Z liefert mindestens 90 %", "z_sl", ">=", 90.0)],
}


def check(name, facts):
    """Prüft die Kriterien eines Presets gegen ein Wörterbuch von Kennzahlen: Liste (Beschriftung, erfüllt oder None, Wert)."""
    out = []
    for label, key, op, thr in CRITERIA[name]:
        v = facts.get(key)
        if v is None:
            out.append((label, None, None))
            continue
        out.append((label, v >= thr if op == ">=" else v <= thr, v))
    return out


def measured_facts(name):
    """Kennzahlen des Presets aus der Messreihe: Mittel über die 100 Instanzen des Profils in der Zelle des Presets."""
    import sgt_results as R
    p = PRESETS[name]
    cell = R.cell_for(p["size"], p["goal"], p["aht"], p["catalog"])
    rows = R.rows(cell, p["profile"])
    sim = R.sim_rows(rows)
    facts = {"z_sl": R.field_mean(rows, "A", "sl", 100), "k_pct": R.saving(rows, "Az")[0], "o_pct": R.saving(rows, "B")[0],
             "empty": R.field_mean(rows, "B", "empty"), "beq_pct": R.saving(rows, "Beq")[0]}
    facts["over"] = facts["z_sl"] - p["goal"]
    facts["o_minus_bf"] = facts["o_pct"] - R.saving(rows, "BF")[0]
    facts["d_O"] = R.sim_delta(sim, "B")[0] if sim else None
    facts["g_pct"] = R.saving(rows, "BFz", "Az")[0] if R.has(rows, "BFz", "Az") else None
    return facts


def instance_facts(f):
    """Kennzahlen der gezeigten Instanz aus `sgt_evaluation.figures` (Live-Rechnung)."""
    return {"z_sl": f["z_sl"], "over": f["over"], "k_pct": f["k_pct"], "o_pct": f.get("o_pct"), "empty": f.get("o_empty"), "d_O": f.get("d_O"),
            "g_pct": f.get("g_pct"), "beq_pct": None, "o_minus_bf": None}
