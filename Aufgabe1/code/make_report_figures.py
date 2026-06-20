"""Berichtsfiguren-Generator fuer Aufgabe 1 und Aufgabe 2.

Dieses Skript erzeugt alle im Bericht (bericht_aufgabe1.tex) eingebundenen
Abbildungen aus den kuratierten Daten in Aufgabe1/data und Aufgabe2/data.

Aufruf:
  python Aufgabe1/code/make_report_figures.py

Erzeugte Bilder werden nach Aufgabe1/figures/ und Aufgabe2/figures/ geschrieben.
Fuer die CFD-Kontur-/Netzbilder wird das Kommandozeilentool 'h5dump' benoetigt.
"""
from __future__ import annotations

import csv
import math
import re
import shutil
import subprocess
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.tri as mtri
import numpy as np
import pandas as pd
from matplotlib.collections import LineCollection
from PIL import Image, ImageDraw, ImageFont

from parse_plate_structural_results import parse_apdl_mesh


ROOT = Path(__file__).resolve().parents[2]
DATA1 = ROOT / "Aufgabe1" / "data"
FIG1 = ROOT / "Aufgabe1" / "figures"
DATA2 = ROOT / "Aufgabe2" / "data"
FIG2 = ROOT / "Aufgabe2" / "figures"
SCREEN2 = ROOT / "Aufgabe2" / "screenshots"
REPORT_DPI = 420


