"""Erlang C je Stunde: Servicegrad, Tabellen, kleinste Besetzung zu einem Ziel, Tages-Servicegrad, Kennzahlen.

Übernommen aus der Vorab-Messreihe (modell.py); dort gegen die Lehrbuchsumme in Brüchen und gegen die abgeschnittene Markow-Kette
geprüft. Stationär je Stunde: SL(n) = 1 - C(n, a) * exp(-(n - a) * s / AHT) für n > a, sonst 0 (kein stationäres Gleichgewicht).
"""

import math

import sgt_constants as C


def erlang_b(c, a):
    """Blockierwahrscheinlichkeit B(c, a) über die stabile Rekursion."""
    b = 1.0
    for k in range(1, c + 1):
        b = a * b / (k + a * b)
    return b


def erlang_c(c, a):
    """Wartewahrscheinlichkeit C(c, a); c <= a: 1 (kein stationäres Gleichgewicht)."""
    if c <= a:
        return 1.0
    b = erlang_b(c, a)
    return b / (1.0 - (a / c) * (1.0 - b))


def service_level(n, a, aht_min, s_min):
    """P(Wartezeit <= s) im M/M/n-System, a in Erlang, Bediendauer und Servicezeit in Minuten. n <= a: 0 per Festlegung."""
    if n <= a or n <= 0:
        return 0.0
    return 1.0 - erlang_c(n, a) * math.exp(-(n - a) * (1.0 / aht_min) * s_min)


def sl_table(a, aht_min, s_min):
    """Servicegrade SL(0..cap), cap = kleinste Besetzung mit SL >= 1 - 1e-7 (danach konstant)."""
    tab = [0.0]
    n = 1
    while True:
        v = service_level(n, a, aht_min, s_min)
        tab.append(v)
        if v >= 1.0 - 1e-7 and n > a:
            break
        n += 1
    return tab


class Problem:
    """Instanzdaten eines Tages: Last, Servicegrad-Tabellen je Stunde, ganzzahlige Wertetabellen V[t][n] = floor(a_cent * SL * SKALA)."""

    def __init__(self, a_cent, aht_s=240, s_sec=C.SERVICE_S):
        self.tlen = len(a_cent)
        self.a_cent = list(a_cent)
        self.a = [x / 100.0 for x in a_cent]
        self.aht_s = aht_s
        self.aht = aht_s / 60.0   # Minuten
        self.s_sec = s_sec
        self.s_min = s_sec / 60.0
        self.tab = [sl_table(x, self.aht, self.s_min) for x in self.a]
        self.cap = [len(t) - 1 for t in self.tab]
        self.v = [[int(math.floor(self.a_cent[t] * self.tab[t][n] * C.SKALA + 1e-9)) for n in range(self.cap[t] + 1)] for t in range(self.tlen)]
        self.weight_sum = sum(self.a_cent)

    def sl_at(self, t, n):
        """Servicegrad der Stunde t bei Besetzung n (über cap hinaus konstant)."""
        return self.tab[t][min(n, self.cap[t])]

    def v_at(self, t, n):
        return self.v[t][min(n, self.cap[t])]

    def c_target(self, goal):
        """Kleinste Besetzung je Stunde mit SL_t >= goal."""
        out = []
        for t in range(self.tlen):
            n = 0
            while self.sl_at(t, n) < goal - 1e-12:
                n += 1
            out.append(n)
        return out

    def day_sl(self, n):
        """Ankunftsgewichteter Tages-Servicegrad der Besetzung n (Liste je Stunde)."""
        return sum(self.a_cent[t] * self.sl_at(t, n[t]) for t in range(self.tlen)) / self.weight_sum

    def hourly_sl(self, n):
        return [self.sl_at(t, n[t]) for t in range(self.tlen)]

    def v_sum(self, n):
        """Ganzzahlige Wertesumme der Besetzung n (die linke Seite der Tageszeile)."""
        return sum(self.v_at(t, n[t]) for t in range(self.tlen))

    def rhs_goal(self, goal):
        """Ganzzahlige rechte Seite der Tageszeile für das Tagesziel (aufgerundet)."""
        return math.ceil(goal * self.weight_sum * C.SKALA - 1e-9)


def key_figures(prob, n):
    """Kosten, Tages-Servicegrad, Anteil der Stunden und der Anrufe unter 50 %, kleinster Stunden-Servicegrad, leere Stunden."""
    sl = prob.hourly_sl(n)
    tl = prob.tlen
    bad = [t for t in range(tl) if sl[t] < C.EMPTY_LIMIT]
    return {
        "cost": sum(n),
        "day_sl": prob.day_sl(n),
        "hours_below": len(bad) / tl,
        "n_hours_below": len(bad),
        "calls_below": sum(prob.a_cent[t] for t in bad) / prob.weight_sum,
        "sl_min": min(sl),
        "empty": sum(1 for x in n if x == 0),
    }
