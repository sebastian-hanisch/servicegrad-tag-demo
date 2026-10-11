"""Konstanten: Regler-Stufen, Kataloge, Profile, feste Annahmen, Farben (Presets stehen in sgt_stories.py).

Alle Werte der Instanzen sind erfunden (nicht an echten Daten kalibriert). Die Regler-Stufen sind genau die der Vorab-Messreihe.
"""

# --- Modell --------------------------------------------------------------------------------------------------------------------------------
T = 24                    # Stunden je Tag, zyklisch
SKALA = 100_000           # Ganzzahl-Skalierung der Servicegrade (abgerundet, damit eine Lösung das Ziel wirklich erfüllt)
AHT_REF = 240             # Sekunden: Bezugs-Bediendauer, in der die Lasten in 0,01 Erlang erzeugt werden
SERVICE_S = 20            # Servicezeit in Sekunden (fest, kein Regler)
FLOOR = 0.5               # Mindestwert je Stunde der Variante G (eine einzige Wahl, 30 und 70 % sind nicht gemessen)
Z_STEP = 0.01             # Raster des einheitlichen Stundenziels z der Variante K
Z_LOWER = 0.30            # Untergrenze der z-Suche
Z_PATIENCE = 3            # Abbruch der z-Suche nach so vielen Fehlschlägen in Folge
CONCAVE_FROM = 0.5        # ab dieser Untergrenze ist der Servicegrad ab c_t(z) konkav (gemessen, kein Beweis)

# --- Rechenbudget (live) --------------------------------------------------------------------------------------------------------------------
TIME_LIMIT_S = 5.0            # Zeitlimit der Variante O mit Schichten (Stufe 2) ...
TIME_LIMIT_BIG_S = 8.0        # ... und bei großer Last (Spitze ab BIG_LOAD_ERLANG Erlang)
BIG_LOAD_ERLANG = 20.0
TIME_LIMIT_STAGE2_S = 1.0     # Zeitlimit der zweiten Stufe (bester Servicegrad bei gleichen Kosten)
EXACT_LIMIT_S = 30.0          # Zeitlimit des Exakt-Tabs
CALL_BUDGET = 40_000          # simulierte Anrufe je Plan (bestimmt die Zahl der Tage)
SIM_DAYS_MIN, SIM_DAYS_MAX = 5, 40
SIM_WARM_DAYS = 3             # Einschwingzeit in Tagen (nicht gezählt)

# --- Regler ---------------------------------------------------------------------------------------------------------------------------------
PROFILE_ORDER = ("flach", "zwei_spitzen", "morgenspitze", "nachtgrund", "steile_spitze")
PROFILE_LABELS = {"flach": "Flach", "zwei_spitzen": "Zwei Spitzen", "morgenspitze": "Steile Morgenspitze",
                  "nachtgrund": "Nachtgrundlast", "steile_spitze": "Schmaler Gipfel"}
PROFILE_HELP = {
    "flach": "Fast gleichmäßige Last über den ganzen Tag (Schwankung etwa ±8 %).",
    "zwei_spitzen": "Vormittags- und Nachmittagsspitze mit ruhiger Mitte und niedriger Nacht.",
    "morgenspitze": "Steiler Anstieg am Morgen, danach langsam abfallend bis zum Abend, nachts niedrig.",
    "nachtgrund": "Ruhige Nacht mit weniger als 1,5 Erlang, tagsüber ein breiter Gipfel.",
    "steile_spitze": "Ein schmaler Gipfel über sehr niedriger Grundlast (der Stresstest der Messreihe).",
}
SIZES = {"klein": (300, 600), "mittel": (800, 1500), "gross": (2500, 4000)}   # Spitzenlast in 0,01 Erlang bei 240 s
SIZE_ORDER = ("klein", "mittel", "gross")
SIZE_LABELS = {"klein": "klein (3 bis 6 Erlang)", "mittel": "mittel (8 bis 15 Erlang)", "gross": "groß (25 bis 40 Erlang)"}
AHT_OPTIONS = (120, 240, 480)
GOAL_OPTIONS = (70, 80, 90, 95)   # Prozent
CATALOG_ORDER = ("8", "6/8/10", "4/6/8", "3/4/5", "3 bis 12", "3/4")
CATALOGS = {"8": (8,), "6/8/10": (6, 8, 10), "4/6/8": (4, 6, 8), "3/4/5": (3, 4, 5), "3 bis 12": tuple(range(3, 13)), "3/4": (3, 4)}
CATALOG_LABELS = {"8": "nur 8 h", "6/8/10": "6, 8, 10 h", "4/6/8": "4, 6, 8 h", "3/4/5": "3, 4, 5 h", "3 bis 12": "3 bis 12 h", "3/4": "3, 4 h"}
SEED_MIN, SEED_MAX = 0, 99
DEFAULT_PROFILE, DEFAULT_SIZE, DEFAULT_AHT, DEFAULT_GOAL, DEFAULT_CATALOG, DEFAULT_SEED = "zwei_spitzen", "mittel", 240, 80, "6/8/10", 2

