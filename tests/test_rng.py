"""SplitMix64 und Zufalls-Seeds: Referenzwerte, Bereiche, Reproduzierbarkeit."""

import zlib

from sgt_rng import SplitMix64, seed_from


def test_splitmix64_seed_zero_matches_the_published_reference_values():
    g = SplitMix64(0)
    assert [g.next() for _ in range(3)] == [0xE220A8397B1DCDAF, 0x6E789E6AA1B965F4, 0x06C45D188009454F]


def test_randint_covers_the_range_and_stays_inside():
    g = SplitMix64(123)
    xs = [g.randint(3, 7) for _ in range(5000)]
    assert min(xs) == 3 and max(xs) == 7
    assert set(xs) == {3, 4, 5, 6, 7}


def test_uniform_is_strictly_inside_the_unit_interval():
    g = SplitMix64(5)
    us = [g.uniform() for _ in range(2000)]
    assert all(0.0 < u < 1.0 for u in us)
    assert 0.45 < sum(us) / len(us) < 0.55


def test_seed_from_is_crc32_of_the_joined_key_and_not_python_hash():
    assert seed_from("a", 1) == zlib.crc32(b"a|1")
    assert seed_from("a", 1) == seed_from("a", 1)
    assert seed_from("a", 1) != seed_from("a", 2)


def test_streams_are_reproducible():
    a, b = SplitMix64(seed_from("x", 3)), SplitMix64(seed_from("x", 3))
    assert [a.randint(0, 99) for _ in range(20)] == [b.randint(0, 99) for _ in range(20)]
