"""Fehler-Einbau-Test: baut einzelne Fehler in die Rechenmodule ein und prüft, ob die Tests (ohne AppTests) sie finden.

Aufruf (im Projektordner, mit dem Test-venv): python tools/mutation_check.py [Teilstring des Dateinamens] [--jobs N] [--indices 5,8-12] [--with-app] [--dry-run]
Jeder Mutant ersetzt genau eine Stelle in einer KOPIE des Projektordners (temporärer Ordner je Mutant, das Original bleibt unberührt);
PYTHONDONTWRITEBYTECODE=1, damit veralteter Bytecode keine Überlebenden vortäuscht; Quelltexte als LF. Vor den Mutanten läuft die unveränderte Kopie:
Ist sie nicht grün, bricht das Werkzeug ab. Ein Mutant kann in eine Endlosschleife laufen; nach TIMEOUT Sekunden gilt er als gefunden. Überlebende sind
entweder gleichwertig (kein sichtbarer Unterschied, dann mit Begründung als viertes Element des Eintrags markiert) oder eine Lücke der Tests.
`--with-app` nimmt die AppTests hinzu, `--dry-run` prüft nur, ob jede Zeichenkette genau einmal vorkommt."""
import concurrent.futures
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
PY = sys.executable
WITH_APP = "--with-app" in sys.argv
TIMEOUT = 900
FIRST = ["test_rng.py", "test_erlang.py", "test_dp.py", "test_cover.py", "test_sim.py", "test_instance.py", "test_oracle_servicegrad_tag.py", "test_plans.py"]
SKIP = {"test_app.py", "test_footer.py"}   # AppTests (Streamlit) nur mit --with-app

