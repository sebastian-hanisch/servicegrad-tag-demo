"""Servicegrad über den Tag - interaktive Fall-Demo
Sebastian Hanisch - Operations Research und Machine Learning

Ein Kontaktcenter will an jedem Tag 80 % der Anrufe innerhalb von 20 Sekunden annehmen. Es rechnet erst den Bedarf je Stunde (Erlang C) und legt dann
Schichten darüber. Die Demo zeigt in der Reihenfolge der Fallstricke: das Tagesziel als Stundenziel gerechnet (Übererfüllung), die scheinbar billigere
gemeinsame Planung (leere Stunden), den Rückstau, den die Stundenrechnung nicht sieht, und was von der Kopplung am Ende bleibt.

Lauffähig mit: streamlit run app.py
"""

import dataclasses

import pandas as pd
import streamlit as st

import sgt_constants as C
import sgt_evaluation as E
import sgt_pipeline as PL
import sgt_plans as P
import sgt_results as R
import sgt_stories as S
import sgt_visualization as V
from sgt_pdf_export import generate_pdf
from sgt_presets import (SETTING_SPECS, apply_preset, init_session_state_defaults, load_permalink_settings, randomize_seed, settings_from_state,
                         sync_query_params)

st.set_page_config(page_title="Servicegrad über den Tag – Sebastian Hanisch", layout="wide")


def _key(settings):
    return tuple(sorted(dataclasses.asdict(settings).items()))


@st.cache_data(show_spinner=False)
def _stage1(key):
    s = PL.Settings(**dict(key))
    prob, plans, sec = PL.stage1(s)
    return prob, plans, sec


@st.cache_data(show_spinner=False)
def _stage2(key, limit):
    s = PL.Settings(**dict(key))
    prob, plans, _ = _stage1(key)
    return PL.stage2(s, prob, plans, time_limit=limit)


@st.cache_data(show_spinner=False)
def _stage3(key):
    s = PL.Settings(**dict(key))
    prob, plans, _ = _stage1(key)
    o, _ = _stage2(key, None)
    plans = dict(plans)
    if o is not None:
        plans["O"] = o
    return PL.stage3(s, prob, plans)


@st.cache_data(show_spinner=False)
def _mess_tables():
    return R.cells_table(), R.profile_table("base"), R.decomposition("base"), R.proof_table()


st.title("📞 Servicegrad über den Tag")
st.markdown(
    """
Ein Kontaktcenter will an jedem Tag **80 % der Anrufe innerhalb von 20 Sekunden** annehmen. Wie viele Leute braucht es in jeder Stunde, und was passiert, wenn man das Ziel
nur über den Tag verlangt? Die Demo zeigt die **drei Fallstricke in der Reihenfolge, in der sie auftreten**: das Tagesziel als Stundenziel gerechnet (**Übererfüllung**), die
scheinbar billigere gemeinsame Planung (**leere Stunden**), den **Rückstau**, den die Stundenrechnung nicht sieht, und was von der Kopplung am Ende **wirklich bleibt**.
Live auf einer Instanz, vorgerechnet über 5.400 (Abschnitt **📐 Was die Messreihe zeigt**; Methode und Formeln in den Expandern **🔧 Wie wir das erreichen**,
**Wie funktioniert diese Demo?** und **📐 Mathematische Formulierung**).

Die erste Demo des Portfolios, die die Warteschlangenrechnung (Erlang C) und die Schichtüberdeckung in einer Rechnung verbindet; Optimierung plus Simulation, kein
Machine Learning. Alle Instanzen sind erfunden: Beispielwerte, keine Prognose für Ihren Betrieb.
"""
)
st.caption(
    "Den Stundenbedarf nimmt die [Schichtplanung](https://sebastianhanisch-shift-demo.streamlit.app/) als gegeben; wie er aus einem Servicegrad-Ziel entsteht, und was die "
    "Trennung kostet, zeigt diese Demo. Die [Wurzelregel](https://sebastianhanisch-square-root-staffing-demo.streamlit.app/) gilt je Stunde; dort rundet ein "
    "[Planungsraster](https://sebastianhanisch-time-varying-arrivals-demo.streamlit.app/) auf, hier tun es die Schichtlängen. Erlang C stammt aus der "
    "[M/M/c-Warteschlange](https://sebastianhanisch-mmc-queue-demo.streamlit.app/); dasselbe Modell trägt auch das Terminal-Gate der "
    "[Warteschlangentheorie-Linie](https://sebastianhanisch.net/konzepte-warteschlangentheorie.html) (Lkw statt Anrufe)."
)

st.caption("🎯 Schnellstart – ein Beispielszenario laden:")
row1 = st.columns(3)
row2 = st.columns(3)
for i, name in enumerate(S.PRESET_ORDER):
    with (row1 if i < 3 else row2)[i % 3]:
        st.button(name, key=f"preset_{name}", width="stretch", on_click=apply_preset, args=(name,), help=S.PRESET_HELP[name])

