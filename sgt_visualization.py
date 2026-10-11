"""Plotly-Figuren der Demo. Alle Achsen fest (fixedrange), damit Touch-Scrollen auf der Seite nicht am Chart hängen bleibt.
Beschriftungen mit Zahlen stehen als Text, damit Plotly keine lineare Achse für Kategorien anlegt. Treppen mit line_shape="hv"."""

import plotly.graph_objects as go

import sgt_constants as C
import sgt_results as R
from sgt_evaluation import de


def _lock(fig, height=360, **layout):
    layout.setdefault("margin", dict(l=55, r=20, t=40, b=55))
    fig.update_layout(height=height, font=dict(size=12), legend=dict(orientation="h", yanchor="bottom", y=1.0, xanchor="left", x=0), **layout)
    fig.update_xaxes(fixedrange=True)
    fig.update_yaxes(fixedrange=True)
    return fig


def _steps(values):
    """Werte je Stunde als Treppe über 0 bis 24 (x, y)."""
    xs = list(range(len(values))) + [len(values)]
    return xs, list(values) + [values[-1]]


def build_staffing(live, keys=C.PLAN_KEYS, with_dp=False):
    """Besetzung je Stunde der gewählten Pläne als Treppe, die Last (Erlang) gestrichelt."""
    fig = go.Figure()
    top = max(live.prob.a)
    xs, ys = _steps(live.prob.a)
    fig.add_trace(go.Scatter(x=xs, y=ys, mode="lines", name="Last (Erlang)", line=dict(color=C.COLOR_LOAD, width=2, dash="dash", shape="hv"),
                             hovertemplate="Stunde %{x}: %{y:.1f} Erlang<extra>Last</extra>"))
    show = list(keys) + (["ODP"] if with_dp and "ODP" not in keys else [])
    for key in show:
        plan = live.plans.get(key)
        if plan is None:
            continue
        top = max(top, max(plan.n))
        xs, ys = _steps(plan.n)
        fig.add_trace(go.Scatter(x=xs, y=ys, mode="lines", name=C.PLAN_SHORT[key], line=dict(color=C.COLORS[key], width=3 if key in ("Z", "O") else 2, shape="hv"),
                                 hovertemplate="Stunde %{x}: %{y} Personen<extra>" + C.PLAN_SHORT[key] + "</extra>"))
    fig.update_xaxes(title_text="Stunde des Tages", range=[0, 24], dtick=3)
    fig.update_yaxes(title_text="Personen bzw. Erlang", range=[0, top * 1.1 + 1])
    return _lock(fig, 380)


def build_hourly_service(live, keys=C.PLAN_KEYS, with_sim=False):
    """Servicegrad je Stunde im Modell (Treppe), optional die Simulation je Stunde als Punkte; Ziel gestrichelt, 50 % gepunktet."""
    fig = go.Figure()
    goal = live.settings.goal
    for key in keys:
        plan = live.plans.get(key)
        if plan is None:
            continue
        sl = [100 * x for x in live.prob.hourly_sl(plan.n)]
        xs, ys = _steps(sl)
        fig.add_trace(go.Scatter(x=xs, y=ys, mode="lines", name=C.PLAN_SHORT[key] + " (Modell)", line=dict(color=C.COLORS[key], width=3, shape="hv"),
                                 hovertemplate="Stunde %{x}: %{y:.0f} %<extra>" + C.PLAN_SHORT[key] + "</extra>"))
        sim = live.sims.get(key)
        if with_sim and sim is not None:
            pts = [(h + 0.5, 100 * v) for h, v in enumerate(sim.hours_sl) if v is not None]
            fig.add_trace(go.Scatter(x=[p[0] for p in pts], y=[p[1] for p in pts], mode="markers", name=C.PLAN_SHORT[key] + " (Simulation)",
                                     marker=dict(color=C.COLORS[key], size=7, symbol="circle-open", line=dict(width=2)),
                                     hovertemplate="Stunde %{x:.0f}: %{y:.0f} %<extra>" + C.PLAN_SHORT[key] + " simuliert</extra>"))
    fig.add_hline(y=goal, line=dict(color=C.COLOR_GOAL, width=1.5, dash="dash"), annotation_text=f"Ziel {goal} %", annotation_position="top left")
    fig.add_hline(y=100 * C.FLOOR, line=dict(color=C.COLOR_FLOOR, width=1.5, dash="dot"), annotation_text="Mindestwert 50 %", annotation_position="bottom left")
    o = live.plans.get("O")
    if o is not None and "O" in keys:
        for h, n in enumerate(o.n):
            if n == 0:
                fig.add_vrect(x0=h, x1=h + 1, fillcolor=C.COLOR_EMPTY, line_width=0)
    fig.update_xaxes(title_text="Stunde des Tages", range=[0, 24], dtick=3)
    fig.update_yaxes(title_text="Servicegrad der Stunde (%)", range=[0, 102])
    return _lock(fig, 380)


