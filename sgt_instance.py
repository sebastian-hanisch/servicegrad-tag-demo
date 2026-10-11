"""Instanzen: Lastprofile eines Tages in 24 Stunden, ganzzahlig in 0,01 Erlang (bei der Bezugs-Bediendauer 240 s).

Übernommen unverändert aus der Vorab-Messreihe (modell.py). Eine Instanz ist durch (Profil, Größe, Instanznummer) bestimmt; die
Instanznummer ist der Zufalls-Seed der Demo. Gleiche Nummer ergibt in jeder Zelle (Ziel, Katalog, Bediendauer) dieselbe Last.
"""

import sgt_constants as C
from sgt_rng import SplitMix64, seed_from


def build_profile(kind, peak_cent, rng, tlen=C.T):
    """Last a_t in 0,01 Erlang (bei 240 s) für `tlen` Stunden, nur ganzzahlig gerechnet. Mindestlast 0,10 Erlang."""
    peak = peak_cent
    a = [0] * tlen
    if kind == "flach":
        level = rng.randint(85, 100)
        for t in range(tlen):
            a[t] = peak * level // 100 * (100 + rng.randint(-8, 8)) // 100
    elif kind == "zwei_spitzen":
        base = peak * rng.randint(8, 20) // 100
        c1, c2 = rng.randint(9, 11), rng.randint(14, 16)
        w1, w2 = rng.randint(3, 4), rng.randint(3, 4)
        h1, h2 = rng.randint(85, 100), rng.randint(70, 100)
        for t in range(tlen):
            b1 = max(0, w1 - abs(t - c1)) * (peak - base) * h1 // (w1 * 100)
            b2 = max(0, w2 - abs(t - c2)) * (peak - base) * h2 // (w2 * 100)
            a[t] = (base + max(b1, b2)) * (100 + rng.randint(-5, 5)) // 100
    elif kind == "morgenspitze":
        base = peak * rng.randint(8, 15) // 100
        day = peak * rng.randint(30, 45) // 100
        s0 = rng.randint(7, 9)
        d = rng.randint(5, 8)
        end = rng.randint(20, 22)
        for t in range(tlen):
            if t < s0 or t >= end:
                v = base
            else:
                v = day + (peak - day) * max(0, d - (t - s0)) // d
            a[t] = v * (100 + rng.randint(-5, 5)) // 100
    elif kind == "nachtgrund":
        night = rng.randint(30, 150)  # 0,30 bis 1,50 Erlang absolut
        c0 = rng.randint(11, 14)
        for t in range(tlen):
            if t >= 23 or t < 6:
                a[t] = night * (100 + rng.randint(-10, 10)) // 100
            else:
                h = peak * rng.randint(50, 60) // 100 + (peak * rng.randint(40, 50) // 100) * max(0, 6 - abs(t - c0)) // 6
                a[t] = h * (100 + rng.randint(-5, 5)) // 100
    elif kind == "steile_spitze":
        base = peak * rng.randint(5, 10) // 100
        c0 = rng.randint(9, 16)
        width = rng.randint(1, 2)  # Stunden mit voller Spitze; Schultern bei 40 %
        for t in range(tlen):
            d = abs(t - c0)
            if d < width:
                v = peak
            elif d == width:
                v = base + (peak - base) * 40 // 100
            else:
                v = base
            a[t] = v * (100 + rng.randint(-5, 5)) // 100
    else:
        raise ValueError(kind)
    return [max(10, min(peak, v)) if kind != "nachtgrund" else max(10, v) for v in a]


def make_instance(kind, size_min_cent, size_max_cent, index, salt=""):
    """Instanz `index` einer Profilart; Spitzenlast gleichverteilt in [min, max] (0,01 Erlang bei 240 s)."""
    rng = SplitMix64(seed_from("inst", kind, size_min_cent, size_max_cent, index, salt))
    peak = rng.randint(size_min_cent, size_max_cent)
    return build_profile(kind, peak, rng)


def instance_for(kind, size, index):
    """Instanz der Profilart `kind` in der Größenstufe `size` ("klein", "mittel", "gross"), Nummer `index` (Zufalls-Seed)."""
    lo, hi = C.SIZES[size]
    return make_instance(kind, lo, hi, index)


def a_cent_at(a_ref_cent, aht_s):
    """Gleiche Anrufzahlen, andere Bediendauer: das Angebot skaliert mit der Bediendauer (ganzzahlig abgerundet, mindestens 1)."""
    return [max(1, x * aht_s // C.AHT_REF) for x in a_ref_cent]