st.caption("🔗 Die Adresszeile oben spiegelt Ihre aktuelle Konfiguration wider – einfach kopieren, um ein Szenario zu teilen.")

load_permalink_settings()
init_session_state_defaults()

with st.sidebar:
    st.header("⚙️ Einstellungen")
    st.markdown("**Betrieb**")
    st.select_slider("Lastprofil", options=C.PROFILE_ORDER, key="profile_select", format_func=lambda p: C.PROFILE_LABELS[p],
                     help="Last je Stunde über den Tag. „Schmaler Gipfel“ ist der Stresstest der Messreihe; das Profil wirkt auf jede Kennzahl.")
    st.caption(C.PROFILE_HELP[st.session_state["profile_select"]])
    st.select_slider("Größe des Betriebs (Spitzenlast)", options=C.SIZE_ORDER, key="size_select", format_func=lambda x: C.SIZE_LABELS[x],
                     help="Gemessene Stufen. Je größer der Betrieb, desto kleiner der echte Spielraum der Planung mit Mindestwert, und desto länger die Rechnung.")
    st.select_slider("Mittlere Bediendauer", options=C.AHT_OPTIONS, key="aht_select", format_func=lambda x: f"{x} s",
                     help="Skaliert das Angebot bei gleichen Anrufzahlen; die Servicezeit von 20 Sekunden ist fest.")
    st.markdown("**Ziel und Schichten**")
    st.select_slider("Tagesziel (Anteil in 20 s)", options=C.GOAL_OPTIONS, key="goal_select", format_func=lambda x: f"{x} %",
                     help="Das Ziel aller Varianten, als ankunftsgewichteter Anteil über den Tag.")
    st.select_slider("Schichtlängen", options=C.CATALOG_ORDER, key="catalog_select", format_func=lambda x: C.CATALOG_LABELS[x],
                     help="Zulässige Schichtlängen, Start in jeder Stunde, zyklisch über Mitternacht. Wirkt auf Z, K, G und O mit Schichten; "
                          "die Untergrenze „ohne Schichtstruktur“ ist katalogfrei, das ist ihr Zweck.")
    st.markdown("**Instanz**")
    st.slider("Zufalls-Seed der Instanz", C.SEED_MIN, C.SEED_MAX, key="seed_slider",
              help="Nummer der Instanz des Profils (0 bis 99). Dieselbe Nummer ergibt dieselbe Last wie in der Messreihe.")
    st.button("🎲 Neue Instanz", width="stretch", on_click=randomize_seed)

values = {k: st.session_state[k] for k in SETTING_SPECS}
sync_query_params(values)
settings = settings_from_state(values)
skey = _key(settings)
tag = "_".join(str(v) for _, v in skey)
ctx = E.coverage_context(settings)

st.markdown("---")
st.markdown("## 📞 Was liefert die Planung?")
if ctx["cell"]:
    st.caption(f"Diese Einstellung ist ein Messpunkt der Vorab-Messreihe: Zelle „{ctx['cell_label']}“ (100 Instanzen je Profil, vorgerechnet).")
else:
    st.caption("Diese Einstellung ist kein Messpunkt der Messreihe (13 von 216 Kombinationen); die Aussagen unten gelten dort nicht automatisch, siehe Abdeckung "
               "im Abschnitt „Was die Messreihe zeigt“.")
metrics_box = st.container()

# --- Stufe 1: Z, K, G und die Untergrenze ohne Schichtstruktur (sofort) -----------------------------------------------------------------
with st.spinner("Stufe 1: Z, K, G und die Untergrenze ohne Schichtstruktur (unter einer Sekunde) …"):
    prob, plans, sec1 = _stage1(skey)

z, k, g, odp = plans["Z"], plans["K"], plans.get("G"), plans["ODP"]
live1 = PL.Live(settings=settings, prob=prob, plans=plans)
f1 = E.figures(live1)
SHOW = {"success": st.success, "info": st.info, "warning": st.warning}


AMPEL_TEXT = {"gilt": "gilt hier", "gilt nicht": "gilt hier nicht", "unklar": "ist hier unklar"}


def say(item):
    """Meldung in ihrem Zustand, darunter die Einordnung: gilt die Aussage in dieser Einstellung laut Abdeckung (20 Instanzen je Profil)?"""
    SHOW[item["level"]](f"💡 {item['text']}")
    ampel = ctx["ampel"]
    if ampel and item["key"] in ampel:
        where = "Messpunkt der Messreihe" if ctx["cell"] else "kein Messpunkt, nur die Abdeckung"
        st.caption(f"Abdeckung ({where}; 20 Instanzen je Profil, Zufalls-Seeds 0 bis 19): Diese Aussage {AMPEL_TEXT[ampel[item['key']]]}.")


