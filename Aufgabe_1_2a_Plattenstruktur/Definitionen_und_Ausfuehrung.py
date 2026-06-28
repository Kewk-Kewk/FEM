"""Aufgabe 1.2a: FE-Berechnung der Aluminiumtafel (Projekt 27)

Definiert Parameter und erzeugt APDL-Eingabedateien fuer ANSYS MAPDL.
"""
from __future__ import annotations

import sys
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

from Gemeinsamer_Code.apdl_platte_schale import generate_plate_apdl, write_post_probe, write_export_plots
from Gemeinsamer_Code.apdl_ergebnis_parser import (
    parse_key_values,
    parse_post_output,
    write_stress_area_csv,
    write_reaction_csv,
    write_legacy_hinge_csv,
    write_plate_summary_report,
)
from Gemeinsamer_Code.hilfsfunktionen import read_summary_value

# Geometrie und Querschnitt der Platte
SCHILDBREITE_M = 3.0         # Breite B
SCHILDHOEHE_M = 2.0          # Hoehe H
SCHILDDICKE_M = 0.003        # Dicke d (3mm)
FELDHOEHE_M = 0.25           # Feldhoehe h (25cm)

# Materialparameter (Aluminium)
E_ALU_MPA = 70_000.0         # E-Modul
NU_ALU = 0.3                 # Querdehnzahl
SAFETY_FACTOR = 1.8          # Sicherheitsbeiwert
SIGMA_ALLOW_ALU_MPA = 190.0 / SAFETY_FACTOR # Zulässige Spannung (105.56 MPa)

# Netz- und Stuetzenparameter
MESH_SIZE_MM = 50.0          # Globale Netzgroesse
SUPPORT_PATCH_MM = 50.0      # Breite der vertikalen Linienstuetzen
SUPPORT_MODE = "line-support-full-height"
ELEMENTTYP = "SHELL181"

PARAMS_PLATE = {
    "project": 27,
    "width_m": SCHILDBREITE_M,
    "height_m": SCHILDHOEHE_M,
    "thickness_m": SCHILDDICKE_M,
    "h_m": FELDHOEHE_M,
}


def step_1_apdl_generieren(total_drag_n: float, apdl_out: Path, out_dir: Path) -> None:
    """Erzeugt die APDL-Eingabedateien fuer ANSYS MAPDL."""
    print("Schritt 1: APDL-Generierung (Linienlager)...")
    job_name = "plate_line_support_full_height"
    
    generate_plate_apdl(
        params=PARAMS_PLATE,
        path=apdl_out,
        mesh_size_mm=MESH_SIZE_MM,
        total_drag_n=total_drag_n,
        support_patch_mm=SUPPORT_PATCH_MM,
        support_refinement_mm=None,
        support_influence_mm=None,
        support_mode=SUPPORT_MODE,
        job_name=job_name,
        mesh_preview_path=None,
    )
    
    write_post_probe(out_dir / "plate_post_probe.inp", job_name)
    write_export_plots(out_dir / "plate_export_plots.inp", job_name)
    print(f"Skripte geschrieben nach: {out_dir}")


def step_2_auswerten(out_dir: Path, apdl_path: Path) -> None:
    """Wertet die MAPDL-Ausgabedateien aus."""
    print("Schritt 2: Ergebnisauswertung...")
    results_txt = out_dir / "plate_structural_results.txt"
    post_output = out_dir / "plate_post_probe.out"
    
    if not results_txt.exists() or not post_output.exists():
        print("MAPDL-Ausgabedateien nicht gefunden. Parser uebersprungen.")
        return
        
    values = parse_key_values(results_txt)
    stress = parse_post_output(post_output)
    allowable = values.get("allowable_stress_MPa", SIGMA_ALLOW_ALU_MPA)
    
    stress_area = write_stress_area_csv(
        out_dir / "plate_stress_area.csv",
        apdl_path,
        post_output,
        allowable,
    )
    reactions = write_reaction_csv(out_dir / "plate_support_reactions.csv", values)
    write_legacy_hinge_csv(out_dir / "plate_hinge_reactions.csv", reactions)
    write_plate_summary_report(
        out_dir / "plate_structural_summary.txt",
        values,
        stress,
        reactions,
        stress_area,
    )
    print(f"Auswertung beendet. Bericht: {out_dir / 'plate_structural_summary.txt'}")


def main() -> None:
    task_dir = ROOT / "Aufgabe_1_2a_Plattenstruktur"
    data_dir = task_dir / "data"
    out_dir = task_dir / "out"
    out_dir.mkdir(parents=True, exist_ok=True)
    
    cfd_summary = ROOT / "Aufgabe_1_1_CFD_Stroemung" / "data" / "drag_summary.txt"
    
    if not cfd_summary.exists():
        total_drag_n = 6430.054
        print(f"Warnung: {cfd_summary} nicht gefunden. Verwende Windkraft-Standardwert: {total_drag_n} N")
    else:
        total_drag_n = read_summary_value(cfd_summary, "total_drag_N")
        
    pressure_mpa = total_drag_n / ((SCHILDBREITE_M * 1000.0) * (SCHILDHOEHE_M * 1000.0))
    
    print("Aufgabe 1.2a: Aluminiumtafel FE-Berechnung (Projekt 27)")
    print(f"  Tafelmasse: {SCHILDBREITE_M} m x {SCHILDHOEHE_M} m x {SCHILDDICKE_M*1000} mm")
    print(f"  Zulaessige Spannung: {SIGMA_ALLOW_ALU_MPA:.2f} MPa")
    print(f"  Windkraft aus CFD: {total_drag_n:.3f} N (Drucklast={pressure_mpa:.8f} N/mm^2)\n")

    apdl_out = out_dir / "plate_structural.inp"
    step_1_apdl_generieren(total_drag_n, apdl_out, out_dir)
    step_2_auswerten(out_dir, apdl_out)


if __name__ == "__main__":
    main()
