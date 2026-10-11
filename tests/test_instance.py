"""Instanzgenerator: Bereiche, Determinismus und Gleichheit mit den gespeicherten Lasten der Vorab-Messreihe."""

import pytest

import sgt_constants as C
import sgt_instance as I
import sgt_results as R


@pytest.mark.parametrize("kind", C.PROFILE_ORDER)
def test_profile_has_24_integer_hours_within_bounds(kind):
    for i in range(10):
        a = I.instance_for(kind, "mittel", i)
        assert len(a) == 24 and all(isinstance(x, int) for x in a)
        assert min(a) >= 10                       # Mindestlast 0,10 Erlang
        if kind != "nachtgrund":
            assert max(a) <= C.SIZES["mittel"][1]  # Spitze höchstens obere Größengrenze


def test_instance_is_deterministic_and_differs_by_index():
    assert I.instance_for("flach", "mittel", 5) == I.instance_for("flach", "mittel", 5)
    assert I.instance_for("flach", "mittel", 5) != I.instance_for("flach", "mittel", 6)
    assert I.instance_for("flach", "mittel", 5) != I.instance_for("zwei_spitzen", "mittel", 5)


def test_peak_load_lies_in_the_size_range():
    for size, (lo, hi) in C.SIZES.items():
        for i in range(10):
            a = I.instance_for("zwei_spitzen", size, i)
            assert lo * 0.5 <= max(a) <= hi        # Rauschen und Profilform können die Spitze unter lo drücken, nie über hi


def test_a_cent_at_scales_with_aht_and_keeps_at_least_one():
    assert I.a_cent_at([100, 10, 1], 240) == [100, 10, 1]
    assert I.a_cent_at([100, 10, 1], 480) == [200, 20, 2]
    assert I.a_cent_at([100, 10, 1], 120) == [50, 5, 1]


def test_generator_reproduces_the_stored_loads_of_the_messreihe():
    """Zwei Instanzen je Profil und Zelle sind mit ihrer Last gespeichert: der Generator muss sie bitgleich treffen."""
    checked = 0
    for name in R.cell_names():
        c = R.cell(name)
        lo, hi = C.SIZES[c["size"]]
        for row in c["rows"]:
            if "a_cent" in row:
                got = I.a_cent_at(I.make_instance(row["art"], lo, hi, row["i"]), c["aht"])
                assert got == row["a_cent"], (name, row["art"], row["i"])
                checked += 1
    assert checked >= 20


def test_every_profile_keeps_the_minimum_load_of_0_10_erlang_even_for_tiny_peaks():
    from sgt_rng import SplitMix64
    for kind in C.PROFILE_ORDER:
        for peak in (12, 20, 40):
            a = I.build_profile(kind, peak, SplitMix64(7))
            assert min(a) >= 10, (kind, peak)
