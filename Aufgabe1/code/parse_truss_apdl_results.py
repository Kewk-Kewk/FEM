"""Aufgabe 1.2 — Parser fuer die ANSYS-MAPDL-Fachwerkergebnisse.

Liest die PRETAB-Ausgabe (Elementtabelle mit Axialkraeften und Spannungen)
aus der ANSYS-Ausgabedatei und vergleicht sie elementweise mit den
Python-FEM-Ergebnissen.

Eingabe:  truss_structural_solver.out (ANSYS-Ausgabe)
          truss_index_table.csv (Element-Zuordnung)
          truss_element_forces.csv (Python-FEM-Ergebnisse)
Ausgabe:  truss_apdl_element_forces.csv
          truss_comparison_python_ansys.csv
          truss_comparison_summary.txt
"""
from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path


OUT_DIR = Path("Aufgabe1/out")


def parse_apdl_element_table(output_path: Path, index_path: Path) -> list[dict[str, float | str]]:
    elements: dict[int, dict[str, str]] = {}
    with index_path.open(newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        for elem_id, row in enumerate(reader, start=1):
            elements[elem_id] = {"name": row["element"], "kind": row["kind"]}

    rows: list[dict[str, float | str]] = []
    reading = False
    row_re = re.compile(r"^\s*(\d+)\s+([-+0-9.Ee]+)\s+([-+0-9.Ee]+)")
    for line in output_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if "PRINT ELEMENT TABLE ITEMS PER ELEMENT" in line:
            reading = True
            continue
        if not reading:
            continue
        match = row_re.match(line)
        if not match:
            if rows and "MINIMUM VALUES" in line:
                break
            continue
        elem_id = int(match.group(1))
        rows.append(
            {
                "element_id": elem_id,
                "name": elements[elem_id]["name"],
                "kind": elements[elem_id]["kind"],
                "axial_N": float(match.group(2)),
                "stress_MPa": float(match.group(3)),
            }
        )
    return rows


def read_python_rows(path: Path) -> dict[str, dict[str, float | str]]:
    with path.open(newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        return {row["name"]: row for row in reader}


def write_apdl_rows(path: Path, rows: list[dict[str, float | str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(
            file, fieldnames=["element_id", "name", "kind", "axial_N", "stress_MPa"]
        )
        writer.writeheader()
        writer.writerows(rows)


def write_comparison(
    path: Path,
    summary_path: Path,
    apdl_rows: list[dict[str, float | str]],
    python_rows: dict[str, dict[str, float | str]],
) -> None:
    comparison: list[dict[str, float | str]] = []
    for apdl in apdl_rows:
        py = python_rows[str(apdl["name"])]
        axial_py = float(py["axial_N"])
        stress_py = float(py["stress_MPa"])
        axial_apdl = float(apdl["axial_N"])
        stress_apdl = float(apdl["stress_MPa"])
        comparison.append(
            {
                "name": apdl["name"],
                "kind": apdl["kind"],
                "python_axial_N": axial_py,
                "ansys_axial_N": axial_apdl,
                "diff_axial_N": axial_apdl - axial_py,
                "python_stress_MPa": stress_py,
                "ansys_stress_MPa": stress_apdl,
                "diff_stress_MPa": stress_apdl - stress_py,
            }
        )

    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(comparison[0].keys()))
        writer.writeheader()
        writer.writerows(comparison)

    max_force_diff = max(abs(float(row["diff_axial_N"])) for row in comparison)
    max_stress_diff = max(abs(float(row["diff_stress_MPa"])) for row in comparison)
    max_by_kind: dict[str, float] = {}
    for row in comparison:
        kind = str(row["kind"])
        max_by_kind[kind] = max(max_by_kind.get(kind, 0.0), abs(float(row["ansys_axial_N"])))

    with summary_path.open("w", encoding="utf-8") as file:
        file.write("Truss Python/ANSYS comparison\n")
        file.write("=============================\n\n")
        file.write(f"max_abs_force_difference_N = {max_force_diff:.6f}\n")
        file.write(f"max_abs_stress_difference_MPa = {max_stress_diff:.6f}\n")
        file.write("\nMaximum ANSYS axial force by member kind:\n")
        for kind, force in sorted(max_by_kind.items()):
            file.write(f"- {kind}: {force:.6f} N\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", type=Path, default=OUT_DIR)
    parser.add_argument(
        "--apdl-output", type=Path, default=OUT_DIR / "truss_structural_solver.out"
    )
    parser.add_argument(
        "--index-table", type=Path, default=OUT_DIR / "truss_index_table.csv"
    )
    parser.add_argument(
        "--python-forces", type=Path, default=OUT_DIR / "truss_element_forces.csv"
    )
    args = parser.parse_args()

    apdl_rows = parse_apdl_element_table(args.apdl_output, args.index_table)
    python_rows = read_python_rows(args.python_forces)
    write_apdl_rows(args.out_dir / "truss_apdl_element_forces.csv", apdl_rows)
    write_comparison(
        args.out_dir / "truss_comparison_python_ansys.csv",
        args.out_dir / "truss_comparison_summary.txt",
        apdl_rows,
        python_rows,
    )
    print((args.out_dir / "truss_apdl_element_forces.csv").as_posix())
    print((args.out_dir / "truss_comparison_python_ansys.csv").as_posix())
    print((args.out_dir / "truss_comparison_summary.txt").as_posix())


if __name__ == "__main__":
    main()
