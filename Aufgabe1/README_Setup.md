# Aufgabe 1 Setup

Dieses Dokument beschreibt die lokale Python-/PyFluent-Umgebung fuer die
Skripte in `Aufgabe1/code/`. Fuer die abzugebenden Zahlen, Tabellen und
Bilder gilt der Bericht `report/bericht_aufgabe1.tex` als Quelle der
Wahrheit.

## Geometrieinterpretation

Fuer den CFD-Teil wird nur die Aluminiumtafel modelliert:

- 2D-Seitenansicht: Plattenhoehe `hT + 1.0 m = 2.0 m`
- Plattendicke `t = 0.003 m`
- Wind normal zur Platte
- Schildbreite aus der Vorderansicht: `3.0 m`

Fluent liefert in der 2D-Rechnung eine Kraft pro Tiefe. Die Gesamtkraft ist:

```text
F_total = F_2D_per_depth * 3.0
cD = F_total / (0.5 * rho * U^2 * 3.0 * (hT + 1.0))
```

## Python-Umgebung

Vom Projektroot aus:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r Aufgabe1\requirements.txt
```

Falls PowerShell `Activate.ps1` blockiert:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

Alternativ ohne Aktivierung:

```powershell
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r Aufgabe1\requirements.txt
```

## ANSYS/PyFluent

PyFluent muss die lokale Fluent-Installation finden. Relevante
Umgebungsvariablen sind zum Beispiel:

```powershell
Get-ChildItem "C:\Program Files\ANSYS Inc" -ErrorAction SilentlyContinue
Get-ChildItem Env:AWP_ROOT*
```

Fuer Ansys Student 2026 R1:

```powershell
$env:AWP_ROOT261 = "C:\Program Files\ANSYS Inc\ANSYS Student\v261"
```

Dauerhaft fuer den Windows-Benutzer:

```powershell
[Environment]::SetEnvironmentVariable("AWP_ROOT261", "C:\Program Files\ANSYS Inc\ANSYS Student\v261", "User")
```

## Baselinewerte Projekt 27

- `b = 45 cm = 0.45 m`
- `h = 25 cm = 0.25 m`
- `hT = 100 cm = 1.00 m`
- CFD-Plattenhoehe `hT + 1.0 m = 2.00 m`
- `cwind = 110 km/h = 30.56 m/s`
- `q = 571.86 Pa`

Diese Werte werden in `Aufgabe1/code/aufgabe1_params.py` berechnet und in den
Entry-Point-Skripten fuer Projekt 27 verwendet.

## CFD-Route

Der primaere Einstieg ist:

```powershell
.\.venv\Scripts\python.exe Aufgabe1\code\run_cfd.py
```

Das Skript erzeugt das Gmsh-Netz und enthaelt die vorbereiteten Fluent- und
Postprocessing-Schritte. Fuer einen manuellen Solverlauf koennen die
Einzelskripte direkt aufgerufen werden:

```powershell
.\.venv\Scripts\python.exe Aufgabe1\code\generate_plate_mesh.py --output Aufgabe1\data\plate_2d_gmsh.msh --no-boundary-layer
.\.venv\Scripts\python.exe Aufgabe1\code\solve_plate_2d_template.py --mesh Aufgabe1\data\plate_2d_gmsh.msh --output Aufgabe1\out\plate_2d_solution.cas.h5 --drag-file Aufgabe1\data\drag_plate.out --summary Aufgabe1\data\drag_summary.txt --iterations 500
.\.venv\Scripts\python.exe Aufgabe1\code\postprocess_solution.py --case Aufgabe1\out\plate_2d_solution.cas.h5 --data-dir Aufgabe1\data
```

## Berichtseinstellungen

Im Bericht dokumentierte CFD-Einstellungen:

- Domain: `x = -10 m` bis `x = 30 m`, `y = -10 m` bis `y = +10 m`
- Platte zentriert bei `x = 0`, `y = 0`
- Einlass `v = 30.56 m/s`
- Auslass `p = 0 Pa` relativ
- oben/unten Symmetrie
- Schild als No-Slip-Wand
- stationaere SIMPLE-Rechnung mit SST-k-omega
- 500 Iterationen fuer die berichteten Ergebnisse