st.markdown("### ① Das Tagesziel als Stundenziel")
say(E.statements(live1, f1)[0])
st.plotly_chart(V.build_staffing(live1, ("Z", "K")), width="stretch", key=f"over_{tag}")
st.caption(f"Besetzung je Stunde von Z und K; gestrichelt die Last in Erlang. Z: {E.thou(z.cost)} Personenstunden, {E.de(f1['z_sl'])} % Tages-Servicegrad; K: {E.thou(k.cost)} "
           f"Personenstunden, {E.de(f1['k_sl'])} %. Rechenzeit der Stufe 1: {E.de(sec1, 2)} s.")

# --- Stufe 2: O mit Schichten (HiGHS) -------------------------------------------------------------------------------------------------
limit = P.time_limit_for(prob)
with st.spinner(f"Stufe 2: O mit Schichten (HiGHS, höchstens {limit:.0f} Sekunden) …"):
    o_plan, sec2 = _stage2(skey, None)
if o_plan is not None:
    plans = dict(plans)
    plans["O"] = o_plan

# --- Stufe 3: Simulation --------------------------------------------------------------------------------------------------------------
with st.spinner("Stufe 3: Ereignissimulation der vier Pläne (etwa eine Sekunde) …"):
    sims, sec3 = _stage3(skey)

live = PL.Live(settings=settings, prob=prob, plans=plans, sims=sims, seconds={"stage1": sec1, "stage2": sec2, "stage3": sec3})
f = E.figures(live)
stm = {s["key"]: s for s in E.statements(live, f)}


with metrics_box:
    m = st.columns(2)
    m[0].metric("Z liefert (Tages-Servicegrad)", f"{E.de(f['z_sl'])} %", delta=f"{E.de(f['over'], 1, True)} Punkte gegenüber dem Ziel {settings.goal} %", delta_color="off",
                help="Z rechnet das Tagesziel als Stundenziel: jede Stunde einzeln auf das Ziel aufgerundet, danach rundet die Schichtlänge weiter auf. Wer das "
                     "nicht merkt, bezahlt jeden Tag für die Übererfüllung. „Über dem Ziel“ ist hier der Befund, kein Gewinn.")
    m[1].metric("K gegenüber Z (Personenstunden)", f"{E.thou(k.cost)} h",
                delta=f"{k.cost - z.cost:+d} h gegenüber Z ({E.de(-f['k_pct'], 1, True)} %)" if k.cost != z.cost else "kostet dasselbe wie Z",
                delta_color="inverse" if k.cost != z.cost else "off",
                help="K: ein einheitliches Stundenziel z unter dem Tagesziel, so weit abgesenkt, wie der Tages-Servicegrad der Überdeckung noch das Ziel hält. "
                     f"Hier z = {E.de(k.z, 2) if k.z is not None else 'Ziel'}.")
    m2 = st.columns(2)
    if o_plan is not None:
        m2[0].metric("O: leere Stunden", f"{f['o_empty']} von {C.T}", delta=f"{E.de(f['o_calls_below'])} % der Anrufe in Stunden unter 50 %", delta_color="off",
                     help="O verlangt das Ziel nur über den Tag. Die scheinbare Ersparnis entsteht, indem kleine Stunden aufgegeben werden.")
    else:
        m2[0].metric("O: leere Stunden", "nicht berechnet")
    if g is not None:
        m2[1].metric("G gegenüber K (Personenstunden)", f"{E.thou(g.cost)} h",
                     delta=f"{g.cost - k.cost:+d} h gegenüber K" if g.cost != k.cost else "kostet dasselbe wie K",
                     delta_color="inverse" if g.cost != k.cost else "off",
                     help="G: gemeinsam geplant, jede Stunde mindestens 50 %, Tages-Servicegrad mindestens der von K. Das ist die Kopplungsersparnis ohne "
                          "Kalibrierungsgewinn.")
    else:
        m2[1].metric("G gegenüber K", "nicht berechnet")

st.markdown("### ② Die scheinbare Ersparnis: leere Stunden")
if o_plan is not None:
    say(stm["empty"])
    st.plotly_chart(V.build_hourly_service(live, ("Z", "K", "O")), width="stretch", key=f"empty_{tag}")
    status = ("bewiesen optimal" if o_plan.status == "optimal"
              else f"bestes Ergebnis nach {limit:.0f} s, Untergrenze {E.thou(o_plan.bound)} h (Lücke {o_plan.cost - o_plan.bound} h)")
    st.caption(f"Servicegrad je Stunde im Modell; schattiert die leeren Stunden von O. O mit Schichten: {E.thou(o_plan.cost)} Personenstunden, {status}. "
               f"Ohne Schichtstruktur (jedes Muster erlaubt) wären es mindestens {E.thou(odp.cost)} Personenstunden. Rechenzeit der Stufe 2: {E.de(sec2, 1)} s.")
