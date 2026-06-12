from __future__ import annotations

import argparse
from pathlib import Path

from fluent_env import ensure_awp_root
from aufgabe1_params import get_params
from postprocess_drag import read_drag_history, write_summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Load a 2D mesh and set up the Aufgabe 1.1 Fluent solver case."
    )
    parser.add_argument("--project", type=int, default=27, help="Project number")
    parser.add_argument("--mesh", type=Path, required=True)
    parser.add_argument("--cores", type=int, default=2)
    parser.add_argument("--iterations", type=int, default=500)
    parser.add_argument("--inlet", default="inlet")
    parser.add_argument("--outlet", default="outlet")
    parser.add_argument("--plate-wall", default="plate_wall")
    parser.add_argument("--top", default="top")
    parser.add_argument("--bottom", default="bottom")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("Aufgabe1/plate_2d_solution.cas.h5"),
    )
    parser.add_argument(
        "--drag-file",
        type=Path,
        default=Path("Aufgabe1/out/drag_plate.out"),
    )
    parser.add_argument(
        "--summary",
        type=Path,
        default=Path("Aufgabe1/out/drag_summary.txt"),
    )
    return parser.parse_args()


def set_velocity_inlet(session, name: str, velocity: float) -> None:
    inlet = session.settings.setup.boundary_conditions.velocity_inlet[name]
    state = inlet.get_state()

    # PyFluent key names vary a little between generated API versions.
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


def main() -> None:
    ensure_awp_root()

    import ansys.fluent.core as pyfluent

    args = parse_args()
    params = get_params(args.project)

    if not args.mesh.exists():
        raise FileNotFoundError(args.mesh)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.drag_file.parent.mkdir(parents=True, exist_ok=True)
    if args.drag_file.exists():
        args.drag_file.unlink()

    solver = pyfluent.launch_fluent(
        mode=pyfluent.FluentMode.SOLVER,
        precision=pyfluent.Precision.DOUBLE,
        dimension=pyfluent.Dimension.TWO,
        processor_count=args.cores,
    )

    try:
        mesh_file = str(args.mesh.resolve())
        if args.mesh.suffix == ".msh" or args.mesh.name.endswith(".msh.h5"):
            solver.settings.file.read_mesh(file_name=mesh_file)
        else:
            solver.settings.file.read_case(file_name=mesh_file)
        solver.settings.mesh.check()

        bc = solver.settings.setup.boundary_conditions
        try:
            bc.set_zone_type(zone_list=[args.inlet], new_type="velocity-inlet")
            bc.set_zone_type(zone_list=[args.outlet], new_type="pressure-outlet")
            bc.set_zone_type(zone_list=[args.plate_wall], new_type="wall")
            bc.set_zone_type(zone_list=[args.top, args.bottom], new_type="symmetry")
        except Exception as exc:
            print(f"Boundary zone types were not changed automatically: {exc}")

        set_velocity_inlet(solver, args.inlet, params.wind_speed_mps)
        bc.pressure_outlet[args.outlet].momentum.gauge_pressure = 0.0
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
            print("Set the turbulence model manually in Fluent if needed.")

        drag_name = "drag_plate"
        solver.settings.solution.report_definitions.drag[drag_name] = {
            "zones": [args.plate_wall],
            "force_vector": [1, 0, 0],
        }
        solver.settings.solution.monitor.report_files.create(name=drag_name)
        solver.settings.solution.monitor.report_files[drag_name] = {
            "file_name": str(args.drag_file),
            "report_defs": [drag_name],
        }

        solver.settings.solution.initialization.hybrid_initialize()
        solver.settings.solution.run_calculation.iterate(iter_count=args.iterations)
        solver.settings.file.write(file_type="case-data", file_name=str(args.output))

        print(f"Wrote solved case/data: {args.output}")
        history = read_drag_history(args.drag_file)
        iteration, monitor_c_d = history[-1]
        drag_per_depth = monitor_c_d * params.dynamic_pressure_pa * params.plate_height_m
        total_drag = drag_per_depth * params.sign_width_m
        summary_lines = [
            f"project = {params.project}",
            f"iteration = {iteration}",
            f"drag_monitor_cD = {monitor_c_d:.6f}",
            f"drag_2d_per_depth_N_per_m = {drag_per_depth:.6f}",
            f"sign_width_m = {params.sign_width_m:.6f}",
            f"total_drag_N = {total_drag:.6f}",
            f"dynamic_pressure_Pa = {params.dynamic_pressure_pa:.6f}",
            f"hT_m = {params.hT_m:.6f}",
            f"plate_height_m = {params.plate_height_m:.6f}",
            f"cD = {monitor_c_d:.6f}",
        ]
        write_summary(args.summary, summary_lines)
        print("\n".join(summary_lines))
        print(f"Wrote drag report: {args.drag_file}")
        print(f"Wrote summary: {args.summary}")
    finally:
        solver.exit()


if __name__ == "__main__":
    main()
