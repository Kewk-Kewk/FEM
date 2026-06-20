"""Aufgabe 1.2 a) — Hauptskript fuer die Tafel-Schalenberechnung.

Workflow:
  1. Lese Windkraft aus drag_summary.txt
  2. Erzeuge APDL-Eingabefile (line-support-full-height)
  3. Erzeuge APDL-Nachbearbeitungsskripte
  4. Fuehre optional die Singularitaetsstudie durch

Nach dem Lauf dieses Skripts muessen die .inp-Dateien in ANSYS MAPDL
ausgefuehrt werden; danach parse_plate_structural_results.py aufrufen.

Aufruf:
  python Aufgabe1/code/run_plate.py
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Parameter fuer Projekt 27
# ---------------------------------------------------------------------------
MESH_SIZE_MM = 50.0                # globale Netzgroesse [mm]
SUPPORT_PATCH_MM = 50.0            # Breite der Linienstuetzen [mm]
SUPPORT_MODE = "line-support-full-height"

ROOT = Path(__file__).resolve().parents[2]
CODE_DIR = ROOT / "Aufgabe1" / "code"
DATA_DIR = ROOT / "Aufgabe1" / "data"
OUT_DIR = ROOT / "Aufgabe1" / "out"
DRAG_SUMMARY = DATA_DIR / "drag_summary.txt"


def step_1_generate_apdl() -> None:
    """Erzeuge APDL-Eingabedateien fuer die Schalenberechnung."""
    print("=" * 60)
    print("Schritt 1: APDL-Generierung (line-support-full-height)")
    print("=" * 60)
    subprocess.run(
        [
            sys.executable,
            str(CODE_DIR / "structural_plate_apdl.py"),
            "--summary", str(DRAG_SUMMARY),
            "--out-dir", str(OUT_DIR),
            "--mesh-size-mm", str(MESH_SIZE_MM),
            "--support-patch-mm", str(SUPPORT_PATCH_MM),
            "--support-mode", SUPPORT_MODE,
        ],
        check=True,
    )
    print(f"APDL-Dateien geschrieben nach: {OUT_DIR}")
    print()
    print("Naechster Schritt:")
    print(f"  1. Oeffne ANSYS MAPDL")
    print(f"  2. Fuehre aus: {OUT_DIR / 'plate_structural.inp'}")
    print(f"  3. Fuehre aus: {OUT_DIR / 'plate_post_probe.inp'}")
    print(f"  4. Fuehre aus: {OUT_DIR / 'plate_export_plots.inp'}")
    print(f"  5. Werte aus mit: python {CODE_DIR / 'parse_plate_structural_results.py'}")


def step_2_singularity_study() -> None:
    """Fuehre die Singularitaetsstudie (Punktlager) durch."""
    print("=" * 60)
    print("Schritt 2: Singularitaetsstudie (3 Netzstufen)")
    print("=" * 60)
    subprocess.run(
        [
            sys.executable,
            str(CODE_DIR / "run_plate_singularity_study.py"),
            "--summary", str(DRAG_SUMMARY),
            "--refinements-mm", "10", "2", "1",
        ],
        check=True,
    )


def main() -> None:
    print("Aufgabe 1.2a: Schalenberechnung der Aluminiumtafel (Projekt 27)")
    print(f"  Netzgroesse: {MESH_SIZE_MM} mm")
    print(f"  Lagermodell: {SUPPORT_MODE}")
    print(f"  Stuetzenbreite: {SUPPORT_PATCH_MM} mm")
    print()

    step_1_generate_apdl()
    # step_2_singularity_study()  # Nur bei Bedarf


if __name__ == "__main__":
    main()