else:
    st.warning("O mit Schichten wurde nicht berechnet (kein zulässiger Fund).")

st.markdown("### ③ Der Rückstau: was die Simulation daraus macht")
if "O" in sims:
    say(stm["drop"])
    st.plotly_chart(V.build_model_vs_sim(live), width="stretch", key=f"drop_{tag}")
    st.caption(f"Tages-Servicegrad im Modell (grau) und in der Ereignissimulation ({sims['O'].days} Tage nach {C.SIM_WARM_DAYS} Tagen Einschwingzeit, "
               f"etwa {E.thou(sims['O'].calls)} Anrufe je Plan, Fehlerbalken ± 2 Standardfehler). Eine Instanz ist ein Zufallsfall von 100: Die vorgerechnete Messreihe "
               f"steht gleichberechtigt daneben. Rechenzeit der Stufe 3: {E.de(sec3, 1)} s.")
    note = E.measured_profile_note(settings)
    if note and "d_b" in note:
        st.caption(f"Messreihe, dieses Profil in der Basiszelle ({note['n_sim']} simulierte Instanzen): O liegt in der Simulation im Mittel {E.de(note['d_b'][0], 1, True)} "
                   f"± {E.de(note['d_b'][1], 1)} Punkte vom Modell entfernt, das Ziel halten {E.de(note['hold_b'], 0)} % der Instanzen.")
else:
    st.warning("Keine Simulation vorhanden.")

st.markdown("### ④ Was an echter Kopplung bleibt")
say(stm["couple"])
st.plotly_chart(V.build_costs(live), width="stretch", key=f"costs_{tag}")
st.caption("Personenstunden je Tag der vier Pläne; die gestrichelte Linie ist die Untergrenze ohne Schichtstruktur. Jede Ersparnis steht auf der Basis ihrer Variante: "
           "Mit Schichten wird nur gegen Pläne mit Schichten gerechnet, die Untergrenze ohne Schichtstruktur ist nur eine Schranke.")

# --- Download -------------------------------------------------------------------------------------------------------------------------
summary = [f"Lastprofil {C.PROFILE_LABELS[settings.profile]}, Größe {C.SIZE_LABELS[settings.size]}, Bediendauer {settings.aht} s, Tagesziel {settings.goal} % in 20 s, "
           f"Schichten {C.CATALOG_LABELS[settings.catalog]}, Zufalls-Seed {settings.seed}.",
           f"Z {E.thou(z.cost)} h ({E.de(f['z_sl'])} %), K {E.thou(k.cost)} h, G {g.cost if g else 'n/a'} h, O {o_plan.cost if o_plan else 'n/a'} h, "
           f"Untergrenze ohne Schichtstruktur {E.thou(odp.cost)} h. Alle Instanzen sind erfunden."]
st.download_button("📄 Auswertung als PDF herunterladen", data=generate_pdf("Servicegrad über den Tag", summary, [stm[x]["text"] for x in ("over", "empty", "drop", "couple")], live),
                   file_name="servicegrad_ueber_den_tag.pdf", mime="application/pdf", key="pdf_download")

# --- Wer macht was ---------------------------------------------------------------------------------------------------------------------
with st.expander("🧭 Die Pläne Z, K, G, O: wer macht was?", expanded=True):
    st.markdown("Die Kürzel dieser Seite und ihre Namen in der Vorab-Messreihe. Die Spalte „in dieser Instanz“ zeigt, was der Plan hier liefert.")
    rows = []
    for short, mess, desc, how in C.VARIANT_TABLE:
        key = {"Z": "Z", "K": "K", "G": "G", "O": "O", "O ohne Schichten": "ODP"}.get(short)
        p = plans.get(key) if key else None
        here = "nur vorgerechnet (Messreihe)" if p is None else f"{p.cost} h, Tages-SL {E.de(100 * p.day_sl)} %, leere Stunden {p.figures['empty']}"
        rows.append({"Plan": short, "Messreihe": mess, "Was er tut": desc, "in dieser Instanz": here})
    st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
    st.markdown("**Beispielspur der ersten sechs Stunden** (Besetzung je Stunde, Last in Erlang):")
    trace = [{"Stunde": t, "Last (Erlang)": round(prob.a[t], 1), **{C.PLAN_SHORT[kk]: plans[kk].n[t] for kk in ("Z", "K", "G", "O", "ODP") if kk in plans}} for t in range(6)]
    st.dataframe(pd.DataFrame(trace), width="stretch", hide_index=True)

