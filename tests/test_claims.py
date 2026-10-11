"""Claims-Tests: jede Zahl des READMEs wird aus data/sgt_results.json (Messreihe) bzw. data/sgt_coverage.json (Abdeckung) nachgerechnet und muss in
der Zeile des READMEs stehen, die die Aussage trägt. Keine Zahl ohne Voraussetzung (Zelle, Instanzzahl): sie steht in derselben Zeile oder davor."""

import pathlib
import re

import pytest

import sgt_constants as C
import sgt_results as R

README = (pathlib.Path(__file__).resolve().parent.parent / "README.md").read_text(encoding="utf-8")
F = R.FIELD


def de(x, d=1):
    return f"{x:.{d}f}".replace(".", ",")


def thou(n):
    return f"{int(n):,}".replace(",", ".")


def row(prefix):
    """Die Zeile der Befunde-Tabelle, die mit `| prefix` beginnt."""
    lines = [ln for ln in README.splitlines() if ln.startswith("| " + prefix)]
    assert len(lines) == 1, (prefix, len(lines))
    return lines[0]


def has_all(line, *numbers):
    missing = [n for n in numbers if n not in line]
    assert not missing, (missing, line)


@pytest.fixture(scope="module")
def base():
    return R.rows("base")


def test_readme_has_no_placeholders_left():
    assert "@@" not in README and "TODO" not in README


def test_overfulfilment_row(base):
    sl = [100 * R.get(r, "A", "sl") for r in base]
    m, s, _ = R.saving(base, "Az")
    h, _ = R.hours_saved(base, "Az")
    hb, _ = R.hours_saved(base, "B")
    beq, _, _ = R.saving(base, "Beq")
    beq_h, _ = R.hours_saved(base, "Beq")
    a_h = R.mean(R.get(r, "A", "cost") for r in base)
    z = [R.get(r, "Az", "z") for r in base]
    line1 = row("Fallstrick 1")
    has_all(line1, de(R.mean(sl)), de(min(sl)), de(max(sl)))
    line2 = row("Was holt K zurück?")
    has_all(line2, de(m), de(s), de(h), de(a_h), de(R.field_mean(base, "Az", "sl", 100)), de(R.mean(z), 2), de(min(z), 2), de(max(z), 2),
            de(100 * h / hb), de(beq), de(beq_h), de(100 * beq_h / hb))


def test_empty_hours_row(base):
    m, s, _ = R.saving(base, "B")
    h, _ = R.hours_saved(base, "B")
    a_h = R.mean(R.get(r, "A", "cost") for r in base)
    line = row("Fallstrick 2")
    has_all(line, de(m), de(s), de(h), de(100 * h / a_h), de(R.field_mean(base, "B", "sl", 100)), de(R.field_mean(base, "B", "empty")), de(a_h))
    line = row("Wie viele Instanzen")
    has_all(line, de(R.share(base, "B", lambda v: v[F["int50"]] > 0)), de(R.field_mean(base, "B", "anr50", 100)),
            de(R.share(base, "B1", lambda v: v[F["int50"]] > 0)), de(R.field_mean(base, "B1", "anr50", 100)),
            de(R.field_mean(base, "B1", "slmin"), 2), de(R.field_mean(base, "B", "slmin"), 2))


def test_backlog_rows(base):
    sim = R.sim_rows(base)
    assert len(sim) == 100
    line = row("Fallstrick 3")
    for v in ("A", "Az", "Beq", "BF", "B1", "B"):
        use = [r for r in sim if r["v"].get(v)]
        model = 100 * R.mean(R.get(r, v, "sl") for r in use)
        simv = 100 * R.mean(R.get(r, v, "sim") for r in use)
        has_all(line, f"{de(model)} → {de(simv)}")
    d, _, _ = R.sim_delta(sim, "B")
    has_all(line, de(d))
    per = []
    for art in R.cell("base")["profiles"]:
        per.append(R.sim_delta(R.sim_rows(R.rows("base", art)), "B")[0])
    has_all(line, de(min(per)), de(max(per)))
    line = row("Wie oft hält")
    for v in ("A", "Az", "BF", "Beq", "B1", "B"):
        assert f"{de(R.hold_share(sim, v, 80), 0)} %" in line


