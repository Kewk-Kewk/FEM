"""Aufgabe 1.1 a) -- CFD-Netzgenerierung fuer die 2D-Plattenumstroemung.

Erzeugt ein Gmsh-Dreiecksnetz und konvertiert es in das Fluent-.msh-Format.
Die Rechendomaene ist ein Rechteck mit ausgeschnittener Platte in der Mitte.
Verfeinerungszonen:
  - An der Plattenkante (Staudruck, Drucksprung)
  - Im Nachlaufbereich (Unterdruck, reduzierte Geschwindigkeit)
  - Optionale Grenzschicht (BoundaryLayer-Feld)

Benoetigte Pakete: gmsh, fluent_mesh_writer (eigenes Modul)
"""
from __future__ import annotations

import argparse
from pathlib import Path

import gmsh

from aufgabe1_params import get_params
from fluent_mesh_writer import write_fluent_mesh


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a 2D mesh for the CFD plate simulation."
    )
    parser.add_argument("--output", type=Path, default=Path("Aufgabe1/out/plate_2d.msh"))
    parser.add_argument("--gmsh-output", type=Path, default=Path("Aufgabe1/out/plate_2d_gmsh.msh"))
    parser.add_argument("--no-boundary-layer", action="store_true")
    parser.add_argument("--show-gmsh", action="store_true")
    return parser.parse_args()


def bbox_close(value: float, target: float, tol: float) -> bool:
    return abs(value - target) <= tol


def classify_boundary_curves(params, curve_tags: list[int]) -> dict[str, list[int]]:
    """Ordne die Gmsh-Kurven den physikalischen Raendern zu.

    Anhand der Bounding-Box jeder Kurve wird entschieden, ob sie
    zum Einlass, Auslass, Ober-/Unterseite oder zur Plattenwand gehoert.
    """
    domain = params.domain_m
    tol = max(params.sign_thickness_m * 0.25, 1.0e-6)
    groups = {name: [] for name in ["inlet", "outlet", "top", "bottom", "plate_wall"]}

    for tag in curve_tags:
        xmin, ymin, _zmin, xmax, ymax, _zmax = gmsh.model.getBoundingBox(1, tag)
        if bbox_close(xmin, domain["x_min"], tol) and bbox_close(xmax, domain["x_min"], tol):
            groups["inlet"].append(tag)
        elif bbox_close(xmin, domain["x_max"], tol) and bbox_close(xmax, domain["x_max"], tol):
            groups["outlet"].append(tag)
        elif bbox_close(ymin, domain["y_max"], tol) and bbox_close(ymax, domain["y_max"], tol):
            groups["top"].append(tag)
        elif bbox_close(ymin, domain["y_min"], tol) and bbox_close(ymax, domain["y_min"], tol):
            groups["bottom"].append(tag)
        elif (
            xmin >= domain["plate_x_min"] - tol
            and xmax <= domain["plate_x_max"] + tol
            and ymin >= domain["plate_y_min"] - tol
            and ymax <= domain["plate_y_max"] + tol
        ):
            groups["plate_wall"].append(tag)

    return groups


