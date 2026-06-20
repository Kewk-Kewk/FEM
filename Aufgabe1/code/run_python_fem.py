"""Aufgabe 1.2 e)–h) — Hauptskript fuer die eigene Python-FEM-Berechnung.

Fuehrt die vollstaendige Fachwerk-FEM-Berechnung durch:
  1. Topologie aufbauen (7 Felder, 3 Stabgruppen)
  2. Elementsteifigkeitsmatrizen K^(e) berechnen
  3. Globale Steifigkeitsmatrix K assemblieren
  4. Randbedingungen einarbeiten (L0 fest, R0 Loslager)
  5. K * U = F loesen
  6. Stabkraefte und Spannungen berechnen
  7. Ergebnisse mit ANSYS-Werten vergleichen

Aufruf:
  python Aufgabe1/code/run_python_fem.py

Ausgabe: CSV-Dateien, Verformungsplot, Zusammenfassung.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Parameter fuer Projekt 27
# ---------------------------------------------------------------------------
PANEL_COUNT = 7       # Anzahl Felder
TRUSS_COUNT = 3       # Anzahl Traeger ueber die Schildbreite

ROOT = Path(__file__).resolve().parents[2]
CODE_DIR = ROOT / "Aufgabe1" / "code"
DATA_DIR = ROOT / "Aufgabe1" / "data"
OUT_DIR = ROOT / "Aufgabe1" / "out"

import csv
def get_average_loads() -> tuple[float, float]:
    csv_path = OUT_DIR / "plate_hinge_reactions.csv"
    if not csv_path.exists():
        return 1604.9, 540.8 # Fallback to governing if not found
    
    with csv_path.open(newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        rows = list(reader)
        
    uppers = [abs(float(r["load_on_truss_N"])) for r in rows if "upper" in r["hinge"]]
    lowers = [abs(float(r["load_on_truss_N"])) for r in rows if "lower" in r["hinge"]]
    return sum(uppers) / len(uppers), sum(lowers) / len(lowers)

UPPER_LOAD_N, LOWER_LOAD_N = get_average_loads()


def main() -> None:
    print("Aufgabe 1.2 e)-h): Eigene Python-FEM-Berechnung (Projekt 27)")
    print(f"  Feldanzahl: {PANEL_COUNT}")
    print(f"  Obere Gelenkkraft: {UPPER_LOAD_N} N")
    print(f"  Untere Gelenkkraft: {LOWER_LOAD_N} N")
    print()

    print("=" * 60)
    print("Python-FEM-Loesung")
    print("=" * 60)
    subprocess.run(
        [
            sys.executable,
            str(CODE_DIR / "structural_truss_1_2.py"),
            "--summary", str(DATA_DIR / "drag_summary.txt"),
            "--out-dir", str(OUT_DIR),
            "--panel-count", str(PANEL_COUNT),
            "--truss-count", str(TRUSS_COUNT),
            "--upper-load-n", str(UPPER_LOAD_N),
            "--lower-load-n", str(LOWER_LOAD_N),
        ],
        check=True,
    )
    print()
    print("Ergebnisse geschrieben nach:")
    print(f"  {OUT_DIR / 'truss_summary.txt'}")
    print(f"  {OUT_DIR / 'truss_element_forces.csv'}")
    print(f"  {OUT_DIR / 'truss_index_table.csv'}")
    print(f"  {OUT_DIR / 'truss_deformed.png'}")


if __name__ == "__main__":
    main()