# --- Varianten ------------------------------------------------------------------------------------------------------------------------------
PLAN_KEYS = ("Z", "K", "G", "O")        # live gerechnet, mit Schichten; dazu die Untergrenze ohne Schichtstruktur ("ODP")
PLAN_LABELS = {
    "Z": "Z: Tagesziel als Stundenziel",
    "K": "K: kalibriertes Stundenziel",
    "G": "G: gemeinsam mit Mindestwert",
    "O": "O: gemeinsam ohne Mindestwert",
    "ODP": "O ohne Schichtstruktur (Untergrenze)",
}
PLAN_SHORT = {"Z": "Z", "K": "K", "G": "G", "O": "O", "ODP": "O ohne Schichten"}
# Kürzel der Vorab-Messreihe: Z = A, K = Az, G = BFz, O = B; dazu die nur vorgerechneten Varianten Beq, BF, B1, Bz
MESS_CODE = {"Z": "A", "K": "Az", "G": "BFz", "O": "B"}
VARIANT_TABLE = (
    # Kürzel der App, Kürzel der Messreihe, Kurzbeschreibung, live oder vorgerechnet
    ("Z", "A", "Zweistufig: je Stunde die kleinste Besetzung, deren Servicegrad das Tagesziel erreicht; Schichten darüber kostenminimal.", "live"),
    ("K", "Az", "Wie Z, aber ein einheitliches Stundenziel z unter dem Tagesziel, so weit abgesenkt, wie der Tages-Servicegrad noch das Ziel hält.", "live"),
    ("G", "BFz", "Gemeinsam geplant: jede Stunde mindestens 50 % Servicegrad, der Tages-Servicegrad mindestens der von K.", "live"),
    ("O", "B", "Gemeinsam geplant, nur der Tages-Servicegrad zählt: kein Mindestwert, Stunden dürfen leer bleiben.", "live"),
    ("O ohne Schichten", "B (DP)", "Dieselbe Aufgabe wie O, aber jedes Besetzungsmuster ist erlaubt (Rucksack-Rechnung): die Untergrenze der Kosten von O.", "live"),
    ("Beq", "Beq", "Wie O, aber mit dem Tages-Servicegrad, den Z tatsächlich liefert (gleiche gelieferte Qualität wie Z).", "vorgerechnet"),
    ("BF", "BF", "Wie O, aber jede Stunde mindestens 50 % und der Tages-Servicegrad mindestens das Ziel.", "vorgerechnet"),
    ("B1", "B1", "Wie O, aber in jeder Stunde mindestens eine Person.", "vorgerechnet"),
)

# --- Auswertung ----------------------------------------------------------------------------------------------------------------------------
HOLD_TOLERANCE = 0.005    # Ziel gilt als gehalten, wenn der simulierte Wert mindestens Ziel minus 0,5 Punkte erreicht
EMPTY_LIMIT = 0.5         # Stunden unter 50 % Servicegrad zählen als "schlecht bedient"
DROP_POINTS = 3.0         # Zustand 3 des Rückstau-Abschnitts: Simulation mehr als 3 Punkte unter dem Modell ...
DROP_SE = 2.0             # ... und mehr als 2 Standardfehler
NOISE_POINTS = 1.0        # Unterschied im Rauschen: höchstens 2 SE oder 1 Punkt
OVER_POINTS = 1.0         # Übererfüllung gilt ab Ziel plus 1 Punkt (Abdeckung)

# --- Farben (Okabe-Ito, farbenblindenfreundlich) ---------------------------------------------------------------------------------------------
COLORS = {"Z": "#0072B2", "K": "#009E73", "G": "#E69F00", "O": "#D55E00", "ODP": "#999999"}
COLOR_LOAD = "#555555"
COLOR_GOAL = "#222222"
COLOR_FLOOR = "#999999"
COLOR_EMPTY = "rgba(213,94,0,0.18)"
