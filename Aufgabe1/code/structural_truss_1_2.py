from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from math import cos, pi, sin, sqrt
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from aufgabe1_params import get_params


PROJECT = 27
OUT_DIR = Path("Aufgabe1/out")
DRAG_SUMMARY = OUT_DIR / "drag_summary.txt"

E_STEEL_PA = 210_000e6
SIGMA_ALLOW_STEEL_PA = 235e6 / 1.8
SIGMA_ALLOW_ALU_PA = 190e6 / 1.8
PANEL_COUNT = 7
TRUSS_COUNT = 3


@dataclass(frozen=True)
class Node:
    name: str
    x: float
    y: float


@dataclass(frozen=True)
class Element:
    name: str
    node_i: int
    node_j: int
    kind: str


@dataclass(frozen=True)
class Tube:
    outer_mm: float
    wall_mm: float

    @property
    def inner_mm(self) -> float:
        return self.outer_mm - 2.0 * self.wall_mm

    @property
    def area_m2(self) -> float:
        outer_m = self.outer_mm / 1000.0
        inner_m = self.inner_mm / 1000.0
        return pi / 4.0 * (outer_m**2 - inner_m**2)

    @property
    def label(self) -> str:
        return f"{self.outer_mm:g} x {self.wall_mm:g} mm"


TUBE_CATALOG = [
    Tube(12, 1.5),
    Tube(16, 1.5),
    Tube(16, 2.0),
    Tube(20, 2.0),
    Tube(25, 2.0),
    Tube(30, 2.0),
    Tube(30, 3.0),
    Tube(40, 2.0),
    Tube(40, 3.0),
    Tube(50, 3.0),
    Tube(60, 3.0),
]


def read_summary_value(path: Path, key: str) -> float:
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith(f"{key} ="):
            continue
        return float(line.split("=", maxsplit=1)[1].strip())
    raise KeyError(f"Could not find {key!r} in {path}")


def build_truss(params, panel_count: int) -> tuple[list[Node], list[Element]]:
    nodes: list[Node] = []
    left_indices: list[int] = []
    right_indices: list[int] = []

    for level in range(panel_count):
        y = level * params.h_m
        left_indices.append(len(nodes))
        nodes.append(Node(f"L{level}", 0.0, y))
        right_indices.append(len(nodes))
        nodes.append(Node(f"R{level}", params.b_m, y))

    right_indices.append(len(nodes))
    nodes.append(Node(f"R{panel_count}", params.b_m, panel_count * params.h_m))

    elements: list[Element] = []
    for level in range(panel_count):
        elements.append(
            Element(f"VR{level + 1}", right_indices[level], right_indices[level + 1], "vertical")
        )
        elements.append(
            Element(f"D{level + 1}", left_indices[level], right_indices[level + 1], "diagonal")
        )
        if level < panel_count - 1:
            elements.append(
                Element(
                    f"VL{level + 1}",
                    left_indices[level],
                    left_indices[level + 1],
                    "vertical",
                )
            )

    for level in range(panel_count):
        elements.append(
            Element(f"H{level}", left_indices[level], right_indices[level], "horizontal")
        )

    return nodes, elements


def find_node_index(nodes: list[Node], name: str) -> int:
    for index, node in enumerate(nodes):
        if node.name == name:
            return index
    raise ValueError(f"Node {name!r} does not exist in the truss topology.")


def element_geometry(nodes: list[Node], element: Element) -> tuple[float, float, float]:
    node_i = nodes[element.node_i]
    node_j = nodes[element.node_j]
    dx = node_j.x - node_i.x
    dy = node_j.y - node_i.y
    length = sqrt(dx**2 + dy**2)
    return length, dx / length, dy / length


def element_stiffness(nodes: list[Node], element: Element, area_m2: float) -> np.ndarray:
    length, c, s = element_geometry(nodes, element)
    return (E_STEEL_PA * area_m2 / length) * np.array(
        [
            [c * c, c * s, -c * c, -c * s],
            [c * s, s * s, -c * s, -s * s],
            [-c * c, -c * s, c * c, c * s],
            [-c * s, -s * s, c * s, s * s],
        ]
    )


def dof_indices(element: Element) -> list[int]:
    return [
        2 * element.node_i,
        2 * element.node_i + 1,
        2 * element.node_j,
        2 * element.node_j + 1,
    ]


