"""Gemeinsame Fixtures: die Mini-Instanz, an der jede Einheit von Hand geprüft wird (DEMO-PLAYBOOK §1b)."""

import sys
from pathlib import Path

import pytest

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sgt_erlang import Problem  # noqa: E402


@pytest.fixture
def mini():
    """Vier Stunden mit 0,6; 1,2; 0,4 und 0,9 Erlang bei 240 s Bediendauer, Servicezeit 20 s (zyklisch).

    Handrechnung (M/M/1 mit a = 0,6: C = a = 0,6; SL(1) = 1 - 0,6 * exp(-(1 - 0,6) * 20/240) = 1 - 0,6 * exp(-1/30) = 0,4199...)."""
    return Problem([60, 120, 40, 90], aht_s=240, s_sec=20)


@pytest.fixture
def mini5():
    """Fünf Stunden für die Aufzählung aller Besetzungsmuster."""
    return Problem([30, 80, 110, 60, 20], aht_s=240, s_sec=20)