def test_coupling_row(base):
    zz = R.has(base, "BFz", "Az")
    m, s, _ = R.saving(zz, "BFz", "Az")
    h, _ = R.hours_saved(zz, "BFz", "Az")
    zero = 100 * sum(1 for r in zz if R.get(r, "BFz", "cost") == R.get(r, "Az", "cost")) / len(zz)
    max_h = max(R.get(r, "Az", "cost") - R.get(r, "BFz", "cost") for r in zz)
    max_p = max(100.0 * (R.get(r, "Az", "cost") - R.get(r, "BFz", "cost")) / R.get(r, "Az", "cost") for r in zz)
    bz, _, _ = R.saving(zz, "Bz", "Az")
    bz_h, _ = R.hours_saved(zz, "Bz", "Az")
    simz = [r for r in zz if all(r["v"][v][F["sim"]] is not None for v in ("Az", "BFz", "Bz"))]
    line = row("Was bleibt an echter Kopplung?")
    has_all(line, de(m), de(h), de(zero), str(max_h), de(max_p), de(bz), de(bz_h),
            de(100 * R.mean(R.get(r, "Bz", "sim") for r in simz)), de(100 * R.mean(R.get(r, "Az", "sim") for r in simz)),
            f"{sum(1 for r in simz if R.get(r, 'Bz', 'sim') >= 0.795)} gegen {sum(1 for r in simz if R.get(r, 'Az', 'sim') >= 0.795)} von 100")
    bf, _, _ = R.saving(R.rows("base"), "BF")
    bf_h, _ = R.hours_saved(R.rows("base"), "BF")
    use = [r for r in R.sim_rows(R.rows("base")) if r["v"].get("BF")]
    line = row("Was spart BF")
    has_all(line, de(bf), de(bf_h), de(100 * R.mean(R.get(r, "BF", "sl") for r in use)), de(100 * R.mean(R.get(r, "BF", "sim") for r in use)))


def test_stress_cell_row():
    hart = R.rows("hart")
    zh = R.has(hart, "BFz", "Az")
    steep = [r for r in zh if r["art"] == "steile_spitze"]
    line = row("Stresszelle (Katalog 3, 4 h")
    has_all(line, de(R.saving(hart, "B")[0]), de(R.saving(hart, "B1")[0]), de(R.saving(hart, "BF")[0]),
            de(R.saving(zh, "BFz", "Az")[0]), de(R.hours_saved(zh, "BFz", "Az")[0]), de(R.saving(steep, "BFz", "Az")[0]), de(R.hours_saved(steep, "BFz", "Az")[0]),
            de(R.saving([r for r in hart if r["art"] == "steile_spitze"], "BF")[0]))
    assert len(hart) == 500


def test_proof_status_and_branch_test_rows(base):
    line = row("Beweisstatus")
    has_all(line, de(R.proven_share(base, "B")), de(R.proven_share(base, "B1")), de(R.proven_share(base, "Beq")),
            de(R.proven_share(R.rows("kat8"), "B")), de(R.proven_share(R.rows("aht480"), "B")), de(R.proven_share(R.rows("gross"), "B")))
    for v in ("A", "Az", "BF"):
        assert all(R.proven_share(R.rows(n), v) == 100.0 for n in R.cell_names() if R.has(R.rows(n), v)), v
    line = row("Zweig-Test")
    for a, b in (("A", "Az"), ("Az", "Beq"), ("Beq", "BF"), ("BF", "B1"), ("B1", "B"), ("A", "B")):
        n = sum(1 for r in base if R.get(r, a, "cost") != R.get(r, b, "cost"))
        assert f"{n}" in line and n > 0


