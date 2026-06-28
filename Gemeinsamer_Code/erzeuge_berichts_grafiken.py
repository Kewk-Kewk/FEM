"""Gemeinsamer_Code/erzeuge_berichts_grafiken.py

Skript zum Generieren aller Abbildungen und Tabellen für den LaTeX-Bericht
aus den Daten in den jeweiligen Aufgabenverzeichnissen.

Aufruf:
  python Gemeinsamer_Code/erzeuge_berichts_grafiken.py
"""
from __future__ import annotations

import sys
import shutil
from pathlib import Path

# Pfad-Manipulation, damit Gemeinsamer_Code gefunden wird
ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

from Gemeinsamer_Code.berichts_abbildungen import (
    save_cfd_velocity_plot,
    save_pressure_distribution_plot,
    save_drag_convergence_plot,
    save_cfd_mesh_overview_plot,
    save_plate_singularity_mesh_panel_plot,
    save_plate_singularity_stress_panel_plot,
    save_plate_hinges_plot,
    save_truss_ansys_result_plot,
    save_truss_comparison_outputs_plot,
    save_kerb_convergence_plot,
)

def main() -> None:
    # --- Pfade definieren ---
    cfd_dir = ROOT / "Aufgabe_1_1_CFD_Stroemung"
    plate_dir = ROOT / "Aufgabe_1_2a_Plattenstruktur"
    truss_ansys_dir = ROOT / "Aufgabe_1_2b_d_Fachwerk_ANSYS"
    truss_python_dir = ROOT / "Aufgabe_1_2e_h_Fachwerk_Python"
    aufgabe2_dir = ROOT / "Aufgabe_2"

    print("Generiere Abbildungen und Tabellen...")

    # 1. CFD-Abbildungen (Aufgabe 1.1)
    print("  -> CFD Strömung...")
    save_cfd_velocity_plot(
        mesh_path=cfd_dir / "data" / "plate_2d_gmsh.msh",
        data_path=cfd_dir / "data" / "plate_2d_solution.dat.h5",
        target=cfd_dir / "figures" / "contour_velocity_report.png"
    )
    save_pressure_distribution_plot(
        source=cfd_dir / "data" / "wall_pressure.csv",
        target=cfd_dir / "figures" / "pressure_distribution.png"
    )
    save_drag_convergence_plot(
        drag_file=cfd_dir / "data" / "drag_plate.out",
        summary_file=cfd_dir / "data" / "drag_summary.txt",
        target=cfd_dir / "figures" / "drag_convergence.png"
    )
    save_cfd_mesh_overview_plot(
        mesh_path=cfd_dir / "data" / "plate_2d_gmsh.msh",
        target=cfd_dir / "figures" / "mesh_overview_report.png"
    )

    # 2. Platten-Abbildungen (Aufgabe 1.2a)
    print("  -> Plattenstruktur...")
    # Singulartitätsstudie Panels
    save_plate_singularity_mesh_panel_plot(
        h10_path=plate_dir / "out" / "plate_singularity_study" / "h10" / "plate_point_mesh_preview.png",
        h2_path=plate_dir / "out" / "plate_singularity_study" / "h2" / "plate_point_mesh_preview.png",
        h1_path=plate_dir / "out" / "plate_singularity_study" / "h1" / "plate_point_mesh_preview.png",
        target=plate_dir / "figures" / "plate_singularity_mesh_panel.png"
    )
    save_plate_singularity_stress_panel_plot(
        study_csv=plate_dir / "data" / "plate_singularity_study.csv",
        h10_dir=plate_dir / "out" / "plate_singularity_study" / "h10",
        h2_dir=plate_dir / "out" / "plate_singularity_study" / "h2",
        h1_dir=plate_dir / "out" / "plate_singularity_study" / "h1",
        target=plate_dir / "figures" / "plate_singularity_stress_panel.png"
    )
    # Gelenkreaktions-Plot (Erwartet plate_hinge_reactions.csv)
    # Falls in out/ vorhanden, nach data/ kopieren und plotten
    reactions_out = plate_dir / "out" / "plate_hinge_reactions.csv"
    reactions_data = plate_dir / "data" / "plate_hinge_reactions.csv"
    if reactions_out.exists():
        shutil.copyfile(reactions_out, reactions_data)
    save_plate_hinges_plot(
        csv_path=reactions_data,
        target=plate_dir / "figures" / "plate_hinge_probes.png"
    )

    # 3. Truss-ANSYS-Abbildungen (Aufgabe 1.2b-d)
    print("  -> Fachwerk ANSYS...")
    # APDL summary aus out/ nach data/ kopieren falls vorhanden
    apdl_sum_out = truss_ansys_dir / "out" / "truss_apdl_summary.txt"
    apdl_sum_data = truss_ansys_dir / "data" / "truss_apdl_summary.txt"
    if apdl_sum_out.exists():
        shutil.copyfile(apdl_sum_out, apdl_sum_data)
        
    save_truss_ansys_result_plot(
        forces_csv=truss_ansys_dir / "data" / "truss_apdl_element_forces.csv",
        index_csv=truss_python_dir / "data" / "truss_index_table.csv",
        summary_txt=apdl_sum_data,
        displacement_csv=truss_python_dir / "out" / "truss_displacements.csv",  # Displacement von Python-FEM
        target=truss_ansys_dir / "figures" / "truss_ansys_force_plot.png"
    )

    # 4. Truss-Python-Abbildungen (Aufgabe 1.2e-h)
    print("  -> Fachwerk Python...")
    # Comparison CSV aus out/ nach data/ kopieren falls vorhanden
    comp_out = truss_python_dir / "out" / "truss_comparison_python_ansys.csv"
    comp_data = truss_python_dir / "data" / "truss_comparison_python_ansys.csv"
    if comp_out.exists():
        shutil.copyfile(comp_out, comp_data)
        
    save_truss_comparison_outputs_plot(
        comparison_csv=comp_data,
        target_tex=truss_python_dir / "data" / "truss_comparison_report_table.tex",
        target_png=truss_python_dir / "figures" / "truss_python_ansys_comparison.png"
    )
    # deformed.png aus out/ nach figures/ kopieren falls vorhanden
    deformed_out = truss_python_dir / "out" / "truss_deformed.png"
    deformed_fig = truss_python_dir / "figures" / "truss_deformed.png"
    if deformed_out.exists():
        shutil.copyfile(deformed_out, deformed_fig)

    # 5. Aufgabe 2 Abbildungen
    print("  -> Aufgabe 2...")
    save_kerb_convergence_plot(
        source_csv=aufgabe2_dir / "data" / "kerb_convergence.csv",
        target_png=aufgabe2_dir / "figures" / "kerb_convergence.png"
    )
    
    # Screenshots nach figures/ kopieren für Bericht
    screenshots = {
        "meshgesamt.PNG": "mesh_gesamt_report.png",
        "meshzoom.PNG": "mesh_zoom_report.png",
        "Normalspannung.PNG": "normalspannung_report.png",
        "Vergleichspannungmises.PNG": "vergleichspannung_mises_report.png",
    }
    screen_dir = aufgabe2_dir / "screenshots" / "final_report"
    if screen_dir.exists():
        for src_name, dst_name in screenshots.items():
            src_f = screen_dir / src_name
            if src_f.exists():
                shutil.copyfile(src_f, aufgabe2_dir / "figures" / dst_name)

    print("Alle Grafiken und Tabellen wurden erfolgreich erzeugt.")

if __name__ == "__main__":
    main()
