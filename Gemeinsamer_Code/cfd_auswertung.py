"""Gemeinsamer_Code/cfd_auswertung.py

Nachbearbeitungsfunktionen für die CFD-Rechnung (Kraftreports, Druckverteilungsplots,
Widerstandskonvergenz und Mesh-Visualisierung).
"""
from __future__ import annotations

import re
from pathlib import Path
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

FORCE_LINE_RE = re.compile(
    r"^Net\s+"
    r"(?P<pressure>[-+0-9.eE]+)\s+"
    r"(?P<viscous>[-+0-9.eE]+)\s+"
    r"(?P<total>[-+0-9.eE]+)\s+"
    r"(?P<pressure_coeff>[-+0-9.eE]+)\s+"
    r"(?P<viscous_coeff>[-+0-9.eE]+)\s+"
    r"(?P<total_coeff>[-+0-9.eE]+)"
)


def read_drag_history(path: Path) -> list[tuple[int, float]]:
    values: list[tuple[int, float]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        parts = line.strip().split()
        if len(parts) != 2:
            continue
        try:
            iteration = int(parts[0])
            drag = float(parts[1])
        except ValueError:
            continue
        values.append((iteration, drag))
    if not values:
        raise ValueError(f"No drag values found in {path}")
    return values


def write_summary(path: Path, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_force_report(path: Path) -> dict[str, float]:
    matches = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        match = FORCE_LINE_RE.search(line.strip())
        if match:
            matches.append({key: float(value) for key, value in match.groupdict().items()})
    if not matches:
        raise ValueError(f"Could not parse force report: {path}")
    return matches[-1]


def write_force_report(solver, path: Path, wall: str) -> dict[str, float]:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    solver.settings.results.report.forces(
        write_to_file=True,
        file_name=str(path),
        direction_vector=[1, 0, 0],
        wall_zones=[wall],
        option="forces",
    )
    return parse_force_report(path)


def export_contours(solver, out_dir: Path) -> None:
    picture = solver.settings.results.graphics.picture
    picture.use_window_resolution = False
    picture.x_resolution = 1600
    picture.y_resolution = 900
    solver.settings.results.graphics.views.camera.set_state(
        {
            "position": [2.0, 0.0, 28.0],
            "target": [2.0, 0.0, 0.0],
            "up_vector": [0.0, 1.0, 0.0],
            "field": [8.0, 4.5],
            "projection": "orthographic",
        }
    )

    contour_defs = [
        ("pressure_contour", "pressure", out_dir / "contour_pressure.png"),
        ("velocity_contour", "velocity-magnitude", out_dir / "contour_velocity.png"),
    ]
    contours = solver.settings.results.graphics.contour
    for name, field, path in contour_defs:
        if name not in contours:
            contours.create(name=name)
        contours[name].set_state(
            {
                "field": field,
                "surfaces_list": ["interior"],
                "range_option": {
                    "option": "auto-range-on",
                    "auto_range_on": {"global_range": True},
                },
                "options": {
                    "filled": True,
                    "node_values": True,
                    "boundary_values": True,
                    "contour_lines": False,
                },
                "coloring": {"option": "smooth", "smooth": True},
            }
        )
        contours.display(object_name=name)
        picture.save_picture(file_name=str(path))


def get_wall_pressure_data(solver, params, wall: str) -> pd.DataFrame:
    fd = solver.fields.field_data
    fields = {
        name: fd.get_scalar_field_data(field_name=name, surfaces=[wall])[wall]
        for name in [
            "x-coordinate",
            "y-coordinate",
            "pressure",
            "wall-shear",
            "x-wall-shear",
            "y-wall-shear",
        ]
    }
    frame = pd.DataFrame(
        {
            "x_m": np.asarray(fields["x-coordinate"], dtype=float),
            "y_m": np.asarray(fields["y-coordinate"], dtype=float),
            "pressure_Pa": np.asarray(fields["pressure"], dtype=float),
            "wall_shear_Pa": np.asarray(fields["wall-shear"], dtype=float),
            "x_wall_shear_Pa": np.asarray(fields["x-wall-shear"], dtype=float),
            "y_wall_shear_Pa": np.asarray(fields["y-wall-shear"], dtype=float),
        }
    )
    frame["cp_manual"] = frame["pressure_Pa"] / params.dynamic_pressure_pa

    domain = params.domain_m
    tol = params.sign_thickness_m * 0.35
    front = np.isclose(frame["x_m"], domain["plate_x_min"], atol=tol)
    back = np.isclose(frame["x_m"], domain["plate_x_max"], atol=tol)
    frame["side"] = np.where(front, "front_upstream", np.where(back, "back_downstream", "thin_edge"))
    return frame


def plot_pressure_distribution(frame: pd.DataFrame, path: Path) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(10, 4), constrained_layout=True)
    colors = {"front_upstream": "#1f77b4", "back_downstream": "#d62728"}
    labels = {"front_upstream": "Vorderseite", "back_downstream": "Rückseite"}

    for side in ["front_upstream", "back_downstream"]:
        data = frame[frame["side"] == side].sort_values("y_m")
        axes[0].plot(data["y_m"], data["pressure_Pa"], label=labels[side], color=colors[side])
        axes[1].plot(data["y_m"], data["cp_manual"], label=labels[side], color=colors[side])

    axes[0].set_xlabel("y [m]")
    axes[0].set_ylabel("statischer Druck p [Pa]")
    axes[0].grid(True, alpha=0.3)
    axes[0].legend()

    axes[1].set_xlabel("y [m]")
    axes[1].set_ylabel("Druckbeiwert Cp = p/q")
    axes[1].grid(True, alpha=0.3)
    axes[1].legend()

    fig.savefig(path, dpi=220)
    plt.close(fig)


def read_drag_monitor(path: Path) -> pd.DataFrame:
    values = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        parts = line.split()
        if len(parts) != 2:
            continue
        try:
            values.append((int(parts[0]), float(parts[1])))
        except ValueError:
            continue
    return pd.DataFrame(values, columns=["iteration", "fluent_default_coefficient"])


def plot_drag_convergence(drag_file: Path, force_report: dict[str, float], path: Path) -> None:
    if not drag_file.exists():
        return
    data = read_drag_monitor(drag_file)
    if data.empty:
        return
    scale = force_report["total"] / data["fluent_default_coefficient"].iloc[-1]
    data["drag_N_per_m"] = data["fluent_default_coefficient"] * scale

    fig, ax = plt.subplots(figsize=(7, 4), constrained_layout=True)
    ax.plot(data["iteration"], data["drag_N_per_m"], color="#2ca02c")
    ax.set_xlabel("Iteration")
    ax.set_ylabel("Widerstandskraft pro Tiefe [N/m]")
    ax.grid(True, alpha=0.3)
    fig.savefig(path, dpi=220)
    plt.close(fig)


def plot_mesh_from_gmsh(gmsh_mesh: Path, overview_path: Path, zoom_path: Path) -> None:
    try:
        import meshio
        from matplotlib.collections import LineCollection
    except Exception:
        return
    if not gmsh_mesh.exists():
        return

    mesh = meshio.read(gmsh_mesh)
    points = mesh.points[:, :2]
    segments = []
    for block in mesh.cells:
        if block.type == "line":
            segments.extend(points[block.data])
        elif block.type in {"triangle", "quad"}:
            for cell in block.data:
                for idx, node in enumerate(cell):
                    segments.append(points[[node, cell[(idx + 1) % len(cell)]]])
    if not segments:
        return

    for target, limits, linewidth in [
        (overview_path, (-10.5, 30.5, -10.5, 10.5), 0.03),
        (zoom_path, (-0.08, 0.20, -0.62, 0.62), 0.15),
    ]:
        fig, ax = plt.subplots(figsize=(8, 4), constrained_layout=True)
        collection = LineCollection(segments, colors="#202020", linewidths=linewidth)
        ax.add_collection(collection)
        ax.set_xlim(limits[0], limits[1])
        ax.set_ylim(limits[2], limits[3])
        ax.set_aspect("equal", adjustable="box")
        ax.set_xlabel("x [m]")
        ax.set_ylabel("y [m]")
        ax.grid(True, alpha=0.2)
        fig.savefig(target, dpi=220)
        plt.close(fig)


def write_summary_report(path: Path, params, force_report: dict[str, float]) -> None:
    pressure_total = force_report["pressure"] * params.sign_width_m
    viscous_total = force_report["viscous"] * params.sign_width_m
    total = force_report["total"] * params.sign_width_m
    cd = force_report["total"] / (params.dynamic_pressure_pa * params.plate_height_m)
    cd_pressure = force_report["pressure"] / (params.dynamic_pressure_pa * params.plate_height_m)
    cd_viscous = force_report["viscous"] / (params.dynamic_pressure_pa * params.plate_height_m)
    viscous_fraction_abs = abs(force_report["viscous"]) / abs(force_report["total"])

    lines = [
        f"project = {params.project}",
        f"hT_m = {params.hT_m:.6f}",
        f"plate_height_m = {params.plate_height_m:.6f}",
        f"sign_width_m = {params.sign_width_m:.6f}",
        f"wind_speed_m_per_s = {params.wind_speed_mps:.6f}",
        f"dynamic_pressure_Pa = {params.dynamic_pressure_pa:.6f}",
        f"pressure_drag_2d_N_per_m = {force_report['pressure']:.6f}",
        f"viscous_drag_2d_N_per_m = {force_report['viscous']:.6f}",
        f"total_drag_2d_N_per_m = {force_report['total']:.6f}",
        f"pressure_drag_total_N = {pressure_total:.6f}",
        f"viscous_drag_total_N = {viscous_total:.6f}",
        f"total_drag_N = {total:.6f}",
        f"cD_pressure = {cd_pressure:.6f}",
        f"cD_viscous = {cd_viscous:.6f}",
        f"cD_total = {cd:.6f}",
        f"viscous_fraction_abs = {viscous_fraction_abs:.8f}",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
