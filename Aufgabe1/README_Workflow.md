# Aufgabe 1 Workflow

Dieses Verzeichnis enthaelt die reproduzierbaren Python-, Fluent- und ANSYS/MAPDL-Schritte fuer Aufgabe 1.

> Hinweis zur Ordnerstruktur (nach dem Aufraeumen): Die Skripte liegen jetzt in
> `Aufgabe1/code/`, die kuratierten Eingangsdaten in `Aufgabe1/data/` und die
> fertigen Reportbilder in `Aufgabe1/figures/`. In den Kommandobeispielen unten
> ist den Skriptpfaden entsprechend `code\` voranzustellen
> (z. B. `Aufgabe1\code\generate_plate_mesh.py`). Ein vollstaendiger Neulauf
> erzeugt wieder ein Arbeitsverzeichnis `Aufgabe1\out\`. Alle Reportbilder lassen
> sich mit `python Aufgabe1\code\make_report_figures.py` neu erzeugen.

## Vorbereitung

PowerShell im Projektordner:

```powershell
cd C:\Users\Moritz\Desktop\FEM
.\.venv\Scripts\python.exe Aufgabe1\check_pyfluent_setup.py --launch
```

Wenn Fluent startet und `Health: Status.SERVING` ausgibt, ist PyFluent korrekt eingerichtet.

## 1.1 CFD

Baseline und Parameter pruefen:

```powershell
.\.venv\Scripts\python.exe Aufgabe1\aufgabe1_wind_baseline.py
```

Mesh erzeugen:

```powershell
.\.venv\Scripts\python.exe Aufgabe1\generate_plate_mesh.py
```

Mesh in Fluent pruefen:

```powershell
.\.venv\Scripts\python.exe Aufgabe1\probe_fluent_read_mesh.py Aufgabe1\out\plate_2d.msh
```

CFD loesen:

```powershell
.\.venv\Scripts\python.exe Aufgabe1\solve_plate_2d_template.py --mesh Aufgabe1\out\plate_2d.msh --iterations 500 --output Aufgabe1\out\plate_2d_solution.cas.h5 --summary Aufgabe1\out\drag_summary.txt
```

Postprocessing:

```powershell
.\.venv\Scripts\python.exe Aufgabe1\postprocess_solution.py
```

Wichtige Ergebnisse:

- `Aufgabe1/out/drag_summary.txt`
- `Aufgabe1/out/wall_pressure.csv`
- `Aufgabe1/out/mesh_overview.png`
- `Aufgabe1/out/mesh_plate_zoom.png`
- `Aufgabe1/out/contour_pressure.png`
- `Aufgabe1/out/contour_velocity.png`
- `Aufgabe1/out/pressure_distribution.png`
- `Aufgabe1/out/drag_convergence.png`

## 1.2 Aluminiumtafel in ANSYS/MAPDL

APDL-Modell erzeugen:

```powershell
.\.venv\Scripts\python.exe Aufgabe1\structural_plate_apdl.py
```

MAPDL loesen:

```powershell
& 'C:\Program Files\ANSYS Inc\ANSYS Student\v261\ansys\bin\winx64\ANSYS261.exe' -b -i 'C:\Users\Moritz\Desktop\FEM\Aufgabe1\out\plate_structural.inp' -o 'C:\Users\Moritz\Desktop\FEM\Aufgabe1\out\plate_structural_solver.out' -dir 'C:\Users\Moritz\Desktop\FEM\Aufgabe1\out' -j plate_1_2
```

Stress-/Verschiebungs-Postprocessing:

```powershell
& 'C:\Program Files\ANSYS Inc\ANSYS Student\v261\ansys\bin\winx64\ANSYS261.exe' -b -i 'C:\Users\Moritz\Desktop\FEM\Aufgabe1\plate_post_probe.inp' -o 'C:\Users\Moritz\Desktop\FEM\Aufgabe1\out\plate_post_probe.out' -dir 'C:\Users\Moritz\Desktop\FEM\Aufgabe1\out' -j plate_post_probe
.\.venv\Scripts\python.exe Aufgabe1\parse_plate_structural_results.py
```

Bilder exportieren:

```powershell
& 'C:\Program Files\ANSYS Inc\ANSYS Student\v261\ansys\bin\winx64\ANSYS261.exe' -b -i 'C:\Users\Moritz\Desktop\FEM\Aufgabe1\plate_export_plots.inp' -o 'C:\Users\Moritz\Desktop\FEM\Aufgabe1\out\plate_export_plots.out' -dir 'C:\Users\Moritz\Desktop\FEM\Aufgabe1\out' -j plate_export
```

Die exportierten Dateien `plate_export000.png`, `plate_export001.png`, `plate_export002.png` wurden als klare Reportdateien abgelegt:

- `Aufgabe1/out/plate_mesh_ansys.png`
- `Aufgabe1/out/plate_stress_eqv_ansys.png`
- `Aufgabe1/out/plate_deformation_ansys.png`
- `Aufgabe1/out/plate_connection_points.png`

### Zusatzrechnung: Flaechenlager der Aluminiumtafel

Die aktuelle Variante mit kreisfoermigen Flaechenlagern verwendet sechs
Kreisflaechen mit `100 mm` Durchmesser an den Anschlussstellen. Die lokale
Teilung im Kreisbereich ist `10 mm`; damit werden pro Lagerkreis 81 Knoten in
Normalrichtung fixiert. Die Dateien liegen in
`Aufgabe1/out/plate_circle_flaechenlager_d100`:

```powershell
.\.venv\Scripts\python.exe Aufgabe1\structural_plate_apdl.py --support-mode circle-flaechenlager --support-patch-mm 100 --support-refinement-mm 10 --out-dir Aufgabe1\out\plate_circle_flaechenlager_d100 --job-name plate_circle_flaechenlager_d100
```

MAPDL loesen:

```powershell
& 'C:\Program Files\ANSYS Inc\ANSYS Student\v261\ansys\bin\winx64\ANSYS261.exe' -b -i 'C:\Users\Moritz\Desktop\FEM\Aufgabe1\out\plate_circle_flaechenlager_d100\plate_structural.inp' -o 'C:\Users\Moritz\Desktop\FEM\Aufgabe1\out\plate_circle_flaechenlager_d100\plate_structural_solver.out' -dir 'C:\Users\Moritz\Desktop\FEM\Aufgabe1\out\plate_circle_flaechenlager_d100' -j plate_circle_flaechenlager_d100
```

Stress-/Verschiebungs-Postprocessing:

```powershell
& 'C:\Program Files\ANSYS Inc\ANSYS Student\v261\ansys\bin\winx64\ANSYS261.exe' -b -i 'C:\Users\Moritz\Desktop\FEM\Aufgabe1\out\plate_circle_flaechenlager_d100\plate_post_probe.inp' -o 'C:\Users\Moritz\Desktop\FEM\Aufgabe1\out\plate_circle_flaechenlager_d100\plate_post_probe.out' -dir 'C:\Users\Moritz\Desktop\FEM\Aufgabe1\out\plate_circle_flaechenlager_d100' -j plate_circle_flaechenlager_d100_post
.\.venv\Scripts\python.exe Aufgabe1\parse_plate_structural_results.py --results Aufgabe1\out\plate_circle_flaechenlager_d100\plate_structural_results.txt --post-output Aufgabe1\out\plate_circle_flaechenlager_d100\plate_post_probe.out --out-dir Aufgabe1\out\plate_circle_flaechenlager_d100
```

Bilder exportieren:

```powershell
& 'C:\Program Files\ANSYS Inc\ANSYS Student\v261\ansys\bin\winx64\ANSYS261.exe' -b -i 'C:\Users\Moritz\Desktop\FEM\Aufgabe1\out\plate_circle_flaechenlager_d100\plate_export_plots.inp' -o 'C:\Users\Moritz\Desktop\FEM\Aufgabe1\out\plate_circle_flaechenlager_d100\plate_export_plots.out' -dir 'C:\Users\Moritz\Desktop\FEM\Aufgabe1\out\plate_circle_flaechenlager_d100' -j plate_circle_flaechenlager_d100_export
```

Eine Variante mit drei vertikalen `50 mm` breiten Linienstuetzen von
`y = 750 mm` bis zur Tafeloberkante liegt in
`Aufgabe1/out/plate_line_support_top`:

```powershell
.\.venv\Scripts\python.exe Aufgabe1\structural_plate_apdl.py --support-mode line-support-top --support-refinement-mm 25 --out-dir Aufgabe1\out\plate_line_support_top --job-name plate_line_support_top
```

Die durchgehende Variante mit drei vertikalen `50 mm` breiten Linienstuetzen
von Unterkante bis Oberkante liegt in
`Aufgabe1/out/plate_line_support_full_height`:

```powershell
.\.venv\Scripts\python.exe Aufgabe1\structural_plate_apdl.py --support-mode line-support-full-height --support-refinement-mm 25 --out-dir Aufgabe1\out\plate_line_support_full_height --job-name plate_line_support_full_height
```

MAPDL loesen:

```powershell
& 'C:\Program Files\ANSYS Inc\ANSYS Student\v261\ansys\bin\winx64\ANSYS261.exe' -b -i 'C:\Users\Moritz\Desktop\FEM\Aufgabe1\out\plate_flaechenlager\plate_structural.inp' -o 'C:\Users\Moritz\Desktop\FEM\Aufgabe1\out\plate_flaechenlager\plate_structural_solver.out' -dir 'C:\Users\Moritz\Desktop\FEM\Aufgabe1\out\plate_flaechenlager' -j plate_flaechenlager
```

Stress-/Verschiebungs-Postprocessing:

```powershell
& 'C:\Program Files\ANSYS Inc\ANSYS Student\v261\ansys\bin\winx64\ANSYS261.exe' -b -i 'C:\Users\Moritz\Desktop\FEM\Aufgabe1\out\plate_flaechenlager\plate_post_probe.inp' -o 'C:\Users\Moritz\Desktop\FEM\Aufgabe1\out\plate_flaechenlager\plate_post_probe.out' -dir 'C:\Users\Moritz\Desktop\FEM\Aufgabe1\out\plate_flaechenlager' -j plate_flaechenlager_post
.\.venv\Scripts\python.exe Aufgabe1\parse_plate_structural_results.py --results Aufgabe1\out\plate_flaechenlager\plate_structural_results.txt --post-output Aufgabe1\out\plate_flaechenlager\plate_post_probe.out --out-dir Aufgabe1\out\plate_flaechenlager
```

Bilder exportieren:

```powershell
& 'C:\Program Files\ANSYS Inc\ANSYS Student\v261\ansys\bin\winx64\ANSYS261.exe' -b -i 'C:\Users\Moritz\Desktop\FEM\Aufgabe1\out\plate_flaechenlager\plate_export_plots.inp' -o 'C:\Users\Moritz\Desktop\FEM\Aufgabe1\out\plate_flaechenlager\plate_export_plots.out' -dir 'C:\Users\Moritz\Desktop\FEM\Aufgabe1\out\plate_flaechenlager' -j plate_flaechenlager_export
```

## 1.2 Fachwerk in Python und ANSYS/MAPDL

Python-Fachwerkrechnung mit den realen Gelenkkraeften des massgebenden Traegers:

```powershell
.\.venv\Scripts\python.exe Aufgabe1\structural_truss_1_2.py --upper-load-n 1604.90034026 --lower-load-n 540.83818341
```

ANSYS-Fachwerkmodell erzeugen:

```powershell
.\.venv\Scripts\python.exe Aufgabe1\structural_truss_apdl.py
```

ANSYS-Fachwerk loesen:

```powershell
& 'C:\Program Files\ANSYS Inc\ANSYS Student\v261\ansys\bin\winx64\ANSYS261.exe' -b -i 'C:\Users\Moritz\Desktop\FEM\Aufgabe1\out\truss_structural.inp' -o 'C:\Users\Moritz\Desktop\FEM\Aufgabe1\out\truss_structural_solver.out' -dir 'C:\Users\Moritz\Desktop\FEM\Aufgabe1\out' -j truss_1_2
```

Python/ANSYS-Vergleich erzeugen:

```powershell
.\.venv\Scripts\python.exe Aufgabe1\parse_truss_apdl_results.py
```

Wichtige Ergebnisse:

- `Aufgabe1/out/truss_summary.txt`
- `Aufgabe1/out/truss_index_table.csv`
- `Aufgabe1/out/truss_element_forces.csv`
- `Aufgabe1/out/truss_apdl_element_forces.csv`
- `Aufgabe1/out/truss_comparison_python_ansys.csv`
- `Aufgabe1/out/truss_comparison_summary.txt`
- `Aufgabe1/out/truss_deformed.png`

## Bericht

Der aktuelle deutsche Entwurf fuer Aufgabe 1 liegt hier:

```text
Aufgabe1/bericht_aufgabe1_entwurf.md
```

Der Entwurf deckt 1.1 a-f und 1.2 a-h ab. Fuer die finale Abgabe sollte er in das Gesamt-Dokument uebernommen und mit den Bildern aus `Aufgabe1/out` versehen werden.