def build_model_vs_sim(live):
    """Tages-Servicegrad je Plan: Modell und Simulation (± 2 Standardfehler), das Ziel gestrichelt."""
    keys = [k for k in C.PLAN_KEYS if k in live.plans and k in live.sims]
    labels = [C.PLAN_SHORT[k] for k in keys]
    fig = go.Figure()
    fig.add_trace(go.Bar(x=labels, y=[100 * live.plans[k].day_sl for k in keys], name="Modell (stationär je Stunde)", marker_color="rgba(120,120,120,0.55)",
                         text=[f"{100 * live.plans[k].day_sl:.1f} %" for k in keys], textposition="outside",
                         hovertemplate="%{x}: %{y:.1f} %<extra>Modell</extra>"))
    fig.add_trace(go.Bar(x=labels, y=[100 * live.sims[k].sl for k in keys], name="Simulation", marker_color=[C.COLORS[k] for k in keys],
                         error_y=dict(type="data", array=[200 * live.sims[k].se for k in keys], visible=True, color="#222"),
                         text=[f"{100 * live.sims[k].sl:.1f} %" for k in keys], textposition="outside",
                         hovertemplate="%{x}: %{y:.1f} %<extra>Simulation</extra>"))
    fig.add_hline(y=live.settings.goal, line=dict(color=C.COLOR_GOAL, width=1.5, dash="dash"), annotation_text=f"Ziel {live.settings.goal} %",
                  annotation_position="top left")
    fig.update_layout(barmode="group")
    fig.update_yaxes(title_text="Tages-Servicegrad (%)", range=[0, 112])
    _all_ticks(fig, labels)
    return _lock(fig, 380)


def build_costs(live):
    """Personenstunden je Variante (Balken), die Untergrenze ohne Schichtstruktur als senkrechte Linie."""
    keys = [k for k in ("Z", "K", "G", "O") if k in live.plans]
    labels = [C.PLAN_LABELS[k] for k in keys]
    fig = go.Figure()
    fig.add_trace(go.Bar(y=labels, x=[live.plans[k].cost for k in keys], orientation="h", marker_color=[C.COLORS[k] for k in keys],
                         text=[f"{live.plans[k].cost} h" for k in keys], textposition="outside", hovertemplate="%{y}: %{x} Personenstunden<extra></extra>"))
    odp = live.plans.get("ODP")
    top = max(live.plans[k].cost for k in keys)
    if odp is not None:
        fig.add_vline(x=odp.cost, line=dict(color=C.COLORS["ODP"], width=2, dash="dash"), annotation_text=f"ohne Schichtstruktur: {odp.cost} h",
                      annotation_position="bottom right")
    fig.update_xaxes(title_text="Personenstunden je Tag", range=[0, top * 1.15 + 5])
    fig.update_yaxes(autorange="reversed")
    return _lock(fig, 300, showlegend=False)


# --- Messreihe -----------------------------------------------------------------------------------------------------------------------------

MESS_VARIANTS = (("Az", "K", C.COLORS["K"]), ("Beq", "Beq", "#56B4E9"), ("BF", "BF", "#CC79A7"), ("B1", "B1", "#F0E442"), ("B", "O", C.COLORS["O"]))


def _all_ticks(fig, labels):
    """Alle Kategorien beschriften (Plotly lässt bei schmaler Breite sonst Beschriftungen aus)."""
    fig.update_xaxes(type="category", tickmode="array", tickvals=list(labels), ticktext=list(labels))


def build_mess_savings(rows):
    """Ersparnis gegenüber Z je Variante in Prozent der Personenstunden (Mittel ± 2 Standardfehler)."""
    labels, vals, errs, cols = [], [], [], []
    for v, label, color in MESS_VARIANTS:
        m, s, n = R.saving(rows, v)
        labels.append(label)
        vals.append(m)
        errs.append(2 * s)
        cols.append(color)
    fig = go.Figure(go.Bar(x=labels, y=vals, marker_color=cols, error_y=dict(type="data", array=errs, visible=True, color="#222"),
                           text=[f"{de(v)} %" for v in vals], textposition="outside", hovertemplate="%{x}: %{y:.1f} %<extra></extra>"))
    fig.update_yaxes(title_text="Ersparnis gegenüber Z (% der Personenstunden)", range=[0, max(vals) * 1.25 + 1])
    _all_ticks(fig, labels)
    return _lock(fig, 360, showlegend=False)