# --- Kernabschnitt: Messreihe ---------------------------------------------------------------------------------------------------------
st.markdown("---")
st.subheader("📐 Was die Messreihe zeigt")
cells_tab, prof_tab, decomp, proof_tab = _mess_tables()
meta = R.load()["meta"]
st.caption(f"Vorgerechnet (tools/build_results.py aus der Vorab-Messreihe, {E.thou(sum(len(R.rows(n)) for n in R.cell_names()))} Instanzen in 13 Zellen, "
           f"{meta['per_cell_profile']} Instanzen je Zelle und Profil, CP-SAT, {E.thou(round(meta['duration_s']))} s Rechenzeit); nichts davon wird im Browser gerechnet. "
           "Basis: fünf Profile (flach, zwei Spitzen, steile Morgenspitze, Nachtgrundlast, schmaler Gipfel), 8 bis 15 Erlang, Ziel 80 % in 20 s, "
           "Bediendauer 240 s, Schichten 6, 8, 10 h.")
base_rows = R.rows("base")
sim_rows = R.sim_rows(base_rows)
b1, b2 = st.columns(2)
with b1:
    st.markdown("**Was die Variante spart** (Basiszelle, 500 Instanzen)")
    st.plotly_chart(V.build_mess_savings(base_rows), width="stretch", key="mess_savings")
with b2:
    st.markdown(f"**Was davon die Simulation übrig lässt** ({len(sim_rows)} Instanzen, 40 Tage)")
    st.plotly_chart(V.build_mess_sim(sim_rows, 80), width="stretch", key="mess_sim")
st.caption("Links: Ersparnis gegenüber Z in Prozent der Personenstunden, Mittel ± 2 Standardfehler. Rechts: Tages-Servicegrad im Modell und in der Simulation; die "
           "gestrichelte Linie ist das Ziel. Kürzel: K kalibriertes Stundenziel, Beq gleiche gelieferte Qualität wie Z, BF Mindestwert 50 % je Stunde, B1 mindestens eine Person "
           "je Stunde, O ohne Mindestwert. Die einfache Mittelung (O) fällt weit unter das Ziel, B1 ebenfalls; alle übrigen halten es in mindestens 90 % der Instanzen.")

st.markdown("**Die 13 Zellen** (alle Profile gemittelt; Ersparnis gegenüber Z in Prozent)")
st.plotly_chart(V.build_mess_cells(), width="stretch", key="mess_cells")
highlight = ctx["cell"]
st.dataframe(pd.DataFrame(cells_tab).assign(**{"Ihre Einstellung": [("◀ hier" if r["Zelle"] == (ctx["cell_label"] or "") else "") for r in cells_tab]}),
             width="stretch", hide_index=True)
st.caption("Je höher das Tagesziel, desto weniger kann O an Stunden aufgeben (bei 90 und 95 % fällt O auf BF); je kürzer die Schichten, desto kleiner der Abstand K zu Z. "
           "K ist überall im z-Raster 0,01 gezeigt wie live; in neun Zellen rechnete die Messreihe selbst mit 0,05 (Spalte „K in der Messreihe“, dort eine Untergrenze der Ersparnis), "
           "die Werte im Raster 0,01 sind mit der Live-Rechnung nachgerechnet. "
           "Die Zellen mit Katalog 3/4/5 und 3 bis 12 h sind bis auf 8 von 400 Instanzen kostengleich.")

p1, p2 = st.columns(2)
with p1:
    st.markdown("**Je Profil** (Basiszelle, 100 Instanzen je Profil, davon 20 simuliert)")
    st.dataframe(pd.DataFrame(prof_tab), width="stretch", hide_index=True)
with p2:
    st.markdown("**Zerlegung der Ersparnis von O** (Anteil, den die einfacheren Varianten schon erreichen)")
    st.dataframe(pd.DataFrame(decomp), width="stretch", hide_index=True)

st.markdown("**Beweisstatus je Zelle** (Kosten von O; ersetzte Einträge zählen nicht als bewiesen)")
st.dataframe(pd.DataFrame(proof_tab), width="stretch", hide_index=True)

st.markdown("**Abdeckung: gelten die Aussagen auch außerhalb der 13 Zellen?**")
cov = ctx["coverage"]
if cov is None:
    st.info("Die Abdeckungsrechnung liegt nicht vor.")
