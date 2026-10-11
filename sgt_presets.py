"""SETTING_SPECS, Permalink (Begrenzen und Einrasten), Presets und Zufalls-Seed-Button (Standardmuster aus dem Demo-Portfolio).

Alle Regler sind immer sichtbar mit festen Grenzen: kein ausblendbarer Regler, also kein KEPT-Muster nötig.
`view_select` ist reine Anzeigewahl und gehört nicht zur Rechnung (nicht in `PRESET_KEYS`, nicht in `Settings`).
"""

import random
from dataclasses import dataclass

import streamlit as st

import sgt_constants as C
import sgt_stories as S
from sgt_pipeline import Settings


@dataclass(frozen=True)
class SettingSpec:
    url_param: str
    caster: type
    default: object
    options: tuple | None = None
    lo: float | None = None
    hi: float | None = None
    step: float | None = None


SETTING_SPECS = {
    "profile_select": SettingSpec("prof", str, C.DEFAULT_PROFILE, C.PROFILE_ORDER),
    "size_select": SettingSpec("size", str, C.DEFAULT_SIZE, C.SIZE_ORDER),
    "aht_select": SettingSpec("aht", int, C.DEFAULT_AHT, C.AHT_OPTIONS),
    "goal_select": SettingSpec("goal", int, C.DEFAULT_GOAL, C.GOAL_OPTIONS),
    "catalog_select": SettingSpec("cat", str, C.DEFAULT_CATALOG, C.CATALOG_ORDER),
    "seed_slider": SettingSpec("seed", int, C.DEFAULT_SEED, None, C.SEED_MIN, C.SEED_MAX, 1),
    "view_select": SettingSpec("view", str, "alle", S.VIEW_OPTIONS),
}
# Szenario-Schlüssel -> Widget-Schlüssel (view_select ist Anzeigewahl und gehört nicht zum Szenario)
PRESET_KEYS = {"profile": "profile_select", "size": "size_select", "aht": "aht_select", "goal": "goal_select", "catalog": "catalog_select",
               "seed": "seed_slider"}


def init_session_state_defaults():
    for state_key, spec in SETTING_SPECS.items():
        if state_key not in st.session_state:
            st.session_state[state_key] = spec.default


def bounds(state_key):
    spec = SETTING_SPECS[state_key]
    return spec.lo, spec.hi


def _coerce(spec, raw):
    """Wert aus der Adresszeile: auf eine zulässige Option bzw. auf Grenzen und Raster begrenzen; unbekannte Optionen ergeben None."""
    if isinstance(raw, (list, tuple)):    # Streamlit liefert je nach Version str oder list
        raw = raw[0] if raw else ""
    value = spec.caster(raw)
    if spec.options is not None:
        return value if value in spec.options else None
    return int(max(spec.lo, min(spec.hi, value)))


def load_permalink_settings():
    """Einmal je Sitzung: Werte aus der Adresszeile übernehmen, auf zulässige Werte begrenzt (Unbekanntes wird ignoriert)."""
    if "permalink_loaded" in st.session_state:
        return
    qp = st.query_params
    for state_key, spec in SETTING_SPECS.items():
        if spec.url_param in qp:
            try:
                value = _coerce(spec, qp[spec.url_param])
            except (ValueError, TypeError):
                continue
            if value is not None:
                st.session_state[state_key] = value
    st.session_state["permalink_loaded"] = True


def sync_query_params(values):
    """`values`: {Widget-Schlüssel: aktueller Wert}; die Adresszeile spiegelt die Konfiguration."""
    try:
        for state_key, value in values.items():
            st.query_params[SETTING_SPECS[state_key].url_param] = str(value)
    except Exception:
        pass


def apply_preset(name):
    p = S.PRESETS[name]
    for key, state_key in PRESET_KEYS.items():
        st.session_state[state_key] = p[key]


def randomize_seed():
    st.session_state["seed_slider"] = random.randint(C.SEED_MIN, C.SEED_MAX)


def settings_from_state(values):
    """Settings (immer mit Schlüsselwörtern) aus den Widget-Werten."""
    return Settings(profile=str(values["profile_select"]), size=str(values["size_select"]), aht=int(values["aht_select"]),
                    goal=int(values["goal_select"]), catalog=str(values["catalog_select"]), seed=int(values["seed_slider"]))
