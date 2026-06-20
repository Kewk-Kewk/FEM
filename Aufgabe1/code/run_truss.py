"""Aufgabe 1.2 b)–d) — Hauptskript fuer die ANSYS-Fachwerkberechnung.

Workflow:
  1. Erzeuge APDL-Eingabefile mit LINK180-Stabelementen
  2. Nach ANSYS-Lauf: parse_truss_apdl_results.py ausfuehren

Aufruf:
  python Aufgabe1/code/run_truss.py
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Parameter fuer Projekt 27
# ---------------------------------------------------------------------------
PANEL_COUNT = 7   # Anzahl Felder im Fachwerk

ROOT = Path(__file__).resolve().parents[2]
CODE_DIR = ROOT / "Aufgabe1" / "code"
DATA_DIR = ROOT / "Aufgabe1" / "data"
OUT_DIR = ROOT / "Aufgabe1" / "out"


def step_1_generate_apdl() -> None:
    """Erzeuge APDL-Eingabedatei fuer das Fachwerk."""
    print("=" * 60)
    print("Schritt 1: APDL-Generierung fuer Fachwerkmodell")
    print("=" * 60)
    subprocess.run(
        [
            sys.executable,
            str(CODE_DIR / "structural_truss_apdl.py"),
            "--out-dir", str(OUT_DIR),
            "--panel-count", str(PANEL_COUNT),
        ],
        check=True,
    )
    print(f"APDL-Dateien geschrieben nach: {OUT_DIR}")
    print()
    print("Naechster Schritt:")
    print(f"  1. Oeffne ANSYS MAPDL")
    print(f"  2. Fuehre aus: {OUT_DIR / 'truss_structural.inp'}")
    print(f"  3. Werte aus mit: python {CODE_DIR / 'parse_truss_apdl_results.py'}")


def main() -> None:
    print("Aufgabe 1.2 b)-d): ANSYS-Fachwerkberechnung (Projekt 27)")
    print(f"  Feldanzahl: {PANEL_COUNT}")
    print()
    step_1_generate_apdl()


if __name__ == "__main__":
    main()
