from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

from aufgabe1_params import get_params


PROJECT = 27
OUT_DIR = Path("Aufgabe1/out")
DRAG_SUMMARY = OUT_DIR / "drag_summary.txt"

E_ALU_MPA = 70_000.0
NU_ALU = 0.3
SAFETY_FACTOR = 1.8
SIGMA_ALLOW_ALU_MPA = 190.0 / SAFETY_FACTOR


@dataclass(frozen=True)
class Hinge:
    name: str
    x_mm: float
    y_mm: float


def read_summary_value(path: Path, key: str) -> float:
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith(f"{key} ="):
            continue
        return float(line.split("=", maxsplit=1)[1].strip())
    raise KeyError(f"Could not find {key!r} in {path}")


def build_coords(stop_mm: float, step_mm: float, required: list[float]) -> list[float]:
    coords = {round(i * step_mm, 9) for i in range(int(round(stop_mm / step_mm)) + 1)}
    coords.update(round(value, 9) for value in required)
    return sorted(coords)


def build_patch_coords(center_mm: float, half_width_mm: float, step_mm: float) -> list[float]:
    count = int(round((2.0 * half_width_mm) / step_mm))
    start = center_mm - half_width_mm
    return [start + index * step_mm for index in range(count + 1)]


def build_interval_coords(start_mm: float, stop_mm: float, step_mm: float) -> list[float]:
    count = int(round((stop_mm - start_mm) / step_mm))
    return [start_mm + index * step_mm for index in range(count + 1)]


def is_inside_patch(
    x: float,
    y: float,
    hinge: Hinge,
    half_width_mm: float,
    support_mode: str,
) -> bool:
    if support_mode == "circle-flaechenlager":
        dx = x - hinge.x_mm
        dy = y - hinge.y_mm
        return dx * dx + dy * dy <= half_width_mm * half_width_mm + 1e-9
    return (
        abs(x - hinge.x_mm) <= half_width_mm + 1e-9
        and abs(y - hinge.y_mm) <= half_width_mm + 1e-9
    )


