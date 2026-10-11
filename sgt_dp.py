"""Rucksack-Rechnung ohne Schichtstruktur: kleinste Kosten, wenn jedes Besetzungsmuster erlaubt ist (Mehrfachauswahl über die Kosten).

Übernommen aus der Vorab-Messreihe (dp_ohne_schichten). best[c] = größte Wertesumme bei genau c Personenstunden, Stunde für Stunde.
Das Ergebnis ist exakt und zugleich die untere Schranke der Kosten jeder Planung mit Schichten (jedes Schichtmuster ist ein Muster).
"""

import numpy as np


def unit_best_table(prob, lower_bounds, kmax):
    """Eine Stunde nach der anderen: Tabellen best_t[c] (-1 = nicht erreichbar) und die gewählte Besetzung je (Stunde, c)."""
    neg = -1
    best = np.full(kmax + 1, neg, dtype=np.int64)
    best[0] = 0
    choices = []
    for t in range(prob.tlen):
        new = np.full(kmax + 1, neg, dtype=np.int64)
        ch = np.full(kmax + 1, -1, dtype=np.int64)
        for k in range(lower_bounds[t], prob.cap[t] + 1):
            val = prob.v[t][k]
            src = best[: kmax + 1 - k]
            cand = np.where(src >= 0, src + val, neg)
            seg = new[k:]
            better = cand > seg
            seg[better] = cand[better]
            cseg = ch[k:]
            cseg[better] = k
        choices.append(ch)
        best = new
    return best, choices


def dp_no_shifts(prob, lower_bounds, rhs):
    """Kleinste Summe n_t mit n_t >= lower_bounds[t] und Wertesumme >= rhs. Rückgabe (Kosten, Besetzung, Wertesumme) oder None."""
    kmax = sum(prob.cap) + 1
    best, choices = unit_best_table(prob, lower_bounds, kmax)
    for c in range(kmax + 1):
        if best[c] >= rhs:
            n = [0] * prob.tlen
            cur = c
            for t in range(prob.tlen - 1, -1, -1):
                k = int(choices[t][cur])
                n[t] = k
                cur -= k
            return c, n, int(best[c])
    return None
