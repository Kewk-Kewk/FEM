"""Aufgabe 1.2 a) — Parser fuer die ANSYS-MAPDL-Tafelberechnung.

Wertet die Ergebnisdateien der Schalenberechnung aus:
  - plate_structural_results.txt (Lagerreaktionen, Druck)
  - plate_post_probe.out (nodale Spannungen, Verschiebungen)
  - plate_structural.inp (Netz fuer Tributarflaechen-Berechnung)

Berechnet die Tributarflaeche ueber der zul. Spannung (Singularitaetsindikator)
und schreibt zusammenfassende CSV- und Textdateien.
"""
from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path


OUT_DIR = Path("Aufgabe1/out")
RESULTS_TXT = OUT_DIR / "plate_structural_results.txt"
POST_OUT = OUT_DIR / "plate_post_probe.out"


FLOAT_RE = re.compile(r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[Ee][-+]?\d+)?")


def to_float(value: str) -> float:
    return float(value.replace("D", "E"))


def parse_key_values(path: Path) -> dict[str, float]:
    values: dict[str, float] = {}
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", maxsplit=1)
        matches = FLOAT_RE.findall(value)
        if matches:
            values[key.strip()] = to_float(matches[-1])
    return values


def parse_post_output(path: Path) -> dict[str, float]:
    max_seqv = {"top": 0.0, "bottom": 0.0}
    estimated_seqv = {"top": 0.0, "bottom": 0.0}
    max_abs_uz = 0.0
    current_side: str | None = None
    reading_principal_rows = False
    reading_displacement_rows = False
    in_estimated_bounds = False
    waiting_for_estimated_value = False

    for raw_line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw_line.strip()
        upper = line.upper()

        if "SHELL NODAL RESULTS ARE AT TOP" in upper:
            current_side = "top"
        elif "SHELL NODAL RESULTS ARE AT BOTTOM" in upper:
            current_side = "bottom"

        if "ESTIMATED BOUNDS" in upper:
            in_estimated_bounds = True

        if "NODE" in upper and "UX" in upper and "UZ" in upper:
            reading_displacement_rows = True
            continue
        if reading_displacement_rows:
            if upper.startswith("MAXIMUM") or upper.startswith("MINIMUM") or upper.startswith("***"):
                reading_displacement_rows = False
            else:
                parts = line.split()
                if len(parts) >= 5 and parts[0].isdigit():
                    max_abs_uz = max(max_abs_uz, abs(to_float(parts[3])))

        if "NODE" in upper and "S1" in upper and "SEQV" in upper:
            reading_principal_rows = not in_estimated_bounds
            continue

        if reading_principal_rows:
            if upper.startswith("MINIMUM") or upper.startswith("MAXIMUM") or upper.startswith("***"):
                reading_principal_rows = False
            else:
                parts = line.split()
                if current_side and len(parts) >= 6 and parts[0].isdigit():
                    max_seqv[current_side] = max(max_seqv[current_side], abs(to_float(parts[5])))

        if in_estimated_bounds and upper.startswith("MAXIMUM VALUES"):
            waiting_for_estimated_value = True
            continue
        if waiting_for_estimated_value and upper.startswith("VALUE"):
            matches = FLOAT_RE.findall(line)
            if current_side and len(matches) >= 5:
                estimated_seqv[current_side] = max(
                    estimated_seqv[current_side], abs(to_float(matches[-1]))
                )
            waiting_for_estimated_value = False
            in_estimated_bounds = False

    return {
        "max_eqv_stress_top_MPa": max_seqv["top"],
        "max_eqv_stress_bottom_MPa": max_seqv["bottom"],
        "max_eqv_stress_MPa": max(max_seqv.values()),
        "estimated_max_eqv_stress_top_MPa": estimated_seqv["top"],
        "estimated_max_eqv_stress_bottom_MPa": estimated_seqv["bottom"],
        "estimated_max_eqv_stress_MPa": max(estimated_seqv.values()),
        "max_abs_UZ_mm": max_abs_uz,
    }


def polygon_area(corners_xy: list[tuple[float, float]]) -> float:
    area = 0.0
    for index, (x1, y1) in enumerate(corners_xy):
        x2, y2 = corners_xy[(index + 1) % len(corners_xy)]
        area += x1 * y2 - x2 * y1
    return abs(area) * 0.5


