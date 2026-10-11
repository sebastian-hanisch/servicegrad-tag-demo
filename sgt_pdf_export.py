"""Auswertung als PDF (fpdf2, Kernschrift Helvetica: Umlaute gehen; Gedankenstrich, Euro-Zeichen, Emoji und U+2212 nicht)."""

from fpdf import FPDF

import sgt_constants as C

_REPLACE = {"–": "-", "—": "-", "−": "-", "≤": "<=", "≥": ">=", "→": "->", "↔": "<->", "…": "...", "€": "EUR", "·": ".", "Ø": "Durchschnitt",
            "±": "+/-", "×": "x", "²": "^2", "③": "3", "①": "1", "②": "2", "④": "4"}


def _clean(text):
    for a, b in _REPLACE.items():
        text = text.replace(a, b)
    return text.encode("latin-1", "replace").decode("latin-1")


def hour_rows(live, keys=C.PLAN_KEYS):
    """Zeilen der Stundentabelle: Stunde, Last (Erlang) und je Plan Besetzung und Servicegrad der Stunde in Prozent."""
    rows = []
    for t in range(live.prob.tlen):
        row = [f"{t:02d}", f"{live.prob.a[t]:.1f}"]
        for k in keys:
            p = live.plans.get(k)
            row += ["-", "-"] if p is None else [str(p.n[t]), f"{100 * live.prob.sl_at(t, p.n[t]):.0f}"]
        rows.append(row)
    return rows


def shift_rows(plan):
    """Schichten eines Plans: (Start, Länge, Anzahl)."""
    return [(f"{s:02d}:00", f"{length} h", str(count)) for s, length, count in plan.shifts]


def generate_pdf(title, summary_lines, statement_lines, live, keys=C.PLAN_KEYS):
    """Auswertung: Einstellung, die vier Aussagen, Besetzung und Servicegrad je Stunde, Schichten je Plan."""
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, _clean(title), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    for line in summary_lines:
        pdf.multi_cell(0, 5, _clean(line), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 7, _clean("Die vier Aussagen"), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    for line in statement_lines:
        pdf.multi_cell(0, 5, _clean(line), new_x="LMARGIN", new_y="NEXT")
        pdf.ln(1)
    pdf.ln(2)
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 7, _clean("Besetzung und Servicegrad je Stunde"), new_x="LMARGIN", new_y="NEXT")
    head = "Stunde | Last (Erlang) | " + " | ".join(f"{k}: Pers. / SL %" for k in keys)
    pdf.set_font("Helvetica", "B", 9)
    pdf.cell(0, 5, _clean(head), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 9)
    for row in hour_rows(live, keys):
        cells = [row[0], row[1]] + [f"{row[2 + 2 * i]} / {row[3 + 2 * i]}" for i in range(len(keys))]
        pdf.cell(0, 4.5, _clean(" | ".join(cells)), new_x="LMARGIN", new_y="NEXT")
    for k in keys:
        p = live.plans.get(k)
        if p is None or not p.shifts:
            continue
        pdf.ln(2)
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(0, 7, _clean(f"Schichten {C.PLAN_LABELS[k]}: {p.cost} Personenstunden"), new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 10)
        pdf.cell(0, 5, _clean("Start | Länge | Anzahl"), new_x="LMARGIN", new_y="NEXT")
        for a, b, c in shift_rows(p):
            pdf.cell(0, 5, _clean(f"{a} | {b} | {c}"), new_x="LMARGIN", new_y="NEXT")
    return bytes(pdf.output())