def create_geometry(params, no_boundary_layer: bool) -> None:
    """Erstelle die 2D-Geometrie und das Netzfeld in Gmsh.

    Erzeugt ein Rechteck (Domain) mit einem ausgeschnittenen Rechteck (Platte)
    und setzt Verfeinerungsfelder (Distance/Threshold fuer Plattenkante,
    Box fuer Nachlauf, optional BoundaryLayer).
    """
    domain = params.domain_m
    mesh = params.recommended_mesh_m

    gmsh.model.add("aufgabe1_plate_2d")
    occ = gmsh.model.occ

    domain_surface = occ.addRectangle(
        domain["x_min"],
        domain["y_min"],
        0.0,
        domain["x_max"] - domain["x_min"],
        domain["y_max"] - domain["y_min"],
    )
    plate_surface = occ.addRectangle(
        domain["plate_x_min"],
        domain["plate_y_min"],
        0.0,
        domain["plate_x_max"] - domain["plate_x_min"],
        domain["plate_y_max"] - domain["plate_y_min"],
    )
    cut, _ = occ.cut([(2, domain_surface)], [(2, plate_surface)], removeObject=True, removeTool=True)
    occ.synchronize()

    surfaces = [tag for dim, tag in cut if dim == 2]
    if not surfaces:
        surfaces = [tag for _dim, tag in gmsh.model.getEntities(2)]

    gmsh.model.addPhysicalGroup(2, surfaces, tag=1)
    gmsh.model.setPhysicalName(2, 1, "fluid")

    curve_tags = [tag for _dim, tag in gmsh.model.getEntities(1)]
    boundary_groups = classify_boundary_curves(params, curve_tags)
    physical_tag = 2
    for name, tags in boundary_groups.items():
        if not tags:
            raise RuntimeError(f"No curves were classified as {name}")
        gmsh.model.addPhysicalGroup(1, tags, tag=physical_tag)
        gmsh.model.setPhysicalName(1, physical_tag, name)
        physical_tag += 1

    gmsh.option.setNumber("Mesh.ElementOrder", 1)
    gmsh.option.setNumber("Mesh.Algorithm", 6)
    gmsh.option.setNumber("Mesh.MeshSizeMin", mesh["plate_edge_size"])
    gmsh.option.setNumber("Mesh.MeshSizeMax", 0.35 * params.plate_height_m)

    distance = gmsh.model.mesh.field.add("Distance")
    gmsh.model.mesh.field.setNumbers(distance, "CurvesList", boundary_groups["plate_wall"])
    gmsh.model.mesh.field.setNumber(distance, "Sampling", 200)

    plate_refinement = gmsh.model.mesh.field.add("Threshold")
    gmsh.model.mesh.field.setNumber(plate_refinement, "InField", distance)
    gmsh.model.mesh.field.setNumber(plate_refinement, "SizeMin", mesh["plate_edge_size"])
    gmsh.model.mesh.field.setNumber(plate_refinement, "SizeMax", 0.15 * params.plate_height_m)
    gmsh.model.mesh.field.setNumber(plate_refinement, "DistMin", 0.02 * params.plate_height_m)
    gmsh.model.mesh.field.setNumber(plate_refinement, "DistMax", 1.0 * params.plate_height_m)

    wake = gmsh.model.mesh.field.add("Box")
    gmsh.model.mesh.field.setNumber(wake, "VIn", mesh["wake_size"])
    gmsh.model.mesh.field.setNumber(wake, "VOut", 0.35 * params.plate_height_m)
    gmsh.model.mesh.field.setNumber(wake, "XMin", domain["plate_x_min"])
    gmsh.model.mesh.field.setNumber(wake, "XMax", 14.0 * params.plate_height_m)
    gmsh.model.mesh.field.setNumber(wake, "YMin", -1.5 * params.plate_height_m)
    gmsh.model.mesh.field.setNumber(wake, "YMax", 1.5 * params.plate_height_m)

    fields = [plate_refinement, wake]
    if not no_boundary_layer:
        boundary_layer = gmsh.model.mesh.field.add("BoundaryLayer")
        gmsh.model.mesh.field.setNumbers(boundary_layer, "EdgesList", boundary_groups["plate_wall"])
        gmsh.model.mesh.field.setNumber(boundary_layer, "hwall_n", mesh["first_layer_height"])
        gmsh.model.mesh.field.setNumber(boundary_layer, "ratio", 1.2)
        gmsh.model.mesh.field.setNumber(boundary_layer, "thickness", 0.02 * params.plate_height_m)
        gmsh.model.mesh.field.setNumber(boundary_layer, "Quads", 1)
        gmsh.model.mesh.field.setAsBoundaryLayer(boundary_layer)

    background = gmsh.model.mesh.field.add("Min")
    gmsh.model.mesh.field.setNumbers(background, "FieldsList", fields)
    gmsh.model.mesh.field.setAsBackgroundMesh(background)


def collect_mesh_data() -> tuple[
    list[tuple[float, float]],
    list[list[int]],
    dict[tuple[int, int], str],
]:
    node_tags, coords, _ = gmsh.model.mesh.getNodes()
    tag_to_node_id = {int(tag): idx + 1 for idx, tag in enumerate(node_tags)}
    points = [
        (float(coords[3 * idx]), float(coords[3 * idx + 1]))
        for idx in range(len(node_tags))
    ]

    cells: list[list[int]] = []
    for element_type, _element_tags, node_tag_data in zip(*gmsh.model.mesh.getElements(2)):
        name, _dim, _order, n_nodes, _local_coords, _ = gmsh.model.mesh.getElementProperties(element_type)
        if name not in {"Triangle 3", "Quadrilateral 4"}:
            raise RuntimeError(f"Unsupported element type from Gmsh: {name}")
        for start in range(0, len(node_tag_data), n_nodes):
            cells.append(
                [tag_to_node_id[int(tag)] for tag in node_tag_data[start : start + n_nodes]]
            )

    boundary_zones_by_edge: dict[tuple[int, int], str] = {}
    for _dim, physical_tag in gmsh.model.getPhysicalGroups(1):
        name = gmsh.model.getPhysicalName(1, physical_tag)
        for entity in gmsh.model.getEntitiesForPhysicalGroup(1, physical_tag):
            element_data = gmsh.model.mesh.getElements(1, entity)
            for element_type, _element_tags, node_tag_data in zip(*element_data):
                element_name, _dim, _order, n_nodes, _local_coords, _ = gmsh.model.mesh.getElementProperties(element_type)
                if element_name != "Line 2":
                    continue
                for start in range(0, len(node_tag_data), n_nodes):
                    n0 = tag_to_node_id[int(node_tag_data[start])]
                    n1 = tag_to_node_id[int(node_tag_data[start + 1])]
                    boundary_zones_by_edge[tuple(sorted((n0, n1)))] = name

    return points, cells, boundary_zones_by_edge


def main() -> None:
    args = parse_args()
    params = get_params()

    gmsh.initialize()
    try:
        gmsh.option.setNumber("General.Terminal", 1)
        create_geometry(params, args.no_boundary_layer)
        gmsh.model.mesh.generate(2)
        args.gmsh_output.parent.mkdir(parents=True, exist_ok=True)
        gmsh.write(str(args.gmsh_output))
        points, cells, boundary_zones_by_edge = collect_mesh_data()
        write_fluent_mesh(args.output, points, cells, boundary_zones_by_edge)
        print(f"Wrote Gmsh mesh: {args.gmsh_output}")
        print(f"Wrote Fluent mesh: {args.output}")
        print(f"Nodes: {len(points)}")
        print(f"Cells: {len(cells)}")
        print(f"Boundary faces: {len(boundary_zones_by_edge)}")
        if args.show_gmsh:
            gmsh.fltk.run()
    finally:
        gmsh.finalize()


if __name__ == "__main__":
    main()
