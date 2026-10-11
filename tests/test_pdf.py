"""PDF-Export: Sonderzeichen (fpdf2-Kernschrift), Stundentabelle, Schichten."""

import pytest

import sgt_constants as C
import sgt_pdf_export as X
import sgt_pipeline as PL


@pytest.fixture(scope="module")
def live():
    return PL.run_live(PL.Settings(profile="flach", size="klein", seed=1), with_sim=False)


def test_clean_replaces_characters_the_core_font_cannot_draw():
    text = "– — − ≤ ≥ → … € · Ø ± × ① ä ö ü ß 😀"
    out = X._clean(text)
    out.encode("latin-1")                                      # darf nicht werfen
    assert "ä ö ü ß" in out and "EUR" in out and "<=" in out and ">=" in out and "+/-" in out


def test_pdf_is_generated_with_all_special_characters_in_the_texts(live):
    data = X.generate_pdf("Servicegrad über den Tag", ["Zeile – mit Gedankenstrich ± € …"], ["① Übererfüllung ≥ 1 Punkt −3 😀"], live,
                          keys=("Z", "K", "G"))
    assert data[:5] == b"%PDF-" and len(data) > 1500


def test_hour_rows_have_one_row_per_hour_and_two_columns_per_plan(live):
    rows = X.hour_rows(live, ("Z", "K"))
    assert len(rows) == 24 and all(len(r) == 2 + 2 * 2 for r in rows)
    assert rows[0][0] == "00"
    z = live.plans["Z"]
    assert rows[5][2] == str(z.n[5])


def test_shift_rows_sum_to_the_cost(live):
    for key in ("Z", "K"):
        p = live.plans[key]
        rows = X.shift_rows(p)
        assert sum(int(r[1].split()[0]) * int(r[2]) for r in rows) == p.cost
