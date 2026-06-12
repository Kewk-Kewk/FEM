from __future__ import annotations

import re
import subprocess
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.collections import LineCollection
from PIL import Image, ImageDraw, ImageFilter, ImageFont


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


def save_plate_mesh_full() -> None:
    target = FIG1 / "plate_mesh_full_report.png"
    target.parent.mkdir(parents=True, exist_ok=True)
    width, height, dx, dy = 3000.0, 2000.0, 50.0, 50.0
    xs = np.arange(0.0, width + dx, dx)
    ys = np.arange(0.0, height + dy, dy)

    fig, ax = plt.subplots(figsize=(7.2, 4.8), constrained_layout=True)
    for x in xs:
        ax.plot([x, x], [0, height], color="#64748b", linewidth=0.35)
    for y in ys:
        ax.plot([0, width], [y, y], color="#64748b", linewidth=0.35)
    for x in [500.0, 1500.0, 2500.0]:
        ax.add_patch(plt.Rectangle((x - 25.0, 0.0), 50.0, height, facecolor="#0f766e", alpha=0.35, edgecolor="#0f766e"))
    ax.set_xlim(-80, width + 80)
    ax.set_ylim(-80, height + 80)
    ax.set_aspect("equal")
    ax.set_xlabel("x [mm]")
    ax.set_ylabel("y [mm]")
    ax.set_title("Schalennetz der Tafel mit drei 50-mm-Linienstützen")
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


def _crop_workbench(name: str, mode: str = "model") -> Image.Image:
    image = Image.open(SCREEN2 / name).convert("RGB")
    if mode == "detail":
        box = (500, 155, 1780, 930)
    elif mode == "result":
        box = (480, 145, 1690, 1010)
    else:
        box = (560, 145, 1660, 990)
    return image.crop(box)


def _panel(images: list[tuple[str, Image.Image]], target: Path, cols: int = 2) -> None:
    cell_w, cell_h, label_h = 1120, 710, 58
    rows = int(np.ceil(len(images) / cols))
    canvas = Image.new("RGB", (cols * cell_w, rows * (cell_h + label_h)), "white")
    draw = ImageDraw.Draw(canvas)
    font = _font(38)

    for idx, (label, image) in enumerate(images):
        row, col = divmod(idx, cols)
        x0, y0 = col * cell_w, row * (cell_h + label_h)
        image = image.copy()
        image.thumbnail((cell_w - 16, cell_h - 16), Image.Resampling.LANCZOS)
        ix = x0 + (cell_w - image.width) // 2
        iy = y0 + label_h + (cell_h - image.height) // 2
        draw.text((x0 + 12, y0 + 8), label, fill="#111827", font=font)
        canvas.paste(image, (ix, iy))
        draw.rectangle((x0 + 6, y0 + label_h + 6, x0 + cell_w - 7, y0 + label_h + cell_h - 7), outline="#cbd5e1", width=2)

    target.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(target)


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


def save_plate_support_panels() -> None:
    save_dir = FIG1
    _support_panel(
        [
            ("Punktlager", DATA1 / "plate_hinge_refined_fine" / "plate_spannung_eqv_ansys.png"),
            ("100 mm Kreis-Flächenlager", DATA1 / "plate_circle_flaechenlager_d100" / "plate_spannung_eqv_ansys.png"),
            ("vertikale Linienstützen", DATA1 / "plate_line_support_full_height" / "plate_spannung_eqv_ansys.png"),
        ],
        save_dir / "plate_support_stress_panel.png",
    )
    _support_panel(
        [
            ("Punktlager", DATA1 / "plate_hinge_refined_fine" / "plate_verformung_ansys.png"),
            ("100 mm Kreis-Flächenlager", DATA1 / "plate_circle_flaechenlager_d100" / "plate_verformung_ansys.png"),
            ("vertikale Linienstützen", DATA1 / "plate_line_support_full_height" / "plate_verformung_ansys.png"),
        ],
        save_dir / "plate_support_deformation_panel.png",
    )


def save_aufgabe2_screenshot_panels() -> None:
    if not SCREEN2.exists():
        return
    _panel(
        [
            ("Geometrie", _crop_workbench("Geometrie.PNG")),
            ("Randbedingung: Kraft", _crop_workbench("Kraft.PNG")),
            ("Randbedingung: Verschiebung", _crop_workbench("Geometrie_Verschiebung.PNG")),
            ("globales Netz", _crop_workbench("netz.PNG")),
        ],
        FIG2 / "aufgabe2_setup_screens.png",
    )
    _panel(
        [
            ("Netzdetail am Lochrand", _crop_workbench("Netzdetail.PNG", "detail")),
            ("Normalspannung in y-Richtung", _crop_workbench("newscreenshots/1mm.PNG", "result")),
            ("Vergleichsspannung nach von Mises", _crop_workbench("newscreenshots/mises.PNG", "result")),
            ("Verschiebungsrandbedingungen", _crop_workbench("Verschieung1.PNG")),
        ],
        FIG2 / "aufgabe2_result_screens.png",
    )


def main() -> None:
    save_clean_velocity()
    save_pressure_distribution_single()
    save_drag_convergence()
    save_cfd_mesh_overview()
    save_plate_mesh_full()
    save_plate_support_panels()
    save_kerb_convergence()
    save_aufgabe2_screenshot_panels()


if __name__ == "__main__":
    main()
