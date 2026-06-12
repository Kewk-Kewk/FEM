from __future__ import annotations

import argparse
import csv
import re
from math import pi
from pathlib import Path

from aufgabe1_params import get_params
from structural_truss_1_2 import build_truss


PROJECT = 27
OUT_DIR = Path("Aufgabe1/out")
PLATE_REACTIONS = OUT_DIR / "plate_hinge_reactions.csv"

E_STEEL_MPA = 210_000.0
PANEL_COUNT = 7


def tube_area_mm2(outer_mm: float, inner_mm: float) -> float:
    return pi / 4.0 * (outer_mm**2 - inner_mm**2)


AREA_BY_KIND_MM2 = {
    "vertical": tube_area_mm2(16.0, 13.0),
    "horizontal": tube_area_mm2(12.0, 9.0),
    "diagonal": tube_area_mm2(12.0, 9.0),
}


def read_governing_hinge_loads(path: Path) -> tuple[str, float, float]:
    by_hinge: dict[str, float] = {}
    with path.open(newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        for row in reader:
            by_hinge[row["hinge"]] = abs(float(row["load_on_truss_N"]))
    carriers = sorted({hinge.split("_")[0] for hinge in by_hinge})
    governing = max(
        carriers,
        key=lambda carrier: by_hinge[f"{carrier}_upper"] + by_hinge[f"{carrier}_lower"],
    )
    return governing, by_hinge[f"{governing}_upper"], by_hinge[f"{governing}_lower"]


def section_number(kind: str) -> int:
    return {"vertical": 1, "horizontal": 2, "diagonal": 3}[kind]


def generate_apdl(
    path: Path,
    project: int,
    upper_load_n: float,
    lower_load_n: float,
) -> None:
    params = get_params(project)
    nodes, elements = build_truss(params, PANEL_COUNT)

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
        file.write(f"D,{node_by_name['L0']},UX,0\n")
        file.write(f"D,{node_by_name['L0']},UY,0\n")
        file.write(f"D,{node_by_name['R0']},UY,0\n")
        file.write(f"F,{node_by_name['R7']},FX,{-upper_load_n:.12g}\n")
        file.write(f"F,{node_by_name['R6']},FX,{-lower_load_n:.12g}\n")
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
        file.write(f"*GET,R_L0_FX,NODE,{node_by_name['L0']},RF,FX\n")
        file.write(f"*GET,R_L0_FY,NODE,{node_by_name['L0']},RF,FY\n")
        file.write(f"*GET,R_R0_FY,NODE,{node_by_name['R0']},RF,FY\n")
        file.write(f"*GET,UX_G,NODE,{node_by_name['R7']},U,X\n")
        file.write(f"*GET,UY_G,NODE,{node_by_name['R7']},U,Y\n")
        file.write(f"*GET,UX_R6,NODE,{node_by_name['R6']},U,X\n")
        file.write(f"*GET,UY_R6,NODE,{node_by_name['R6']},U,Y\n")
        file.write("*CFOPEN,truss_apdl_summary,txt\n")
        file.write("*VWRITE,R_L0_FX\n('R_L0_FX_N = ',F20.8)\n")
        file.write("*VWRITE,R_L0_FY\n('R_L0_FY_N = ',F20.8)\n")
        file.write("*VWRITE,R_R0_FY\n('R_R0_FY_N = ',F20.8)\n")
        file.write("*VWRITE,UX_G\n('UX_G_mm = ',F20.8)\n")
        file.write("*VWRITE,UY_G\n('UY_G_mm = ',F20.8)\n")
        file.write("*VWRITE,UX_R6\n('UX_R6_mm = ',F20.8)\n")
        file.write("*VWRITE,UY_R6\n('UY_R6_mm = ',F20.8)\n")
        file.write("*CFCLOS\n")
        file.write("FINISH\n")


def parse_pretab(output_path: Path, csv_path: Path, element_names_path: Path) -> None:
    names: list[tuple[int, str, str]] = []
    with element_names_path.open(newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        for elem_id, row in enumerate(reader, start=1):
            names.append((elem_id, row["element"], row["kind"]))

    text = output_path.read_text(encoding="utf-8", errors="ignore").splitlines()
    rows: list[dict[str, str | float]] = []
    reading = False
    number_re = re.compile(r"^\s*(\d+)\s+([-+0-9.Ee]+)\s+([-+0-9.Ee]+)")
    for line in text:
        if "PRINT ELEMENT TABLE ITEMS PER ELEMENT" in line:
            reading = True
            continue
        if reading:
            match = number_re.match(line)
            if match:
                elem_id = int(match.group(1))
                name, kind = next(
                    (name, kind) for candidate, name, kind in names if candidate == elem_id
                )
                rows.append(
                    {
                        "element_id": elem_id,
                        "name": name,
                        "kind": kind,
                        "axial_N": float(match.group(2)),
                        "stress_MPa": float(match.group(3)),
                    }
                )
            elif rows and line.strip() == "":
                break

    with csv_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(
            file, fieldnames=["element_id", "name", "kind", "axial_N", "stress_MPa"]
        )
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", type=int, default=PROJECT)
    parser.add_argument("--reactions", type=Path, default=PLATE_REACTIONS)
    parser.add_argument("--out-dir", type=Path, default=OUT_DIR)
    args = parser.parse_args()

    governing, upper_load_n, lower_load_n = read_governing_hinge_loads(args.reactions)
    apdl_path = args.out_dir / "truss_structural.inp"
    generate_apdl(apdl_path, args.project, upper_load_n, lower_load_n)
    print(apdl_path.as_posix())
    print(f"governing_carrier = {governing}")
    print(f"upper_load_n = {upper_load_n:.8f}")
    print(f"lower_load_n = {lower_load_n:.8f}")


if __name__ == "__main__":
    main()
