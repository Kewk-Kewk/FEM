"""Aufgabe 1.2 a) — Singularitaetsstudie fuer die Punktlagerung.

Erzeugt fuer mehrere lokale Netzgroessen (10, 2, 1 mm) je ein
APDL-Eingabefile mit Punktlagern und fuehrt optional den ANSYS-Lauf durch.
Sammelt die Ergebnisse (max. Vergleichsspannung, Tributarflaeche ueber
zul. Spannung) in einer CSV-Datei und erzeugt eine LaTeX-Tabelle.

Dies zeigt, dass die Maximalspannung an einem Punktlager unbegrenzt waechst
(Singularitaet), waehrend die Tributarflaeche konvergiert.
"""
from __future__ import annotations

import argparse
import csv
import os
import shutil
import subprocess
import sys
from pathlib import Path

from parse_plate_structural_results import parse_apdl_mesh, parse_key_values
from structural_plate_apdl import (
    generate_apdl,
    write_export_plots,
    write_post_probe,
)
from utils import read_summary_value


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SUMMARY = ROOT / "Aufgabe1" / "data" / "drag_summary.txt"
DEFAULT_OUT_ROOT = ROOT / "Aufgabe1" / "out" / "plate_singularity_study"
DEFAULT_DATA_CSV = ROOT / "Aufgabe1" / "data" / "plate_singularity_study.csv"
DEFAULT_TABLE = ROOT / "Aufgabe1" / "data" / "plate_singularity_study_table.tex"
DEFAULT_REFINEMENTS = (10.0, 2.0, 1.0)


def case_suffix(value: float) -> str:
    text = f"{value:g}".replace(".", "p")
    return f"h{text}"


def read_summary_optional(path: Path) -> dict[str, float]:
    if not path.exists():
        return {}
    return parse_key_values(path)


def run_ansys(ansys_exe: Path, input_file: Path, output_file: Path, work_dir: Path, job: str) -> None:
    command = [str(ansys_exe)]
    if os.name != "nt" and ansys_exe.suffix.lower() == ".exe":
        command = ["wine", str(ansys_exe)]
    subprocess.run(
        command
        + [
            "-b",
            "-i",
            str(input_file),
            "-o",
            str(output_file),
            "-dir",
            str(work_dir),
            "-j",
            job,
        ],
        check=True,
    )


def mesh_stats_from_apdl(path: Path) -> dict[str, int]:
    nodes, elements = parse_apdl_mesh(path)
    support_node_count = 0
    for raw_line in path.read_text(encoding="ascii", errors="ignore").splitlines():
        parts = [part.strip().upper() for part in raw_line.split(",")]
        if len(parts) >= 3 and parts[0] == "D" and parts[2] == "UZ":
            support_node_count += 1
    return {
        "nodes": len(nodes),
        "elements": len(elements),
        "support_node_count": support_node_count,
    }


def parse_case_if_ready(case_dir: Path) -> None:
    results = case_dir / "plate_structural_results.txt"
    post_output = case_dir / "plate_post_probe.out"
    apdl = case_dir / "plate_structural.inp"
    if not results.exists() or not post_output.exists():
        return

    subprocess.run(
        [
            sys.executable,
            str(ROOT / "Aufgabe1" / "code" / "parse_plate_structural_results.py"),
            "--results",
            str(results),
            "--post-output",
            str(post_output),
            "--apdl",
            str(apdl),
            "--out-dir",
            str(case_dir),
        ],
        check=True,
    )


def normalize_exported_plots(case_dir: Path, export_job_name: str) -> None:
    exported = sorted(case_dir.glob(f"{export_job_name}*.png"))
    exported = [
        path
        for path in exported
        if path.name
        not in {
            "plate_point_mesh_preview.png",
            "plate_stress_eqv_ansys.png",
            "plate_deformation_ansys.png",
        }
    ]
    if len(exported) >= 2:
        shutil.copyfile(exported[1], case_dir / "plate_stress_eqv_ansys.png")
    if len(exported) >= 3:
        shutil.copyfile(exported[2], case_dir / "plate_deformation_ansys.png")