def generate_apdl(
    path: Path,
    project: int,
    mesh_size_mm: float,
    total_drag_n: float,
    support_patch_mm: float,
    support_refinement_mm: float | None,
    support_mode: str,
    job_name: str,
) -> dict[str, float | int | str]:
    params = get_params(project)

    width_mm = params.sign_width_m * 1000.0
    height_mm = params.plate_height_m * 1000.0
    thickness_mm = params.sign_thickness_m * 1000.0
    h_mm = params.h_m * 1000.0
    hinge_upper_y = 1000.0
    hinge_lower_y = hinge_upper_y - h_mm
    hinge_xs = [500.0, 1500.0, 2500.0]
    line_support_y_min = 0.0 if support_mode == "line-support-full-height" else hinge_lower_y
    line_support_y_max = height_mm
    pressure_mpa = total_drag_n / (width_mm * height_mm)

    hinges = [
        Hinge(f"H{idx + 1}_upper", x, hinge_upper_y)
        for idx, x in enumerate(hinge_xs)
    ] + [
        Hinge(f"H{idx + 1}_lower", x, hinge_lower_y)
        for idx, x in enumerate(hinge_xs)
    ]
    patch_half_mm = support_patch_mm / 2.0

    area_support_modes = {"flaechenlager", "circle-flaechenlager"}

    required_x = hinge_xs + [
        value
        for x in hinge_xs
        for value in (x - patch_half_mm, x + patch_half_mm)
        if 0.0 <= value <= width_mm
    ]
    required_y = [hinge_upper_y, hinge_lower_y] + [
        value
        for y in (hinge_upper_y, hinge_lower_y)
        for value in (y - patch_half_mm, y + patch_half_mm)
        if 0.0 <= value <= height_mm
    ]
    if support_mode in {"line-support-top", "line-support-full-height"}:
        required_y.extend([line_support_y_min, line_support_y_max])
    if support_refinement_mm is not None:
        required_x.extend(
            value
            for x in hinge_xs
            for value in build_patch_coords(x, patch_half_mm, support_refinement_mm)
            if 0.0 <= value <= width_mm
        )
        required_y.extend(
            value
            for y in (hinge_upper_y, hinge_lower_y)
            for value in build_patch_coords(y, patch_half_mm, support_refinement_mm)
            if 0.0 <= value <= height_mm
        )
        if support_mode in {"line-support-top", "line-support-full-height"}:
            required_y.extend(
                build_interval_coords(
                    line_support_y_min,
                    line_support_y_max,
                    support_refinement_mm,
                )
            )
    x_coords = build_coords(width_mm, mesh_size_mm, required_x)
    y_coords = build_coords(height_mm, mesh_size_mm, required_y)
    node_by_coord: dict[tuple[float, float], int] = {}
    nodal_loads: dict[int, float] = {}

    node_id = 1
    for y in y_coords:
        for x in x_coords:
            node_by_coord[(x, y)] = node_id
            nodal_loads[node_id] = 0.0
            node_id += 1

    elements: list[tuple[int, int, int, int]] = []
    for j in range(len(y_coords) - 1):
        for i in range(len(x_coords) - 1):
            n1 = node_by_coord[(x_coords[i], y_coords[j])]
            n2 = node_by_coord[(x_coords[i + 1], y_coords[j])]
            n3 = node_by_coord[(x_coords[i + 1], y_coords[j + 1])]
            n4 = node_by_coord[(x_coords[i], y_coords[j + 1])]
            elements.append((n1, n2, n3, n4))
            area_mm2 = (x_coords[i + 1] - x_coords[i]) * (y_coords[j + 1] - y_coords[j])
            elemental_force_n = pressure_mpa * area_mm2
            for node in (n1, n2, n3, n4):
                nodal_loads[node] += elemental_force_n / 4.0

    hinge_nodes = {
        hinge.name: node_by_coord[(hinge.x_mm, hinge.y_mm)] for hinge in hinges
    }
    hinge_patch_nodes = {
        hinge.name: [
            node
            for (x, y), node in node_by_coord.items()
            if is_inside_patch(x, y, hinge, patch_half_mm, support_mode)
        ]
        for hinge in hinges
    }
    line_support_nodes = {
        f"L{idx}": [
            node
            for (x, y), node in node_by_coord.items()
            if abs(x - support_x) <= patch_half_mm + 1e-9
            and line_support_y_min - 1e-9 <= y <= line_support_y_max + 1e-9
        ]
        for idx, support_x in enumerate(hinge_xs, start=1)
    }

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="ascii", newline="\n") as file:
        file.write("/CLEAR\n")
        file.write(f"/FILNAME,{job_name},1\n")
        file.write("/PREP7\n")
        file.write("ET,1,SHELL181\n")
        file.write("KEYOPT,1,8,2\n")
        file.write(f"MP,EX,1,{E_ALU_MPA:.9g}\n")
        file.write(f"MP,PRXY,1,{NU_ALU:.9g}\n")
        file.write("SECTYPE,1,SHELL\n")
        file.write(f"SECDATA,{thickness_mm:.9g},1\n")
        file.write("SECNUM,1\n")
        file.write("TYPE,1\n")
        file.write("MAT,1\n")
        for (x, y), node in node_by_coord.items():
            file.write(f"N,{node},{x:.9g},{y:.9g},0\n")
        for elem_id, (n1, n2, n3, n4) in enumerate(elements, start=1):
            file.write(f"E,{n1},{n2},{n3},{n4}\n")
        file.write("ALLSEL,ALL\n")
        if support_mode == "hinge-patches":
            for hinge in hinges:
                for node in hinge_patch_nodes[hinge.name]:
                    file.write(f"D,{node},UZ,0\n")
            support_reaction_nodes = []
        elif support_mode in area_support_modes:
            support_reaction_nodes = sorted(
                {node for nodes in hinge_patch_nodes.values() for node in nodes}
            )
            for node in support_reaction_nodes:
                file.write(f"D,{node},UZ,0\n")
        elif support_mode in {"line-support-top", "line-support-full-height"}:
            support_reaction_nodes = sorted(
                {node for nodes in line_support_nodes.values() for node in nodes}
            )
            for node in support_reaction_nodes:
                file.write(f"D,{node},UZ,0\n")
        else:
            raise ValueError(f"Unknown support mode: {support_mode}")
        file.write(f"D,{hinge_nodes['H1_lower']},UX,0\n")
        file.write(f"D,{hinge_nodes['H1_lower']},UY,0\n")
        file.write(f"D,{hinge_nodes['H2_lower']},UY,0\n")
        for node, load in nodal_loads.items():
            if abs(load) > 1e-12:
                file.write(f"F,{node},FZ,{-load:.12g}\n")
        file.write("FINISH\n")
        file.write("/SOLU\n")
        file.write("ANTYPE,STATIC\n")
        file.write("NLGEOM,OFF\n")
        file.write("OUTRES,ALL,ALL\n")
        file.write("SOLVE\n")
        file.write("FINISH\n")
        file.write("/POST1\n")
        file.write("SET,LAST\n")
        if support_mode == "hinge-patches":
            for hinge in hinges:
                file.write(f"*SET,R_{hinge.name},0\n")
                for index, node in enumerate(hinge_patch_nodes[hinge.name], start=1):
                    file.write(f"*GET,R_{hinge.name}_{index},NODE,{node},RF,FZ\n")
                    file.write(f"*SET,R_{hinge.name},R_{hinge.name}+R_{hinge.name}_{index}\n")
        elif support_mode in area_support_modes:
            reaction_set = "R_circle_flaechenlager" if support_mode == "circle-flaechenlager" else "R_flaechenlager"
            file.write(f"*SET,{reaction_set},0\n")
            for hinge in hinges:
                file.write(f"*SET,R_FL_{hinge.name},0\n")
                for index, node in enumerate(hinge_patch_nodes[hinge.name], start=1):
                    file.write(f"*GET,R_FL_{hinge.name}_{index},NODE,{node},RF,FZ\n")
                    file.write(
                        f"*SET,R_FL_{hinge.name},R_FL_{hinge.name}+R_FL_{hinge.name}_{index}\n"
                    )
                file.write(f"*SET,{reaction_set},{reaction_set}+R_FL_{hinge.name}\n")
        else:
            file.write("*SET,R_line_support,0\n")
            for name, nodes in line_support_nodes.items():
                file.write(f"*SET,R_{name},0\n")
                for index, node in enumerate(nodes, start=1):
                    file.write(f"*GET,R_{name}_{index},NODE,{node},RF,FZ\n")
                    file.write(f"*SET,R_{name},R_{name}+R_{name}_{index}\n")
                file.write(f"*SET,R_line_support,R_line_support+R_{name}\n")
        file.write("*CFOPEN,plate_structural_results,txt\n")
        file.write(f"*VWRITE,{pressure_mpa:.12g}\n")
        file.write("('pressure_N_per_mm2 = ',F20.12)\n")
        file.write(f"*VWRITE,{SIGMA_ALLOW_ALU_MPA:.12g}\n")
        file.write("('allowable_stress_MPa = ',F20.8)\n")
        if support_mode == "hinge-patches":
            for hinge in hinges:
                file.write(f"*VWRITE,R_{hinge.name}\n")
                file.write(f"('{hinge.name}_RFZ_N = ',F20.8)\n")
        elif support_mode in area_support_modes:
            for hinge in hinges:
                file.write(f"*VWRITE,R_FL_{hinge.name}\n")
                file.write(f"('FL_{hinge.name}_RFZ_N = ',F20.8)\n")
            if support_mode == "circle-flaechenlager":
                file.write("*VWRITE,R_circle_flaechenlager\n")
                file.write("('circle_flaechenlager_RFZ_N = ',F20.8)\n")
            else:
                file.write("*VWRITE,R_flaechenlager\n")
                file.write("('flaechenlager_RFZ_N = ',F20.8)\n")
        else:
            for name in line_support_nodes:
                file.write(f"*VWRITE,R_{name}\n")
                file.write(f"('{name}_RFZ_N = ',F20.8)\n")
            file.write("*VWRITE,R_line_support\n")
            file.write("('line_support_RFZ_N = ',F20.8)\n")
        file.write("*CFCLOS\n")
        file.write("FINISH\n")

    return {
        "nodes": len(node_by_coord),
        "elements": len(elements),
        "pressure_mpa": pressure_mpa,
        "total_nodal_load_n": sum(nodal_loads.values()),
        "mesh_size_mm": mesh_size_mm,
        "support_patch_mm": support_patch_mm,
        "support_refinement_mm": support_refinement_mm or 0.0,
        "support_mode": support_mode,
        "support_nodes_per_patch": len(next(iter(hinge_patch_nodes.values()))),
        "support_node_count": len(support_reaction_nodes),
        "line_support_nodes_per_strip": len(next(iter(line_support_nodes.values()))),
    }