# (Datei, alter Text, neuer Text[, Begründung, warum der Mutant gleichwertig ist])
MUTANTS = [
    # ---------------------------------------------------------------- sgt_rng.py
    ('sgt_rng.py', '        z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & M64', '        z = ((z ^ (z >> 31)) * 0xBF58476D1CE4E5B9) & M64'),                       # falsche Mischung
    ('sgt_rng.py', '        return lo + self.next() % (hi - lo + 1)', '        return lo + self.next() % (hi - lo)'),                                       # Obergrenze nie erreicht
    # ---------------------------------------------------------------- sgt_instance.py
    ('sgt_instance.py', '            a[t] = peak * level // 100 * (100 + rng.randint(-8, 8)) // 100', '            a[t] = peak * level // 100 * (100 + rng.randint(-9, 9)) // 100'),  # Rauschbreite
    ('sgt_instance.py', '    return [max(10, min(peak, v)) if kind != "nachtgrund" else max(10, v) for v in a]', '    return [max(5, min(peak, v)) if kind != "nachtgrund" else max(5, v) for v in a]'),   # Mindestlast
    ('sgt_instance.py', '    return [max(1, x * aht_s // C.AHT_REF) for x in a_ref_cent]', '    return [max(1, x * aht_s // C.AHT_REF + 1) for x in a_ref_cent]'),                     # Skalierung mit Bediendauer
    # ---------------------------------------------------------------- sgt_erlang.py
    ('sgt_erlang.py', '    if c <= a:\n        return 1.0\n    b = erlang_b(c, a)', '    if c < a:\n        return 1.0\n    b = erlang_b(c, a)'),                                       # n = a ist stabil
    ('sgt_erlang.py', '    return b / (1.0 - (a / c) * (1.0 - b))', '    return b / (1.0 - (a / c) * b)'),                                                                    # Erlang C aus B falsch
    ('sgt_erlang.py', '        b = a * b / (k + a * b)', '        b = a * b / (k + b)'),                                                                            # Rekursion von Erlang B
    ('sgt_erlang.py', '    if n <= a or n <= 0:\n        return 0.0', '    if n < a or n <= 0:\n        return 0.0',
     'Bei n = a liefert erlang_c(n, a) die 1 (Zweig c <= a) und der Servicegrad wird 1 - 1 * exp(0) = 0: dasselbe Ergebnis auf anderem Weg, die Festlegung steht doppelt'),
    ('sgt_erlang.py', 'return 1.0 - erlang_c(n, a) * math.exp(-(n - a) * (1.0 / aht_min) * s_min)', 'return 1.0 - erlang_c(n, a) * math.exp(-(1.0 / aht_min) * s_min)'),   # Überschuss (n - a) fehlt
    ('sgt_erlang.py', 'return 1.0 - erlang_c(n, a) * math.exp(-(n - a) * (1.0 / aht_min) * s_min)', 'return 1.0 - erlang_c(n, a) * math.exp(-(n - a) * aht_min * s_min)'),   # Rate und Dauer vertauscht
    ('sgt_erlang.py', '        if v >= 1.0 - 1e-7 and n > a:', '        if v >= 1.0 - 1e-3 and n > a:'),                                                                  # Tabelle endet zu früh
    ('sgt_erlang.py', 'int(math.floor(self.a_cent[t] * self.tab[t][n] * C.SKALA + 1e-9))', 'int(math.ceil(self.a_cent[t] * self.tab[t][n] * C.SKALA + 1e-9))'),   # Werte aufgerundet statt abgerundet
    ('sgt_erlang.py', '                n += 1\n            out.append(n)', '                n += 2\n            out.append(n)'),                                    # c_t in Zweierschritten
    ('sgt_erlang.py', '        return sum(self.a_cent[t] * self.sl_at(t, n[t]) for t in range(self.tlen)) / self.weight_sum', '        return sum(self.a_cent[t] * self.sl_at(t, n[t]) for t in range(self.tlen)) / self.tlen'),   # Tagesmittel ungewichtet geteilt
    ('sgt_erlang.py', '        return math.ceil(goal * self.weight_sum * C.SKALA - 1e-9)', '        return math.floor(goal * self.weight_sum * C.SKALA - 1e-9)'),   # rechte Seite abgerundet
    ('sgt_erlang.py', '        "empty": sum(1 for x in n if x == 0),', '        "empty": sum(1 for x in n if x <= 1),'),                                                          # leere Stunden falsch gezählt
    # ---------------------------------------------------------------- sgt_dp.py
    ('sgt_dp.py', '        for k in range(lower_bounds[t], prob.cap[t] + 1):', '        for k in range(0, prob.cap[t] + 1):'),                                                    # Untergrenzen ignoriert
    ('sgt_dp.py', '            cand = np.where(src >= 0, src + val, neg)', '            cand = np.where(src >= 0, src, neg)'),                                                 # Wert der Stunde nicht addiert
    ('sgt_dp.py', '        if best[c] >= rhs:', '        if best[c] > rhs:',
     'Gleichheit der Wertesumme mit der rechten Seite tritt bei ganzzahligen Werten nur zufällig auf; das nächste c liefert dann dieselben Kosten plus eins: der Mutant ist nur bei genau gleicher Summe sichtbar'),
    ('sgt_dp.py', '                cur -= k', '                cur -= 1'),                                                                        # Rückverfolgung
    # ---------------------------------------------------------------- sgt_cover.py
    ('sgt_cover.py', '        if length > tlen:\n            continue', '        if length >= tlen:\n            continue'),                                           # Schicht über den ganzen Tag entfällt
    ('sgt_cover.py', 'out.append((s, length, tuple((s + k) % tlen for k in range(length))))', 'out.append((s, length, tuple((s + k) for k in range(length))))'),   # kein Umlauf über Mitternacht
    ('sgt_cover.py', '        d = [prob.v[t][k] - prob.v[t][k - 1] for k in range(lb[t] + 1, prob.cap[t] + 1)]', '        d = [prob.v[t][k] - prob.v[t][k - 1] for k in range(lb[t], prob.cap[t] + 1)]'),   # Sprung an der Untergrenze mitgeprüft
    ('sgt_cover.py', '        ok.append(all(d[i + 1] <= d[i] for i in range(len(d) - 1)))', '        ok.append(all(d[i + 1] >= d[i] for i in range(len(d) - 1)))'),                      # Konkavität umgekehrt
    ('sgt_cover.py', '    conc = concave_hours(prob, lb) if with_value else [True] * tl', '    conc = [True] * tl'),                                                             # nie binär (Relaxierung statt Modell)
    ('sgt_cover.py', '            binary_hour[t] = force_binary or not conc[t]', '            binary_hour[t] = force_binary'),                                              # nichtkonkave Stunden stetig
    ('sgt_cover.py', '        row_lo.append(float(lb[t]))', '        row_lo.append(float(lb[t] + 1))'),                                                  # Untergrenze um eins zu hoch
    ('sgt_cover.py', '                vals.append(-1.0)', '                vals.append(1.0)'),                                                       # Zuwächse addiert statt abgezogen
    ('sgt_cover.py', '                obj[c] = -dv / V_SCALE', '                obj[c] = dv / V_SCALE'),                                               # zweite Stufe minimiert den Wert
    ('sgt_cover.py', '            need = (rhs - base) / V_SCALE', '            need = rhs / V_SCALE'),                                                 # Sockelwert V_t[lb] nicht abgezogen
    ('sgt_cover.py', '            if need > 0:', '            if need > 1e15:'),                                                                  # Wertezeile fehlt
    ('sgt_cover.py', '                    vals.extend([1.0, -1.0])', '                    vals.extend([1.0, 1.0])'),                                         # Kettenzeile falsch
    ('sgt_cover.py', '                    row_hi.append(0.0)', '                    row_hi.append(1.0)'),                                             # Kette locker
    ('sgt_cover.py', '            obj[j] = float(s[1])', '            obj[j] = 1.0'),                                                                 # Kosten zählen Schichten statt Stunden
    ('sgt_cover.py', '        row_hi.append(float(cost_cap) if cost_cap is not None else np.inf)', '        row_hi.append(np.inf)'),                                  # Kostenobergrenze der zweiten Stufe fehlt
    ('sgt_cover.py', '        row_lo.append(float(cost_floor) if cost_floor is not None else -np.inf)', '        row_lo.append(-np.inf)',
     'Die Untergrenze der Kosten ist ein gültiger Schnitt: ohne ihn ändert sich nur die Lösungszeit, nicht das Ergebnis (die Schranke im Ergebnis kommt aus dem Parameter)'),
    ('sgt_cover.py', '                ub[c] = 1.0', '                ub[c] = 2.0'),                                                                  # Zuwachs mehrfach nutzbar
    ('sgt_cover.py', '    out.status = "optimal" if res.status == 0 else "feasible"', '    out.status = "optimal"'),                                       # Zeitlimit als bewiesen gemeldet
    ('sgt_cover.py', '        out.bound = max(out.bound, int(np.ceil(dual - 1e-3)))', '        out.bound = max(out.bound, int(np.ceil(dual - 1e-9)))',
     'Wirkt nur, wenn HiGHS im Zeitlimit eine Dualschranke knapp über einer ganzen Zahl meldet; die Regression ist an zwei Instanzen mit knappem Zeitlimit getestet, deren Verhalten von der Rechengeschwindigkeit abhängt'),
    ('sgt_cover.py', '    if res.status == 2:\n        out.status = "infeasible"', '    if res.status == 3:\n        out.status = "infeasible"'),                          # unzulässig nicht erkannt
    ('sgt_cover.py', '    x = [int(round(float(v))) for v in res.x[:len(shifts)]]', '    x = [int(float(v)) for v in res.x[:len(shifts)]]'),               # abgeschnitten statt gerundet
    ('sgt_cover.py', '    if any(n[t] < lb[t] for t in range(prob.tlen)):\n        return False', '    if any(n[t] < lb[t] for t in range(prob.tlen)):\n        return True'),   # Prüfer gibt Untergrenzenverletzung frei
    ('sgt_cover.py', '    return rhs is None or prob.v_sum(n) >= rhs', '    return rhs is None or prob.v_sum(n) >= 0'),                      # Prüfer ignoriert die Tageszeile
    ('sgt_cover.py', '        if c2 <= current.cost and prob.v_sum(n2) > current.vsum:', '        if c2 <= current.cost and prob.v_sum(n2) < current.vsum:'),   # zweite Stufe nimmt den schlechteren Wert
    # ---------------------------------------------------------------- sgt_plans.py
    ('sgt_plans.py', '    rhs = prob.rhs_goal(goal)\n    cache = {}', '    rhs = 0\n    cache = {}'),                                                          # z-Suche ohne Zielprüfung
    ('sgt_plans.py', '        z = goal - k * z_step\n', '        z = goal - k * z_step / 2\n'),                                                       # feineres Raster
    ('sgt_plans.py', '        if z < z_lower - 1e-9:\n            break', '        if z < z_lower + 0.2:\n            break'),                                       # Untergrenze der Suche zu hoch
    ('sgt_plans.py', '            if fails >= patience:', '            if fails > patience:'),                                                       # eine Geduld zu viel
    ('sgt_plans.py', '        if best is None or res.cost <= best[1].cost:', '        if best is None or res.cost < best[1].cost:'),                                     # Gleichstand: größeres z behalten
    ('sgt_plans.py', '    lb = prob.c_target(floor)\n    rhs = k_plan.vsum if k_plan is not None else prob.rhs_goal(goal)', '    lb = [0] * prob.tlen\n    rhs = k_plan.vsum if k_plan is not None else prob.rhs_goal(goal)'),   # G ohne Mindestwert
    ('sgt_plans.py', '    rhs = k_plan.vsum if k_plan is not None else prob.rhs_goal(goal)', '    rhs = prob.rhs_goal(goal)'),                                                       # G mit dem Tagesziel statt der Qualität von K
    ('sgt_plans.py', '    return C.TIME_LIMIT_BIG_S if max(prob.a) >= C.BIG_LOAD_ERLANG else C.TIME_LIMIT_S', '    return C.TIME_LIMIT_BIG_S if min(prob.a) >= C.BIG_LOAD_ERLANG else C.TIME_LIMIT_S'),   # Last nach dem Minimum
    ('sgt_plans.py', '    if plan.cost <= plan.bound:\n        plan.status = "optimal"', '    if plan.cost < plan.bound:\n        plan.status = "optimal"'),                      # Gleichheit mit der Schranke gilt nicht als bewiesen
    ('sgt_plans.py', '    plan.bound = max(plan.bound, floor)\n    if plan.cost', '    plan.bound = min(plan.bound, floor)\n    if plan.cost'),                                     # Schranke: Minimum statt Maximum
    ('sgt_plans.py', '        if plan is None or cand.cost < plan.cost:', '        if plan is None or cand.cost > plan.cost:'),                                       # Rückfall nimmt den teureren Fund
    ('sgt_plans.py', '    cands = [c for c in candidates if c is not None and c.vsum >= rhs]', '    cands = [c for c in candidates if c is not None]'),                              # unzulässige Kandidaten zugelassen
    # ---------------------------------------------------------------- sgt_pipeline.py
    ('sgt_pipeline.py', '    return Problem(I.a_cent_at(a_ref, settings.aht), settings.aht, C.SERVICE_S)', '    return Problem(I.a_cent_at(a_ref, settings.aht), C.AHT_REF, C.SERVICE_S)'),   # Bediendauer im Problem fest
    ('sgt_pipeline.py', '    g = P.plan_g(prob, settings.shifts, plans["K"], goal)', '    g = P.plan_g(prob, settings.shifts, plans["Z"], goal)'),                           # G gegen die Qualität von Z
    ('sgt_pipeline.py', '    return seed_from("sim", settings.profile, settings.seed, C.MESS_CODE.get(key, key))', '    return seed_from("sim", settings.profile, C.MESS_CODE.get(key, key))'),   # Instanznummer fehlt im Simulationsseed
    ('sgt_pipeline.py', '        res = S.simulate(prob, plan.n, days=days, warm=C.SIM_WARM_DAYS, seed=sim_seed(settings, key))', '        res = S.simulate(prob, plan.n, days=days, warm=0, seed=sim_seed(settings, key))'),   # keine Einschwingzeit
    # ---------------------------------------------------------------- sgt_sim.py
    ('sgt_sim.py', '        counted = warm <= d < warm + days', '        counted = warm < d < warm + days'),                                                   # erster Zähltag fehlt
    ('sgt_sim.py', '        if day >= 0 and t_start - arrival <= s_min + eps:', '        if day >= 0 and t_start - arrival <= s_min * 2:'),                                      # Servicezeit verdoppelt
    ('sgt_sim.py', '            count_d[day] += len(arr)', '            count_d[day] += 1'),                                                          # Tageszähler falsch
    ('sgt_sim.py', '            ok_h[hour] += 1\n            ok_d[day] += 1', '            ok_h[hour] += 1'),                                                           # Tages-Treffer fehlen
    ('sgt_sim.py', '    total_days = warm + days + 1', '    total_days = warm + days',
     'Der Auslauftag liegt hinter dem Zählfenster: die gezählten Ankünfte und Bedienungen ändern sich nicht (Ankünfte hinter dem Fenster zählen nicht)'),
    ('sgt_sim.py', '            t += -log(ra.uniform()) / lam', '            t += -log(ra.uniform()) * lam'),                                               # Ankunftsabstand falsch
    ('sgt_sim.py', 'heappush(deps, t_start + (-log(rs.uniform())) * aht)', 'heappush(deps, t_start + (-log(rs.uniform())) / aht)'),                                              # Bedienzeit falsch
    ('sgt_sim.py', '                if busy > n:\n                    busy -= 1', '                if busy > n:\n                    busy -= 2'),                                       # Abgänge bei sinkender Besetzung
    ('sgt_sim.py', '    var = sum((x - m) ** 2 for x in sl) / (k - 1)', '    var = sum((x - m) ** 2 for x in sl) / k'),                                              # Stichprobenvarianz ohne Bessel
    ('sgt_sim.py', '    return res["sl_day"], math.sqrt(var / k)', '    return res["sl_day"], math.sqrt(var)'),                                                    # Standardfehler = Standardabweichung
    ('sgt_sim.py', '    per_day = sum(prob.a) * 3600.0 / prob.aht_s', '    per_day = sum(prob.a) * 60.0 / prob.aht_s'),                                                # Anrufe je Tag falsch
    # ---------------------------------------------------------------- sgt_evaluation.py
    ('sgt_evaluation.py', '    if f["k_z"] is not None and f["k_z"] <= C.Z_LOWER + 1e-9:', '    if f["k_z"] is not None and f["k_z"] < C.Z_LOWER:'),                                     # Untergrenze nur strikt
    ('sgt_evaluation.py', '    return 1 if f["k_h"] > 0 else 2', '    return 1 if f["k_h"] >= 0 else 2'),                                                        # Null Ersparnis gilt als Ersparnis
    ('sgt_evaluation.py', '    if d <= -C.DROP_POINTS and d < -C.DROP_SE * se:', '    if d <= -C.DROP_POINTS or d < -C.DROP_SE * se:'),                                             # Einbruch: oder statt und
    ('sgt_evaluation.py', '    if d >= C.NOISE_POINTS and d > C.DROP_SE * se:', '    if d >= C.NOISE_POINTS or d > C.DROP_SE * se:'),                                             # über dem Modell: oder statt und
    ('sgt_evaluation.py', '    return 1 if f["g_h"] >= 1 else (2 if f["g_h"] == 0 else 3)', '    return 1 if f["g_h"] > 1 else (2 if f["g_h"] == 0 else 3)'),                                # eine Personenstunde zählt nicht
    ('sgt_evaluation.py', '    f["g_h"] = k.cost - g.cost if g is not None else None', '    f["g_h"] = g.cost - k.cost if g is not None else None'),                                      # Vorzeichen G gegen K
    ('sgt_evaluation.py', '    f["over"] = f["z_sl"] - goal', '    f["over"] = goal - f["z_sl"]'),                                                              # Vorzeichen Übererfüllung
    ('sgt_evaluation.py', '            f[f"d_{key}"] = 100 * (sim.sl - plan.day_sl)', '            f[f"d_{key}"] = 100 * (plan.day_sl - sim.sl)'),                                    # Vorzeichen Simulation minus Modell
    ('sgt_evaluation.py', '            f[f"hold_{key}"] = sim.sl >= goal / 100.0 - C.HOLD_TOLERANCE', '            f[f"hold_{key}"] = sim.sl >= goal / 100.0'),                                  # keine Toleranz beim Halten
    # ---------------------------------------------------------------- sgt_results.py
    ('sgt_results.py', '    q = [100.0 * (get(r, ref, "cost") - get(r, variant, "cost")) / get(r, ref, "cost") for r in use]', '    q = [100.0 * (get(r, variant, "cost") - get(r, ref, "cost")) / get(r, ref, "cost") for r in use]'),   # Vorzeichen der Ersparnis
    ('sgt_results.py', '    d = [100 * (get(r, variant, "sim") - get(r, variant, "sl")) for r in use]', '    d = [100 * (get(r, variant, "sl") - get(r, variant, "sim")) for r in use]'),                  # Vorzeichen Simulation minus Modell
    ('sgt_results.py', '    return share(rows_, variant, lambda v: v[FIELD["opt"]] == 1 and v[FIELD["replaced"]] == 0)', '    return share(rows_, variant, lambda v: v[FIELD["opt"]] == 1)'),                    # ersetzte Einträge als bewiesen
    ('sgt_results.py', '    return math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1) / len(xs))', '    return math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))'),                           # Standardfehler ohne Teilung durch n
]


