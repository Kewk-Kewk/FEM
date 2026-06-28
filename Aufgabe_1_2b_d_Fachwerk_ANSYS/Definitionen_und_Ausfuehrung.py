"""Aufgabe 1.2b-d: Fachwerkberechnung in ANSYS MAPDL (Projekt 27)

Definiert Parameter und erzeugt APDL-Skripte fuer das Gelenkstabwerk in ANSYS MAPDL.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

from Gemeinsamer_Code.apdl_fachwerk import (
    generate_truss_apdl,
    read_average_hinge_loads,
    parse_apdl_element_table,
    write_apdl_rows,
    write_comparison,
    read_python_rows,
)
from Gemeinsamer_Code.python_fem_loesung import build_truss
from Gemeinsamer_Code.hilfsfunktionen import read_summary_value

# Geometrie des Fachwerks
FACHWERKBREITE_M = 0.45      # Breite b (Feldbreite)
FELDHOEHE_M = 0.25           # Feldhoehe h
FELDER_ANZAHL = 7            # Anzahl Felder (Panels)

# Materialparameter (Stahl S235)
E_STAHL_MPA = 210_000.0      # E-Modul
NU_STAHL = 0.3               # Querdehnzahl
SAFETY_FACTOR = 1.8          # Sicherheitsbeiwert
SIGMA_ALLOW_STAHL_MPA = 235.0 / SAFETY_FACTOR # Zulässige Spannung (130.56 MPa)

# Querschnittswerte (Stahlrohre)
OUTER_DIAMETERS_MM = {"vertical": 16.0, "horizontal": 12.0, "diagonal": 12.0}
WALL_THICKNESSES_MM = {"vertical": 1.5, "horizontal": 1.5, "diagonal": 1.5}
ELEMENTTYP = "LINK180"

PARAMS_TRUSS = {
    "project": 27,
    "b_m": FACHWERKBREITE_M,
    "h_m": FELDHOEHE_M,
}


def step_1_apdl_generieren(upper_load_n: float, lower_load_n: float, apdl_out: Path) -> None:
    """Erzeugt die APDL-Eingabedatei fuer ANSYS MAPDL."""
    print("Schritt 1: APDL-Generierung fuer Fachwerk...")
    nodes, elements = build_truss(PARAMS_TRUSS, FELDER_ANZAHL)
    
    generate_truss_apdl(
        path=apdl_out,
        params=PARAMS_TRUSS,
        nodes=nodes,
        elements=elements,
        upper_load_n=upper_load_n,
        lower_load_n=lower_load_n,
    )
    print(f"APDL-Eingabedatei geschrieben nach: {apdl_out}")


def step_2_auswerten(out_dir: Path, index_table: Path, python_forces: Path) -> None:
    """Wertet die MAPDL-Ausgabedateien aus."""
    print("Schritt 2: Ergebnisauswertung...")
    apdl_output = out_dir / "truss_structural_solver.out"
    
    if not apdl_output.exists():
        print("Solver-Ausgabedatei von MAPDL nicht gefunden. Parser uebersprungen.")
        return
        
    apdl_rows = parse_apdl_element_table(apdl_output, index_table)
    write_apdl_rows(out_dir / "truss_apdl_element_forces.csv", apdl_rows)
    
    if not python_forces.exists():
        print(f"Python-FEM-Ergebnisdatei {python_forces} nicht gefunden. Kein Vergleich moeglich.")
        return
        
    python_rows = read_python_rows(python_forces)
    write_comparison(
        out_dir / "truss_comparison_python_ansys.csv",
        out_dir / "truss_comparison_summary.txt",
        apdl_rows,
        python_rows,
    )
    print(f"Auswertung beendet. Vergleichsdatei: {out_dir / 'truss_comparison_summary.txt'}")


def main() -> None:
    task_dir = ROOT / "Aufgabe_1_2b_d_Fachwerk_ANSYS"
    data_dir = task_dir / "data"
    out_dir = task_dir / "out"
    out_dir.mkdir(parents=True, exist_ok=True)
    
    plate_reactions = ROOT / "Aufgabe_1_2a_Plattenstruktur" / "out" / "plate_hinge_reactions.csv"
    if not plate_reactions.exists():
        upper_load_n = 1604.90
        lower_load_n = 540.84
        print(f"Warnung: {plate_reactions} nicht gefunden. Verwende Windkraft-Standardwert: upper={upper_load_n} N, lower={lower_load_n} N")
    else:
        _, upper_load_n, lower_load_n = read_average_hinge_loads(plate_reactions)
        
    print("Aufgabe 1.2b-d: Fachwerkmodellierung in ANSYS MAPDL (Projekt 27)")
    print(f"  Fachwerk: {FELDER_ANZAHL} Felder (b={FACHWERKBREITE_M} m, h={FELDHOEHE_M} m)")
    print(f"  Material: Stahl (E={E_STAHL_MPA:.0f} MPa, zul. Spannung={SIGMA_ALLOW_STAHL_MPA:.2f} MPa)")
    print(f"  Eingeleitete Windlasten (Traeger H3):")
    print(f"    - Obere Gelenkkraft: {upper_load_n:.2f} N")
    print(f"    - Untere Gelenkkraft: {lower_load_n:.2f} N\n")

    apdl_out = out_dir / "truss_structural.inp"
    step_1_apdl_generieren(upper_load_n, lower_load_n, apdl_out)
    
    index_table = ROOT / "Aufgabe_1_2e_h_Fachwerk_Python" / "out" / "truss_index_table.csv"
    python_forces = ROOT / "Aufgabe_1_2e_h_Fachwerk_Python" / "out" / "truss_element_forces.csv"
    step_2_auswerten(out_dir, index_table, python_forces)


if __name__ == "__main__":
    main()