def assemble_global(
    nodes: list[Node],
    elements: list[Element],
    areas_by_kind: dict[str, float],
) -> np.ndarray:
    dof_count = 2 * len(nodes)
    stiffness = np.zeros((dof_count, dof_count))
    for element in elements:
        indices = dof_indices(element)
        ke = element_stiffness(nodes, element, areas_by_kind[element.kind])
        for local_i, global_i in enumerate(indices):
            for local_j, global_j in enumerate(indices):
                stiffness[global_i, global_j] += ke[local_i, local_j]
    return stiffness


def solve_truss(
    nodes: list[Node],
    elements: list[Element],
    areas_by_kind: dict[str, float],
    force: np.ndarray,
    fixed_dofs: list[int],
) -> tuple[np.ndarray, np.ndarray, list[dict[str, float | str]]]:
    stiffness = assemble_global(nodes, elements, areas_by_kind)
    all_dofs = np.arange(len(force))
    free_dofs = np.array([dof for dof in all_dofs if dof not in fixed_dofs])

    displacement = np.zeros_like(force)
    displacement[free_dofs] = np.linalg.solve(
        stiffness[np.ix_(free_dofs, free_dofs)], force[free_dofs]
    )
    reactions = stiffness @ displacement - force

    element_rows: list[dict[str, float | str]] = []
    for element in elements:
        indices = dof_indices(element)
        length, c, s = element_geometry(nodes, element)
        ue = displacement[indices]
        axial = (
            E_STEEL_PA
            * areas_by_kind[element.kind]
            / length
            * np.array([-c, -s, c, s])
            @ ue
        )
        element_rows.append(
            {
                "name": element.name,
                "kind": element.kind,
                "node_i": nodes[element.node_i].name,
                "node_j": nodes[element.node_j].name,
                "length_m": length,
                "axial_N": float(axial),
                "stress_MPa": float(axial / areas_by_kind[element.kind] / 1e6),
            }
        )

    return displacement, reactions, element_rows


def choose_tube(required_area_m2: float) -> Tube:
    for tube in TUBE_CATALOG:
        if tube.area_m2 >= required_area_m2:
            return tube
    return TUBE_CATALOG[-1]


def write_index_table(path: Path, nodes: list[Node], elements: list[Element]) -> None:
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(
            [
                "element",
                "kind",
                "node_i",
                "node_j",
                "global_dofs",
                "coordinate_i_m",
                "coordinate_j_m",
            ]
        )
        for element in elements:
            node_i = nodes[element.node_i]
            node_j = nodes[element.node_j]
            writer.writerow(
                [
                    element.name,
                    element.kind,
                    node_i.name,
                    node_j.name,
                    " ".join(str(dof) for dof in dof_indices(element)),
                    f"({node_i.x:.6f}, {node_i.y:.6f})",
                    f"({node_j.x:.6f}, {node_j.y:.6f})",
                ]
            )