def write_table(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as file:
        file.write("\\begin{tabular}{rrrrrr}\n")
        file.write("\\toprule\n")
        file.write(
            "lokale Netzgroesse [mm] & Knoten & Elemente & "
            "$\\sigma_{v,\\max}$ [MPa] & $A(\\sigma_v>\\sigma_\\mathrm{zul})$ "
            "[mm$^2$] & Status\\\\\n"
        )
        file.write("\\midrule\n")
        for row in rows:
            file.write(
                f"{row['local_refinement_mm']} & {row['nodes']} & {row['elements']} & "
                f"{row['max_eqv_stress_MPa']} & {row['area_over_allowable_mm2']} & "
                f"{row['status']}\\\\\n"
            )
        file.write("\\bottomrule\n")
        file.write("\\end{tabular}\n")


def format_number(value: float | None, decimals: int = 2) -> str:
    if value is None:
        return "--"
    return f"{value:.{decimals}f}"


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Generate and optionally solve the point-support mesh study "
            "for Aufgabe 1.2."
        )
    )
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument("--out-root", type=Path, default=DEFAULT_OUT_ROOT)
    parser.add_argument("--data-csv", type=Path, default=DEFAULT_DATA_CSV)
    parser.add_argument("--table-tex", type=Path, default=DEFAULT_TABLE)
    parser.add_argument("--refinements-mm", type=float, nargs="+", default=list(DEFAULT_REFINEMENTS))
    parser.add_argument("--mesh-size-mm", type=float, default=50.0)
    parser.add_argument("--support-patch-mm", type=float, default=100.0)
    parser.add_argument("--support-influence-mm", type=float, default=200.0)
    parser.add_argument("--circle-angular-divisions", type=int, default=60)
    parser.add_argument("--ansys-exe", type=Path, default=None)
    parser.add_argument("--solve", action="store_true")
    args = parser.parse_args()

    if args.solve and args.ansys_exe is None:
        raise SystemExit("--solve requires --ansys-exe")

    total_drag_n = read_summary_value(args.summary, "total_drag_N")
    rows: list[dict[str, str]] = []
    csv_rows: list[dict[str, str]] = []

    for refinement in args.refinements_mm:
        suffix = case_suffix(refinement)
        case_name = f"plate_point_{suffix}"
        case_dir = args.out_root / suffix
        job_name = case_name
        apdl_path = case_dir / "plate_structural.inp"

        stats = generate_apdl(
            apdl_path,
            args.mesh_size_mm,
            total_drag_n,
            args.support_patch_mm,
            refinement,
            args.support_influence_mm,
            "point-support",
            job_name,
            circle_angular_divisions=args.circle_angular_divisions,
            mesh_preview_path=case_dir / "plate_point_mesh_preview.png",
        )
        write_post_probe(case_dir / "plate_post_probe.inp", job_name)
        write_export_plots(case_dir / "plate_export_plots.inp", job_name)

        if args.solve:
            assert args.ansys_exe is not None
            run_ansys(
                args.ansys_exe,
                apdl_path,
                case_dir / "plate_structural_solver.out",
                case_dir,
                job_name,
            )
            run_ansys(
                args.ansys_exe,
                case_dir / "plate_post_probe.inp",
                case_dir / "plate_post_probe.out",
                case_dir,
                f"{job_name}_post",
            )
            run_ansys(
                args.ansys_exe,
                case_dir / "plate_export_plots.inp",
                case_dir / "plate_export_plots.out",
                case_dir,
                f"{job_name}_export",
            )
            normalize_exported_plots(case_dir, f"{job_name}_export")

        normalize_exported_plots(case_dir, f"{job_name}_export")
        parse_case_if_ready(case_dir)
        summary_values = read_summary_optional(case_dir / "plate_structural_summary.txt")
        status = "ausgewertet" if summary_values else "offen"

        max_stress = summary_values.get("max_eqv_stress_MPa")
        area_over = summary_values.get("area_over_allowable_mm2")
        area_percent = summary_values.get("area_over_allowable_percent")
        max_uz = summary_values.get("max_abs_UZ_mm")

        csv_row = {
            "status": status,
            "case_dir": case_dir.as_posix(),
            "local_refinement_mm": f"{refinement:g}",
            "mesh_size_mm": f"{args.mesh_size_mm:g}",
            "support_diameter_mm": f"{args.support_patch_mm:g}",
            "support_influence_mm": f"{args.support_influence_mm:g}",
            "nodes": str(int(stats["nodes"])),
            "elements": str(int(stats["elements"])),
            "support_node_count": str(int(stats["support_node_count"])),
            "max_eqv_stress_MPa": format_number(max_stress),
            "max_abs_UZ_mm": format_number(max_uz),
            "area_over_allowable_mm2": format_number(area_over, 1),
            "area_over_allowable_percent": format_number(area_percent, 4),
        }
        csv_rows.append(csv_row)
        rows.append(csv_row)

    args.data_csv.parent.mkdir(parents=True, exist_ok=True)
    with args.data_csv.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(csv_rows[0]))
        writer.writeheader()
        writer.writerows(csv_rows)

    write_table(args.table_tex, rows)
    print(args.data_csv.as_posix())
    print(args.table_tex.as_posix())
    print(args.out_root.as_posix())


if __name__ == "__main__":
    main()