def check_unique():
    bad = []
    for n, m in enumerate(MUTANTS, 1):
        name, old, new = m[:3]
        p = ROOT / name
        if not p.exists():
            bad.append((n, name, "Datei fehlt", 0))
            continue
        text = p.read_bytes().decode("utf-8").replace("\r\n", "\n")
        if text.count(old) != 1:
            bad.append((n, name, old[:70], text.count(old)))
        if old == new:
            bad.append((n, name, "alt == neu", 0))
    return bad


def test_files(base: pathlib.Path):
    names = sorted(f.name for f in (base / "tests").glob("test_*.py"))
    skip = set() if WITH_APP else SKIP
    ordered = [f for f in FIRST if f in names] + [f for f in names if f not in FIRST]
    return [f"tests/{f}" for f in ordered if f not in skip]


def run_tests(tmp: pathlib.Path):
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    return subprocess.run([PY, "-m", "pytest", "-x", "-q", "-p", "no:cacheprovider", "-k", "not test_readme_has_no_placeholders_left", *test_files(tmp)], cwd=tmp, env=env, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=TIMEOUT)


def run_one(args):
    n, name, old, new, base = args
    tmp = pathlib.Path(tempfile.mkdtemp(prefix=f"sgt_mut{n}_"))
    try:
        shutil.copytree(base, tmp, dirs_exist_ok=True)
        path = tmp / name
        original = path.read_bytes().decode("utf-8")
        path.write_bytes(original.replace(old, new).encode("utf-8"))
        try:
            r = run_tests(tmp)
            return n, name, old, new, r.returncode == 0, False
        except subprocess.TimeoutExpired:
            return n, name, old, new, False, True       # Endlosschleife oder zu langsam: gilt als gefunden
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def make_base() -> pathlib.Path:
    base = pathlib.Path(tempfile.mkdtemp(prefix="sgt_mut_base_"))
    for f in ROOT.glob("*.py"):
        (base / f.name).write_bytes(f.read_bytes().replace(b"\r\n", b"\n"))
    shutil.copytree(ROOT / "tests", base / "tests", ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copytree(ROOT / "tools", base / "tools", ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copytree(ROOT / "data", base / "data")
    for extra in ("README.md", "requirements.txt", "requirements-dev.txt"):
        if (ROOT / extra).exists():
            shutil.copy(ROOT / extra, base / extra)
    if (ROOT / ".streamlit").exists():
        shutil.copytree(ROOT / ".streamlit", base / ".streamlit")
    for f in (base / "tests").glob("*.py"):
        f.write_bytes(f.read_bytes().replace(b"\r\n", b"\n"))
    return base


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")   # Windows-Konsole (cp1252) vertrüge Umlaute sonst nicht
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    only = args[0] if args else ""
    jobs = 4
    if "--jobs" in sys.argv:
        jobs = int(sys.argv[sys.argv.index("--jobs") + 1])
        only = "" if only == str(jobs) else only
    wanted = None
    if "--indices" in sys.argv:
        spec = sys.argv[sys.argv.index("--indices") + 1]
        only = "" if only == spec else only
        wanted = set()
        for part in spec.split(","):
            lo, _, hi = part.partition("-")
            wanted.update(range(int(lo), int(hi or lo) + 1))
    bad = check_unique()
    for b in bad:
        print("FEHLER (Stelle nicht eindeutig gefunden):", b)
    if "--dry-run" in sys.argv:
        print(f"{len(MUTANTS)} Mutanten, {len(bad)} Fehler in der Mutantenliste")
        return
    base = make_base()
    try:
        r = run_tests(base)
        if r.returncode != 0:
            print("Die unveränderte Kopie besteht die Tests nicht; Abbruch.\n" + r.stdout[-3000:])
            sys.exit(2)
        bad_ids = {b[0] for b in bad}
        work = [(n, m[0], m[1], m[2], base) for n, m in enumerate(MUTANTS, 1)
                if n not in bad_ids and (not only or only in m[0]) and (wanted is None or n in wanted)]
        survivors, equivalent, killed = [], [], 0
        with concurrent.futures.ThreadPoolExecutor(max_workers=jobs) as pool:
            for n, name, old, new, survived, timeout in pool.map(run_one, work):
                reason = MUTANTS[n - 1][3] if len(MUTANTS[n - 1]) > 3 else ""
                if timeout:
                    print(f"[{n:3d}] Zeitüberschreitung (als gefunden gezählt)  {name}", flush=True)
                if survived and reason:
                    equivalent.append(n)
                    print(f"[{n:3d}] überlebt, gleichwertig  {name}: {old[:60]!r} -> {new[:60]!r}\n        Begründung: {reason}", flush=True)
                elif survived:
                    survivors.append(n)
                    print(f"[{n:3d}] ÜBERLEBT  {name}: {old[:70]!r} -> {new[:70]!r}", flush=True)
                else:
                    killed += 1
                    print(f"[{n:3d}] gefunden  {name}", flush=True)
        print(f"\n{killed} gefunden, {len(survivors)} überlebt (Lücken), {len(equivalent)} gleichwertig (begründet), {len(bad)} Fehler in der Mutantenliste")
    finally:
        shutil.rmtree(base, ignore_errors=True)


if __name__ == "__main__":
    main()