def write_element_rows(path: Path, rows: list[dict[str, float | str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def plot_truss(
    path: Path,
    nodes: list[Node],
    elements: list[Element],
    displacement: np.ndarray,
    rows: list[dict[str, float | str]],
) -> None:
    max_force = max(abs(float(row["axial_N"])) for row in rows)
    disp_xy = displacement.reshape((-1, 2))
    max_disp = float(np.max(np.linalg.norm(disp_xy, axis=1)))
    scale = 0.15 / max_disp if max_disp > 0 else 1.0

    row_by_name = {row["name"]: row for row in rows}
    fig, ax = plt.subplots(figsize=(6, 8), dpi=180)
    for element in elements:
        node_i = nodes[element.node_i]
        node_j = nodes[element.node_j]
        axial = float(row_by_name[element.name]["axial_N"])
        color = "#b11b1b" if axial >= 0 else "#1f5aa6"
        linewidth = 0.8 + 3.0 * abs(axial) / max_force
        ax.plot([node_i.x, node_j.x], [node_i.y, node_j.y], color="#9aa0a6", linewidth=0.8)
        ax.plot(
            [
                node_i.x + scale * disp_xy[element.node_i, 0],
                node_j.x + scale * disp_xy[element.node_j, 0],
            ],
            [
                node_i.y + scale * disp_xy[element.node_i, 1],
                node_j.y + scale * disp_xy[element.node_j, 1],
            ],
            color=color,
            linewidth=linewidth,
        )

    for idx, node in enumerate(nodes):
        ax.scatter(node.x, node.y, s=12, color="#20252b")
        ax.text(node.x + 0.015, node.y + 0.01, node.name, fontsize=7)

    ax.set_aspect("equal", adjustable="box")
    ax.set_xlabel("x [m]")
    ax.set_ylabel("y [m]")
    ax.set_title("Aufgabe 1.2 governing truss: deformed shape, red tension, blue compression")
    ax.grid(True, color="#d8dde3", linewidth=0.5)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def write_summary(
    path: Path,
    params,
    total_drag_n: float,
    pressure_pa: float,
    force_per_truss_n: float,
    upper_joint_load_n: float,
    lower_joint_load_n: float,
    nodes: list[Node],
    fixed_dofs: list[int],
    displacement: np.ndarray,
    reactions: np.ndarray,
    rows: list[dict[str, float | str]],
    tubes_by_kind: dict[str, Tube],
) -> None:
    max_by_kind: dict[str, float] = {}
    for kind in ["vertical", "horizontal", "diagonal"]:
        max_by_kind[kind] = max(
            abs(float(row["axial_N"])) for row in rows if row["kind"] == kind
        )

    panel_count = max(
        int(node.name[1:]) for node in nodes if node.name.startswith("R")
    )
    g_node = find_node_index(nodes, f"R{panel_count}")
    lower_joint = find_node_index(nodes, f"R{panel_count - 1}")
    g_ux, g_uy = displacement[2 * g_node : 2 * g_node + 2]
    b_ux, b_uy = displacement[2 * lower_joint : 2 * lower_joint + 2]

    with path.open("w", encoding="utf-8") as file:
        file.write("Aufgabe 1.2 structural helper summary\n")
        file.write("======================================\n\n")
        file.write("Assumptions used by this Python truss model:\n")
        file.write(f"- Project: {params.project}\n")
        file.write(f"- Truss carrier count across sign width: {TRUSS_COUNT}\n")
        file.write("- The governing truss is loaded by the upper/lower joint loads listed below.\n")
        file.write("- Without supplied joint loads, the script uses an equal one-third load split.\n")
        file.write(f"- Loads act on the upper two right-side truss joints.\n")
        file.write(f"- Truss panel count: {panel_count}\n")
        file.write(f"- Bottom left node L0 fixed in x/y; bottom right node R0 fixed in y.\n\n")

        file.write("CFD load converted for structural model:\n")
        file.write(f"- total_drag_N = {total_drag_n:.3f}\n")
        file.write(f"- equivalent uniform pressure = {pressure_pa:.6f} Pa\n")
        file.write(f"- equivalent uniform pressure = {pressure_pa * 1e-6:.9f} N/mm^2\n")
        file.write(f"- force per truss carrier = {force_per_truss_n:.3f} N\n")
        file.write(f"- upper joint load = {upper_joint_load_n:.3f} N\n")
        file.write(f"- lower joint load = {lower_joint_load_n:.3f} N\n\n")

        file.write("Allowable stresses with safety factor 1.8:\n")
        file.write(f"- aluminium sign: {SIGMA_ALLOW_ALU_PA / 1e6:.3f} N/mm^2\n")
        file.write(f"- steel truss: {SIGMA_ALLOW_STEEL_PA / 1e6:.3f} N/mm^2\n\n")

        file.write("Maximum axial forces by member group:\n")
        for kind, max_force in max_by_kind.items():
            required_area_mm2 = max_force / SIGMA_ALLOW_STEEL_PA * 1e6
            tube = tubes_by_kind[kind]
            stress_mpa = max_force / tube.area_m2 / 1e6
            file.write(
                f"- {kind}: Nmax = {max_force:.3f} N, "
                f"A_required = {required_area_mm2:.3f} mm^2, "
                f"selected tube = {tube.label}, "
                f"Di = {tube.inner_mm:g} mm, "
                f"sigma = {stress_mpa:.3f} N/mm^2\n"
            )

        file.write("\nSupport reactions at constrained DOFs:\n")
        for dof in fixed_dofs:
            node = nodes[dof // 2]
            component = "Fx" if dof % 2 == 0 else "Fy"
            file.write(f"- {node.name} {component} = {reactions[dof]:.3f} N\n")

        file.write("\nDisplacements:\n")
        file.write(
            f"- G/top joint {nodes[g_node].name}: ux = {g_ux * 1000:.6f} mm, "
            f"uy = {g_uy * 1000:.6f} mm\n"
        )
        file.write(
            f"- lower loaded joint {nodes[lower_joint].name}: ux = {b_ux * 1000:.6f} mm, "
            f"uy = {b_uy * 1000:.6f} mm\n"
        )

        file.write("\nAssembly core loop for the report:\n")
        file.write("for a in range(4):\n")
        file.write("    for b in range(4):\n")
        file.write("        K[index[e,a], index[e,b]] += Ke[e][a,b]\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", type=int, default=PROJECT)
    parser.add_argument("--summary", type=Path, default=DRAG_SUMMARY)
    parser.add_argument("--out-dir", type=Path, default=OUT_DIR)
    parser.add_argument("--panel-count", type=int, default=PANEL_COUNT)
    parser.add_argument("--truss-count", type=int, default=TRUSS_COUNT)
    parser.add_argument(
        "--upper-load-n",
        type=float,
        default=None,
        help="Force magnitude from the sign into the upper joint of the governing truss.",
    )
    parser.add_argument(
        "--lower-load-n",
        type=float,
        default=None,
        help="Force magnitude from the sign into the lower joint of the governing truss.",
    )
    args = parser.parse_args()

    params = get_params(args.project)
    args.out_dir.mkdir(parents=True, exist_ok=True)

    total_drag_n = read_summary_value(args.summary, "total_drag_N")
    pressure_pa = total_drag_n / params.frontal_area_m2
    force_per_truss_n = total_drag_n / args.truss_count
    if args.upper_load_n is None and args.lower_load_n is None:
        upper_joint_load_n = force_per_truss_n / 2.0
        lower_joint_load_n = force_per_truss_n / 2.0
    elif args.upper_load_n is not None and args.lower_load_n is not None:
        upper_joint_load_n = args.upper_load_n
        lower_joint_load_n = args.lower_load_n
        force_per_truss_n = upper_joint_load_n + lower_joint_load_n
    else:
        raise ValueError("Provide both --upper-load-n and --lower-load-n, or neither.")

    nodes, elements = build_truss(params, args.panel_count)
    dof_count = 2 * len(nodes)
    force = np.zeros(dof_count)

    top_right = find_node_index(nodes, f"R{args.panel_count}")
    lower_right = find_node_index(nodes, f"R{args.panel_count - 1}")
    force[2 * top_right] = -upper_joint_load_n
    force[2 * lower_right] = -lower_joint_load_n

    fixed_dofs = [0, 1, 3]
    trial_areas = {"vertical": 1e-4, "horizontal": 1e-4, "diagonal": 1e-4}
    _, _, trial_rows = solve_truss(nodes, elements, trial_areas, force, fixed_dofs)

    max_by_kind = {
        kind: max(abs(float(row["axial_N"])) for row in trial_rows if row["kind"] == kind)
        for kind in ["vertical", "horizontal", "diagonal"]
    }
    tubes_by_kind = {
        kind: choose_tube(max_force / SIGMA_ALLOW_STEEL_PA)
        for kind, max_force in max_by_kind.items()
    }
    selected_areas = {kind: tube.area_m2 for kind, tube in tubes_by_kind.items()}
    displacement, reactions, rows = solve_truss(
        nodes, elements, selected_areas, force, fixed_dofs
    )

    write_index_table(args.out_dir / "truss_index_table.csv", nodes, elements)
    write_element_rows(args.out_dir / "truss_element_forces.csv", rows)
    plot_truss(args.out_dir / "truss_deformed.png", nodes, elements, displacement, rows)
    write_summary(
        args.out_dir / "truss_summary.txt",
        params,
        total_drag_n,
        pressure_pa,
        force_per_truss_n,
        upper_joint_load_n,
        lower_joint_load_n,
        nodes,
        fixed_dofs,
        displacement,
        reactions,
        rows,
        tubes_by_kind,
    )

    print((args.out_dir / "truss_summary.txt").as_posix())
    print((args.out_dir / "truss_index_table.csv").as_posix())
    print((args.out_dir / "truss_element_forces.csv").as_posix())
    print((args.out_dir / "truss_deformed.png").as_posix())


if __name__ == "__main__":
    main()
