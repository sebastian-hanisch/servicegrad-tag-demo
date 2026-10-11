"""Kennzahlen, Meldungen in drei Zuständen und erzeugte Sätze aus den Live-Zahlen einer Instanz.

Die vier Abschnitte der Seite folgen der Reihenfolge der Fallstricke: ① Übererfüllung, ② leere Stunden, ③ Rückstau, ④ echte Kopplung.
Jeder hat drei Zustände mit eigener Meldung (Schwellen: sgt_constants). Delta immer als "mein Wert minus Bezug".
"""

import sgt_constants as C
import sgt_results as R


def de(x, d=1, sign=False):
    """Zahl mit Dezimalkomma (nur die Zahl, nie ein ganzer Satz)."""
    s = f"{x:+.{d}f}" if sign else f"{x:.{d}f}"
    return s.replace(".", ",")


def thou(n):
    """Ganze Zahl mit Tausenderpunkt (nur die Zahl umformatieren, nie einen ganzen Satz)."""
    return f"{int(n):,}".replace(",", ".")


def pct(x, d=1):
    return de(x, d) + " %"


def hours(h):
    h = int(round(h))
    return f"{thou(h)} Personenstunde" + ("" if h == 1 else "n")


def figures(live):
    """Kennzahlen der Live-Rechnung (alles in Prozent bzw. Personenstunden); fehlende Pläne ergeben None."""
    s = live.settings
    goal = float(s.goal)
    z, k, g, o, odp = (live.plans.get(x) for x in ("Z", "K", "G", "O", "ODP"))
    f = {"goal": goal, "z": z, "k": k, "g": g, "o": o, "odp": odp}
    f["z_sl"] = 100 * z.day_sl
    f["over"] = f["z_sl"] - goal
    f["k_h"] = z.cost - k.cost
    f["k_pct"] = 100.0 * f["k_h"] / z.cost
    f["k_sl"] = 100 * k.day_sl
    f["k_z"] = k.z
    f["g_h"] = k.cost - g.cost if g is not None else None
    f["g_pct"] = 100.0 * f["g_h"] / k.cost if g is not None else None
    if o is not None:
        f["o_h"] = z.cost - o.cost
        f["o_pct"] = 100.0 * f["o_h"] / z.cost
        f["o_sl"] = 100 * o.day_sl
        f["o_empty"] = o.figures["empty"]
        f["o_below"] = o.figures["n_hours_below"]
        f["o_calls_below"] = 100 * o.figures["calls_below"]
    if odp is not None:
        f["odp_h"] = z.cost - odp.cost
        f["odp_pct"] = 100.0 * f["odp_h"] / z.cost
    sims = live.sims
    for key in C.PLAN_KEYS:
        sim = sims.get(key)
        plan = live.plans.get(key)
        if sim is not None and plan is not None:
            f[f"sim_{key}"] = 100 * sim.sl
            f[f"se_{key}"] = 100 * sim.se
            f[f"d_{key}"] = 100 * (sim.sl - plan.day_sl)
            f[f"hold_{key}"] = sim.sl >= goal / 100.0 - C.HOLD_TOLERANCE
    return f


# --- Zustände -----------------------------------------------------------------------------------------------------------------------------

def state_over(f):
    """① Übererfüllung: 1 = K holt Personenstunden zurück, 2 = Z und K kosten dasselbe, 3 = K erreicht die Untergrenze der z-Suche."""
    if f["k_z"] is not None and f["k_z"] <= C.Z_LOWER + 1e-9:
        return 3
    return 1 if f["k_h"] > 0 else 2


def state_empty(f):
    """② Leere Stunden: 1 = Stunden bleiben leer, 2 = keine leere, aber Stunden unter 50 %, 3 = nichts aufzugeben."""
    if f.get("o_empty", 0) >= 1:
        return 1
    return 2 if f.get("o_below", 0) >= 1 else 3


def state_drop(f):
    """③ Rückstau: 1 = Simulation mehr als 3 Punkte und mehr als 2 SE unter dem Modell, 3 = über dem Modell, sonst 2."""
    if "d_O" not in f:
        return None
    d, se = f["d_O"], f["se_O"]
    if d <= -C.DROP_POINTS and d < -C.DROP_SE * se:
        return 1
    if d >= C.NOISE_POINTS and d > C.DROP_SE * se:
        return 3
    return 2