def test_cell_table_in_readme_matches_the_data():
    for name in R.cell_names():
        c = R.cell(name)
        rows = R.rows(name)
        star = "*" if c["az_step"] == 0.05 else ""
        line = next((ln for ln in README.splitlines() if ln.startswith("| " + c["label"] + star + " |")), None)
        assert line is not None, name
        has_all(line, de(R.field_mean(rows, "A", "sl", 100)), de(R.saving(rows, "B")[0]), de(R.saving(rows, "BF")[0]),
                de(R.saving_k(rows)[0]), de(R.saving(rows, "Beq")[0]), de(R.proven_share(rows, "B")))
        if star:
            assert line.rstrip().endswith(f"| {de(R.saving(rows, 'Az')[0])} |"), name          # Wert der Messreihe im groben Raster
            assert R.saving_k(rows)[0] >= R.saving(rows, "Az")[0] - 1e-9                       # feiner nie schlechter im Mittel


def test_numbers_of_the_plan_are_not_silently_changed():
    """Die Aussagen des Plans (Basiszelle) stehen hier als feste Erwartung: eine Änderung der Daten fällt sofort auf."""
    base = R.rows("base")
    assert round(R.mean(100 * R.get(r, "A", "sl") for r in base), 1) == 88.6
    assert round(R.saving(base, "Az")[0], 1) == 7.8 and round(R.saving(base, "B")[0], 1) == 13.0
    assert round(R.field_mean(base, "B", "empty"), 1) == 5.8
    assert round(R.sim_delta(R.sim_rows(base), "B")[0], 1) == -10.6
    assert round(R.hold_share(R.sim_rows(base), "B", 80)) == 10
    zz = R.has(base, "BFz", "Az")
    assert round(R.saving(zz, "BFz", "Az")[0], 1) == 0.5 and round(R.hours_saved(zz, "BFz", "Az")[0], 1) == 0.8


def test_coverage_row_matches_the_coverage_file():
    cov = R.load_coverage()
    assert cov is not None
    counts = R.coverage_counts()
    assert counts["rows"] == 216 * 5 and counts["runs"] == 216 * 5 * 20
    assert cov["meta"]["instances_per_profile"] == 20 and cov["meta"]["seeds"] == [0, 19]
    line = row("Abdeckung aller 216 Kombinationen")
    for stm, label in (("over", "Übererfüllung"), ("empty", "leere Stunden von O"), ("drop", "Einbruch in der Simulation"), ("couple", "echte Kopplung")):
        t = counts["total"][stm]
        assert sum(t.values()) == 1080
        trio = f"{label} gilt {thou(t['gilt'])}, unklar {thou(t['unklar'])}, gilt nicht {thou(t['gilt nicht'])}"
        assert trio in line, (trio, line)
    has_all(line, thou(counts["rows"]), thou(counts["runs"]))
    for goal, word in ((70, "bei 70 %"), (80, "bei 80 %"), (90, "bei 90 %"), (95, "bei 95 %")):
        assert f"{counts['by_goal'][goal]['empty']['gilt']} {word}" in line or f"{counts['by_goal'][goal]['empty']['gilt']} von 270 Zeilen {word}" in line
    th = cov["meta"]["thresholds"]
    assert th["over_yes"] == 1.0 and th["empty_yes"] == 1.0 and th["drop_yes_points"] == -3.0 and th["drop_se_factor"] == 2.0 and th["couple_yes_h"] == 1.0


def test_coverage_agrees_with_the_messreihe_on_the_simulated_base_sample():
    """Zufalls-Seeds 0 bis 19 der Basiszelle sind die simulierte Stichprobe der Messreihe: gleiche Instanzen, gleiche Mittel (Z und K exakt)."""
    cov = R.load_coverage()
    for art in R.cell("base")["profiles"]:
        s = cov["cells"][R.combo_key("mittel", 80, 240, "6/8/10")][art]
        rows = [r for r in R.rows("base", art) if r["i"] < 20]
        assert s["over"][0] == pytest.approx(R.mean(100 * R.get(r, "A", "sl") - 80 for r in rows), abs=2e-3)
        assert s["k_save_pct"][0] == pytest.approx(R.saving(rows, "Az")[0], abs=1e-6)
        assert s["k_save_h"][0] == pytest.approx(R.hours_saved(rows, "Az")[0], abs=1e-6)
        assert abs(s["o_save_pct"][0] - R.saving(rows, "B")[0]) < 1.0           # O mit Zeitlimit, Messreihe teils nur bester Fund
