"""Permalink, Presets und Einstellungen: Begrenzen, unbekannte Werte, Schlüsselwörter, Wirkung jedes Presets."""

import pytest
import streamlit as st

import sgt_constants as C
import sgt_presets as SP
import sgt_stories as S
from sgt_pipeline import Settings


def spec(key):
    return SP.SETTING_SPECS[key]


def test_every_widget_key_has_a_unique_url_parameter():
    params = [s.url_param for s in SP.SETTING_SPECS.values()]
    assert len(params) == len(set(params))


def test_coerce_accepts_known_options_and_rejects_unknown_ones():
    assert SP._coerce(spec("profile_select"), "flach") == "flach"
    assert SP._coerce(spec("profile_select"), "unbekannt") is None
    assert SP._coerce(spec("goal_select"), "95") == 95
    assert SP._coerce(spec("goal_select"), "85") is None
    assert SP._coerce(spec("aht_select"), "480") == 480
    assert SP._coerce(spec("aht_select"), "60") is None
    assert SP._coerce(spec("catalog_select"), "3 bis 12") == "3 bis 12"
    assert SP._coerce(spec("size_select"), "riesig") is None


def test_coerce_clamps_the_seed_to_the_bounds_and_tolerates_str_and_list():
    assert SP._coerce(spec("seed_slider"), "500") == C.SEED_MAX
    assert SP._coerce(spec("seed_slider"), "-3") == C.SEED_MIN
    assert SP._coerce(spec("seed_slider"), ["7"]) == 7
    assert SP._coerce(spec("seed_slider"), "7") == 7
    with pytest.raises(ValueError):
        SP._coerce(spec("seed_slider"), "abc")


def test_settings_from_state_uses_keywords_and_types():
    values = {"profile_select": "flach", "size_select": "gross", "aht_select": 480, "goal_select": 95, "catalog_select": "8", "seed_slider": 17}
    s = SP.settings_from_state(values)
    assert s == Settings(profile="flach", size="gross", aht=480, goal=95, catalog="8", seed=17)
    assert s.goal_fraction == 0.95 and s.shifts == (8,)


def test_preset_keys_cover_exactly_the_settings_fields():
    assert set(SP.PRESET_KEYS) == {"profile", "size", "aht", "goal", "catalog", "seed"}
    assert set(S.PRESETS["Standard"]) == set(SP.PRESET_KEYS)


def test_presets_use_known_options_and_each_differs_from_the_standard_in_at_least_one_setting():
    base = S.PRESETS["Standard"]
    for name in S.PRESET_ORDER:
        p = S.PRESETS[name]
        assert p["profile"] in C.PROFILE_ORDER and p["size"] in C.SIZE_ORDER and p["aht"] in C.AHT_OPTIONS
        assert p["goal"] in C.GOAL_OPTIONS and p["catalog"] in C.CATALOG_ORDER and C.SEED_MIN <= p["seed"] <= C.SEED_MAX
        if name != "Standard":
            assert p != base
        assert name in S.PRESET_HELP and S.PRESET_HELP[name]


def test_there_are_five_presets_and_each_sits_on_a_measured_cell():
    import sgt_results as R
    assert len(S.PRESET_ORDER) == 5
    for name in S.PRESET_ORDER:
        p = S.PRESETS[name]
        assert R.cell_for(p["size"], p["goal"], p["aht"], p["catalog"]) is not None, name


def test_apply_preset_writes_all_widget_keys(monkeypatch):
    state = {}
    monkeypatch.setattr(st, "session_state", state)
    SP.apply_preset("Hohes Ziel")
    assert state["goal_select"] == 95 and state["profile_select"] == "zwei_spitzen" and state["seed_slider"] == C.DEFAULT_SEED
    assert "view_select" not in state                      # Anzeigewahl gehört nicht zum Szenario


def test_randomize_seed_stays_in_bounds(monkeypatch):
    state = {}
    monkeypatch.setattr(st, "session_state", state)
    for _ in range(50):
        SP.randomize_seed()
        assert C.SEED_MIN <= state["seed_slider"] <= C.SEED_MAX