def _read_h5dump_array(path: Path, dataset: str) -> np.ndarray:
    text = subprocess.check_output(["h5dump", "-A", "0", "-y", "-w", "0", "-d", dataset, str(path)], text=True)
    data = text.split("DATA {", 1)[1].rsplit("}", 1)[0]
    return np.asarray([float(value) for value in re.findall(r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[Ee][-+]?\d+)?", data)])


def _read_gmsh_cell_centers(path: Path) -> np.ndarray:
    text = path.read_text(encoding="utf-8", errors="replace").splitlines()
    nodes: dict[int, tuple[float, float]] = {}

    i = text.index("$Nodes") + 1
    _, total_nodes, _, _ = map(int, text[i].split())
    i += 1
    read_nodes = 0
    while read_nodes < total_nodes:
        _, _, _, num_nodes = map(int, text[i].split())
        i += 1
        tags = [int(text[i + j]) for j in range(num_nodes)]
        i += num_nodes
        for tag in tags:
            x, y, *_ = map(float, text[i].split())
            nodes[tag] = (x, y)
            i += 1
        read_nodes += num_nodes

    centers: list[tuple[float, float]] = []
    i = text.index("$Elements") + 1
    _, total_elements, _, _ = map(int, text[i].split())
    i += 1
    read_elements = 0
    while read_elements < total_elements:
        _, _, element_type, num_elements = map(int, text[i].split())
        i += 1
        for _ in range(num_elements):
            parts = list(map(int, text[i].split()))
            if element_type in {2, 3}:
                xy = np.asarray([nodes[tag] for tag in parts[1:]], dtype=float)
                centers.append(tuple(xy.mean(axis=0)))
            i += 1
        read_elements += num_elements
    return np.asarray(centers)


def save_clean_velocity() -> None:
    target = FIG1 / "contour_velocity_report.png"
    data_path = DATA1 / "plate_2d_solution.dat.h5"
    mesh_path = DATA1 / "plate_2d_gmsh.msh"
    if not data_path.exists() or not mesh_path.exists():
        return

    centers = _read_gmsh_cell_centers(mesh_path)
    u = _read_h5dump_array(data_path, "/results/1/phase-1/cells/SV_U/1")
    v = _read_h5dump_array(data_path, "/results/1/phase-1/cells/SV_V/1")
    speed = np.hypot(u, v)

    keep = (
        (centers[:, 0] >= -10.0)
        & (centers[:, 0] <= 30.0)
        & (centers[:, 1] >= -10.0)
        & (centers[:, 1] <= 10.0)
    )
    x, y, z = centers[keep, 0], centers[keep, 1], np.clip(speed[keep], 0.0, 45.0)

    fig, ax = plt.subplots(figsize=(8.4, 4.6), constrained_layout=True)
    levels = np.linspace(0.0, 45.0, 46)
    contour = ax.tricontourf(x, y, z, levels=levels, cmap="turbo", extend="max")
    ax.add_patch(plt.Rectangle((-0.0015, -1.0), 0.003, 2.0, facecolor="#111827", edgecolor="white", linewidth=0.7, zorder=5))
    ax.set_xlim(-10.0, 30.0)
    ax.set_ylim(-10.0, 10.0)
    ax.set_aspect("equal")
    ax.set_xlabel("x [m]")
    ax.set_ylabel("y [m]")
    ax.set_title("Geschwindigkeitsbetrag aus Fluent")
    cbar = fig.colorbar(contour, ax=ax, shrink=0.9, pad=0.012)
    cbar.set_label("|v| [m/s]")
    fig.savefig(target, dpi=REPORT_DPI)
    plt.close(fig)


def save_pressure_distribution_single() -> None:
    source = DATA1 / "wall_pressure.csv"
    target = FIG1 / "pressure_distribution.png"
    if not source.exists():
        return

    frame = pd.read_csv(source)
    fig, ax = plt.subplots(figsize=(7.2, 4.0), constrained_layout=True)
    for side, color, label in [
        ("front_upstream", "#1f77b4", "Vorderseite"),
        ("back_downstream", "#d62728", "Rückseite"),
    ]:
        data = frame[frame["side"] == side].sort_values("y_m")
        if not data.empty:
            ax.plot(data["y_m"], data["pressure_Pa"], label=label, color=color, linewidth=1.8)
    ax.set_xlabel("y [m]")
    ax.set_ylabel("statischer Druck p [Pa]")
    ax.set_title("Druckverlauf an Vorder- und Rückseite")
    ax.grid(True, alpha=0.3)
    ax.legend()
    fig.savefig(target, dpi=REPORT_DPI)
    plt.close(fig)


def save_drag_convergence() -> None:
    drag_file = DATA1 / "drag_plate.out"
    summary_file = DATA1 / "drag_summary.txt"
    target = FIG1 / "drag_convergence.png"
    if not drag_file.exists() or not summary_file.exists():
        return

    values: list[tuple[int, float]] = []
    for line in drag_file.read_text(encoding="utf-8", errors="replace").splitlines():
        parts = line.split()
        if len(parts) != 2:
            continue
        try:
            values.append((int(parts[0]), float(parts[1])))
        except ValueError:
            continue
    if not values:
        return

    total_2d = None
    for line in summary_file.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("total_drag_2d_N_per_m"):
            total_2d = float(line.split("=", 1)[1])
            break
    if total_2d is None:
        return

    data = pd.DataFrame(values, columns=["iteration", "monitor"])
    data["drag_N_per_m"] = data["monitor"] * (total_2d / data["monitor"].iloc[-1])

    fig, ax = plt.subplots(figsize=(7.2, 4.0), constrained_layout=True)
    ax.plot(data["iteration"], data["drag_N_per_m"], color="#2ca02c", linewidth=1.8)
    ax.axhline(total_2d, color="#b00020", linestyle="--", linewidth=1.2, label=f"Endwert {total_2d:.1f} N/m")
    ax.set_xlabel("Iteration")
    ax.set_ylabel("Widerstandskraft pro Tiefe [N/m]")
    ax.set_title("Konvergenz der Widerstandskraft")
    ax.grid(True, alpha=0.3)
    ax.legend()
    fig.savefig(target, dpi=REPORT_DPI)
    plt.close(fig)


def _read_gmsh_nodes_and_triangles(path: Path) -> tuple[np.ndarray, np.ndarray]:
    text = path.read_text(encoding="utf-8", errors="replace").splitlines()
    nodes: dict[int, tuple[float, float]] = {}
    triangles: list[list[int]] = []

    i = text.index("$Nodes") + 1
    _, total_nodes, _, _ = map(int, text[i].split())
    i += 1
    read_nodes = 0
    while read_nodes < total_nodes:
        _, _, _, num_nodes = map(int, text[i].split())
        i += 1
        tags = [int(text[i + j]) for j in range(num_nodes)]
        i += num_nodes
        for tag in tags:
            x, y, *_ = map(float, text[i].split())
            nodes[tag] = (x, y)
            i += 1
        read_nodes += num_nodes

    i = text.index("$Elements") + 1
    _, total_elements, _, _ = map(int, text[i].split())
    i += 1
    read_elements = 0
    while read_elements < total_elements:
        _, _, element_type, num_elements = map(int, text[i].split())
        i += 1
        for _ in range(num_elements):
            parts = list(map(int, text[i].split()))
            if element_type == 2:
                triangles.append(parts[1:4])
            i += 1
        read_elements += num_elements

    points = np.full((max(nodes) + 1, 2), np.nan)
    for tag, xy in nodes.items():
        points[tag] = xy
    return points, np.asarray(triangles, dtype=int)


def save_cfd_mesh_overview() -> None:
    mesh_path = DATA1 / "plate_2d_gmsh.msh"
    target = FIG1 / "mesh_overview_report.png"
    if not mesh_path.exists():
        return
    points, triangles = _read_gmsh_nodes_and_triangles(mesh_path)
    edges = set()
    for tri in triangles:
        for a, b in ((tri[0], tri[1]), (tri[1], tri[2]), (tri[2], tri[0])):
            edges.add(tuple(sorted((int(a), int(b)))))
    segments = [points[list(edge)] for edge in edges]

    fig, ax = plt.subplots(figsize=(8.2, 4.1), constrained_layout=True)
    ax.add_collection(LineCollection(segments, colors="#4b5563", linewidths=0.035, alpha=0.65))
    ax.add_patch(plt.Rectangle((-0.0015, -1.0), 0.003, 2.0, color="#b91c1c", zorder=5))
    ax.set_xlim(-10.0, 30.0)
    ax.set_ylim(-10.0, 10.0)
    ax.set_aspect("equal")
    ax.set_xlabel("x [m]")
    ax.set_ylabel("y [m]")
    ax.set_title("CFD-Netz: gesamte Domain mit Nachlaufverfeinerung")
    ax.grid(True, color="#cbd5e1", linewidth=0.35, alpha=0.55)
    fig.savefig(target, dpi=REPORT_DPI)
    plt.close(fig)


def save_kerb_convergence() -> None:
    source = DATA2 / "kerb_convergence.csv"
    target = FIG2 / "kerb_convergence.png"
    if not source.exists():
        return
    data = pd.read_csv(source).sort_values("local_mesh_mm", ascending=False)
    ref = float(data.loc[data["local_mesh_mm"].isin([3.0, 2.0, 1.0]), "sigma_max_MPa"].mean())

    fig, ax = plt.subplots(figsize=(7.2, 4.0), constrained_layout=True)
    ax.plot(data["local_mesh_mm"], data["sigma_max_MPa"], marker="o", color="#1f77b4", linewidth=1.8, label="Netzstudie")
    ax.axhline(ref, color="#b00020", linestyle="--", linewidth=1.5, label=rf"$\sigma_{{max}}\approx {ref:.3f}$ MPa")
    ax.set_xlabel("lokale Netzgröße am Lochrand [mm]")
    ax.set_ylabel(r"$\sigma_{max}$ [MPa]")
    ax.set_title("Aufgabe 2: Konvergenz der Maximalspannung")
    ax.invert_xaxis()
    ax.grid(True, alpha=0.3)
    ax.legend()
    fig.savefig(target, dpi=REPORT_DPI)
    plt.close(fig)


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for candidate in ["/usr/share/fonts/TTF/DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]:
        path = Path(candidate)
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


def _load_report_image(path: Path) -> Image.Image:
    return Image.open(path).convert("RGB")


def _support_panel(images: list[tuple[str, Path]], target: Path) -> None:
    cell_w, cell_h, label_h = 740, 560, 54
    canvas = Image.new("RGB", (3 * cell_w, cell_h + label_h), "white")
    draw = ImageDraw.Draw(canvas)
    font = _font(34)

    for idx, (label, path) in enumerate(images):
        x0 = idx * cell_w
        image = _load_report_image(path)
        image.thumbnail((cell_w - 18, cell_h - 18), Image.Resampling.LANCZOS)
        ix = x0 + (cell_w - image.width) // 2
        iy = label_h + (cell_h - image.height) // 2
        draw.text((x0 + 12, 8), label, fill="#111827", font=font)
        canvas.paste(image, (ix, iy))
        draw.rectangle((x0 + 6, label_h + 6, x0 + cell_w - 7, label_h + cell_h - 7), outline="#cbd5e1", width=2)

    target.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(target)


def save_plate_singularity_mesh_panel() -> None:
    images = [
        ("h = 10 mm", ROOT / "Aufgabe1" / "out" / "plate_singularity_study" / "h10" / "plate_point_mesh_preview.png"),
        ("h = 2 mm", ROOT / "Aufgabe1" / "out" / "plate_singularity_study" / "h2" / "plate_point_mesh_preview.png"),
        ("h = 1 mm", ROOT / "Aufgabe1" / "out" / "plate_singularity_study" / "h1" / "plate_point_mesh_preview.png"),
    ]
    if not all(path.exists() for _, path in images):
        return
    _support_panel(images, FIG1 / "plate_singularity_mesh_panel.png")


def _plate_singularity_zoom_limits() -> tuple[float, float, float, float]:
    hinge_upper_y = 1000.0
    zoom_radius_mm = 50.0
    x_center = 500.0
    return (
        max(0.0, x_center - zoom_radius_mm),
        min(3000.0, x_center + zoom_radius_mm),
        max(0.0, hinge_upper_y - zoom_radius_mm),
        min(2000.0, hinge_upper_y + zoom_radius_mm),
    )


def _save_plate_stress_zoom(case_dir: Path, label: str) -> Path | None:
    stress_csv = case_dir / "plate_stress_area.csv"
    apdl_path = case_dir / "plate_structural.inp"
    target = case_dir / "plate_stress_eqv_zoom.png"
    if not stress_csv.exists() or not apdl_path.exists():
        return None

    nodes, elements = parse_apdl_mesh(apdl_path)
    stress_data = pd.read_csv(stress_csv)
    stress_by_node = dict(zip(stress_data["node"].astype(int), stress_data["seqv_MPa"].astype(float)))
    node_ids = sorted(nodes)
    node_index = {node_id: index for index, node_id in enumerate(node_ids)}
    points = np.asarray([nodes[node_id] for node_id in node_ids], dtype=float)
    values = np.asarray([stress_by_node.get(node_id, 0.0) for node_id in node_ids], dtype=float)

    triangles: list[list[int]] = []
    for element in elements:
        unique_nodes = tuple(dict.fromkeys(element))
        if len(unique_nodes) < 3:
            continue
        triangles.append([node_index[node_id] for node_id in unique_nodes[:3]])
    triangulation = mtri.Triangulation(points[:, 0], points[:, 1], np.asarray(triangles, dtype=int))

    x_min, x_max, y_min, y_max = _plate_singularity_zoom_limits()
    tri_centers_x = points[triangulation.triangles, 0].mean(axis=1)
    tri_centers_y = points[triangulation.triangles, 1].mean(axis=1)
    mask = (
        (tri_centers_x < x_min)
        | (tri_centers_x > x_max)
        | (tri_centers_y < y_min)
        | (tri_centers_y > y_max)
    )
    triangulation.set_mask(mask)

    levels = np.linspace(0.0, 1300.0, 14)
    fig, ax = plt.subplots(figsize=(4.6, 5.2), constrained_layout=True)
    contour = ax.tricontourf(
        triangulation,
        np.clip(values, levels[0], levels[-1]),
        levels=levels,
        cmap="turbo",
        extend="max",
    )
    ax.tricontour(
        triangulation,
        values,
        levels=[190.0 / 1.8],
        colors="white",
        linewidths=0.8,
    )
    x, y = 500.0, 1000.0
    ax.add_patch(
        plt.Circle(
            (x, y),
            200.0,
            fill=False,
            edgecolor="#64748b",
            linewidth=0.8,
            linestyle="--",
            alpha=0.7,
        )
    )
    ax.plot(
        x,
        y,
        marker="o",
        markersize=4.0,
        color="#111827",
        markeredgecolor="white",
        markeredgewidth=0.5,
    )
    ax.set_xlim(x_min, x_max)
    ax.set_ylim(y_min, y_max)
    ax.set_aspect("equal")
    ax.set_xlabel("x [mm]")
    ax.set_ylabel("y [mm]")
    ax.set_title("Vergleichsspannung")
    cbar = fig.colorbar(contour, ax=ax, shrink=0.82, pad=0.012)
    cbar.set_label(r"$\sigma_v$ [MPa]")
    target.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(target, dpi=320)
    plt.close(fig)
    return target


def _singularity_stress_label(mesh_mm: float) -> str:
    source = DATA1 / "plate_singularity_study.csv"
    base = f"h = {mesh_mm:g} mm"
    if not source.exists():
        return base
    data = pd.read_csv(source)
    data["local_refinement_mm"] = pd.to_numeric(data["local_refinement_mm"], errors="coerce")
    data["max_eqv_stress_MPa"] = pd.to_numeric(data["max_eqv_stress_MPa"], errors="coerce")
    row = data[np.isclose(data["local_refinement_mm"], mesh_mm)]
    if row.empty or pd.isna(row.iloc[0]["max_eqv_stress_MPa"]):
        return base
    return f"{base}, σmax = {row.iloc[0]['max_eqv_stress_MPa']:.1f} MPa"


def save_plate_singularity_stress_panel() -> None:
    cases = [
        (_singularity_stress_label(10.0), ROOT / "Aufgabe1" / "out" / "plate_singularity_study" / "h10"),
        (_singularity_stress_label(2.0), ROOT / "Aufgabe1" / "out" / "plate_singularity_study" / "h2"),
        (_singularity_stress_label(1.0), ROOT / "Aufgabe1" / "out" / "plate_singularity_study" / "h1"),
    ]
    images = [(label, _save_plate_stress_zoom(case_dir, label)) for label, case_dir in cases]
    if not all(path is not None and path.exists() for _, path in images):
        return
    _support_panel([(label, path) for label, path in images if path is not None], FIG1 / "plate_singularity_stress_panel.png")


def _truss_comparison_source() -> Path | None:
    candidates = [
        DATA1 / "truss_comparison_python_ansys.csv",
        ROOT / "Aufgabe1" / "out" / "truss_comparison_python_ansys.csv",
        ROOT / "_archive_unused" / "Aufgabe1" / "out" / "truss_comparison_python_ansys.csv",
    ]
    return next((path for path in candidates if path.exists()), None)


def _kind_label(kind: str) -> str:
    return {
        "vertical": "vertikal",
        "horizontal": "horizontal",
        "diagonal": "diagonal",
    }.get(kind, kind)


def _first_existing(paths: list[Path]) -> Path | None:
    return next((path for path in paths if path.exists()), None)


def _parse_xy(text: str) -> tuple[float, float]:
    values = [float(value) for value in re.findall(r"[-+]?\d+(?:\.\d+)?", text)]
    if len(values) < 2:
        raise ValueError(f"Could not parse coordinate pair: {text}")
    return values[0], values[1]


def _read_apdl_summary(path: Path | None) -> dict[str, float]:
    if path is None:
        return {}
    values: dict[str, float] = {}
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", maxsplit=1)
        try:
            values[key.strip()] = float(value)
        except ValueError:
            continue
    return values


def save_truss_ansys_result_plot() -> None:
    forces_path = _first_existing(
        [
            DATA1 / "truss_apdl_element_forces.csv",
            ROOT / "Aufgabe1" / "out" / "truss_apdl_element_forces.csv",
            ROOT / "_archive_unused" / "Aufgabe1" / "out" / "truss_apdl_element_forces.csv",
        ]
    )
    index_path = _first_existing(
        [
            DATA1 / "truss_index_table.csv",
            ROOT / "Aufgabe1" / "out" / "truss_index_table.csv",
            ROOT / "_archive_unused" / "Aufgabe1" / "out" / "truss_index_table.csv",
        ]
    )
    summary_path = _first_existing(
        [
            DATA1 / "truss_apdl_summary.txt",
            ROOT / "Aufgabe1" / "out" / "truss_apdl_summary.txt",
            ROOT / "_archive_unused" / "Aufgabe1" / "out" / "truss_apdl_summary.txt",
        ]
    )
    if forces_path is None or index_path is None:
        return

    forces = pd.read_csv(forces_path)
    index = pd.read_csv(index_path)
    if forces.empty or index.empty:
        return

    forces.to_csv(DATA1 / "truss_apdl_element_forces.csv", index=False)
    index.to_csv(DATA1 / "truss_index_table.csv", index=False)
    if summary_path is not None:
        (DATA1 / "truss_apdl_summary.txt").write_text(
            summary_path.read_text(encoding="utf-8", errors="ignore"),
            encoding="utf-8",
        )

    merged = index.merge(forces[["name", "axial_N", "stress_MPa"]], left_on="element", right_on="name")
    max_force = float(merged["axial_N"].abs().max())

    # Read displacements if available
    disp_path = _first_existing([DATA1 / "truss_displacements.csv", Path("Aufgabe1/out/truss_displacements.csv")])
    disp_dict = {}
    if disp_path and disp_path.exists():
        disp_df = pd.read_csv(disp_path)
        for _, r in disp_df.iterrows():
            disp_dict[r["node"]] = (float(r["ux_m"]), float(r["uy_m"]))

    # Determine scaling
    max_disp = 0.0
    for uxy in disp_dict.values():
        max_disp = max(max_disp, math.hypot(uxy[0], uxy[1]))
    scale = 0.15 / max_disp if max_disp > 0 else 1.0

    fig, ax = plt.subplots(figsize=(8, 10), dpi=REPORT_DPI)
    cmap = plt.cm.coolwarm
    norm = plt.Normalize(vmin=-max_force, vmax=max_force)

    for _, row in merged.iterrows():
        node_i_name = row["node_i"]
        node_j_name = row["node_j"]
        x_i, y_i = _parse_xy(str(row["coordinate_i_m"]))
        x_j, y_j = _parse_xy(str(row["coordinate_j_m"]))
        
        dx_i, dy_i = disp_dict.get(node_i_name, (0.0, 0.0))
        dx_j, dy_j = disp_dict.get(node_j_name, (0.0, 0.0))

        axial = float(row["axial_N"])
        color = cmap(norm(axial))
        
        # Unverformte Lage (grau, gestrichelt)
        ax.plot([x_i, x_j], [y_i, y_j], color="#b0b5b9", linewidth=1.0, linestyle="--", zorder=1)
        
        # Verformte Lage (farbig)
        ax.plot(
            [x_i + scale * dx_i, x_j + scale * dx_j],
            [y_i + scale * dy_i, y_j + scale * dy_j],
            color=color,
            linewidth=2.0,
            zorder=2,
        )
        
        # Elementname am Mittelpunkt anzeigen
        mid_x = (x_i + scale * dx_i + x_j + scale * dx_j) / 2.0
        mid_y = (y_i + scale * dy_i + y_j + scale * dy_j) / 2.0
        element_name = row["name"]
        ax.text(mid_x, mid_y, element_name, fontsize=7, color="#555555", ha="center", va="center", 
                bbox=dict(boxstyle="round,pad=0.1", fc="white", ec="none", alpha=0.7), zorder=6)

    # Knoten zeichnen
    nodes_info = {}
    for _, row in merged.iterrows():
        nodes_info[row["node_i"]] = _parse_xy(str(row["coordinate_i_m"]))
        nodes_info[row["node_j"]] = _parse_xy(str(row["coordinate_j_m"]))

    for node_name, (nx, ny) in nodes_info.items():
        dx, dy = disp_dict.get(node_name, (0.0, 0.0))
        vx = nx + scale * dx
        vy = ny + scale * dy
        ax.scatter(vx, vy, s=30, color="#2c3e50", zorder=3, edgecolors="white", linewidth=0.5)
        ax.text(vx + 0.02, vy + 0.02, node_name, fontsize=8, fontweight="bold", color="#34495e", zorder=4)

    # Lager symbolisieren (unverformte Position)
    for node_name, (nx, ny) in nodes_info.items():
        if node_name == "R0": # Festlager (jetzt rechts)
            ax.plot([nx, nx-0.05, nx+0.05, nx], [ny, ny-0.05, ny-0.05, ny], color="black", linewidth=1.5, zorder=5)
            ax.plot([nx-0.06, nx+0.06], [ny-0.05, ny-0.05], color="black", linewidth=2.0, zorder=5)
        elif node_name == "L0": # Loslager (jetzt links)
            ax.plot([nx, nx-0.05, nx+0.05, nx], [ny, ny-0.05, ny-0.05, ny], color="black", linewidth=1.5, zorder=5)
            ax.scatter([nx-0.025, nx+0.025], [ny-0.065, ny-0.065], s=15, color="white", edgecolors="black", zorder=5)
            ax.plot([nx-0.06, nx+0.06], [ny-0.08, ny-0.08], color="black", linewidth=2.0, zorder=5)

    # Lasteinleitung zeichnen (Pfeile fuer Windkraft)
    panel_count = max(int(name[1:]) for name in nodes_info.keys() if name.startswith("R"))
    for node_name, (nx, ny) in nodes_info.items():
        if node_name in [f"R{panel_count}", f"R{panel_count-1}"]:
            dx, dy = disp_dict.get(node_name, (0.0, 0.0))
            vx = nx + scale * dx
            vy = ny + scale * dy
            ax.annotate("", xy=(vx, vy), xytext=(vx + 0.2, vy),
                        arrowprops=dict(facecolor='#e74c3c', edgecolor='none', shrink=0.0, width=3, headwidth=8), zorder=4)

    # Colorbar hinzufuegen
    sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
    sm.set_array([])
    cbar = fig.colorbar(sm, ax=ax, fraction=0.046, pad=0.04)
    cbar.set_label("Stabnormalkraft [N]", fontsize=10, fontweight="bold")
    cbar.ax.tick_params(labelsize=9)

    ax.set_aspect("equal", adjustable="box")
    # Add enough padding on the right so wind arrows and text box don't get cut off
    ax.set_xlim(-0.15, 1.2)
    ax.set_xlabel("x [m]", fontsize=10, fontweight="bold")
    ax.set_ylabel("y [m]", fontsize=10, fontweight="bold")
    
    # Text box placed nicely inside the axes on the right
    summary = _read_apdl_summary(summary_path)
    info = (
        "ANSYS MAPDL export\n"
        "LINK180, PRETAB AXIAL\n"
        rf"$N_{{max}}={max_force:.1f}\,$N"
    )
    if summary:
        info += (
            "\n"
            rf"$R_{{R0x}}={summary.get('R_R0_FX_N', 0.0):.1f}\,$N" "\n"
            rf"$R_{{L0y}}={summary.get('R_L0_FY_N', 0.0):.1f}\,$N" "\n"
            rf"$u_{{R7x}}={summary.get('UX_G_mm', 0.0):.3f}\,$mm"
        )
    ax.text(
        0.95,
        0.95,
        info,
        transform=ax.transAxes,
        fontsize=9,
        va="top",
        ha="right",
        bbox={"boxstyle": "round,pad=0.25", "facecolor": "white", "edgecolor": "#c7ccd2"},
    )
    
    ax.set_title(f"ANSYS: Verformtes Fachwerk (Skalierung {scale:.1f}x)", fontsize=12, fontweight="bold", pad=15)
    
    # Schoenes Grid
    ax.grid(True, color="#ecf0f1", linewidth=0.8, linestyle="-")
    ax.set_axisbelow(True)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['bottom'].set_color('#bdc3c7')
    ax.spines['left'].set_color('#bdc3c7')

    fig.tight_layout()
    fig.savefig(FIG1 / "truss_ansys_force_plot.png", bbox_inches="tight")
    plt.close(fig)


def save_truss_comparison_outputs() -> None:
    source = _truss_comparison_source()
    if source is None:
        return

    data = pd.read_csv(source)
    if data.empty:
        return

    target_csv = DATA1 / "truss_comparison_python_ansys.csv"
    if source != target_csv:
        data.to_csv(target_csv, index=False)

    representative_names = ["VR1", "H1", "D1", "VL3"]
    representative = data[data["name"].isin(representative_names)].copy()
    representative["order"] = representative["name"].map(
        {name: index for index, name in enumerate(representative_names)}
    )
    representative = representative.sort_values("order")

    table_path = DATA1 / "truss_comparison_report_table.tex"
    with table_path.open("w", encoding="utf-8") as file:
        file.write("\\begin{tabular}{llrrrrr}\n")
        file.write("\\toprule\n")
        file.write(
            "Element & Art & $N_\\mathrm{Py}$ [N] & $N_\\mathrm{ANSYS}$ [N] "
            "& $\\Delta N$ [N] & $\\sigma_\\mathrm{Py}$ [MPa] "
            "& $\\sigma_\\mathrm{ANSYS}$ [MPa]\\\\\n"
        )
        file.write("\\midrule\n")
        for _, row in representative.iterrows():
            file.write(
                f"{row['name']} & {_kind_label(str(row['kind']))} & "
                f"{row['python_axial_N']:.2f} & {row['ansys_axial_N']:.2f} & "
                f"{row['diff_axial_N']:.3f} & {row['python_stress_MPa']:.3f} & "
                f"{row['ansys_stress_MPa']:.3f}\\\\\n"
            )
        file.write("\\bottomrule\n")
        file.write("\\end{tabular}\n")

    x = np.arange(len(data))
    fig, axes = plt.subplots(
        2,
        1,
        figsize=(7.1, 4.6),
        dpi=REPORT_DPI,
        sharex=True,
        gridspec_kw={"height_ratios": [2.5, 1.0]},
    )

    axes[0].plot(x, data["python_axial_N"], color="#1f5aa6", linewidth=1.8, label="Python-FEM")
    axes[0].scatter(x, data["ansys_axial_N"], color="#c33a2b", s=15, marker="x", label="ANSYS MAPDL")
    axes[0].axhline(0.0, color="#6b7280", linewidth=0.7)
    axes[0].set_ylabel("$N$ [N]")
    axes[0].set_title("Elementweiser Vergleich der Stabnormalkraefte")
    axes[0].grid(True, color="#d8dde3", linewidth=0.5)
    axes[0].legend(loc="upper right", frameon=False)

    axes[1].bar(x, data["diff_axial_N"], color="#6f7f8f", width=0.75)
    axes[1].axhline(0.0, color="#222222", linewidth=0.7)
    axes[1].set_ylabel("$\\Delta N$ [N]")
    axes[1].set_xlabel("Element")
    axes[1].grid(True, axis="y", color="#d8dde3", linewidth=0.5)

    axes[1].set_xticks(x)
    axes[1].set_xticklabels(data["name"], rotation=90, fontsize=7)
    fig.tight_layout()
    fig.savefig(FIG1 / "truss_python_ansys_comparison.png")
    plt.close(fig)


def save_aufgabe2_screenshot_panels() -> None:
    source_dir = SCREEN2 / "final_report"
    sources = {
        "meshgesamt.PNG": "mesh_gesamt_report.png",
        "meshzoom.PNG": "mesh_zoom_report.png",
        "Normalspannung.PNG": "normalspannung_report.png",
        "Vergleichspannungmises.PNG": "vergleichspannung_mises_report.png",
    }
    if not source_dir.exists():
        return

    FIG2.mkdir(parents=True, exist_ok=True)
    for source_name, target_name in sources.items():
        source = source_dir / source_name
        if not source.exists():
            continue
        shutil.copyfile(source, FIG2 / target_name)


def main() -> None:
    save_clean_velocity()
    save_pressure_distribution_single()
    save_drag_convergence()
    save_cfd_mesh_overview()
    save_plate_singularity_mesh_panel()
    save_plate_singularity_stress_panel()
    save_truss_comparison_outputs()
    save_truss_ansys_result_plot()
    save_plate_hinges_plot()
    save_kerb_convergence()
    save_aufgabe2_screenshot_panels()


if __name__ == "__main__":
    main()
