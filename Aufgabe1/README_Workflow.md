# Aufgabe 1 Workflow

Dieses Verzeichnis enthaelt die reproduzierbaren Python-, Fluent- und
ANSYS/MAPDL-Schritte fuer Aufgabe 1. Der Bericht
`report/bericht_aufgabe1.tex` ist die Quelle der Wahrheit: Die dort
referenzierten Tabellen und Bilder liegen in `Aufgabe1/data/` und
`Aufgabe1/figures/`.

Die Skripte liegen in `Aufgabe1/code/`. Ein vollstaendiger Neulauf erzeugt
wieder ein Arbeitsverzeichnis `Aufgabe1/out/`; daraus werden nur die fuer den
Bericht benoetigten Daten und Bilder nach `data/` und `figures/` uebernommen.

## Schnellstart

```powershell
cd C:\Users\Moritz\Desktop\FEM
.\.venv\Scripts\python.exe Aufgabe1\code\run_cfd.py
.\.venv\Scripts\python.exe Aufgabe1\code\run_plate.py
.\.venv\Scripts\python.exe Aufgabe1\code\run_truss.py
.\.venv\Scripts\python.exe Aufgabe1\code\run_python_fem.py
.\.venv\Scripts\python.exe Aufgabe1\code\make_report_figures.py
```

`run_cfd.py`, `run_plate.py` und `run_truss.py` erzeugen Eingaben bzw.
steuern Schritte, die Fluent oder MAPDL benoetigen. Die externen Solverlaeufe
muessen je nach Lizenz/Installation lokal ausgefuehrt werden.

## 1.1 CFD

Projekt 27 ist in `run_cfd.py` gesetzt. Das Skript erzeugt zuerst das Gmsh-
Netz und enthaelt die vorbereiteten Aufrufe fuer Fluent-Loesung und
Nachbearbeitung:

```powershell
.\.venv\Scripts\python.exe Aufgabe1\code\run_cfd.py
```

Wichtige Berichtsdaten:

- `Aufgabe1/data/drag_summary.txt`
- `Aufgabe1/data/wall_pressure.csv`
- `Aufgabe1/figures/mesh_overview_report.png`
- `Aufgabe1/figures/contour_velocity_report.png`
- `Aufgabe1/figures/pressure_distribution.png`
- `Aufgabe1/figures/drag_convergence.png`

Die Ausgangswerte im Bericht sind:

- `F_D = 6430.05 N`
- `F'_D = 2143.3515 N/m`
- `c_D = 1.874`

## 1.2a Aluminiumtafel

Das Berichtmodell fuer die konstruktive Bewertung ist die durchgehende
Linienstuetze ueber die Tafelhoehe:

```powershell
.\.venv\Scripts\python.exe Aufgabe1\code\run_plate.py
```

Das erzeugt unter `Aufgabe1/out/` die MAPDL-Dateien
`plate_structural.inp`, `plate_post_probe.inp` und
`plate_export_plots.inp`. Nach dem MAPDL-Lauf wertet der Parser die
Ergebnisse aus:

```powershell
.\.venv\Scripts\python.exe Aufgabe1\code\parse_plate_structural_results.py --results Aufgabe1\out\plate_structural_results.txt --post-output Aufgabe1\out\plate_post_probe.out --apdl Aufgabe1\out\plate_structural.inp --out-dir Aufgabe1\out
```

Die im Bericht verwendeten kuratierten Bilder der Linienstuetze liegen hier:

- `Aufgabe1/data/plate_line_support_full_height/plate_spannung_eqv_ansys.png`
- `Aufgabe1/data/plate_line_support_full_height/plate_verformung_ansys.png`

## Singularitaetsnachweis

Die Punktlager-Netzstudie ist Bestandteil des Berichts. Sie erzeugt APDL-
Faelle fuer lokale Netzgroessen `10 mm`, `2 mm` und `1 mm`:

```powershell
.\.venv\Scripts\python.exe Aufgabe1\code\run_plate_singularity_study.py
```

Mit MAPDL-Solverlauf:

```powershell
.\.venv\Scripts\python.exe Aufgabe1\code\run_plate_singularity_study.py --solve --ansys-exe 'C:\Program Files\ANSYS Inc\ANSYS Student\v261\ansys\bin\winx64\ANSYS261.exe'
```

Die Berichtstabellen und -bilder werden daraus aktualisiert:

- `Aufgabe1/data/plate_singularity_study.csv`
- `Aufgabe1/data/plate_singularity_study_table.tex`
- `Aufgabe1/figures/plate_singularity_mesh_panel.png`
- `Aufgabe1/figures/plate_singularity_stress_panel.png`

## 1.2b-d Fachwerk in ANSYS/MAPDL

Das ANSYS-Fachwerkmodell wird mit LINK180-Staeben erzeugt:

```powershell
.\.venv\Scripts\python.exe Aufgabe1\code\run_truss.py
```

Nach dem MAPDL-Lauf wird der elementweise ANSYS/Python-Vergleich erzeugt:

```powershell
.\.venv\Scripts\python.exe Aufgabe1\code\parse_truss_apdl_results.py --out-dir Aufgabe1\out --apdl-output Aufgabe1\out\truss_structural_solver.out --index-table Aufgabe1\out\truss_index_table.csv --python-forces Aufgabe1\out\truss_element_forces.csv
```

## 1.2e-h Eigene Python-FEM

Die Python-Fachwerkrechnung verwendet die im Bericht angegebenen
Gelenkkraefte des massgebenden Traegers H3:

```powershell
.\.venv\Scripts\python.exe Aufgabe1\code\run_python_fem.py
```

Wichtige Berichtsdaten:

- `Aufgabe1/data/truss_comparison_python_ansys.csv`
- `Aufgabe1/data/truss_comparison_report_table.tex`
- `Aufgabe1/figures/truss_deformed.png`
- `Aufgabe1/figures/truss_ansys_force_plot.png`
- `Aufgabe1/figures/truss_python_ansys_comparison.png`

## Berichtsfiguren und PDF

Alle reportrelevanten PNGs werden gesammelt erzeugt:

```powershell
.\.venv\Scripts\python.exe Aufgabe1\code\make_report_figures.py
```

Anschliessend den Bericht aus dem Verzeichnis `report/` kompilieren:

```powershell
cd report
pdflatex bericht_aufgabe1.tex
```
