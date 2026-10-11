"""Ganzzahliger Zufallsgenerator (SplitMix64) und Zufalls-Seeds aus Schlüsseltexten.

Übernommen aus der Vorab-Messreihe (modell.py): Instanzen, Pläne und Simulationen sind damit plattformunabhängig und mit der Messreihe
vergleichbar. Zufall steckt nie in numpy-Strömen oder `hash()` (pro Prozess gesalzen, PEP 456), sondern nur hier.
"""

import zlib

M64 = (1 << 64) - 1


class SplitMix64:
    """SplitMix64 (Steele, Lea, Flood 2014): 64-Bit-Zustand, Ausgabe nach der Standardvorschrift."""

    def __init__(self, seed):
        self.s = seed & M64

    def next(self):
        self.s = (self.s + 0x9E3779B97F4A7C15) & M64
        z = self.s
        z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & M64
        z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & M64
        return z ^ (z >> 31)

    def randint(self, lo, hi):
        """Ganzzahl in [lo, hi] (Modulo-Abbildung, für die kleinen Spannen hier ausreichend gleichverteilt)."""
        return lo + self.next() % (hi - lo + 1)

    def uniform(self):
        """Gleichverteilt in (0, 1), nie genau 0 oder 1 (53 Bit plus Halbschritt)."""
        return ((self.next() >> 11) + 0.5) / 9007199254740992.0


def seed_from(*parts):
    """Zufalls-Seed aus einem Schlüsseltext (zlib.crc32, nie Python hash())."""
    return zlib.crc32("|".join(str(p) for p in parts).encode("utf-8"))