def build_mess_sim(rows, goal):
    """Tages-Servicegrad im Modell und in der Simulation je Variante (Messreihe, Basiszelle, Instanzen mit Simulation)."""
    labels, model, sim = [], [], []
    for v, label in (("A", "Z"), ("Az", "K"), ("Beq", "Beq"), ("BF", "BF"), ("B1", "B1"), ("B", "O")):
        use = [r for r in rows if r["v"].get(v) and r["v"][v][R.FIELD["sim"]] is not None]
        labels.append(label)
        model.append(100 * R.mean(R.get(r, v, "sl") for r in use))
        sim.append(100 * R.mean(R.get(r, v, "sim") for r in use))
    fig = go.Figure()
    fig.add_trace(go.Bar(x=labels, y=model, name="Modell", marker_color="rgba(120,120,120,0.55)", text=[f"{de(v)} %" for v in model], textposition="outside"))
    fig.add_trace(go.Bar(x=labels, y=sim, name="Simulation", marker_color="#0072B2", text=[f"{de(v)} %" for v in sim], textposition="outside"))
    fig.add_hline(y=goal, line=dict(color=C.COLOR_GOAL, width=1.5, dash="dash"), annotation_text=f"Ziel {goal} %", annotation_position="top left")
    fig.update_layout(barmode="group")
    fig.update_yaxes(title_text="Tages-Servicegrad (%)", range=[0, 112])
    _all_ticks(fig, labels)
    return _lock(fig, 360)


def build_mess_cells(names=None):
    """Ersparnis gegenüber Z in den 13 Zellen (alle Profile gemittelt): O, BF, K, Beq."""
    names = names or R.cell_names()
    labels = [R.cell(n)["label"] for n in names]
    fig = go.Figure()
    for v, label, color in (("B", "O", C.COLORS["O"]), ("BF", "BF", "#CC79A7"), ("Az", "K", C.COLORS["K"]), ("Beq", "Beq", "#56B4E9")):
        ys = []
        for n in names:
            rows = R.has(R.rows(n), v)
            ys.append((R.saving_k(rows)[0] if v == "Az" else R.saving(rows, v)[0]) if rows else None)
        fig.add_trace(go.Bar(x=labels, y=ys, name=label, marker_color=color, hovertemplate="%{x}: %{y:.1f} %<extra>" + label + "</extra>"))
    fig.update_layout(barmode="group")
    fig.update_yaxes(title_text="Ersparnis gegenüber Z (%)", range=[0, 26])
    _all_ticks(fig, labels)
    fig.update_xaxes(tickangle=-35)
    return _lock(fig, 460, margin=dict(l=55, r=20, t=40, b=170))


def build_coverage_drop(size=None, profile=None):
    """Abdeckung: mittlerer Einbruch von O in der Simulation (Punkte) über dem Tagesziel, je Kombination ein Punkt."""
    cov = R.load_coverage()
    if cov is None:
        return None
    xs, ys, texts, colors = [], [], [], []
    for key, profs in cov["cells"].items():
        sz, goal, aht, cat = key.split("|")
        if size and sz != size:
            continue
        for prof, s in profs.items():
            if profile and prof != profile:
                continue
            xs.append(f"{goal} %")
            ys.append(s["d_O"][0])
            texts.append(f"{C.SIZE_LABELS[sz]}, {aht} s, {cat} h, {C.PROFILE_LABELS[prof]}")
            colors.append({"gilt": C.COLORS["O"], "unklar": "#E69F00", "gilt nicht": "#009E73"}[s["verdict"]["drop"]])
    fig = go.Figure(go.Scatter(x=xs, y=ys, mode="markers", marker=dict(color=colors, size=8, opacity=0.7), text=texts,
                               hovertemplate="%{text}<br>Einbruch %{y:.1f} Punkte<extra></extra>"))
    fig.update_xaxes(title_text="Tagesziel", categoryorder="array", categoryarray=[f"{g} %" for g in C.GOAL_OPTIONS])
    fig.update_yaxes(title_text="Simulation minus Modell für O (Punkte)")
    return _lock(fig, 380, showlegend=False)