def write_post_probe(path: Path, job_name: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="ascii", newline="\n") as file:
        file.write("/POST1\n")
        file.write(f"FILE,{job_name},rst\n")
        file.write("SET,LAST\n")
        file.write("SHELL,TOP\n")
        file.write("PRNSOL,U,COMP\n")
        file.write("PRNSOL,S,COMP\n")
        file.write("PRNSOL,S,PRIN\n")
        file.write("SHELL,BOT\n")
        file.write("PRNSOL,S,COMP\n")
        file.write("PRNSOL,S,PRIN\n")
        file.write("FINISH\n")


def write_export_plots(path: Path, job_name: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="ascii", newline="\n") as file:
        file.write("/POST1\n")
        file.write(f"FILE,{job_name},rst\n")
        file.write("SET,LAST\n")
        file.write("/GRAPHICS,FULL\n")
        file.write("/ESHAPE,1\n")
        file.write("/PNUM,NODE,0\n")
        file.write("/PNUM,ELEM,0\n")
        file.write("/NUMBER,0\n")
        file.write("/EDGE,1\n")
        file.write("/VIEW,1,1,1,0.75\n")
        file.write("/AUTO,1\n")
        file.write("/SHOW,PNG\n")
        file.write("EPLOT\n")
        file.write("/SHOW,CLOSE\n")
        file.write("/SHOW,PNG\n")
        file.write("SHELL,TOP\n")
        file.write("PLNSOL,S,EQV\n")
        file.write("/SHOW,CLOSE\n")
        file.write("/SHOW,PNG\n")
        file.write("PLDISP,2\n")
        file.write("/SHOW,CLOSE\n")
        file.write("FINISH\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", type=int, default=PROJECT)
    parser.add_argument("--summary", type=Path, default=DRAG_SUMMARY)
    parser.add_argument("--out-dir", type=Path, default=OUT_DIR)
    parser.add_argument("--mesh-size-mm", type=float, default=50.0)
    parser.add_argument("--support-patch-mm", type=float, default=None)
    parser.add_argument("--support-refinement-mm", type=float, default=None)
    parser.add_argument(
        "--support-mode",
        choices=(
            "hinge-patches",
            "flaechenlager",
            "circle-flaechenlager",
            "line-support-top",
            "line-support-full-height",
        ),
        default="hinge-patches",
    )
    parser.add_argument("--job-name", default=None)
    args = parser.parse_args()

    support_patch_mm = args.support_patch_mm
    if support_patch_mm is None:
        support_patch_mm = (
            100.0
            if args.support_mode == "circle-flaechenlager"
            else
            50.0
            if args.support_mode
            in {"flaechenlager", "line-support-top", "line-support-full-height"}
            else 100.0
        )
    support_refinement_mm = args.support_refinement_mm

    total_drag_n = read_summary_value(args.summary, "total_drag_N")
    apdl_path = args.out_dir / "plate_structural.inp"
    job_name = args.job_name or (
        {
            "flaechenlager": "plate_flaechenlager",
            "circle-flaechenlager": "plate_circle_flaechenlager_d100",
            "line-support-top": "plate_line_support_top",
            "line-support-full-height": "plate_line_support_full_height",
        }.get(args.support_mode, "plate_1_2")
    )
    stats = generate_apdl(
        apdl_path,
        args.project,
        args.mesh_size_mm,
        total_drag_n,
        support_patch_mm,
        support_refinement_mm,
        args.support_mode,
        job_name,
    )
    write_post_probe(args.out_dir / "plate_post_probe.inp", job_name)
    write_export_plots(args.out_dir / "plate_export_plots.inp", job_name)

    print(apdl_path.as_posix())
    print((args.out_dir / "plate_post_probe.inp").as_posix())
    print((args.out_dir / "plate_export_plots.inp").as_posix())
    for key, value in stats.items():
        print(f"{key} = {value}")


if __name__ == "__main__":
    main()