def state_couple(f):
    """④ Kopplung: 1 = G spart mindestens eine Personenstunde gegenüber K, 2 = gleich, 3 = G teurer (K unterschreitet den Mindestwert)."""
    if f["g_h"] is None:
        return None
    return 1 if f["g_h"] >= 1 else (2 if f["g_h"] == 0 else 3)


def statements(live, f=None):
    """Die vier Aussagen als Liste von Wörterbüchern: key, title, state, level (success/info/warning), text."""
    f = f or figures(live)
    s = live.settings
    out = []
    # ① Übererfüllung
    st = state_over(f)
    if st == 1:
        text = (f"Z liefert {pct(f['z_sl'])} Tages-Servicegrad statt {s.goal} %. Ein einheitliches Stundenziel von {de(f['k_z'], 2)} (K) hält das Tagesziel "
                f"mit {pct(f['k_sl'])} und spart {hours(f['k_h'])} ({pct(f['k_pct'])}).")
        level = "warning"
    elif st == 2:
        text = (f"Z und K kosten dasselbe ({thou(f['z'].cost)} Personenstunden): Die Schichtstruktur erzwingt die Übererfüllung von {de(f['over'], 1)} Punkten, "
                f"es gibt nichts zurückzuholen.")
        level = "info"
    else:
        text = (f"K senkt das Stundenziel bis zur Untergrenze {de(C.Z_LOWER, 2)} der Suche und spart {hours(f['k_h'])} ({pct(f['k_pct'])}): "
                f"Die Schichtlängen ({C.CATALOG_LABELS[s.catalog]}) erzwingen die Übererfüllung von Z ({pct(f['z_sl'])}), "
                f"auch ein sehr niedriges Stundenziel führt nicht unter das Tagesziel.")
        level = "info"
    out.append({"key": "over", "title": "① Übererfüllung: das Tagesziel als Stundenziel", "state": st, "level": level, "text": text})
    # ② leere Stunden
    st = state_empty(f)
    if f.get("o") is None:
        out.append({"key": "empty", "title": "② Leere Stunden: die scheinbare Ersparnis", "state": None, "level": "info",
                    "text": "O mit Schichten wurde nicht berechnet."})
    else:
        if st == 1:
            text = (f"O spart gegenüber Z {pct(f['o_pct'])} ({hours(f['o_h'])}), aber {f['o_empty']} von {C.T} Stunden bleiben leer; "
                    f"{pct(f['o_calls_below'])} der Anrufe fallen in Stunden unter 50 % Servicegrad.")
            level = "warning"
        elif st == 2:
            text = (f"O spart {pct(f['o_pct'])} ({hours(f['o_h'])}) ohne leere Stunde, aber {f['o_below']} Stunden liegen unter 50 % Servicegrad "
                    f"({pct(f['o_calls_below'])} der Anrufe): Die Ersparnis kommt aus schlecht bedienten Stunden.")
            level = "warning"
        else:
            text = (f"Hier gibt es nichts aufzugeben: Keine Stunde liegt unter 50 % Servicegrad, O gibt keine Stunde auf. O spart {pct(f['o_pct'])} "
                    f"({hours(f['o_h'])}) gegenüber Z, davon holt schon K {pct(f['k_pct'])} zurück.")
            level = "success"
        out.append({"key": "empty", "title": "② Leere Stunden: die scheinbare Ersparnis", "state": st, "level": level, "text": text})
    # ③ Rückstau
    st = state_drop(f)
    if st is None:
        out.append({"key": "drop", "title": "③ Rückstau: was die Simulation daraus macht", "state": None, "level": "info", "text": "Keine Simulation vorhanden."})
    else:
        d, se = f["d_O"], f["se_O"]
        days = live.sims["O"].days
        if st == 1:
            text = (f"Die Simulation ({days} Tage) liegt für O {de(abs(d), 1)} Punkte unter dem Modell ({pct(f['sim_O'])} statt {pct(f['o_sl'])}, ± {de(2 * se, 1)} Punkte): "
                    f"O verfehlt das Ziel von {s.goal} % in der Simulation. Das Modell zählt die Anrufe leerer Stunden als verloren, nicht aber, dass sie als Rückstau "
                    f"in die nächsten Stunden laufen.")
            level = "warning"
        elif st == 3:
            text = (f"Die Simulation ({days} Tage) liegt für O {de(d, 1)} Punkte über dem Modell ({pct(f['sim_O'])} statt {pct(f['o_sl'])}, ± {de(2 * se, 1)} Punkte): "
                    f"Die stationäre Näherung ist hier pessimistisch.")
            level = "info"
        else:
            if d < -max(C.DROP_SE * se, C.NOISE_POINTS):
                text = (f"Die Simulation ({days} Tage) liegt für O {de(abs(d), 1)} Punkte unter dem Modell ({pct(f['sim_O'])} statt {pct(f['o_sl'])}, ± {de(2 * se, 1)} Punkte), "
                        f"weniger als {de(C.DROP_POINTS, 0)} Punkte: ein mäßiger Rückstau.")
                level = "info"
            else:
                held = "hält das Ziel" if f["hold_O"] else "bleibt knapp unter dem Ziel"
                text = (f"Der Unterschied zwischen Simulation und Modell ({de(d, 1, True)} Punkte, ± {de(2 * se, 1)}) liegt im Rauschen: O {held} auch simuliert "
                        f"({pct(f['sim_O'])}, {days} Tage).")
                level = "success" if f["hold_O"] else "info"
        out.append({"key": "drop", "title": "③ Rückstau: was die Simulation daraus macht", "state": st, "level": level, "text": text})
    # ④ Kopplung
    st = state_couple(f)
    if st is None:
        out.append({"key": "couple", "title": "④ Was an echter Kopplung bleibt", "state": None, "level": "info", "text": "G wurde nicht berechnet."})
    else:
        if st == 1:
            text = (f"G spart gegenüber K {hours(f['g_h'])} ({pct(f['g_pct'])}) bei mindestens derselben gelieferten Qualität und mit Mindestwert "
                    f"{de(100 * C.FLOOR, 0)} % je Stunde: Das ist die echte Kopplungsersparnis dieser Instanz.")
            level = "success"
        elif st == 2:
            text = f"G und K kosten dasselbe ({thou(f['k'].cost)} Personenstunden): Bei gleicher Qualität und mit Mindestwert bleibt von der Kopplung nichts."
            level = "info"
        else:
            text = (f"G ist {hours(-f['g_h'])} teurer als K: K unterschreitet in einzelnen Stunden den Mindestwert von {de(100 * C.FLOOR, 0)} % "
                    f"(einheitliches Stundenziel {de(f['k_z'], 2)} ist unter dem Mindestwert), G hält ihn.")
            level = "info"
        out.append({"key": "couple", "title": "④ Was an echter Kopplung bleibt", "state": st, "level": level, "text": text})
    return out