def parse_apdl_mesh(path: Path) -> tuple[dict[int, tuple[float, float]], list[tuple[int, ...]]]:
    nodes: dict[int, tuple[float, float]] = {}
    elements: list[tuple[int, ...]] = []

    for raw_line in path.read_text(encoding="ascii", errors="ignore").splitlines():
        line = raw_line.strip()
        if not line or line.startswith(("!", "*")):
            continue
        parts = [part.strip() for part in line.split(",")]
        command = parts[0].upper()
        if command == "N" and len(parts) >= 4:
            nodes[int(parts[1])] = (to_float(parts[2]), to_float(parts[3]))
        elif command == "E" and len(parts) >= 4:
            element_nodes = tuple(int(part) for part in parts[1:] if part)
            if len(element_nodes) >= 3:
                elements.append(element_nodes)

    return nodes, elements


def nodal_tributary_areas(
    nodes: dict[int, tuple[float, float]],
    elements: list[tuple[int, ...]],
) -> dict[int, float]:
    areas = {node_id: 0.0 for node_id in nodes}
    for element in elements:
        unique_nodes = tuple(dict.fromkeys(element))
        if len(unique_nodes) < 3:
            continue
        corners = [nodes[node_id] for node_id in unique_nodes]
        share = polygon_area(corners) / len(unique_nodes)
        for node_id in unique_nodes:
            areas[node_id] += share
    return areas


def parse_nodal_eqv_stresses(path: Path) -> dict[int, float]:
    stresses: dict[int, float] = {}
    reading_principal_rows = False
    in_estimated_bounds = False

    for raw_line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw_line.strip()
        upper = line.upper()

        if "ESTIMATED BOUNDS" in upper:
            in_estimated_bounds = True
        if upper.startswith("PRINT S"):
            in_estimated_bounds = False

        if "NODE" in upper and "S1" in upper and "SEQV" in upper:
            reading_principal_rows = not in_estimated_bounds
            continue

        if not reading_principal_rows:
            continue

        if upper.startswith(("MINIMUM", "MAXIMUM", "***")):
            reading_principal_rows = False
            in_estimated_bounds = False
            continue

        parts = line.split()
        if len(parts) >= 6 and parts[0].isdigit():
            node = int(parts[0])
            seqv = abs(to_float(parts[5]))
            stresses[node] = max(stresses.get(node, 0.0), seqv)

    return stresses


def write_stress_area_csv(
    path: Path,
    apdl_path: Path,
    post_output_path: Path,
    allowable_mpa: float,
) -> dict[str, float]:
    nodes, elements = parse_apdl_mesh(apdl_path)
    tributary_areas = nodal_tributary_areas(nodes, elements)
    stresses = parse_nodal_eqv_stresses(post_output_path)

    total_area = sum(tributary_areas.values())
    area_over_allowable = 0.0
    nodes_over_allowable = 0
    max_stress = 0.0

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(
            [
                "node",
                "x_mm",
                "y_mm",
                "tributary_area_mm2",
                "seqv_MPa",
                "over_allowable",
            ]
        )
        for node_id in sorted(nodes):
            x, y = nodes[node_id]
            area = tributary_areas.get(node_id, 0.0)
            stress = stresses.get(node_id, 0.0)
            over_allowable = stress > allowable_mpa
            if over_allowable:
                area_over_allowable += area
                nodes_over_allowable += 1
            max_stress = max(max_stress, stress)
            writer.writerow(
                [
                    node_id,
                    f"{x:.9g}",
                    f"{y:.9g}",
                    f"{area:.9g}",
                    f"{stress:.9g}",
                    int(over_allowable),
                ]
            )

    return {
        "nodal_area_total_mm2": total_area,
        "area_over_allowable_mm2": area_over_allowable,
        "area_over_allowable_percent": 100.0 * area_over_allowable / total_area
        if total_area
        else 0.0,
        "nodes_over_allowable": float(nodes_over_allowable),
        "max_eqv_stress_from_area_MPa": max_stress,
    }


def write_reaction_csv(path: Path, values: dict[str, float]) -> list[tuple[str, float]]:
    reactions = [
        (key.removesuffix("_RFZ_N"), value)
        for key, value in values.items()
        if key.endswith("_RFZ_N")
    ]
    reactions.sort()
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["support", "reaction_FZ_N", "applied_load_N"])
        for name, reaction in reactions:
            writer.writerow([name, f"{reaction:.8f}", f"{-reaction:.8f}"])
    return reactions


def write_legacy_hinge_csv(path: Path, reactions: list[tuple[str, float]]) -> None:
    hinge_reactions = [
        (name, reaction)
        for name, reaction in reactions
        if name.endswith("_upper") or name.endswith("_lower")
    ]
    if not hinge_reactions:
        return
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["hinge", "reaction_FZ_N", "load_on_truss_N"])
        for name, reaction in hinge_reactions:
            writer.writerow([name, f"{reaction:.8f}", f"{-reaction:.8f}"])