else:
    rows = [
        {"Aussage": "Übererfüllung (Z über dem Ziel)", "Diese Instanz": f"{E.de(f['over'], 1, True)} Punkte", "Abdeckung (Mittel ± SE, 20 Instanzen)":
            f"{E.de(cov['over'][0], 1, True)} ± {E.de(cov['over'][1], 1)} Punkte", "Ampel": cov["verdict"]["over"]},
        {"Aussage": "Leere Stunden von O", "Diese Instanz": f"{f.get('o_empty', 0)}", "Abdeckung (Mittel ± SE, 20 Instanzen)":
            f"{E.de(cov['o_empty'][0], 1)} ± {E.de(cov['o_empty'][1], 1)}", "Ampel": cov["verdict"]["empty"]},
        {"Aussage": "Einbruch von O in der Simulation", "Diese Instanz": f"{E.de(f.get('d_O', float('nan')), 1, True)} Punkte", "Abdeckung (Mittel ± SE, 20 Instanzen)":
            f"{E.de(cov['d_O'][0], 1, True)} ± {E.de(cov['d_O'][1], 1)} Punkte", "Ampel": cov["verdict"]["drop"]},
        {"Aussage": "Echte Kopplung (G gegen K)", "Diese Instanz": f"{f['g_h'] if f['g_h'] is not None else 'n/a'} h", "Abdeckung (Mittel ± SE, 20 Instanzen)":
            f"{E.de(cov['g_vs_k_h'][0], 1, True)} ± {E.de(cov['g_vs_k_h'][1], 1)} h", "Ampel": cov["verdict"]["couple"]},
    ]
    st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
    th = R.load_coverage()["meta"]["thresholds"]
    st.caption(f"Profil {C.PROFILE_LABELS[settings.profile]}, Zufalls-Seeds 0 bis 19, mit derselben Live-Rechnung wie oben (216 Kombinationen mal 5 Profile mal 20 Instanzen). "
               f"„gilt“: Übererfüllung über {E.de(th['over_yes'], 1)} Punkte, leere Stunden im Mittel mindestens {E.de(th['empty_yes'], 0)}, Einbruch um mehr als "
               f"{E.de(-th['drop_yes_points'], 0)} Punkte und mehr als {E.de(th['drop_se_factor'], 0)} Standardfehler, Kopplung mindestens {E.de(th['couple_yes_h'], 0)} Personenstunde; "
               f"„gilt nicht“: darunter (Übererfüllung unter {E.de(th['over_no'], 1)}, leere Stunden unter {E.de(th['empty_no'], 1)}, Einbruch um höchstens "
               f"{E.de(-th['drop_no_points'], 0)} Punkt, Kopplung unter {E.de(th['couple_no_h'], 1)} Personenstunden); dazwischen „unklar“.")
    drop_fig = V.build_coverage_drop(size=settings.size)
    if drop_fig is not None:
        st.plotly_chart(drop_fig, width="stretch", key=f"cov_drop_{settings.size}")
        st.caption(f"Einbruch von O (Simulation minus Modell) je Kombination und Profil für die Größe {C.SIZE_LABELS[settings.size]}: orange „gilt“, gelb „unklar“, grün „gilt nicht“. "
                   "Der Einbruch tritt vor allem bei niedrigem Tagesziel auf; bei 90 und 95 % kaum.")
st.caption(f"Rechenzeiten (dieses Gerät, gemessen): Messreihe {E.de(R.mean(r['sec'] for r in base_rows), 1)} s je Instanz der Basiszelle mit CP-SAT; die Live-Rechnung dieser "
           f"Seite braucht für Stufe 1 meist unter einer halben Sekunde. Diese Instanz: Stufe 1 {E.de(sec1, 2)} s, Stufe 2 {E.de(sec2, 1)} s, Stufe 3 {E.de(sec3, 1)} s. Die Messreihe wird nie live gerechnet.")

