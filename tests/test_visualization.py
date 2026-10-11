"""Plotly-Figuren: alle Achsen fest (fixedrange), feste Bereiche, Treppen mit hv, richtige Zahlen in den Spuren."""

import pytest

import sgt_constants as C
import sgt_pipeline as PL
import sgt_results as R
import sgt_visualization as V


@pytest.fixture(scope="module")
def live():
    return PL.run_live(PL.Settings(profile="zwei_spitzen", size="klein", seed=1), with_sim=True)


def axes_locked(fig):
    layout = fig.layout
    axes = [getattr(layout, k) for k in layout if k.startswith(("xaxis", "yaxis"))]
    return axes and all(a.fixedrange is True for a in axes)


def test_staffing_figure_has_one_step_trace_per_plan_plus_the_load(live):
    fig = V.build_staffing(live, ("Z", "K", "G", "O"), with_dp=True)
    names = [t.name for t in fig.data]
    assert names == ["Last (Erlang)", "Z", "K", "G", "O", "O ohne Schichten"]
    assert axes_locked(fig)
    z = next(t for t in fig.data if t.name == "Z")
    assert list(z.y)[:24] == live.plans["Z"].n and len(z.x) == 25 and z.line.shape == "hv"
    assert fig.layout.xaxis.range == (0, 24)
    assert fig.layout.yaxis.range[0] == 0 and fig.layout.yaxis.range[1] > max(live.plans["Z"].n)


def test_staffing_figure_respects_the_plan_selection(live):
    fig = V.build_staffing(live, ("Z", "O"))
    assert [t.name for t in fig.data] == ["Last (Erlang)", "Z", "O"]


def test_hourly_service_has_goal_and_floor_lines_and_empty_hours_shaded(live):
    fig = V.build_hourly_service(live, ("Z", "K", "G", "O"), with_sim=True)
    assert axes_locked(fig) and fig.layout.yaxis.range == (0, 102)
    ys = [s.y0 for s in fig.layout.shapes if s.type == "line"]
    assert live.settings.goal in ys and 100 * C.FLOOR in ys
    n_empty = sum(1 for x in live.plans["O"].n if x == 0)
    rects = [s for s in fig.layout.shapes if s.type == "rect"]
    assert len(rects) == n_empty
    modelled = next(t for t in fig.data if t.name == "Z (Modell)")
    assert max(modelled.y) <= 100 and min(modelled.y) >= 0
    assert any(t.name.endswith("(Simulation)") for t in fig.data)


def test_model_vs_sim_bars_have_error_bars_of_two_standard_errors(live):
    fig = V.build_model_vs_sim(live)
    sim_bar = next(t for t in fig.data if t.name == "Simulation")
    assert axes_locked(fig)
    assert list(sim_bar.error_y.array) == pytest.approx([200 * live.sims[k].se for k in C.PLAN_KEYS])
    assert list(sim_bar.y) == pytest.approx([100 * live.sims[k].sl for k in C.PLAN_KEYS])


def test_cost_bars_mark_the_lower_bound_without_shift_structure(live):
    fig = V.build_costs(live)
    assert axes_locked(fig)
    assert list(fig.data[0].x) == [live.plans[k].cost for k in ("Z", "K", "G", "O")]
    assert any(abs(s.x0 - live.plans["ODP"].cost) < 1e-9 for s in fig.layout.shapes)


def test_messreihe_figures_use_the_stored_numbers():
    base = R.rows("base")
    fig = V.build_mess_savings(base)
    assert axes_locked(fig)
    assert list(fig.data[0].y) == pytest.approx([R.saving(base, v)[0] for v in ("Az", "Beq", "BF", "B1", "B")])
    fig = V.build_mess_sim(R.sim_rows(base), 80)
    assert axes_locked(fig) and len(fig.data) == 2
    cells = V.build_mess_cells()
    assert axes_locked(cells) and len(cells.data[0].x) == 13


def test_coverage_figure_exists_only_with_coverage_data():
    fig = V.build_coverage_drop(size="mittel")
    if R.load_coverage() is None:
        assert fig is None
    else:
        assert axes_locked(fig) and len(fig.data[0].x) == 4 * 3 * 6 * 5
