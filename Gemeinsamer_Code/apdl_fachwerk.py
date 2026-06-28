"""Gemeinsamer_Code/apdl_fachwerk.py

Erzeugt Eingabedateien (.inp) für das Fachwerkmodell in ANSYS MAPDL und wertet die Ergebnisse aus.
"""
from __future__ import annotations

import csv
import re
from math import pi
from pathlib import Path


def tube_area_mm2(outer_mm: float, inner_mm: float) -> float:
    return pi / 4.0 * (outer_mm**2 - inner_mm**2)


# Rohrquerschnitte aus Dimensionierung (Aufgabe 1.2d)
AREA_BY_KIND_MM2 = {
    "vertical": tube_area_mm2(16.0, 13.0),    # 16 x 1.5 mm
    "horizontal": tube_area_mm2(12.0, 9.0),   # 12 x 1.5 mm
    "diagonal": tube_area_mm2(12.0, 9.0),     # 12 x 1.5 mm
}

E_STEEL_MPA = 210_000.0   # E-Modul Stahl [N/mm^2]


def read_average_hinge_loads(path: Path) -> tuple[str, float, float]:
    by_hinge: dict[str, float] = {}
    with path.open(newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        for row in reader:
            by_hinge[row["hinge"]] = abs(float(row["load_on_truss_N"]))
    
    uppers = [force for name, force in by_hinge.items() if "upper" in name]
    lowers = [force for name, force in by_hinge.items() if "lower" in name]
    
    mean_upper = sum(uppers) / len(uppers) if uppers else 0.0
    mean_lower = sum(lowers) / len(lowers) if lowers else 0.0
    
    return "Average", mean_upper, mean_lower


def section_number(kind: str) -> int:
    return {"vertical": 1, "horizontal": 2, "diagonal": 3}[kind]


def generate_truss_apdl(
    path: Path,
    params,
    nodes,
    elements,
    upper_load_n: float,
    lower_load_n: float,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="ascii", newline="\n") as file:
        file.write("/CLEAR\n")
        file.write("/FILNAME,truss_1_2,1\n")
        file.write("/PREP7\n")
        file.write("ET,1,LINK180\n")
        file.write(f"MP,EX,1,{E_STEEL_MPA:.9g}\n")
        file.write("MP,PRXY,1,0.3\n")
        file.write(f"SECTYPE,1,LINK\nSECDATA,{AREA_BY_KIND_MM2['vertical']:.12g}\n")
        file.write(f"SECTYPE,2,LINK\nSECDATA,{AREA_BY_KIND_MM2['horizontal']:.12g}\n")
        file.write(f"SECTYPE,3,LINK\nSECDATA,{AREA_BY_KIND_MM2['diagonal']:.12g}\n")
        
        for index, node in enumerate(nodes, start=1):
            file.write(f"N,{index},{node.x * 1000.0:.9g},{node.y * 1000.0:.9g},0\n")
            
        file.write("TYPE,1\n")
        file.write("MAT,1\n")
        
        for element in elements:
            file.write(f"SECNUM,{section_number(element.kind)}\n")
            file.write(f"E,{element.node_i + 1},{element.node_j + 1}\n")
            
        file.write("ALLSEL,ALL\n")
        file.write("D,ALL,UZ,0\n")

        node_by_name = {node.name: index for index, node in enumerate(nodes, start=1)}
        file.write(f"D,{node_by_name['L0']},UY,0\n")
        file.write(f"D,{node_by_name['R0']},UX,0\n")
        file.write(f"D,{node_by_name['R0']},UY,0\n")
        file.write(f"F,{node_by_name[f'R{len(nodes)//2 - 1}']},FX,{-upper_load_n:.12g}\n")
        file.write(f"F,{node_by_name[f'R{len(nodes)//2 - 2}']},FX,{-lower_load_n:.12g}\n")
        file.write("FINISH\n")

        file.write("/SOLU\n")
        file.write("ANTYPE,STATIC\n")
        file.write("NLGEOM,OFF\n")
        file.write("OUTRES,ALL,ALL\n")
        file.write("SOLVE\n")
        file.write("FINISH\n")

        file.write("/POST1\n")
        file.write("SET,LAST\n")
        file.write("ETABLE,AXIAL,SMISC,1\n")
        file.write("ETABLE,STRESS,LS,1\n")
        file.write("PRETAB,AXIAL,STRESS\n")
        file.write("PRNSOL,U,COMP\n")
        file.write(f"*GET,R_L0_FY,NODE,{node_by_name['L0']},RF,FY\n")
        file.write(f"*GET,R_R0_FX,NODE,{node_by_name['R0']},RF,FX\n")
        file.write(f"*GET,R_R0_FY,NODE,{node_by_name['R0']},RF,FY\n")
        
        last_r_node = f"R{len(nodes)//2 - 1}"
        prev_r_node = f"R{len(nodes)//2 - 2}"
        file.write(f"*GET,UX_G,NODE,{node_by_name[last_r_node]},U,X\n")
        file.write(f"*GET,UY_G,NODE,{node_by_name[last_r_node]},U,Y\n")
        file.write(f"*GET,UX_R6,NODE,{node_by_name[prev_r_node]},U,X\n")
        file.write(f"*GET,UY_R6,NODE,{node_by_name[prev_r_node]},U,Y\n")
        
        file.write("*CFOPEN,truss_apdl_summary,txt\n")
        file.write("*VWRITE,R_L0_FY\n('R_L0_FY_N = ',F20.8)\n")
        file.write("*VWRITE,R_R0_FX\n('R_R0_FX_N = ',F20.8)\n")
        file.write("*VWRITE,R_R0_FY\n('R_R0_FY_N = ',F20.8)\n")
        file.write("*VWRITE,UX_G\n('UX_G_mm = ',F20.8)\n")
        file.write("*VWRITE,UY_G\n('UY_G_mm = ',F20.8)\n")
        file.write("*VWRITE,UX_R6\n('UX_R6_mm = ',F20.8)\n")
        file.write("*VWRITE,UY_R6\n('UY_R6_mm = ',F20.8)\n")
        file.write("*CFCLOS\n")
        file.write("FINISH\n")


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
