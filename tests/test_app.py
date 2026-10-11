"""End-to-end-Tests über Streamlits AppTest: Seite lädt, jedes Preset, jeder Regler an seinen Grenzen, Permalink (auch unbekannte Werte),
angezeigte Zahlen gegen die Rechnung mit denselben Reglerwerten, Exakt-Tab, PDF. Live-Rechnungen vorzugsweise mit der Größe klein."""

import os

import pytest
from streamlit.testing.v1 import AppTest

import sgt_constants as C
import sgt_evaluation as E
import sgt_pipeline as PL
import sgt_stories as S

APP_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app.py")
TIMEOUT = 240


def fresh(query=None):
    at = AppTest.from_file(APP_PATH, default_timeout=TIMEOUT)
    for k, v in (query or {}).items():
        at.query_params[k] = v
    at.run(timeout=TIMEOUT)
    assert not at.exception, [str(e) for e in at.exception]
    return at


def metric_values(at):
    return {m.label: m.value for m in at.metric}


def messages(at):
    return [x.value for x in list(at.success) + list(at.info) + list(at.warning)]


def qp(at, key):
    v = at.query_params[key]
    return v[0] if isinstance(v, list) else v        # ab Streamlit 1.65 str, vorher Liste


def test_app_loads_and_shows_the_four_headline_numbers_and_the_four_statements():
    at = fresh()
    assert at.title[0].value.startswith("📞")
    vals = metric_values(at)
    assert set(vals) >= {"Z liefert (Tages-Servicegrad)", "K gegenüber Z (Personenstunden)", "O: leere Stunden", "G gegenüber K (Personenstunden)"}
    texts = messages(at)
    assert any("Z liefert" in t for t in texts)
    assert any("Simulation" in t for t in texts)
    assert len(at.sidebar.header) == 1                       # genau ein Header in der Seitenleiste


def test_displayed_numbers_come_from_the_sidebar_values_for_the_right_settings():
    """Vertauschte Reglerwerte wären still: die angezeigten Zahlen müssen der Rechnung mit denselben Werten entsprechen (Schlüsselwörter)."""
    q = {"prof": "morgenspitze", "size": "klein", "aht": "120", "goal": "90", "cat": "4/6/8", "seed": "5"}
    at = fresh(q)
    s = PL.Settings(profile="morgenspitze", size="klein", aht=120, goal=90, catalog="4/6/8", seed=5)
    f = E.figures(PL.run_live(s, with_sim=True))
    vals = metric_values(at)
    assert vals["Z liefert (Tages-Servicegrad)"] == f"{E.de(f['z_sl'])} %"
    assert vals["K gegenüber Z (Personenstunden)"] == f"{E.thou(f['k'].cost)} h"
    assert vals["G gegenüber K (Personenstunden)"] == f"{E.thou(f['g'].cost)} h"


@pytest.mark.parametrize("name", S.PRESET_ORDER)
def test_every_preset_loads_without_exception_and_sets_the_controls(name):
    at = fresh({"size": "klein"})
    btn = next(b for b in at.button if b.key == f"preset_{name}")
    btn.click().run(timeout=TIMEOUT)
    assert not at.exception, [str(e) for e in at.exception]
    p = S.PRESETS[name]
    assert at.session_state["profile_select"] == p["profile"] and at.session_state["goal_select"] == p["goal"]
    assert at.session_state["catalog_select"] == p["catalog"] and at.session_state["seed_slider"] == p["seed"]


def test_every_control_at_its_extremes_does_not_raise():
    controls = {"profile_select": (C.PROFILE_ORDER[0], C.PROFILE_ORDER[-1]), "aht_select": (C.AHT_OPTIONS[0], C.AHT_OPTIONS[-1]),
                "goal_select": (C.GOAL_OPTIONS[0], C.GOAL_OPTIONS[-1]), "catalog_select": (C.CATALOG_ORDER[0], C.CATALOG_ORDER[-1]),
                "seed_slider": (C.SEED_MIN, C.SEED_MAX), "size_select": (C.SIZE_ORDER[0], C.SIZE_ORDER[-1])}
    for key, edges in controls.items():
        for value in edges:
            at = fresh({"size": "klein"})
            widget = next(w for w in list(at.select_slider) + list(at.slider) if w.key == key)
            widget.set_value(value).run(timeout=TIMEOUT)
            assert not at.exception, (key, value, [str(e) for e in at.exception])


def test_permalink_writes_back_and_clamps_and_ignores_unknown_values():
    at = fresh({"prof": "flach", "size": "klein", "goal": "95", "seed": "500", "cat": "unbekannt", "aht": "60"})
    assert at.session_state["profile_select"] == "flach"
    assert at.session_state["goal_select"] == 95
    assert at.session_state["seed_slider"] == C.SEED_MAX              # begrenzt
    assert at.session_state["catalog_select"] == C.DEFAULT_CATALOG    # unbekannt: Vorgabe
    assert at.session_state["aht_select"] == C.DEFAULT_AHT
    assert qp(at, "prof") == "flach" and qp(at, "goal") == "95" and qp(at, "seed") == str(C.SEED_MAX)


def test_permalink_tolerates_a_non_numeric_seed():
    at = fresh({"size": "klein", "seed": "abc"})
    assert at.session_state["seed_slider"] == C.DEFAULT_SEED


def test_view_select_is_display_only_and_not_in_the_computation():
    at = fresh({"size": "klein"})
    before = metric_values(at)
    radio = next(r for r in at.radio if r.key == "view_select")
    radio.set_value("Z und K").run(timeout=TIMEOUT)
    assert not at.exception
    assert metric_values(at) == before


def test_the_variant_table_and_the_download_are_on_the_page():
    at = fresh({"size": "klein"})
    md = " ".join(m.value for m in at.markdown)
    assert "Beispielspur" in md
    frames = [d.value for d in at.dataframe]
    assert any("Messreihe" in df.columns and "Was er tut" in df.columns for df in frames)
    assert len(at.get("download_button")) == 1


def test_exact_tab_runs_o_with_the_longer_limit_and_shows_both_results():
    at = fresh({"size": "klein", "goal": "95", "cat": "8"})
    next(b for b in at.button if b.key == "exact_start").click().run(timeout=TIMEOUT)
    assert not at.exception, [str(e) for e in at.exception]
    frames = [d.value for d in at.dataframe]
    exact = [df for df in frames if "Lauf" in df.columns]
    assert exact and len(exact[0]) == 3
    assert list(exact[0]["Lauf"])[2].startswith("Ohne Schichtstruktur")
