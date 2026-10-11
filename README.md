# Servicegrad über den Tag – Streamlit-Demo

**[→ Demo live ausprobieren](https://sebastianhanisch-servicegrad-tag-demo.streamlit.app/)**

Fall-Demo der Gruppe Personaleinsatzplanung, die Brücke zwischen der Schichtplanung und der Warteschlangen-Linie. Ein Kontaktcenter will an jedem Tag
80 % der Anrufe innerhalb von 20 Sekunden annehmen (Servicezeit 20 s, mittlere Bediendauer 240 s). Es rechnet erst den Bedarf je Stunde (Erlang C) und
legt dann Schichten darüber. [Schichtplanung](https://sebastianhanisch-shift-demo.streamlit.app/) deckt einen gegebenen Stundenbedarf,
[Wurzelregel](https://sebastianhanisch-square-root-staffing-demo.streamlit.app/) und [zeitvariable Last](https://sebastianhanisch-time-varying-arrivals-demo.streamlit.app/)
rechnen den Bedarf aus der Ankunftsrate; hier werden beide verbunden. Dasselbe Modell trägt auch das Terminal-Gate der
[Warteschlangen-Linie](https://sebastianhanisch.net/konzepte-warteschlangentheorie.html) (Lkw statt Anrufe, Minutenziele). Optimierung plus Simulation, kein Machine Learning.
Alle Instanzen sind erfunden: Beispielwerte, keine Prognose für einen echten Betrieb.

## Kernfrage

Was kostet es, das Tagesziel als Stundenziel zu rechnen, was verspricht eine Planung, die das Ziel nur über den ganzen Tag verlangt, und warum hält dieses
Versprechen nicht? Der Aufhänger ist nicht „die gemeinsame Planung spart X“, sondern die **Reihenfolge der drei Fallstricke**:

1. **Übererfüllung.** Wer das Tagesziel als Stundenziel rechnet (Z), liefert im Mittel 88,6 % statt 80 % und bezahlt jeden Tag dafür. Ein einziger Parameter, das
   einheitliche Stundenziel z (K), holt 7,8 % der Kosten zurück.
2. **Leere Stunden.** Die scheinbare Ersparnis der gemeinsamen Planung ohne Mindestwert (O, 13,0 %) entsteht, indem kleine Stunden aufgegeben werden: im Mittel
   5,8 von 24 bleiben leer.
3. **Rückstau.** Die stationäre Rechnung je Stunde sieht nicht, dass die Anrufe einer leeren Stunde beim Öffnen als Schlange die nächsten Stunden zerstören. In der
   Simulation hält O das Ziel nur in 10 % der Instanzen.

Was an echter Kopplung bleibt (gemeinsame Planung mit Mindestwert 50 % je Stunde bei gleicher gelieferter Qualität wie K): 0,5 % der Kosten, 0,8 Personenstunden je
Tag, und in 68,8 % der Instanzen exakt nichts. Die Demo zeigt die vier Abschnitte live auf einer Instanz (Zufalls-Seed 0 bis 99, dieselbe Last wie in der
Messreihe) und stellt die vorgerechnete Messreihe über 5.400 Instanzen daneben.

## Befunde und Korrekturen gegenüber dem Plan

Die Demo folgt dem Detailplan `plan_servicegrad_tag.html` (Vorab-Messreihe „Vom Bedarf zum Plan“, Ampel GELB). Beim Bau (AP 0, Bau-Gate) wurde gemessen und
korrigiert; wo Plan und Messung sich widersprachen, gilt die Messung:

1. **Zeitlimit von O mit Schichten: 5 s, ab 20 Erlang Spitzenlast 8 s (Plan: 2 s und 5 s), und das Bau-Gate wird nicht überall gehalten.** Das Gate des Plans verlangt, dass O je Zelle höchstens in 5 % der Läufe um mehr als 2 Personenstunden schlechter ist als der Bestwert der Messreihe. Mit 2 s (5 s bei großem Betrieb) verfehlten drei Zellen es deutlich (Ziel 70 %: 58 von 400 Instanzen, Bediendauer 480 s: 68, Größe groß: 50; erster Gesamtlauf mit 12 parallelen Prozessen). Mit 5 s und 8 s (drei Prozesse, Anteil der Läufe um mehr als 2 Personenstunden schlechter): Basis 0,0 % (0 von 125), Ziel 70 % 0,0 % (0 von 100), Bediendauer 480 s 6,0 % (6 von 100), Größe groß 2,0 % (2 von 100); ein früherer Lauf derselben Stichprobe ergab 0 %, 14 % und 5 % für Ziel 70 %, Bediendauer 480 s und Größe groß. Das Gate gilt damit in Basis, Ziel 70 % und Größe groß, in der Zelle Bediendauer 480 s liegt es bei 6 bis 14 % darüber. Das Ergebnis hängt stark von der verfügbaren Rechenzeit ab (HiGHS startet je Prozess mehrere Threads; im Gesamtlauf mit 14 Prozessen und fremder Last auf dem Rechner waren es in der Zelle Größe groß 77 von 400). Mit längerem Zeitlimit (`tools/o_quality.py --limit`): Bediendauer 480 s 7,0 % und Größe groß 2,0 % bei 15 s, Größe groß 0,0 % bei 30 s (jeweils 100 Instanzen, drei Prozesse). Entscheidung: Variante L (live mit Status) bleibt, die Limits bleiben bei 5 s und 8 s, weil längere Wartezeiten die Seite unbrauchbar machen würden; die App nennt immer „bestes Ergebnis nach t s“ mit Untergrenze und Lücke, und der Exakt-Tab löst O in 30 s. Der Rückfall F (O nur ohne Schichtstruktur) ist nicht gewählt: dann wirkte der Katalog nicht auf O. O ist damit in schweren Zellen (Bediendauer 480 s, großer Betrieb) teils zu teuer angegeben, nie zu billig; auf einem langsameren Server als diesem Gerät ist die Lücke größer.
2. **Die Dualschranke des Lösers trägt Rauschen.** Der erste Gesamtlauf meldete in zwei Instanzen (Katalog 3/4/5 h und 3 bis 12 h, Profil Flach) O als „optimal“, obwohl die Messreihe einen um eine Personenstunde besseren Wert hatte: HiGHS lieferte im Zeitlimit eine Dualschranke von 402,0000001, die zu 403 aufgerundet wurde. Jetzt wird mit Toleranz 1e-3 aufgerundet; Regressionstest in `tests/test_oracle_servicegrad_tag.py` (die Schranke liegt nie über dem CP-SAT-Optimum).
3. **Konkavität bei z < 0,5.** Der Plan nennt für z = 0,3 Verletzungen in 35 bis 76 von 100 Instanzen. Nachgemessen (60 Demo-Instanzen im Test, 400 in der Nachmessung, Größe klein und mittel, Bediendauer 120 bis 480 s): keine Verletzung bei z = 0,3, 0,4, 0,5 und 0,7; die Zuwächse sind ab c_t(z) nichtsteigend. S-förmig ist die Kurve nur ab 0 (Variante O). Die Laufzeitprüfung je Stunde und die binäre Fassung bleiben (Test mit Untergrenze 0).
4. **Das Raster von K.** Der Plan ließ die K-Spalten der neun Zellen mit Raster 0,05 nach Möglichkeit neu rechnen. Geschehen: Alle 5.400 Instanzen wurden mit der Live-Rechnung (Raster 0,01) nachgerechnet; K ist in 1.751 Instanzen billiger als der Messreihenwert, in 3.646 gleich und in 3 Instanzen teurer (das Abbruchkriterium von drei Fehlschlägen in Folge greift im feinen Raster vor dem z, das das grobe Raster traf). Die Tabellen zeigen K im Raster 0,01, die Spalte „K in der Messreihe“ den gespeicherten Wert.
5. **Die DP-Schranke ersetzter Einträge.** In 36 Instanzen (Basis 1, Katalog nur 8 h 35) weicht die live gerechnete Untergrenze ohne Schichtstruktur von der gespeicherten ab: Dort ersetzte die Auswertung der Messreihe den Eintrag durch die bekannte Lösung einer engeren Variante und übernahm deren Schranke. Kein Fehler der Live-Rechnung; in allen übrigen 5.364 Instanzen ist die Untergrenze gleich.
6. **Beweisstatus ehrlich gezählt.** `auswerten.py` der Messreihe zählt ersetzte Einträge als bewiesen (O in der Basis 89,2 %); hier zählen sie nicht (88,6 %, 4 ersetzt). Der Ordner der Messreihe wurde nicht geändert.
7. **Gemessen und verworfen:** (a) eine Kostenobergrenze aus den bekannten Funden (K, G) im Modell von O: im Zeitlimit schlechtere Funde (flache Last, 12 Instanzen: Summe der Abweichungen 92 gegen 30 Personenstunden ohne Obergrenze); (b) eine Nachbarschaftssuche (Fenster von Startstunden freigeben) nach dem Löser: bei gleicher Gesamtzeit nicht besser als der Löser allein.
8. **Standardfehler.** Der Schätzer aus den Tagesmitteln trifft die Streuung über zwölf Zufalls-Seeds im Mittel (Verhältnis 1,05, `tools/se_check.py`, 100 Läufe mit je 14 Tagen); einzelne Instanzen streuen um etwa ± 20 %.
9. **13,0 % und 24,3 Personenstunden sind zwei Zahlen:** 13,0 % ist das Mittel der Prozentwerte je Instanz, 24,3 von 207,6 Personenstunden im Mittel sind 11,7 % (kleine Instanzen sparen mehr). Der Plan nennt beide nebeneinander; hier steht die Rechnung dabei.
10. **Simulationstage nach Anrufbudget.** Live gelten 5 bis 40 Tage (40.000 Anrufe je Plan), die Messreihe rechnet 40 Tage fest; die Standardinstanz liegt mit 28 Tagen bei −11,4 Punkten, die Messreihe für das Profil bei −9,8.
11. **Presets.** Alle Abnahmekriterien des Plans halten an den Mitteln der Messreihe und an der gezeigten Instanz; der Standard-Zufalls-Seed 2 ist durch die Suche bestätigt (Abstand 1,12). Der Plan forderte Presets außerhalb der Stichproben-Seeds; die Seeds liegen in der Stichprobe, sind aber nach Typizität (Abstand zu den Profil-Mitteln) und nicht nach den Kriterien gewählt.
12. **Abdeckung.** Instanzen sind die Zufalls-Seeds 0 bis 19 (die Vorschau des Plans nutzte 60 und 61); dadurch liegen sie in der simulierten Stichprobe der Basiszelle, und die Mittel der Abdeckung dort stimmen mit der Messreihe überein (Zwei Spitzen: Übererfüllung 8,45 Punkte, K 7,8 %, O 14,0 %, 6,55 leere Stunden, Einbruch −9,8 Punkte in beiden).
13. **Port 8997** am 2026-10-11 frei geprüft (TCP und `launch.json`); 8996 war inzwischen vergeben.
14. **Abdeckung unter Last.** Die Abdeckung lief mit 10 bis 12 parallelen Prozessen; O mit Schichten bekommt dann weniger Rechenzeit und fällt häufiger auf den bekannten Fund (K, G) zurück. Stichprobe: 12 Kombinationen (je Größe und Ziel eine, 60 Zeilen mit 1.200 Läufen) mit drei Prozessen neu gerechnet: alle vier Aussagen haben in allen 60 Zeilen dieselbe Ampel; die mittlere Abweichung der leeren Stunden von O liegt bei 0,03 Stunden, die des simulierten Einbruchs bei −0,3 Punkten (größte Abweichung einer Zeile: 2,2 Stunden bzw. −19 Punkte).

## Modell

- **Tag:** 24 Stundenintervalle, zyklisch. Last je Stunde in Erlang (a = Anrufrate mal Bediendauer), Anrufzahlen ganzzahlig (Last in 0,01 Erlang bei 240 s, danach
  mit der Bediendauer skaliert).
- **Servicegrad je Stunde:** stationär nach Erlang C, SL(n) = 1 − C(n, a) · exp(−(n − a) · s / AHT) für n > a, sonst 0; Servicezeit s = 20 s fest, Bediendauer
  exponentiell, unendliche Geduld, FIFO. **Tages-Servicegrad:** ankunftsgewichtet, Σ a_t · SL_t(n_t) / Σ a_t, Ziel 70 / 80 / 90 / 95 %.
- **Schichten:** zusammenhängend, Länge aus einem Katalog (nur 8 h; 6, 8, 10 h; 4, 6, 8 h; 3, 4, 5 h; 3 bis 12 h; 3, 4 h), Start in jeder Stunde, zyklisch über
  Mitternacht; Kosten gleich Länge in Personenstunden.
- **Z** (Messreihe: A): n_t ≥ c_t, c_t kleinste Besetzung mit SL_t ≥ Ziel; Schichten kostenminimal darüber. **K** (Az): einheitliches Stundenziel z ≤ Ziel, so weit
  abgesenkt (Raster 0,01, Untergrenze 0,30, Abbruch nach drei Fehlschlägen in Folge), wie der Tages-Servicegrad der kostenminimalen Überdeckung noch ≥ Ziel ist.
  **G** (BFz): gemeinsam, jede Stunde mindestens 50 %, Tages-Servicegrad mindestens der von K. **O** (B): gemeinsam, nur der Tages-Servicegrad ≥ Ziel, kein Mindestwert.
  **O ohne Schichtstruktur:** dieselbe Aufgabe, jedes Besetzungsmuster erlaubt (exakte Rucksack-Rechnung): die Untergrenze der Kosten von O. Nur vorgerechnet: Beq
  (gleiche gelieferte Qualität wie Z), BF (50 % je Stunde, Ziel), B1 (mindestens eine Person je Stunde).
- **Rückstau:** Ereignissimulation M_t/M/n_t, stündlich konstante Rate, zyklischer Plan, 3 Tage Einschwingzeit, Tage nach Anrufbudget (40.000 Anrufe je Plan, 5 bis
  40 Tage); jede Ankunft zählt, auch unbediente (sie gelten als nicht rechtzeitig); sinkt n_t, beenden laufende Anrufe ihre Bedienung.
- **Instanzen:** ganzzahliger Generator (SplitMix64, Zufalls-Seeds über `zlib.crc32`, nie `hash()`), fünf Profile (flach, zwei Spitzen, steile Morgenspitze,
  Nachtgrundlast, schmaler Gipfel), Spitzenlast klein 3 bis 6, mittel 8 bis 15, groß 25 bis 40 Erlang.

Die Formeln stehen im Expander „📐 Mathematische Formulierung“ der App.

## Methodik

| Stufe | Rechnung | Werkzeug | Zeit (dieses Gerät) |
|---|---|---|---|
| 1 | Z, K, G, O ohne Schichtstruktur | HiGHS über `scipy.optimize.milp` (Überdeckung, kontinuierliche Zuwachs-Variablen ab c_t(z)), Rucksack-DP (numpy) | Median je Einstellung 0,11 bis 0,30 s, Maximum 0,54 s |
| 2 | O mit Schichten | HiGHS mit unärer Binärkette, DP-Schnitt, Zeitlimit 5 s (8 s ab 20 Erlang Spitzenlast), Status „bewiesen“ oder „bestes Ergebnis“ | Median je Einstellung 0,10 bis 2,33 s, Maximum 8,1 s |
| 3 | Simulation der vier Pläne | Ereignissimulation, SplitMix64-Ströme | Median je Einstellung 0,35 bis 0,55 s, Maximum 1,13 s |
| vorgerechnet | 13 Zellen, 5.400 Instanzen; Abdeckung aller 216 Kombinationen | `tools/build_results.py`, `tools/sweep.py` | Messreihe 2.170 s (CP-SAT), Abdeckung rund 66 Minuten auf 10 bis 12 Prozessen (zwei Teilläufe) |

CP-SAT (OR-Tools) läuft nur als Orakel in den Tests (`requirements-dev.txt`), nie im Betrieb. Ist das Zeitlimit erreicht, zeigt die App „bestes Ergebnis nach t s“ mit der
bewiesenen Untergrenze; bekannte zulässige Funde (K, G, die billigste Überdeckung des DP-Musters) sind der Rückfall und werden nie unterschritten.

## Befunde (gemessen, keine Behauptungen)

Basiszelle der Vorab-Messreihe, wenn nichts anderes steht: fünf Profile, 8 bis 15 Erlang, Ziel 80 % in 20 s, Bediendauer 240 s, Schichten 6, 8, 10 h, 500
Instanzen (100 je Profil). Ersparnis gegenüber Z in Prozent der Personenstunden je Instanz gemittelt (± Standardfehler). Belege: `tests/test_claims.py`.

| Frage | Befund |
|---|---|
| Fallstrick 1: Was liefert Z? | Tages-Servicegrad 88,6 % statt 80 % (Spanne 81,8 bis 94,9 %) |
| Was holt K zurück? | 7,8 ± 0,2 % (14,0 Personenstunden von 207,6 im Mittel), liefert 81,5 %, z im Mittel 0,65 (Spanne 0,30 bis 0,79); das sind 57,6 % der Ersparnis von O. Beq (gleiche gelieferte Qualität wie Z) spart nur 1,4 ± 0,1 % (2,7 Personenstunden), 10,9 % der Ersparnis von O |
| Fallstrick 2: Was „spart“ O? | 13,0 ± 0,2 % (24,3 Personenstunden, das sind 11,7 % der mittleren 207,6), im Modell 80,5 %; im Mittel 5,8 von 24 Stunden bleiben leer |
| Wie viele Instanzen sind betroffen? | 98,8 % haben mindestens eine Stunde unter 50 % Servicegrad, 9,4 % der Anrufe liegen in solchen Stunden; B1 (mindestens eine Person): 90,2 % der Instanzen, 6,7 % der Anrufe, kleinster Stunden-Servicegrad im Mittel 0,11 (O: 0,01) |
| Fallstrick 3: Was bleibt in der Simulation? (100 Instanzen, 40 Tage) | Modell → Simulation: Z 88,6 → 88,8, K 81,6 → 82,0, BF 81,0 → 81,4, Beq 88,9 → 86,7, B1 80,6 → 75,7, O 80,5 → 69,9 %; O: -10,6 Punkte (± 0,6), je Profil -16,4 bis -1,8 |
| Wie oft hält die Simulation das Ziel? | Ziel (mindestens 79,5 %) gehalten: Z 100 %, K 98 %, BF 95 %, Beq 90 %, B1 38 %, O 10 % der Instanzen |
| Was bleibt an echter Kopplung? | G gegenüber K: 0,5 ± 0,1 % (0,8 Personenstunden), in 68,8 % der Instanzen exakt 0, höchstens 8 Personenstunden bzw. 5,5 %. Ohne Mindestwert (Bz): 3,8 % (7,0 Personenstunden), simuliert aber 73,2 statt 82,0 %; Ziel gehalten in 23 gegen 98 von 100 |
| Was spart BF ohne Kalibrierung? | 8,9 ± 0,2 % (16,2 Personenstunden) bei gehaltener Qualität (81,0 % Modell, 81,4 % simuliert) |
| Stresszelle (Katalog 3, 4 h, Ziel 95 %, 500 Instanzen) | O = B1 = BF (7,0 / 7,0 / 6,9 %): bei hohem Ziel gibt es nichts mehr aufzugeben; G gegenüber K 1,9 % (3,2 Personenstunden), bei schmalem Gipfel 4,0 % (5,0); BF bei schmalem Gipfel 12,5 % |
| Beweisstatus (Kosten, Basiszelle, ehrlich gezählt) | Z, K, BF in allen Zellen bewiesen optimal; O bewiesen in 88,6 % der Instanzen (4 ersetzte Einträge nicht mitgezählt), B1 87,4 %, Beq 96,0 %; Katalog nur 8 h: O 80,5 % (35 ersetzt), Bediendauer 480 s: 74,8 %, Größe groß: 75,2 % |
| Zweig-Test (Basiszelle) | Z ≠ K in 498, K ≠ Beq in 492, Beq ≠ BF in 500, BF ≠ B1 in 394, B1 ≠ O in 444, Z ≠ O in 500 von 500 Instanzen: keine Variante läuft ins Leere |
| Live gegen Messreihe (alle 5.400 Instanzen) | Alle 5.400 Instanzen mit den Live-Funktionen nachgerechnet (`tools/reproduce_messreihe.py`): Z gleich in 5.400 (Tages-Servicegrad bis auf die fünf gespeicherten Nachkommastellen in 5.400); K höchstens gleich in 5.397 (1.751 billiger als der Wert der Messreihe, in neun Zellen mit Raster 0,05), teurer in 3; G (gespeichert in 1.800 Instanzen) höchstens gleich in 1.800; Untergrenze ohne Schichtstruktur gleich in 5.364 (die übrigen 36 sind ersetzte Einträge, deren gespeicherte Schranke der engeren Variante gehört); O mit Schichten gleich in 5.046, besser in 55 (dort ist die Messreihe nicht bewiesen), schlechter in 299, davon um mehr als 2 Personenstunden in 189 (Lauf mit 14 parallelen Prozessen und fremder Last, 911 s: das Zeitlimit trifft dann weniger Rechenzeit). Bau-Gate des Plans, Anteil der Läufe mit O um mehr als 2 Personenstunden schlechter als der Bestwert (`tools/o_quality.py`, drei Prozesse, jede vierte Instanz, 100 je Zelle): Basis 0,0 % (0 von 125), Ziel 70 % 0,0 % (0 von 100), Bediendauer 480 s 6,0 % (6 von 100), Größe groß 2,0 % (2 von 100). O wurde nie als „bewiesen“ gemeldet und war dann falsch. |
| Abdeckung aller 216 Kombinationen (20 Instanzen je Profil) | 216 Kombinationen mal 5 Profile = 1.080 Zeilen, je 20 Instanzen (Zufalls-Seeds 0 bis 19), 21.600 Läufe der Live-Pipeline (`tools/sweep.py`). Von 1.080 Zeilen: Übererfüllung gilt 1.068, unklar 12, gilt nicht 0; leere Stunden von O gilt 648, unklar 46, gilt nicht 386; Einbruch in der Simulation gilt 539, unklar 119, gilt nicht 422; echte Kopplung gilt 579, unklar 39, gilt nicht 462. Je Tagesziel gelten die leeren Stunden in 261 von 270 Zeilen bei 70 %, 256 bei 80 %, 109 bei 90 % und 22 bei 95 %; der Einbruch in 255, 212, 71 und 1. Schwellen: Übererfüllung über Ziel + 1 Punkt, leere Stunden im Mittel mindestens 1, Einbruch um mehr als 3 Punkte und mehr als 2 Standardfehler, Kopplung mindestens 1 Personenstunde („gilt nicht“: Übererfüllung unter Ziel + 0,5 Punkte, leere Stunden im Mittel unter 0,5, Einbruch um höchstens 1 Punkt, Kopplung unter 0,5 Personenstunden; dazwischen „unklar“) |

Alle 13 Zellen der Messreihe (alle Profile gemittelt; Ersparnis gegenüber Z in Prozent der Personenstunden, „n“ = Instanzen der Zelle). K steht im z-Raster 0,01 wie live; in den Zellen mit Stern rechnete die Messreihe selbst mit dem Raster 0,05, die letzte Spalte zeigt dort ihren (niedrigeren) Wert.

| Zelle | n | Z liefert (%) | O | BF | K | Beq | O bewiesen (%) | K in der Messreihe |
|---|---|---|---|---|---|---|---|---|
| Ziel 70 %* | 400 | 81,6 | 18,5 | 7,6 | 7,6 | 3,9 | 88,0 | 6,9 |
| Basis (Ziel 80 %) | 500 | 88,6 | 13,0 | 8,9 | 7,8 | 1,4 | 88,6 | - |
| Ziel 90 % | 400 | 94,2 | 7,8 | 7,5 | 5,9 | 0,7 | 100,0 | - |
| Ziel 95 % | 400 | 97,2 | 6,8 | 6,8 | 5,0 | 0,6 | 100,0 | - |
| Katalog nur 8 h* | 400 | 92,8 | 17,8 | 11,9 | 13,2 | 0,1 | 80,5 | 12,8 |
| Katalog 4/6/8 h* | 400 | 87,5 | 12,1 | 8,0 | 6,5 | 1,7 | 88,5 | 5,5 |
| Katalog 3/4/5 h* | 400 | 85,5 | 11,0 | 6,6 | 4,4 | 3,3 | 99,8 | 3,3 |
| Katalog 3 bis 12 h* | 400 | 85,5 | 11,0 | 6,6 | 4,4 | 3,3 | 99,8 | 3,3 |
| Bediendauer 120 s* | 400 | 88,7 | 14,0 | 10,4 | 8,7 | 1,4 | 100,0 | 7,5 |
| Bediendauer 480 s* | 400 | 87,6 | 11,4 | 6,1 | 5,2 | 1,9 | 74,8 | 4,6 |
| Größe klein* | 400 | 88,5 | 13,9 | 11,7 | 9,8 | 1,1 | 99,2 | 8,2 |
| Größe groß* | 400 | 88,0 | 12,3 | 5,3 | 4,6 | 2,4 | 75,2 | 4,1 |
| Stresszelle (Katalog 3/4 h, Ziel 95 %) | 500 | 96,7 | 7,0 | 6,9 | 3,6 | 1,6 | 100,0 | - |

## Presets

Fünf Presets, alle auf gemessenen Zellen der Messreihe; Zufalls-Seed 2 (die typischste Instanz des Profils Zwei Spitzen: kleinster standardisierter Abstand zu den Mitteln der 20 simulierten Instanzen, `tools/seed_search.py`, nicht nach Ergebnis ausgewählt). Die Abnahmekriterien gelten für die Mittel der Messreihe (100 Instanzen des Profils, Simulation 20) und für die gezeigte Instanz; kein Kriterium nutzt O mit Schichten (Zeitlimit). `tests/test_stories.py` prüft jedes Kriterium an seiner Schwelle.

| Preset | Einstellung | Abnahmekriterien |
|---|---|---|
| Standard | Zwei Spitzen, mittel, Ziel 80 %, 240 s, 6, 8, 10 h, Zufalls-Seed 2 | Z liefert mindestens 5 Punkte über dem Ziel; K spart mindestens 4 %; O lässt mindestens 3 Stunden leer; O liegt simuliert mindestens 5 Punkte unter dem Modell; G spart höchstens 2 % gegenüber K |
| Flache Last | Flach, mittel, Ziel 80 %, 240 s, 6, 8, 10 h, Zufalls-Seed 2 | O spart höchstens 8 %; K spart höchstens 5 %; O lässt höchstens 3 Stunden leer; O liegt simuliert mindestens 10 Punkte unter dem Modell |
| Schmaler Gipfel | Schmaler Gipfel, mittel, Ziel 80 %, 240 s, 6, 8, 10 h, Zufalls-Seed 2 | O spart mindestens 15 %; O liegt simuliert höchstens 5 Punkte unter dem Modell; G spart höchstens 1 % gegenüber K |
| Hohes Ziel | Zwei Spitzen, mittel, Ziel 95 %, 240 s, 6, 8, 10 h, Zufalls-Seed 2 | O spart höchstens 0,5 Punkte mehr als BF; O lässt im Mittel höchstens 0,5 Stunden leer; K spart mindestens 3 %; Z liefert mindestens 96 % |
| Nur 8-Stunden-Schichten | Zwei Spitzen, mittel, Ziel 80 %, 240 s, nur 8 h, Zufalls-Seed 2 | K spart mindestens 10 %; Beq spart höchstens 1 %; Z liefert mindestens 90 % |

## Ehrliche Grenzen

- **Stationäre Näherung je Stunde** ist das Modell der Planung; die Simulation prüft nur die Folgen und optimiert nicht darauf. n ≤ a wird mit Servicegrad 0 gerechnet:
  für eine Stunde knapp unter Last pessimistisch, für die Folgestunden ohne Rückstau optimistisch; der Nettoeffekt steht in der Simulation. Eine simulationsbasierte
  gemeinsame Planung würde O vermutlich verbessern; sie ist nicht gemessen.
- **Annahmen:** unendliche Geduld, exponentielle Bedienzeit, keine Abwanderung, kein Wiederanruf, keine Pausen, kein Wochenmuster, keine Ruhezeiten, keine
  Schichtfixkosten, Kosten gleich Länge, ein zyklischer Tag, bekannte Prognose. **Alle Instanzen sind erfunden**, nicht an echten Daten kalibriert; Spitzenlast 3 bis 40 Erlang.
- **Der Mindestwert 50 % ist eine einzige Wahl**; 30 und 70 % wurden nicht gemessen.
- **Die Kosten von O sind teils obere Schranken.** In der Messreihe sind sie nicht überall bewiesen (Basis 88,6 %, Katalog nur 8 h 80,5 %, Bediendauer 480 s
  74,8 %, Größe groß 75,2 %); wo der Löser im Zeitlimit etwas Schlechteres fand als die bekannte Lösung einer engeren Variante, gilt „bestbekannt“ und der Eintrag
  zählt nicht als bewiesen. O ist damit eher zu teuer als zu billig angegeben, die Aussagen (große Scheinersparnis, die in der Simulation zerfällt) werden stärker, nicht schwächer.
  Live gibt es ein Zeitlimit statt eines Beweises; die App nennt Status und Untergrenze.
- **K in neun der 13 Zellen:** die Messreihe rechnete dort mit dem groben z-Raster 0,05 (ihre Ersparnis von K ist eine Untergrenze); App und README zeigen K im Raster 0,01, mit der Live-Rechnung auf diesen Instanzen nachgerechnet (`kfine` in `data/sgt_results.json`). Die Abbruchregel (drei Fehlschläge in Folge) lässt das z der Messreihe in einzelnen Instanzen aus (siehe Korrekturen, Punkt 4).
- **Die Simulation steht in der Messreihe nur in der Basiszelle** (100 Instanzen, 20 je Profil, 40 Tage); live ist eine Instanz ein Zufallsfall von 100 und trägt ± 2 Standardfehler;
  die Abdeckung simuliert 20 Instanzen je Profil und Kombination (Richtwerte, kein Beweis).
- **Aussagen außerhalb der 13 Zellen sind bedingt:** Fallstrick 1 gilt in allen Kombinationen, die Fallstricke 2 und 3 nicht (siehe Abdeckung). Die Konkavität des Servicegrads ab
  c_t(z) ist gemessen, kein Beweis; zur Laufzeit wird sie je Stunde geprüft und sonst die binäre Fassung benutzt.
- **Rechenzeiten gelten für dieses Gerät** (16 Kerne, Python 3.14, SciPy 1.18); auf Streamlit Cloud erschien das Ergebnis im Browser grob nach 15 bis 25 s nach dem Aufruf (Standardfall und der ungünstigste
  Fall, Größe groß mit 480 s; Beobachtung am 2026-10-11, mit Seitenaufbau, keine saubere Messung). HiGHS-Aktualisierungen
  ändern Gleichstände und Zeiten, nie die Kosten bewiesener Optima.

## Verwandte Demos mit demselben mathematischen Modell

Das Kernmodell ist die zyklische Intervallüberdeckung mit einer nichtkonkaven Güte-Nebenbedingung aus Erlang C (Mehrfachauswahl-Rucksack über die Besetzungen). Neu ist
nicht Erlang C und nicht die Überdeckung, sondern ihre Kopplung, die Nichtkonkavität (unterhalb des Angebots ist der Servicegrad 0, danach steil), die das Tauschen
von Servicegrad zwischen Stunden erst möglich und gefährlich macht, und der Preis der Trennung in Personenstunden.

| Demo | Bezug |
|---|---|
| [shift_demo](https://sebastianhanisch-shift-demo.streamlit.app/) | Überdeckung eines gegebenen Bedarfs; hier ist der Bedarf das Ergebnis einer Warteschlangenrechnung und die Überdeckung Mittel, nicht Gegenstand |
| [square-root-staffing-demo](https://sebastianhanisch-square-root-staffing-demo.streamlit.app/) | Spurzahl für ein Ziel bei konstanter Last; hier je Stunde, mit Schichtstruktur und Kosten |
| [time-varying-arrivals-demo](https://sebastianhanisch-time-varying-arrivals-demo.streamlit.app/) | dort rundet ein Planungsraster auf, hier tun es die Schichtlängen, und das Tagesziel kann die Rundung verstecken |
| [mmc-queue-demo](https://sebastianhanisch-mmc-queue-demo.streamlit.app/), [erlang-a-demo](https://sebastianhanisch-erlang-a-demo.streamlit.app/) | Erlang C bzw. Abwanderung bei konstanter Rate |
| [crew-pairing-demo](https://sebastianhanisch-crew-pairing-demo.streamlit.app/) | Dienste decken Bedarf mit Regelwerk (Spaltengenerierung), kein Servicegrad |

Jede Idee „Besetzung mit Schichten und Servicegrad-Ziel“ (Kontaktcenter, Notruf, Check-in, Gate) ist dasselbe Modell; „Tagesziel statt Stundenziel“ ist der Fallstrick.

## Literatur

Bhulai, Koole und Pot (2008), *Simple Methods for Shift Scheduling in Multiskill Call Centers*, Manufacturing & Service Operations Management 10(3), 411 bis 420:
zweistufiges Vorgehen (erst Besetzung je Periode, dann Schichten per LP). Avramidis, Chan, Gendreau, L'Ecuyer und Pisacane (2010), *Optimizing daily agent scheduling in a
multiskill call center*, European Journal of Operational Research 200(3), 822 bis 832: Servicegrad je Anruftyp und Periode sowie aggregiert; das übliche zweistufige
Vorgehen kann weit vom Optimum liegen. Beide per Suche bestätigt (Treffer 2026-10-10), Volltexte nicht gelesen.

## Tests

194 Tests, Laufzeit rund 2 Minuten (126 s) auf diesem Gerät (Windows, Python 3.14). Zusammensetzung: Mini-Instanzen je Einheit von Hand (Erlang C, c_t(z), Rucksack-Rechnung, jede Nebenbedingungsfamilie des HiGHS-Modells einzeln, z-Suche, Simulation je Handler); Orakel (Erlang C gegen Brüche und Markow-Kette, Schichtüberdeckung und Rucksack gegen Vollaufzählung, HiGHS gegen CP-SAT mit festem Zufalls-Seed und einem Suchprozess, Simulation gegen Erlang C und Rückstau-Rechnung); Bitgleichheit der Simulation mit der Messreihe; Selbst-Reproduktion einer Stichprobe der Messreihe; Claims-Tests, die jede Zahl dieses READMEs an `data/*.json` binden; Preset-Kriterien an der Messreihe und an der gezeigten Instanz mit künstlichen Schwellen; AppTest (jedes Preset, jeder Regler an seinen Grenzen, Permalink inklusive unbekannter Werte, Exakt-Tab, PDF), Smoke-Test der Vorlage und Footer-Test. Mutationsprüfung `tools/mutation_check.py`: 85 eingebaute Fehler in den Rechenmodulen (Rundung, Vorzeichen, Schranken, Zählung, Nebenbedingungen, z-Suche, Simulation, Meldungen), 83 von den Tests gefunden, 2 begründet gleichwertig (n = a ist doppelt festgelegt; der Auslauftag liegt hinter dem Zählfenster). CI-robust: keine Zeitverhältnisse, Löser mit Zeitlimit nur gegen Schranken, Simulation nur gegen Bänder oder auf festen Zufalls-Seeds.

## Dateistruktur

| Datei | Zweck |
|---|---|
| `app.py` | Streamlit-App: Presets, Sidebar, drei Stufen, vier Abschnitte, Messreihe, Expander |
| `sgt_constants.py` | Regler-Stufen, Kataloge, Profile, Mindestwert, z-Raster, Zeitlimits, Farben, Variantentabelle |
| `sgt_rng.py` | SplitMix64 und Zufalls-Seeds (`zlib.crc32`) |
| `sgt_instance.py` | Lastprofile, Instanzgenerator, Skalierung mit der Bediendauer |
| `sgt_erlang.py` | Erlang C, Servicegrad-Tabellen, c_t(z), Tages-Servicegrad, Kennzahlen |
| `sgt_dp.py` | Rucksack-Rechnung ohne Schichtstruktur (exakt) |
| `sgt_cover.py` | Schichtüberdeckung als HiGHS-Modell (Nebenbedingungsfamilien, Stufe 1 und 2, Status) |
| `sgt_plans.py` | Z, K (z-Suche), G, O mit Schichten, O ohne Schichtstruktur |
| `sgt_sim.py` | Ereignissimulation mit Zählung je Tag, Standardfehler, Tageszahl nach Anrufbudget |
| `sgt_pipeline.py` | Drei Stufen der Live-Rechnung, `Settings` (immer mit Schlüsselwörtern) |
| `sgt_results.py` | Laden und Auswerten von `data/sgt_results.json` und `data/sgt_coverage.json` |
| `sgt_evaluation.py` | Kennzahlen, Meldungen in drei Zuständen, erzeugte Sätze, Einordnung gegen die Messreihe |
| `sgt_visualization.py` | Plotly-Abbildungen (Achsen gesperrt, Treppen) |
| `sgt_presets.py`, `sgt_stories.py` | Permalink, Zufalls-Seed-Knopf; Presets, Geschichten, Abnahmekriterien |
| `sgt_pdf_export.py` | Auswertung als PDF (fpdf2) |
| `data/sgt_results.json` | 13 Zellen, 5.400 Instanzen, verdichtet aus der Vorab-Messreihe (ersetzte Einträge gekennzeichnet) |
| `data/sgt_coverage.json` | Abdeckung: 216 Kombinationen mal 5 Profile mal 20 Instanzen, Mittel und Standardfehler der vier Aussagen |
| `tools/build_results.py` | erzeugt `sgt_results.json` aus `sweep_data.json` |
| `tools/sweep.py` | Abdeckung (parallel, fortsetzbar) und Aggregation |
| `tools/reproduce_messreihe.py` | Selbst-Reproduktion: Live-Funktionen gegen die gespeicherten 5.400 Instanzen |
| `tools/live_timing.py`, `tools/se_check.py` | Zeitmessung je Stufe; Standardfehler-Schätzer gegen die Streuung über Zufalls-Seeds |
| `tools/o_quality.py` | Qualität von O mit Schichten gegen den Bestwert der Messreihe je Zelle (Bau-Gate), mit wählbarem Zeitlimit |
| `tools/seed_search.py` | typischste Instanz je Preset (Standard-Zufalls-Seed) |
| `tools/mutation_check.py` | Fehler-Einbau-Test über die Rechenmodule |
| `tests/` | Mini-Instanzen, Orakel (Brüche, Markow-Kette, Vollaufzählung, CP-SAT in `oracle_cpsat.py`), Claims, Presets, Reproduktion, AppTest, Footer |
| `requirements.txt`, `requirements-dev.txt` | Laufzeit (Streamlit, Plotly, NumPy, SciPy, pandas, fpdf2); zusätzlich pytest und OR-Tools (nur Orakel) |
| `.github/workflows/tests.yml` | CI: Push, Pull Request, wöchentlicher Canary |

## Bewusst nicht umgesetzt

Mehrere Qualifikationen und Anruftypen (Multiskill; als Tagesbilanz ohne Warteschlange und ohne Stundenlage zeigt die Verteilung der
Zusatzqualifikationen `kreuzschulung-demo`, Skill-based Routing mit Warteschlange bleibt offen), Abwanderung und Wiederanruf (Erlang A), nichtexponentielle Bedienzeiten, eine simulationsbasierte Planung
(sie würde O vermutlich verbessern; nicht gemessen), Pausen und Ruhezeiten, Wochenmuster (das ist der Wochen-Abschnitt in `shift_demo`), Schichtfixkosten,
Prognosefehler, Mindestwerte 30 und 70 % (nur 50 % ist gemessen), Kalibrierung an echten Daten und Personen statt Besetzung (Dienstplanung).

## Lokal ausführen

```bash
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate

pip install -r requirements.txt
streamlit run app.py
```

## Tests ausführen

```bash
pip install -r requirements-dev.txt
pytest tests/ -v
```

Gebaut mit Streamlit, Plotly, NumPy, SciPy (HiGHS) und fpdf2.

---

Diese Demo ist Teil des Portfolios von [Sebastian Hanisch](https://sebastianhanisch.net) – Operations Research und Machine Learning ([Über mich](https://sebastianhanisch.net/ueber-mich.html)). Mehr zum Thema: [Schichtplanung optimieren](https://sebastianhanisch.net/schichtplanung-optimierung.html).
