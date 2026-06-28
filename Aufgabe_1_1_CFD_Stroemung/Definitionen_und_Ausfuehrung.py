"""Aufgabe 1.1: CFD-Stroemungssimulation (Projekt 27)

Definiert alle Parameter, generiert das GMSH-Netz und startet optional den Fluent-Loeser.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

from Gemeinsamer_Code.fluent_loesung_vorlage import solve_fluent_case
from Gemeinsamer_Code.cfd_auswertung import (
    write_force_report,
    get_wall_pressure_data,
    export_contours,
    plot_pressure_distribution,
    plot_drag_convergence,
    plot_mesh_from_gmsh,
    write_summary_report,
)
from Gemeinsamer_Code.fluent_umgebung import ensure_awp_root

# Geometrie und Stroemungsparameter
PROJEKT_NUMMER = 27
TAFELHOEHE_M = 1.00          # Tafelhoehe hT
PLATTENHOEHE_M = 2.00        # Plattenhoehe gesamt (hT + 1.0m Fachwerk)
SCHILDBREITE_M = 3.0         # Schildbreite B
SCHILDDICKE_M = 0.003        # Schilddicke d (3mm)
WINDGESCHWINDIGKEIT_KMH = 110.0
WINDGESCHWINDIGKEIT_MPS = WINDGESCHWINDIGKEIT_KMH / 3.6
ANSTROEMFLAECHE_M2 = SCHILDBREITE_M * PLATTENHOEHE_M
LUFTDICHTE = 1.225           # rho [kg/m^3]
DYNAMISCHE_VISKOSITAET = 1.7894e-5 # mu [Pa*s]

# Reynolds-Zahl und Staudruck
REYNOLDS_ZAHL = (LUFTDICHTE * WINDGESCHWINDIGKEIT_MPS * PLATTENHOEHE_M) / DYNAMISCHE_VISKOSITAET
STAUDRUCK_PA = 0.5 * LUFTDICHTE * WINDGESCHWINDIGKEIT_MPS**2

# Stroemungsdomaene (2D)
UPSTREAM_FAKTOR = 5.0
DOWNSTREAM_FAKTOR = 15.0
VERTIKAL_FAKTOR = 5.0

X_MIN = -UPSTREAM_FAKTOR * PLATTENHOEHE_M
X_MAX = DOWNSTREAM_FAKTOR * PLATTENHOEHE_M
Y_MIN = -VERTIKAL_FAKTOR * PLATTENHOEHE_M
Y_MAX = VERTIKAL_FAKTOR * PLATTENHOEHE_M

# Plattenkoordinaten
PLATE_X_MIN = -0.5 * SCHILDDICKE_M
PLATE_X_MAX = 0.5 * SCHILDDICKE_M
PLATE_Y_MIN = -0.5 * PLATTENHOEHE_M
PLATE_Y_MAX = 0.5 * PLATTENHOEHE_M

# Netzeinstellungen (GMSH)
FAR_FIELD_MAX_SIZE = 0.10 * PLATTENHOEHE_M                 # Max. Elementgroesse im Aussenfeld
WAKE_SIZE = 0.025 * PLATTENHOEHE_M                         # Elementgroesse im Nachlauf
PLATE_EDGE_SIZE = min(0.005, SCHILDDICKE_M / 2.0)          # Elementgroesse an der Plattenkante
FIRST_LAYER_HEIGHT = min(0.001, SCHILDDICKE_M / 5.0)       # Erste Grenzschichthoehe
BOUNDARY_LAYER_COUNT = 8                                   # Anzahl Grenzschichten

class ParamsCFD:
    project = PROJEKT_NUMMER
    sign_thickness_m = SCHILDDICKE_M
    sign_width_m = SCHILDBREITE_M
    plate_height_m = PLATTENHOEHE_M
    hT_m = TAFELHOEHE_M
    wind_speed_mps = WINDGESCHWINDIGKEIT_MPS
    air_density = LUFTDICHTE
    air_dynamic_viscosity = DYNAMISCHE_VISKOSITAET
    dynamic_pressure_pa = STAUDRUCK_PA
    
    domain_m = {
        "x_min": X_MIN,
        "x_max": X_MAX,
        "y_min": Y_MIN,
        "y_max": Y_MAX,
        "plate_x_min": PLATE_X_MIN,
        "plate_x_max": PLATE_X_MAX,
        "plate_y_min": PLATE_Y_MIN,
        "plate_y_max": PLATE_Y_MAX,
    }
    
    recommended_mesh_m = {
        # Grundgroessen
        "far_field_max_size": FAR_FIELD_MAX_SIZE,
        "wake_size": WAKE_SIZE,
        "plate_edge_size": PLATE_EDGE_SIZE,
        "first_layer_height": FIRST_LAYER_HEIGHT,
        "boundary_layer_count": BOUNDARY_LAYER_COUNT,
        # Verfeinerungen
        "mesh_size_max": 0.35 * PLATTENHOEHE_M,            # Max. Elementgroesse global
        "refinement_size_max": 0.15 * PLATTENHOEHE_M,      # Max. Groesse nahe der Platte
        "refinement_dist_min": 0.02 * PLATTENHOEHE_M,      # Abstand fuer maximale Verfeinerung
        "refinement_dist_max": 1.0 * PLATTENHOEHE_M,       # Abstand fuer Auslauf der Verfeinerung
        "wake_vout": 0.35 * PLATTENHOEHE_M,                # Elementgroesse ausserhalb der Nachlaufbox
        "wake_xmax": 14.0 * PLATTENHOEHE_M,                # Ende der Nachlaufbox in x-Richtung
        "wake_ymin": -1.5 * PLATTENHOEHE_M,                # Unterseite der Nachlaufbox
        "wake_ymax": 1.5 * PLATTENHOEHE_M,                 # Oberseite der Nachlaufbox
        "boundary_layer_ratio": 1.2,                       # Wachstumsrate der Grenzschicht
        "boundary_layer_thickness": 0.02 * PLATTENHOEHE_M, # Gesamtdicke der Grenzschichten
    }


def step_1_netz_erzeugen(params, mesh_out: Path, gmsh_out: Path) -> None:
    """Schritt 1: Erzeugt das Netz mit Gmsh."""
    print("Schritt 1: Netzerzeugung mit Gmsh...")
    from Gemeinsamer_Code.cfd_netz_generierung import generate_cfd_mesh
    generate_cfd_mesh(
        params=params,
        output_path=mesh_out,
        gmsh_output_path=gmsh_out,
        no_boundary_layer=True,
        show_gmsh=False,
    )


def step_2_fluent_loesen(params, mesh_out: Path, case_out: Path, drag_out: Path, summary_out: Path) -> None:
    """Schritt 2: Startet den Fluent-Loeser (Lizenz erforderlich)."""
    print("Schritt 2: Fluent-Loeser ausfuehren...")
    solve_fluent_case(
        params=params,
        mesh_path=mesh_out,
        output_path=case_out,
        drag_file_path=drag_out,
        summary_path=summary_out,
        iterations=500,
        cores=2,
    )


def step_3_nachbereitung(params, case_path: Path, out_dir: Path) -> None:
    """Schritt 3: Ergebnisauswertung und Diagramme (Lizenz erforderlich)."""
    print("Schritt 3: CFD-Nachbereitung...")
    ensure_awp_root()
    import ansys.fluent.core as pyfluent

    solver = pyfluent.launch_fluent(
        mode=pyfluent.FluentMode.SOLVER,
        precision=pyfluent.Precision.DOUBLE,
        dimension=pyfluent.Dimension.TWO,
        processor_count=2,
    )
    try:
        solver.settings.file.read_case_data(file_name=str(case_path))
        force_report = write_force_report(solver, out_dir / "wall_forces.txt", "plate_wall")
        wall_data = get_wall_pressure_data(solver, params, "plate_wall")
        export_contours(solver, out_dir)
    finally:
        solver.exit()

    wall_data.to_csv(out_dir / "wall_pressure.csv", index=False)
    plot_pressure_distribution(wall_data, out_dir / "pressure_distribution.png")
    plot_drag_convergence(
        out_dir / "drag_plate.out",
        force_report,
        out_dir / "drag_convergence.png",
    )
    plot_mesh_from_gmsh(
        out_dir / "plate_2d_gmsh.msh",
        out_dir / "mesh_overview.png",
        out_dir / "mesh_plate_zoom.png",
    )
    write_summary_report(out_dir / "drag_summary.txt", params, force_report)


def main() -> None:
    params = ParamsCFD()
    task_dir = ROOT / "Aufgabe_1_1_CFD_Stroemung"
    data_dir = task_dir / "data"
    out_dir = task_dir / "out"
    out_dir.mkdir(parents=True, exist_ok=True)

    mesh_out = data_dir / "plate_2d_fluent.msh"
    gmsh_out = data_dir / "plate_2d_gmsh.msh"
    case_out = out_dir / "plate_2d_solution.cas.h5"
    drag_out = data_dir / "drag_plate.out"
    summary_out = data_dir / "drag_summary.txt"

    print("Aufgabe 1.1: CFD-Stroemungssimulation (Projekt 27)")
    print(f"  Windgeschwindigkeit: {WINDGESCHWINDIGKEIT_KMH} km/h = {WINDGESCHWINDIGKEIT_MPS:.2f} m/s")
    print(f"  Staudruck: {STAUDRUCK_PA:.2f} Pa")
    print(f"  Reynolds-Zahl: {REYNOLDS_ZAHL:.3e}\n")

    if mesh_out.exists():
        print(f"Schritt 1: Netz existiert bereits ({mesh_out.name}), ueberspringe Netzerzeugung.")
    else:
        step_1_netz_erzeugen(params, mesh_out, gmsh_out)

    # Schritte 2 und 3: Fluent-Loeser und Nachbereitung
    step_2_fluent_loesen(params, mesh_out, case_out, drag_out, summary_out)
    step_3_nachbereitung(params, case_out, out_dir)


if __name__ == "__main__":
    main()
