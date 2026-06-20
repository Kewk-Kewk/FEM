"""Aufgabe 1.1 — Hauptskript fuer die CFD-Rechnung.

Workflow:
  1. Netzgenerierung (generate_plate_mesh.py)
  2. Fluent-Loesung (solve_plate_2d_template.py) → benoetigt Fluent-Lizenz
  3. Nachbearbeitung (postprocess_solution.py) → benoetigt Fluent-Lizenz

Aufruf:
  python Aufgabe1/code/run_cfd.py

Alle Parameter fuer Projekt 27 werden hier gesetzt.
Achtung: Schritt 2 und 3 erfordern ANSYS Fluent mit gültiger Lizenz!
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Parameter fuer Projekt 27
# ---------------------------------------------------------------------------

# Verzeichnisse (relativ zum Repository-Root)
ROOT = Path(__file__).resolve().parents[2]
CODE_DIR = ROOT / "Aufgabe1" / "code"
DATA_DIR = ROOT / "Aufgabe1" / "data"
OUT_DIR = ROOT / "Aufgabe1" / "out"


def step_1_generate_mesh() -> None:
    """Erzeuge das 2D-Dreiecksnetz mit Gmsh."""
    print("=" * 60)
    print("Schritt 1: Netzerzeugung")
    print("=" * 60)
    subprocess.run(
        [
            sys.executable,
            str(CODE_DIR / "generate_plate_mesh.py"),
            "--output", str(DATA_DIR / "plate_2d_gmsh.msh"),
            "--no-boundary-layer",
        ],
        check=True,
    )
    print(f"Netz geschrieben: {DATA_DIR / 'plate_2d_gmsh.msh'}")


def step_2_solve_fluent() -> None:
    """Loese die 2D-Umstroemung in Fluent."""
    print("=" * 60)
    print("Schritt 2: Fluent-Loesung (benoetigt Lizenz!)")
    print("=" * 60)
    subprocess.run(
        [
            sys.executable,
            str(CODE_DIR / "solve_plate_2d_template.py"),
            "--mesh", str(DATA_DIR / "plate_2d_gmsh.msh"),
            "--output", str(OUT_DIR / "plate_2d_solution.cas.h5"),
            "--drag-file", str(DATA_DIR / "drag_plate.out"),
            "--summary", str(DATA_DIR / "drag_summary.txt"),
            "--iterations", "500",
        ],
        check=True,
    )


def step_3_postprocess() -> None:
    """Nachbearbeitung: Druck, Geschwindigkeit, Drag-Konvergenz."""
    print("=" * 60)
    print("Schritt 3: CFD-Nachbearbeitung (benoetigt Fluent-Lizenz!)")
    print("=" * 60)
    subprocess.run(
        [
            sys.executable,
            str(CODE_DIR / "postprocess_solution.py"),
            "--case", str(OUT_DIR / "plate_2d_solution.cas.h5"),
            "--data-dir", str(DATA_DIR),
        ],
        check=True,
    )


def main() -> None:
    print("Aufgabe 1.1: CFD-Rechnung fuer Projekt 27")
    print(f"  Windgeschwindigkeit: 110 km/h = 30.56 m/s")
    print(f"  Plattenhoehe: 2.0 m")
    print(f"  Schildbreite: 3.0 m")
    print()

    step_1_generate_mesh()
    # step_2_solve_fluent()    # Auskommentiert: benoetigt Fluent-Lizenz
    # step_3_postprocess()     # Auskommentiert: benoetigt Fluent-Lizenz

    print()
    print("Hinweis: Schritte 2 + 3 benötigen eine ANSYS-Fluent-Installation.")
    print("Entkommentieren Sie die Aufrufe in main() nach Bedarf.")


if __name__ == "__main__":
    main()