def write_summary(
    path: Path,
    values: dict[str, float],
    stress: dict[str, float],
    reactions: list[tuple[str, float]],
    stress_area: dict[str, float] | None = None,
) -> None:
    allowable = values.get("allowable_stress_MPa", 190.0 / 1.8)
    upper = [(name, force) for name, force in reactions if "upper" in name]
    lower = [(name, force) for name, force in reactions if "lower" in name]
    carrier_totals: dict[str, float] = {}
    for name, force in reactions:
        carrier = name.split("_")[0]
        carrier_totals[carrier] = carrier_totals.get(carrier, 0.0) + force
    governing = (
        max(carrier_totals.items(), key=lambda item: abs(item[1]))
        if carrier_totals
        else None
    )

    with path.open("w", encoding="utf-8") as file:
        file.write("Aufgabe 1.2 plate structural summary\n")
        file.write("=====================================\n\n")
        file.write(f"pressure_N_per_mm2 = {values['pressure_N_per_mm2']:.12f}\n")
        file.write(f"allowable_stress_MPa = {allowable:.8f}\n")
        file.write(f"max_eqv_stress_top_MPa = {stress['max_eqv_stress_top_MPa']:.6f}\n")
        file.write(f"max_eqv_stress_bottom_MPa = {stress['max_eqv_stress_bottom_MPa']:.6f}\n")
        file.write(f"max_eqv_stress_MPa = {stress['max_eqv_stress_MPa']:.6f}\n")
        file.write(
            f"estimated_max_eqv_stress_MPa = {stress['estimated_max_eqv_stress_MPa']:.6f}\n"
        )
        file.write(f"stress_utilization = {stress['max_eqv_stress_MPa'] / allowable:.6f}\n")
        file.write(f"max_abs_UZ_mm = {stress['max_abs_UZ_mm']:.6f}\n")
        if stress_area:
            file.write(
                f"area_over_allowable_mm2 = {stress_area['area_over_allowable_mm2']:.6f}\n"
            )
            file.write(
                f"area_over_allowable_percent = "
                f"{stress_area['area_over_allowable_percent']:.6f}\n"
            )
            file.write(
                f"nodes_over_allowable = {stress_area['nodes_over_allowable']:.0f}\n"
            )
        file.write("\nSupport reactions RFZ from support on plate:\n")
        for name, force in reactions:
            file.write(f"- {name}: {force:.6f} N\n")
        file.write("\nCarrier reaction sums:\n")
        for carrier, force in sorted(carrier_totals.items()):
            file.write(f"- {carrier}: {force:.6f} N\n")
        if governing:
            file.write(
                f"\nGoverning support group by absolute reaction sum: {governing[0]} "
                f"with {governing[1]:.6f} N\n"
            )
        if upper or lower:
            file.write("\nUpper hinge reactions:\n")
            for name, force in upper:
                file.write(f"- {name}: {force:.6f} N\n")
            file.write("\nLower hinge reactions:\n")
            for name, force in lower:
                file.write(f"- {name}: {force:.6f} N\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", type=Path, default=RESULTS_TXT)
    parser.add_argument("--post-output", type=Path, default=POST_OUT)
    parser.add_argument("--out-dir", type=Path, default=OUT_DIR)
    parser.add_argument("--apdl", type=Path, default=None)
    args = parser.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)
    values = parse_key_values(args.results)
    stress = parse_post_output(args.post_output)
    allowable = values.get("allowable_stress_MPa", 190.0 / 1.8)
    apdl_path = args.apdl or args.out_dir / "plate_structural.inp"
    stress_area = None
    if apdl_path.exists() and args.post_output.exists():
        stress_area = write_stress_area_csv(
            args.out_dir / "plate_stress_area.csv",
            apdl_path,
            args.post_output,
            allowable,
        )
    reactions = write_reaction_csv(args.out_dir / "plate_support_reactions.csv", values)
    write_legacy_hinge_csv(args.out_dir / "plate_hinge_reactions.csv", reactions)
    write_summary(
        args.out_dir / "plate_structural_summary.txt",
        values,
        stress,
        reactions,
        stress_area,
    )
    print((args.out_dir / "plate_structural_summary.txt").as_posix())
    print((args.out_dir / "plate_support_reactions.csv").as_posix())
    if stress_area:
        print((args.out_dir / "plate_stress_area.csv").as_posix())


if __name__ == "__main__":
    main()