# --- Methodenvergleich ----------------------------------------------------------------------------------------------------------------
st.markdown("---")
with st.expander("🔧 Wie wir das erreichen – vollständiger Methodenvergleich", expanded=False):
    tabs = st.tabs(["📅 Besetzung", "📈 Servicegrad je Stunde", f"🧮 Exakt (HiGHS, bis {C.EXACT_LIMIT_S:.0f} s)", "📊 Messreihe"])
    with tabs[0]:
        view = st.radio("Besetzung anzeigen für", S.VIEW_OPTIONS, key="view_select", horizontal=True, help=S.VIEW_HELP)
        keys = S.VIEW_KEYS[view]
        st.plotly_chart(V.build_staffing(live, keys, with_dp=True), width="stretch", key=f"tab_staff_{tag}_{view}")
        st.caption("Besetzung je Stunde (Personen) als Treppe, gestrichelt die Last in Erlang, grau gestrichelt die Besetzung ohne Schichtstruktur (jedes Muster erlaubt).")
        cols = st.columns(len([kk for kk in keys if plans.get(kk) is not None]) or 1)
        for col, kk in zip(cols, [kk for kk in keys if plans.get(kk) is not None]):
            with col:
                st.markdown(f"**{C.PLAN_SHORT[kk]}: Schichten**")
                if plans[kk].shifts:
                    st.dataframe(pd.DataFrame([{"Start": f"{s:02d}:00", "Länge (h)": length, "Anzahl": cnt} for s, length, cnt in plans[kk].shifts]),
                                 width="stretch", hide_index=True)
    with tabs[1]:
        st.plotly_chart(V.build_hourly_service(live, ("Z", "K", "G", "O"), with_sim=True), width="stretch", key=f"tab_sl_{tag}")
        st.caption("Servicegrad je Stunde im Modell (Linien) und in der Simulation (offene Kreise, Mittel der Tage je Stunde). Gestrichelt das Tagesziel, gepunktet der "
                   "Mindestwert von G. Stunden ohne Bediener sind schattiert (O).")
    with tabs[2]:
        st.caption(f"Löst O mit Schichten noch einmal mit {C.EXACT_LIMIT_S:.0f} Sekunden Zeitlimit und zeigt Fund, bewiesene Untergrenze und Status neben dem Ergebnis der Stufe 2. "
                   "Der Tab ist selbstständig: eigener Knopf, eigener Spinner, gegen die aktuelle Einstellung geprüft. CP-SAT läuft nicht im Betrieb.")
        if st.button(f"🧮 O mit {C.EXACT_LIMIT_S:.0f} Sekunden Zeitlimit lösen", key="exact_start"):
            st.session_state["exact_key"] = skey
        if st.session_state.get("exact_key") == skey:
            with st.spinner(f"Löse O mit Schichten (HiGHS, bis zu {C.EXACT_LIMIT_S:.0f} Sekunden) …"):
                ex, ex_sec = _stage2(skey, C.EXACT_LIMIT_S)
            if ex is not None:
                ex_status = "bewiesen optimal" if ex.status == "optimal" else f"bestes Ergebnis nach {C.EXACT_LIMIT_S:.0f} s"
                st.dataframe(pd.DataFrame([
                    {"Lauf": f"Stufe 2 ({limit:.0f} s)", "Personenstunden": o_plan.cost if o_plan else None, "Untergrenze": o_plan.bound if o_plan else None,
                     "Status": "bewiesen optimal" if o_plan and o_plan.status == "optimal" else "bestes Ergebnis im Zeitlimit", "Zeit (s)": round(sec2, 1)},
                    {"Lauf": f"Exakt ({C.EXACT_LIMIT_S:.0f} s)", "Personenstunden": ex.cost, "Untergrenze": ex.bound, "Status": ex_status, "Zeit (s)": round(ex_sec, 1)},
                    {"Lauf": "Ohne Schichtstruktur (DP)", "Personenstunden": odp.cost, "Untergrenze": odp.cost, "Status": "exakt (jedes Muster erlaubt)", "Zeit (s)": round(odp.seconds, 3)},
                ]), width="stretch", hide_index=True)
            else:
                st.warning("Kein zulässiger Fund.")
        elif st.session_state.get("exact_key") is not None:
            st.caption("Die Einstellungen haben sich seit dem letzten Lauf geändert, bitte erneut lösen.")
    with tabs[3]:
        st.caption("Ersparnis gegenüber Z je Zelle (Prozent der Personenstunden): Median, 10. und 90. Perzentil über alle Instanzen der Zelle, mit Beweisstatus von O.")
        st.dataframe(pd.DataFrame(R.quantile_table()), width="stretch", hide_index=True)

with st.expander("Wie funktioniert diese Demo?"):
    st.markdown(
        f"""
**Vom Angebot zum Servicegrad.** Je Stunde kommen Anrufe mit einer Rate; mit der Bediendauer ist das Angebot a in Erlang. Mit n Bedienern ist der Servicegrad der Stunde (Anteil
in {C.SERVICE_S} Sekunden angenommen) nach Erlang C bekannt. Aus dem Ziel folgt je Stunde die **kleinste Besetzung** c_t, die es erreicht. Darüber liegen **Schichten**
(zusammenhängend, Länge aus dem Katalog, Start in jeder Stunde, zyklisch über Mitternacht); die Kosten sind die Personenstunden.

**Z, K, G, O.** Z (zweistufig) rechnet das Tagesziel als Stundenziel: jede Stunde einzeln auf das Ziel aufgerundet, danach rundet die Schichtlänge weiter auf, also liefert der Tag
mehr als verlangt. K senkt das Stundenziel auf einen einheitlichen Wert z, so weit der Tag noch das Ziel hält (ein einziger Parameter). G plant gemeinsam: der Tag zählt, aber
jede Stunde braucht mindestens {C.FLOOR * 100:.0f} % Servicegrad, und der Tages-Servicegrad darf nicht unter den von K fallen (gleiche gelieferte Qualität). O plant gemeinsam
und verlangt nur den Tag; das ist die scheinbar billigste Variante.

**Warum O billig aussieht.** Ein kleines Stundenangebot braucht je Anruf mehr Puffer (etwa 1/√a) als ein großes; der Mittelwert über den Tag gibt deshalb die kleinen Stunden auf,
ohne dass der Tagesdurchschnitt es merkt. **Warum der Rückstau das Versprechen bricht:** Die stationäre Rechnung zählt die Anrufe einer leeren Stunde als verloren, aber nicht, dass
sie beim Öffnen als Schlange die ersten Stunden danach zerstören. Die Ereignissimulation zählt jede Ankunft, auch unbediente, und trägt den Rückstau über die Stunden.

**Was live läuft.** Stufe 1 (Z, K, G und die Untergrenze ohne Schichtstruktur) in meist unter einer halben Sekunde, Stufe 2 (O mit Schichten, HiGHS mit Zeitlimit und Status),
Stufe 3 (Simulation, Anrufbudget {E.thou(C.CALL_BUDGET)} je Plan: {C.SIM_DAYS_MIN} bis {C.SIM_DAYS_MAX} Tage, {C.SIM_WARM_DAYS} Tage Einschwingzeit; jede simulierte Zahl trägt ihre Tageszahl und ± 2 Standardfehler).
Vorgerechnet sind die 13 Zellen der Messreihe (5.400 Instanzen) und die Abdeckung aller 216 Kombinationen. **Annahmen und Grenzen.** Stationäre Näherung je Stunde (die Simulation prüft nur die
Folgen und optimiert nicht darauf), unendliche Geduld, exponentielle Bedienzeit, keine Abwanderung, kein Wiederanruf, keine Pausen, kein Wochenmuster, keine Ruhezeiten, keine
Schichtfixkosten, Kosten gleich Länge, ein zyklischer Tag, bekannte Prognose; alle Instanzen sind erfunden. n ≤ a wird mit Servicegrad 0 gerechnet. Der Mindestwert 50 % ist eine
einzige Wahl. Eine simulationsbasierte gemeinsame Planung würde O vermutlich verbessern; sie ist nicht gemessen.
""",
    )