# --- Einordnung gegen die Messreihe -------------------------------------------------------------------------------------------------------

AMPEL = {"gilt": "gilt", "gilt nicht": "gilt nicht", "unklar": "unklar"}
AMPEL_TITLES = {"over": "Übererfüllung", "empty": "Leere Stunden", "drop": "Einbruch in der Simulation", "couple": "Echte Kopplung"}


def coverage_context(settings):
    """Einordnung der Einstellung: Messpunkt der Messreihe (13 Zellen), Zeile der Abdeckung (20 Instanzen je Profil) und Ampel je Aussage."""
    cell = R.cell_for(settings.size, settings.goal, settings.aht, settings.catalog)
    cov = R.coverage_for(settings.size, settings.goal, settings.aht, settings.catalog, settings.profile)
    return {"cell": cell, "cell_label": R.cell(cell)["label"] if cell else None, "coverage": cov,
            "ampel": cov["verdict"] if cov else None}


def measured_profile_note(settings):
    """Zeile zur Profilzelle der Messreihe: Mittel über die 100 Instanzen des Profils (nur in einem Messpunkt, sonst None)."""
    cell = R.cell_for(settings.size, settings.goal, settings.aht, settings.catalog)
    if cell is None or settings.profile not in R.cell(cell)["profiles"]:
        return None
    rows = R.rows(cell, settings.profile)
    out = {"cell": cell, "n": len(rows), "az": R.saving(rows, "Az")[:2], "b": R.saving(rows, "B")[:2],
           "a_sl": R.field_mean(rows, "A", "sl", 100), "b_empty": R.field_mean(rows, "B", "empty")}
    sim = R.sim_rows(rows)
    if sim:
        out["n_sim"] = len(sim)
        out["d_b"] = R.sim_delta(sim, "B")[:2]
        out["hold_b"] = R.hold_share(sim, "B", settings.goal)
    return out
