"""Preset-Kriterien: an der Messreihe UND an der gezeigten Instanz; jedes Kriterium kippt einzeln an seiner Schwelle."""

import copy

import pytest

import sgt_evaluation as E
import sgt_pipeline as PL
import sgt_stories as S


@pytest.fixture(scope="module")
def instances():
    out = {}
    for name in S.PRESET_ORDER:
        live = PL.run_live(PL.Settings(**S.PRESETS[name]), with_sim=True)
        out[name] = S.instance_facts(E.figures(live))
    return out


@pytest.mark.parametrize("name", S.PRESET_ORDER)
def test_every_criterion_holds_in_the_messreihe(name):
    facts = S.measured_facts(name)
    results = S.check(name, facts)
    assert any(ok is not None for _, ok, _ in results)
    for label, ok, value in results:
        assert ok in (True, None), (name, label, value)


@pytest.mark.parametrize("name", S.PRESET_ORDER)
def test_every_criterion_holds_on_the_shown_instance(name, instances):
    for label, ok, value in S.check(name, instances[name]):
        assert ok in (True, None), (name, label, value)


@pytest.mark.parametrize("name", S.PRESET_ORDER)
def test_each_criterion_flips_alone_at_its_threshold(name):
    for label, key, op, thr in S.CRITERIA[name]:
        facts = {k: None for k in ("over", "k_pct", "o_pct", "empty", "d_O", "g_pct", "z_sl", "beq_pct", "o_minus_bf")}
        for l2, k2, op2, thr2 in S.CRITERIA[name]:
            facts[k2] = thr2 + (1.0 if op2 == ">=" else -1.0)         # alle gut
        assert all(ok for _, ok, _ in S.check(name, facts))
        at = copy.deepcopy(facts)
        at[key] = thr                                                  # genau auf der Schwelle: erfüllt
        assert dict((l, ok) for l, ok, _ in S.check(name, at))[label] is True
        bad = copy.deepcopy(facts)
        bad[key] = thr + (-0.01 if op == ">=" else 0.01)               # knapp daneben: genau dieses Kriterium fällt
        res = dict((l, ok) for l, ok, _ in S.check(name, bad))
        assert res[label] is False
        assert all(ok for l, ok in res.items() if l != label)


def test_missing_figures_drop_the_criterion_instead_of_failing_it():
    res = S.check("Standard", {"over": 6.0})
    assert dict((l, ok) for l, ok, _ in res)["Z liefert mindestens 5 Punkte über dem Ziel"] is True
    assert sum(1 for _, ok, _ in res if ok is None) == len(S.CRITERIA["Standard"]) - 1


def test_the_presets_tell_different_stories_on_the_primary_numbers(instances):
    """Jedes Preset ändert mindestens eine Kennzahl gegenüber dem Standard."""
    base = instances["Standard"]
    for name in S.PRESET_ORDER[1:]:
        assert any(instances[name][k] != base[k] for k in ("z_sl", "k_pct", "o_pct", "empty", "d_O")), name
