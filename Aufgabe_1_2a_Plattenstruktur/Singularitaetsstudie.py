"""Aufgabe_1_2a_Plattenstruktur/Singularitaetsstudie.py

Steuert die Singularitaetsstudie fuer die Punktlagerung. Erzeugt APDL-Skripte 
fuer verschiedene lokale Netzgroessen (10 mm, 2 mm, 1 mm) und wertet diese aus.
"""
from __future__ import annotations

import sys
import csv
import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

from Gemeinsamer_Code.apdl_platte_schale import generate_plate_apdl, write_post_probe, write_export_plots
from Gemeinsamer_Code.apdl_ergebnis_parser import parse_apdl_mesh, parse_key_values, write_stress_area_csv
from Gemeinsamer_Code.hilfsfunktionen import read_summary_value

# Systemparameter
PARAMS_PLATE = {
    "project": 27,
    "width_m": 3.0,
    "height_m": 2.0,
    "thickness_m": 0.003,
    "h_m": 0.25,
}

REFINEMENTS = [10.0, 2.0, 1.0]  # Lokale Netzgroessen am Punktlager in mm


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


def parse_case_if_ready(case_dir: Path) -> None:
    results = case_dir / "plate_structural_results.txt"
    post_output = case_dir / "plate_post_probe.out"
    apdl = case_dir / "plate_structural.inp"
    if not results.exists() or not post_output.exists():
        return

    values = parse_key_values(results)
    allowable = values.get("allowable_stress_MPa", 190.0 / 1.8)
    
    write_stress_area_csv(
        case_dir / "plate_stress_area.csv",
        apdl,
        post_output,
        allowable,
    )
    
    from Gemeinsamer_Code.apdl_ergebnis_parser import write_reaction_csv, write_legacy_hinge_csv, write_plate_summary_report, parse_post_output
    stress = parse_post_output(post_output)
    reactions = write_reaction_csv(case_dir / "plate_support_reactions.csv", values)
    write_legacy_hinge_csv(case_dir / "plate_hinge_reactions.csv", reactions)
    
    stress_area = {
        "area_over_allowable_mm2": 0.0,
        "area_over_allowable_percent": 0.0,
        "nodes_over_allowable": 0.0
    }
    area_csv = case_dir / "plate_stress_area.csv"
    if area_csv.exists():
        with area_csv.open(newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            total_area = 0.0
            over_area = 0.0
            over_nodes = 0
            for r in reader:
                area = float(r["tributary_area_mm2"])
                total_area += area
                if int(r["over_allowable"]) == 1:
                    over_area += area
                    over_nodes += 1
            stress_area = {
                "area_over_allowable_mm2": over_area,
                "area_over_allowable_percent": 100.0 * over_area / total_area if total_area > 0 else 0.0,
                "nodes_over_allowable": float(over_nodes)
            }
            
    write_plate_summary_report(
        case_dir / "plate_structural_summary.txt",
        values,
        stress,
        reactions,
        stress_area,
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
    task_dir = ROOT / "Aufgabe_1_2a_Plattenstruktur"
    data_dir = task_dir / "data"
    out_root = task_dir / "out" / "plate_singularity_study"
    
    cfd_summary = ROOT / "Aufgabe_1_1_CFD_Stroemung" / "data" / "drag_summary.txt"
    if not cfd_summary.exists():
        total_drag_n = 6430.054
    else:
        total_drag_n = read_summary_value(cfd_summary, "total_drag_N")

    rows: list[dict[str, str]] = []
    csv_rows: list[dict[str, str]] = []

    for refinement in REFINEMENTS:
        suffix = case_suffix(refinement)
        case_name = f"plate_point_{suffix}"
        case_dir = out_root / suffix
        job_name = case_name
        apdl_path = case_dir / "plate_structural.inp"

        stats = generate_plate_apdl(
            params=PARAMS_PLATE,
            path=apdl_path,
            mesh_size_mm=50.0,
            total_drag_n=total_drag_n,
            support_patch_mm=100.0,
            support_refinement_mm=refinement,
            support_influence_mm=200.0,
            support_mode="point-support",
            job_name=job_name,
            circle_angular_divisions=60,
            mesh_preview_path=case_dir / "plate_point_mesh_preview.png",
        )
        write_post_probe(case_dir / "plate_post_probe.inp", job_name)
        write_export_plots(case_dir / "plate_export_plots.inp", job_name)

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
            "mesh_size_mm": "50",
            "support_diameter_mm": "100",
            "support_influence_mm": "200",
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

    data_csv = data_dir / "plate_singularity_study.csv"
    table_tex = data_dir / "plate_singularity_study_table.tex"
    
    with data_csv.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(csv_rows[0].keys()))
        writer.writeheader()
        writer.writerows(csv_rows)

    write_table(table_tex, rows)
    print("Singularitaetsstudie abgeschlossen.")


if __name__ == "__main__":
    main()
