"""Gemeinsamer_Code/fluent_loesung_vorlage.py

Führt die stationäre Fluent-Lösung durch. Löst das 2D-CFD-Modell.
"""
from __future__ import annotations

from pathlib import Path
from Gemeinsamer_Code.fluent_umgebung import ensure_awp_root
from Gemeinsamer_Code.cfd_auswertung import read_drag_history, write_summary


def set_velocity_inlet(session, name: str, velocity: float) -> None:
    inlet = session.settings.setup.boundary_conditions.velocity_inlet[name]
    state = inlet.get_state()

    if "momentum" in state and "velocity_magnitude" in state["momentum"]:
        state["momentum"]["velocity_magnitude"]["value"] = velocity
    elif "momentum" in state and "velocity" in state["momentum"]:
        state["momentum"].setdefault("velocity", {})["value"] = velocity
    elif "vmag" in state:
        state["vmag"]["value"] = velocity
    elif "velocity" in state:
        state["velocity"]["value"] = velocity
    else:
        raise KeyError(f"Could not find a velocity key in inlet state: {state.keys()}")

    inlet.set_state(state)


def set_reference_values(session, params) -> None:
    ref = session.settings.setup.reference_values
    state = ref.get_state()
    state.update(
        {
            "area": params.plate_height_m,
            "depth": 1.0,
            "density": params.air_density,
            "length": params.plate_height_m,
            "velocity": params.wind_speed_mps,
            "viscosity": params.air_dynamic_viscosity,
        }
    )
    ref.set_state(state)


def solve_fluent_case(
    params,
    mesh_path: Path,
    output_path: Path,
    drag_file_path: Path,
    summary_path: Path,
    iterations: int = 500,
    cores: int = 2,
    inlet: str = "inlet",
    outlet: str = "outlet",
    plate_wall: str = "plate_wall",
    top: str = "top",
    bottom: str = "bottom",
) -> None:
    ensure_awp_root()
    import ansys.fluent.core as pyfluent

    if not mesh_path.exists():
        raise FileNotFoundError(mesh_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    drag_file_path.parent.mkdir(parents=True, exist_ok=True)
    if drag_file_path.exists():
        drag_file_path.unlink()

    solver = pyfluent.launch_fluent(
        mode=pyfluent.FluentMode.SOLVER,
        precision=pyfluent.Precision.DOUBLE,
        dimension=pyfluent.Dimension.TWO,
        processor_count=cores,
    )

    try:
        mesh_file = str(mesh_path.resolve())
        if mesh_path.suffix == ".msh" or mesh_path.name.endswith(".msh.h5"):
            solver.settings.file.read_mesh(file_name=mesh_file)
        else:
            solver.settings.file.read_case(file_name=mesh_file)
        solver.settings.mesh.check()

        bc = solver.settings.setup.boundary_conditions
        try:
            bc.set_zone_type(zone_list=[inlet], new_type="velocity-inlet")
            bc.set_zone_type(zone_list=[outlet], new_type="pressure-outlet")
            bc.set_zone_type(zone_list=[plate_wall], new_type="wall")
            bc.set_zone_type(zone_list=[top, bottom], new_type="symmetry")
        except Exception as exc:
            print(f"Boundary zone types were not changed automatically: {exc}")

        set_velocity_inlet(solver, inlet, params.wind_speed_mps)
        bc.pressure_outlet[outlet].momentum.gauge_pressure = 0.0
        set_reference_values(solver, params)

        try:
            solver.settings.setup.general.operating_conditions.operating_pressure = 101325.0
        except Exception as exc:
            print(f"Could not set operating pressure automatically: {exc}")

        try:
            solver.settings.setup.models.viscous.model = "k-omega"
            solver.settings.setup.models.viscous.k_omega_model = "sst"
        except Exception as exc:
            print(f"Could not set SST k-omega automatically: {exc}")

        drag_name = "drag_plate"
        solver.settings.solution.report_definitions.drag[drag_name] = {
            "zones": [plate_wall],
            "force_vector": [1, 0, 0],
        }
        solver.settings.solution.monitor.report_files.create(name=drag_name)
        solver.settings.solution.monitor.report_files[drag_name] = {
            "file_name": str(drag_file_path),
            "report_defs": [drag_name],
        }

        try:
            solver.settings.solution.initialization.initialization_type = "hybrid"
            solver.settings.solution.initialization.initialize()
        except Exception as exc:
            print(f"Could not initialize solver: {exc}")

        # Iterationen starten (API-kompatibel fuer verschiedene PyFluent-Versionen)
        try:
            solver.settings.solution.run_calculation.calculate(iter_count=iterations)
        except Exception:
            try:
                solver.settings.solution.run_calculation.iterate(iter_count=iterations)
            except Exception:
                try:
                    solver.settings.solution.run_calculation.iterate(number_of_iterations=iterations)
                except Exception:
                    # Fallback: TUI-Befehl
                    print(f"Verwende TUI-Fallback: /solve/iterate {iterations}")
                    solver.tui.solve.iterate(iterations)
        solver.settings.file.write_case_data(file_name=str(output_path))
    finally:
        solver.exit()

    history = read_drag_history(drag_file_path)
    iteration, drag_per_depth = history[-1]
    total_drag = drag_per_depth * params.sign_width_m
    c_d = drag_per_depth / (params.dynamic_pressure_pa * params.plate_height_m)

    lines = [
        f"project = {params.project}",
        f"iteration = {iteration}",
        f"drag_2d_per_depth_N_per_m = {drag_per_depth:.6f}",
        f"sign_width_m = {params.sign_width_m:.6f}",
        f"total_drag_N = {total_drag:.6f}",
        f"dynamic_pressure_Pa = {params.dynamic_pressure_pa:.6f}",
        f"hT_m = {params.hT_m:.6f}",
        f"plate_height_m = {params.plate_height_m:.6f}",
        f"cD = {c_d:.6f}",
    ]
    write_summary(summary_path, lines)
    print("\n".join(lines))
