"""Aufgabe 1.2e-h: Python-FEM-Berechnung des Fachwerks (Projekt 27)

Eigener Python-FEM-Loeser zur Berechnung des ebenen Gelenkstabwerks mittels Steifigkeitsmethode.
"""
from __future__ import annotations

import sys
import csv
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

from Gemeinsamer_Code.python_fem_loesung import (
    Node, Element, Tube, TUBE_CATALOG,
    build_truss, find_node_index, solve_truss, choose_tube,
    write_index_table, write_element_rows, write_displacements,
    plot_truss, write_summary,
    SIGMA_ALLOW_STEEL_PA
)
from Gemeinsamer_Code.hilfsfunktionen import read_summary_value

# Geometrie
FACHWERKBREITE_M = 0.45      # Feldbreite b
FELDHOEHE_M = 0.25           # Feldhoehe h
FELDER_ANZAHL = 7            # Feldanzahl

# Material und Querschnitt (Stahl S235)
E_STAHL_PA = 210_000e6
SIGMA_ALLOW_STAHL_PA_VAL = SIGMA_ALLOW_STEEL_PA # Zulässige Spannung (130.56 MPa)
ROHR_KATALOG = TUBE_CATALOG

# Lagerung (Freiheitsgrade)
# U_L0_y (1), U_R0_x (2) und U_R0_y (3) blockiert
FIXIERTE_DOFS = [1, 2, 3]

PARAMS_TRUSS = {
    "project": 27,
    "b_m": FACHWERKBREITE_M,
    "h_m": FELDHOEHE_M,
}


def get_average_loads() -> tuple[float, float]:
    """Liest die Gelenkkraefte zur Lastweiterleitung ein."""
    csv_path = ROOT / "Aufgabe_1_2a_Plattenstruktur" / "out" / "plate_hinge_reactions.csv"
    if not csv_path.exists():
        return 1604.90, 540.84
    
    with csv_path.open(newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        rows = list(reader)
        
    uppers = [abs(float(r["load_on_truss_N"])) for r in rows if "upper" in r["hinge"]]
    lowers = [abs(float(r["load_on_truss_N"])) for r in rows if "lower" in r["hinge"]]
    return sum(uppers) / len(uppers), sum(lowers) / len(lowers)


def step_1_fem_berechnen(
    upper_load_n: float,
    lower_load_n: float,
    summary_txt: Path,
    out_dir: Path,
) -> None:
    """Fuehrt die FEM-Berechnung des Fachwerks durch."""
    print("Schritt 1: Globale FEM-Lösung...")
    
    nodes, elements = build_truss(PARAMS_TRUSS, FELDER_ANZAHL)
    dof_count = 2 * len(nodes)
    force = np.zeros(dof_count)

    # Lastvektor aufbauen (Kraefte an rechten Endknoten)
    top_right = find_node_index(nodes, f"R{FELDER_ANZAHL}")
    lower_right = find_node_index(nodes, f"R{FELDER_ANZAHL - 1}")
    force[2 * top_right] = -upper_load_n
    force[2 * lower_right] = -lower_load_n

    # Vordimensionierung mit Einheitsquerschnitt zur Kraftermittlung
    trial_areas = {"vertical": 1e-4, "horizontal": 1e-4, "diagonal": 1e-4}
    _, _, trial_rows = solve_truss(nodes, elements, trial_areas, force, FIXIERTE_DOFS)

    max_by_kind = {
        kind: max(abs(float(row["axial_N"])) for row in trial_rows if row["kind"] == kind)
        for kind in ["vertical", "horizontal", "diagonal"]
    }

    # Rohre aus Katalog waehlen (A_erf = N_max / sigma_zul)
    tubes_by_kind = {
        kind: choose_tube(max_force / SIGMA_ALLOW_STAHL_PA_VAL)
        for kind, max_force in max_by_kind.items()
    }
    selected_areas = {kind: tube.area_m2 for kind, tube in tubes_by_kind.items()}

    # Endgültige Lösung mit gewaehlten Rohren
    displacement, reactions, rows = solve_truss(
        nodes, elements, selected_areas, force, FIXIERTE_DOFS
    )

    # Ergebnisse schreiben
    write_index_table(out_dir / "truss_index_table.csv", nodes, elements)
    write_element_rows(out_dir / "truss_element_forces.csv", rows)
    write_displacements(out_dir / "truss_displacements.csv", nodes, displacement)
    plot_truss(out_dir / "truss_deformed.png", nodes, elements, displacement, rows)
    
    # CFD-Widerstand laden
    cfd_summary = ROOT / "Aufgabe_1_1_CFD_Stroemung" / "data" / "drag_summary.txt"
    if not cfd_summary.exists():
        total_drag_n = 6430.054
    else:
        total_drag_n = read_summary_value(cfd_summary, "total_drag_N")
    pressure_pa = total_drag_n / 6.0
    force_per_truss_n = upper_load_n + lower_load_n

    write_summary(
        path=summary_txt,
        params=PARAMS_TRUSS,
        total_drag_n=total_drag_n,
        pressure_pa=pressure_pa,
        force_per_truss_n=force_per_truss_n,
        upper_joint_load_n=upper_load_n,
        lower_joint_load_n=lower_load_n,
        nodes=nodes,
        fixed_dofs=FIXIERTE_DOFS,
        displacement=displacement,
        reactions=reactions,
        rows=rows,
        tubes_by_kind=tubes_by_kind,
        truss_count=3,
    )
    print("Python-FEM-Rechnung erfolgreich beendet.")


def main() -> None:
    task_dir = ROOT / "Aufgabe_1_2e_h_Fachwerk_Python"
    out_dir = task_dir / "out"
    out_dir.mkdir(parents=True, exist_ok=True)

    upper_load_n, lower_load_n = get_average_loads()

    print("Aufgabe 1.2e-h: Eigene Python-FEM-Berechnung (Projekt 27)")
    print(f"  Gelenkstabwerk: {FELDER_ANZAHL} Felder (b={FACHWERKBREITE_M} m, h={FELDHOEHE_M} m)")
    print(f"  Zul. Spannung: {SIGMA_ALLOW_STAHL_PA_VAL/1e6:.2f} MPa")
    print(f"  Windlasten (Traeger H3):")
    print(f"    - Obere Knotenkraft: {upper_load_n:.2f} N")
    print(f"    - Untere Knotenkraft: {lower_load_n:.2f} N\n")

    summary_txt = out_dir / "truss_summary.txt"
    step_1_fem_berechnen(upper_load_n, lower_load_n, summary_txt, out_dir)


if __name__ == "__main__":
    main()