with st.expander("📐 Mathematische Formulierung"):
    st.markdown(
        r"""
**Servicegrad je Stunde** bei n Bedienern und Angebot $a_t$ (Erlang): $SL_t(n) = 1 - C(n, a_t)\, e^{-(n - a_t)\, s/\mathrm{AHT}}$ für $n > a_t$, sonst $0$; mit
$C(n, a) = \dfrac{\frac{a^n}{n!}\frac{n}{n-a}}{\sum_{k<n} \frac{a^k}{k!} + \frac{a^n}{n!}\frac{n}{n-a}}$.

**Schichtüberdeckung.** $\min \sum_j L_j x_j$ unter $n_t = \sum_{j \ni t} x_j \ge lb_t$, $x_j \in \mathbb{N}_0$.
**Z:** $lb_t = c_t(\text{Ziel})$. **K:** $lb_t = c_t(z)$ für das kleinste $z$, bei dem der Tages-Servicegrad der kostenminimalen Überdeckung (bei gleichen Kosten bester Wert) noch
$\ge$ Ziel ist. **G:** $lb_t = c_t(0{,}5)$ und $\sum_t a_t SL_t(n_t) \ge \sum_t a_t SL_t(n_t^{K})$. **O:** $lb_t = 0$ und $\sum_t a_t SL_t(n_t) \ge \text{Ziel}\cdot\sum_t a_t$.

**Konkavität.** Für $n \ge c_t(z)$ mit $z \ge 0{,}5$ sind die Zuwächse $SL_t(n+1) - SL_t(n)$ nichtsteigend (gemessen, kein Beweis). Dann ist
$\sum_t a_t SL_t(n_t) = \text{const} + \sum_t \sum_{k > lb_t} a_t \Delta_{tk}\, l_{tk}$ mit kontinuierlichen $l_{tk} \in [0, 1]$ und $\sum_k l_{tk} \le n_t - lb_t$.
Für O ist die Kurve ab 0 S-förmig: dort braucht das Modell die unäre Binärkette $l_{t,k+1} \le l_{tk}$.

**Rucksack ohne Schichtstruktur.** $\mathrm{best}_t[c] = \max \sum_{u \le t} a_u SL_u(n_u)$ bei $\sum n_u = c$; O ohne Schichtstruktur kostet das kleinste $c$ mit
$\mathrm{best}_{24}[c] \ge \text{Ziel} \cdot \sum a$. Das ist zugleich die untere Schranke der Kosten von O mit Schichten und der Schnitt $\sum L_j x_j \ge c^*$.

**Simulation.** Ankünfte Poisson mit Rate $a_t/\mathrm{AHT}$ je Stunde, Bedienzeit exponentiell, FIFO, $n_t$ zyklisch; Servicegrad = Anteil der Anrufe, die höchstens 20 s
warten, über alle Ankünfte der gezählten Tage; Standardfehler aus den Tagesmitteln.
"""
    )

st.markdown("---")
st.caption(
    "Diese Demo ist Teil des Portfolios von [Sebastian Hanisch](https://sebastianhanisch.net) – "
    "Operations Research und Machine Learning ([Über mich](https://sebastianhanisch.net/ueber-mich.html)). "
    "Mehr zum Thema: [Schichtplanung optimieren](https://sebastianhanisch.net/schichtplanung-optimierung.html)."
)
