"""Zustände und erzeugte Sätze der vier Abschnitte: jede Schwelle kippt einzeln, die Sätze nennen die Live-Zahlen."""

import pytest

import sgt_constants as C
import sgt_evaluation as E
import sgt_pipeline as PL


@pytest.fixture(scope="module")
def live():
    s = PL.Settings(profile="zwei_spitzen", size="klein", seed=0)
    return PL.run_live(s, with_sim=True)


def test_german_number_format_is_applied_to_the_number_only():
    assert E.de(3.14159, 1) == "3,1"
    assert E.de(-2.0, 1, True) == "-2,0"
    assert E.de(2.6, 0) == "3"
    assert E.pct(88.64) == "88,6 %"
    assert E.hours(1) == "1 Personenstunde" and E.hours(14) == "14 Personenstunden"


def test_state_over_flips_at_zero_saving_and_at_the_lower_bound_of_the_search():
    assert E.state_over({"k_z": 0.65, "k_h": 14}) == 1
    assert E.state_over({"k_z": 0.65, "k_h": 0}) == 2
    assert E.state_over({"k_z": C.Z_LOWER, "k_h": 14}) == 3          # Untergrenze erreicht, auch mit Ersparnis
    assert E.state_over({"k_z": C.Z_LOWER + 0.01, "k_h": 14}) == 1
    assert E.state_over({"k_z": None, "k_h": 0}) == 2


def test_state_empty_prefers_empty_hours_then_hours_below_half():
    assert E.state_empty({"o_empty": 1, "o_below": 1}) == 1
    assert E.state_empty({"o_empty": 0, "o_below": 1}) == 2
    assert E.state_empty({"o_empty": 0, "o_below": 0}) == 3


def test_state_drop_thresholds_points_and_standard_errors():
    assert E.state_drop({"d_O": -3.0, "se_O": 0.5}) == 1                  # genau 3 Punkte und mehr als 2 SE
    assert E.state_drop({"d_O": -2.99, "se_O": 0.5}) == 2                 # knapp unter 3 Punkten
    assert E.state_drop({"d_O": -3.5, "se_O": 2.0}) == 2                  # 2 SE = 4 Punkte: nicht gesichert
    assert E.state_drop({"d_O": -3.5, "se_O": 1.7}) == 1                  # 2 SE = 3,4 < 3,5
    assert E.state_drop({"d_O": 1.0, "se_O": 0.4}) == 3                   # über dem Modell, über 1 Punkt und 2 SE
    assert E.state_drop({"d_O": 1.0, "se_O": 0.6}) == 2                   # 2 SE = 1,2: im Rauschen
    assert E.state_drop({"d_O": 0.9, "se_O": 0.1}) == 2                   # unter 1 Punkt
    assert E.state_drop({}) is None


def test_state_couple_signs():
    assert E.state_couple({"g_h": 1}) == 1
    assert E.state_couple({"g_h": 0}) == 2
    assert E.state_couple({"g_h": -2}) == 3
    assert E.state_couple({"g_h": None}) is None


def test_figures_are_consistent_with_the_plans(live):
    f = E.figures(live)
    z, k, o = live.plans["Z"], live.plans["K"], live.plans["O"]
    assert f["z_sl"] == pytest.approx(100 * z.day_sl)
    assert f["over"] == pytest.approx(f["z_sl"] - 80)
    assert f["k_h"] == z.cost - k.cost and f["k_pct"] == pytest.approx(100.0 * (z.cost - k.cost) / z.cost)
    assert f["o_empty"] == sum(1 for x in o.n if x == 0)
    assert f["d_O"] == pytest.approx(100 * (live.sims["O"].sl - o.day_sl))
    assert f["hold_O"] == (live.sims["O"].sl >= 0.795)


def test_statements_name_the_live_numbers_and_follow_the_states(live):
    f = E.figures(live)
    st = {s["key"]: s for s in E.statements(live, f)}
    assert set(st) == {"over", "empty", "drop", "couple"}
    assert st["over"]["state"] == E.state_over(f) and E.de(f["z_sl"]) in st["over"]["text"]
    assert st["empty"]["state"] == E.state_empty(f)
    assert st["drop"]["state"] == E.state_drop(f)
    assert st["couple"]["state"] == E.state_couple(f)
    for s in st.values():
        assert s["level"] in ("success", "info", "warning") and s["text"].strip()
        assert "—" not in s["text"] and "–" not in s["text"]


def test_statements_without_o_and_without_simulation_do_not_crash(live):
    plans = {k: v for k, v in live.plans.items() if k != "O"}
    short = PL.Live(settings=live.settings, prob=live.prob, plans=plans)
    st = {s["key"]: s for s in E.statements(short)}
    assert st["empty"]["state"] is None and st["drop"]["state"] is None
    assert st["over"]["state"] in (1, 2, 3) and st["couple"]["state"] in (1, 2, 3)


def test_measured_profile_note_exists_only_at_measurement_points():
    s = PL.Settings()                                                      # Basiszelle, Zwei Spitzen
    note = E.measured_profile_note(s)
    assert note["cell"] == "base" and note["n"] == 100 and note["n_sim"] == 20
    assert 80 < note["a_sl"] < 95 and note["d_b"][0] < -5
    off = PL.Settings(size="klein", goal=90, aht=120, catalog="3/4")       # keine der 13 Zellen
    assert E.measured_profile_note(off) is None


def test_coverage_context_marks_a_measurement_point():
    ctx = E.coverage_context(PL.Settings())
    assert ctx["cell"] == "base" and ctx["cell_label"].startswith("Basis")
    assert E.coverage_context(PL.Settings(size="klein", goal=90, aht=120, catalog="3/4"))["cell"] is None


def test_coupling_gain_is_k_minus_g_and_positive_when_g_is_cheaper():
    live = PL.run_live(PL.Settings(goal=95), with_sim=False)
    f = E.figures(live)
    assert f["g_h"] == live.plans["K"].cost - live.plans["G"].cost == 2
    assert f["g_pct"] == pytest.approx(100.0 * 2 / live.plans["K"].cost)
    assert E.state_couple(f) == 1


def test_a_simulated_value_just_below_the_goal_still_counts_as_holding_it():
    base = PL.run_live(PL.Settings(profile="zwei_spitzen", size="klein", seed=0), with_sim=True)

    def with_sim_level(level):
        sims = dict(base.sims)
        sims["O"] = PL.Simulated(sl=level, se=0.005, days=10, calls=1000)
        return PL.Live(settings=base.settings, prob=base.prob, plans=base.plans, sims=sims)

    assert E.figures(with_sim_level(0.797))["hold_O"] is True        # 0,3 Punkte unter dem Ziel: innerhalb der Toleranz von 0,5
    assert E.figures(with_sim_level(0.794))["hold_O"] is False
    assert E.figures(with_sim_level(0.80))["hold_O"] is True
