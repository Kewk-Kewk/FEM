"""
Aufgabe 1.2a — APDL-Skriptgenerator für die Schalenberechnung der Aluminiumtafel.

Dieses Skript erzeugt ein ANSYS-MAPDL-Eingabefile (.inp), das die Schildtafel
als SHELL181-Modell mit gleichmaessig verteilter Windlast aufbaut, loest und
die Ergebnisse (Spannungen, Verformungen, Lagerreaktionen) exportiert.

Unterstuetzte Lagermodelle:
  - point-support       : Punktlager an den 6 Gelenkknoten (fuer Singularitaetsnachweis)
  - line-support-full-height : Vertikale 50-mm-Linienstuetzen ueber die volle Hoehe
                               (konstruktiv realistische Variante)

Workflow:
  1. Python erzeugt das .inp-File mit Netz, Lasten und Randbedingungen
  2. ANSYS MAPDL liest das .inp-File ein und loest
  3. parse_plate_structural_results.py wertet die Ausgabedateien aus
"""
from __future__ import annotations

import argparse
import math
from dataclasses import dataclass
from pathlib import Path

from aufgabe1_params import get_params
from utils import read_summary_value

# ---------------------------------------------------------------------------
# Material- und Sicherheitsparameter (Aluminium)
# ---------------------------------------------------------------------------
PROJECT = 27
OUT_DIR = Path("Aufgabe1/out")
DRAG_SUMMARY = OUT_DIR / "drag_summary.txt"

E_ALU_MPA = 70_000.0           # Elastizitaetsmodul Aluminium [N/mm^2]
NU_ALU = 0.3                   # Querdehnzahl Aluminium
SAFETY_FACTOR = 1.8            # Sicherheitsfaktor
SIGMA_ALLOW_ALU_MPA = 190.0 / SAFETY_FACTOR  # zul. Spannung [N/mm^2]


# ---------------------------------------------------------------------------
# Datenklasse fuer Gelenkpositionen
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Hinge:
    """Position eines Gelenks auf der Tafelebene (in mm)."""
    name: str
    x_mm: float
    y_mm: float


# ---------------------------------------------------------------------------
# Hilfsfunktionen fuer Netz und Geometrie
# ---------------------------------------------------------------------------
def build_coords(stop_mm: float, step_mm: float, required: list[float]) -> list[float]:
    """Erzeuge sortierte Koordinatenliste mit Pflichtpunkten.

    Erstellt ein gleichmaessiges Raster von 0 bis stop_mm und fuegt
    alle required-Werte hinzu (z.B. Gelenk- und Stuetzenpositionen).
    """
    coords = {round(i * step_mm, 9) for i in range(int(round(stop_mm / step_mm)) + 1)}
    coords.update(round(value, 9) for value in required)
    return sorted(coords)


def build_patch_coords(center_mm: float, half_width_mm: float, step_mm: float) -> list[float]:
    """Erzeuge Koordinaten innerhalb eines Verfeinerungsbereichs um center_mm."""
    count = int(round((2.0 * half_width_mm) / step_mm))
    start = center_mm - half_width_mm
    return [start + index * step_mm for index in range(count + 1)]


def build_interval_coords(start_mm: float, stop_mm: float, step_mm: float) -> list[float]:
    """Erzeuge gleichmaessig verteilte Koordinaten in einem Intervall."""
    count = int(round((stop_mm - start_mm) / step_mm))
    return [start_mm + index * step_mm for index in range(count + 1)]


def is_inside_patch(
    x: float,
    y: float,
    hinge: Hinge,
    half_width_mm: float,
    support_mode: str,
) -> bool:
    """Pruefe, ob (x, y) innerhalb des Stuetzenbereichs eines Gelenks liegt."""
    return (
        abs(x - hinge.x_mm) <= half_width_mm + 1e-9
        and abs(y - hinge.y_mm) <= half_width_mm + 1e-9
    )


def coord_key(x: float, y: float) -> tuple[float, float]:
    """Gerundeter Koordinatenschluessel fuer das Knoten-Woerterbuch."""
    return (round(x, 6), round(y, 6))


def add_node(
    node_by_coord: dict[tuple[float, float], int],
    nodal_loads: dict[int, float],
    x: float,
    y: float,
) -> int:
    """Fuege einen Knoten hinzu oder gib die ID eines bestehenden zurueck.

    Jeder Knoten bekommt eine fortlaufende ID (1-basiert) und wird
    im nodal_loads-Dict mit 0.0 initialisiert.
    """
    key = coord_key(x, y)
    node_id = node_by_coord.get(key)
    if node_id is None:
        node_id = len(node_by_coord) + 1
        node_by_coord[key] = node_id
        nodal_loads[node_id] = 0.0
    return node_id


def append_element_load(
    nodal_loads: dict[int, float],
    nodes: tuple[int, int, int, int],
    corners_xy: tuple[tuple[float, float], ...],
    pressure_mpa: float,
) -> None:
    """Verteile die Elementlast gleichmaessig auf die Knoten.

    Die Windlast ist als gleichfoermiger Druck auf die Tafel aufgebracht.
    Fuer jedes Element wird die Flaeche berechnet und die resultierende
    Kraft gleichmaessig auf alle Elementknoten verteilt.
    """
    # Flaechenberechnung mit der Gauss'schen Trapezformel
    area_mm2 = 0.0
    corner_count = len(corners_xy)
    for index in range(corner_count):
        x1, y1 = corners_xy[index]
        x2, y2 = corners_xy[(index + 1) % corner_count]
        area_mm2 += x1 * y2 - x2 * y1
    area_mm2 = abs(area_mm2) * 0.5

    # Gleichmaessige Verteilung der Kraft auf alle Knoten
    elemental_force_n = pressure_mpa * area_mm2
    share = elemental_force_n / len(nodes)
    for node in nodes:
        nodal_loads[node] += share


def polygon_area(corners_xy: tuple[tuple[float, float], ...]) -> float:
    """Flaechenberechnung eines Polygons (Gauss'sche Trapezformel)."""
    area = 0.0
    corner_count = len(corners_xy)
    for index in range(corner_count):
        x1, y1 = corners_xy[index]
        x2, y2 = corners_xy[(index + 1) % corner_count]
        area += x1 * y2 - x2 * y1
    return abs(area) * 0.5


def verify_mesh_area(
    node_by_coord: dict[tuple[float, float], int],
    elements: list[tuple[int, int, int, int]],
    width_mm: float,
    height_mm: float,
) -> float:
    """Pruefe, ob die Summe aller Elementflaechen der Tafelflaeche entspricht.

    Dies ist ein wichtiger Konsistenzcheck: Wenn die Abweichung > 0.1%
    ist, wurde das Netz fehlerhaft erzeugt.
    """
    id_to_xy = {node_id: key for key, node_id in node_by_coord.items()}
    meshed_area = 0.0
    for n1, n2, n3, n4 in elements:
        corners = tuple(id_to_xy[node_id] for node_id in (n1, n2, n3, n4))
        meshed_area += polygon_area(corners)
    target_area = width_mm * height_mm
    rel_error = abs(meshed_area - target_area) / target_area
    if rel_error > 1e-3:
        raise ValueError(
            f"Mesh area mismatch: meshed={meshed_area:.3f} mm^2, "
            f"plate={target_area:.3f} mm^2, rel_error={rel_error:.4e}"
        )
    return rel_error


# ---------------------------------------------------------------------------
# Netzvisualisierung (optional, fuer Punktlager-Netzstudie)
# ---------------------------------------------------------------------------
def plot_mesh_preview(
    path: Path,
    node_by_coord: dict[tuple[float, float], int],
    elements: list[tuple[int, int, int, int]],
    hinges: list[Hinge],
    support_radius_mm: float,
    collar_radius_mm: float,
    title: str,
) -> None:
    """Erzeuge eine Vorschau des Netzes um das erste Gelenk herum."""
    import matplotlib.pyplot as plt
    from matplotlib.collections import PolyCollection

    id_to_xy = {node_id: key for key, node_id in node_by_coord.items()}
    zoom_hinge = hinges[0]
    zoom_radius_mm = collar_radius_mm
    zoom_x_min = max(0.0, zoom_hinge.x_mm - zoom_radius_mm)
    zoom_x_max = min(3000.0, zoom_hinge.x_mm + zoom_radius_mm)
    zoom_y_min = max(0.0, zoom_hinge.y_mm - zoom_radius_mm)
    zoom_y_max = min(2000.0, zoom_hinge.y_mm + zoom_radius_mm)
    polygons = []
    for n1, n2, n3, n4 in elements:
        polygon = [id_to_xy[node_id] for node_id in dict.fromkeys((n1, n2, n3, n4))]
        cx = sum(x for x, _ in polygon) / len(polygon)
        cy = sum(y for _, y in polygon) / len(polygon)
        if zoom_x_min <= cx <= zoom_x_max and zoom_y_min <= cy <= zoom_y_max:
            polygons.append(polygon)

    fig, ax = plt.subplots(figsize=(4.6, 5.2), constrained_layout=True)
    ax.add_collection(
        PolyCollection(polygons, facecolors="#f8fafc", edgecolors="#64748b", linewidths=0.18)
    )
    for hinge in hinges:
        if not (zoom_x_min <= hinge.x_mm <= zoom_x_max and zoom_y_min <= hinge.y_mm <= zoom_y_max):
            continue
        if support_radius_mm > 1e-9:
            ax.add_patch(
                plt.Circle(
                    (hinge.x_mm, hinge.y_mm),
                    support_radius_mm,
                    fill=False,
                    edgecolor="#b91c1c",
                    linewidth=1.2,
                )
            )
        else:
            ax.plot(
                hinge.x_mm,
                hinge.y_mm,
                marker="o",
                markersize=4.0,
                color="#b91c1c",
                markeredgecolor="white",
                markeredgewidth=0.5,
            )
    ax.set_aspect("equal")
    ax.set_xlim(zoom_x_min, zoom_x_max)
    ax.set_ylim(zoom_y_min, zoom_y_max)
    ax.set_xlabel("x [mm]")
    ax.set_ylabel("y [mm]")
    ax.set_title(title)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=320)
    plt.close(fig)


# ---------------------------------------------------------------------------
# Delaunay-basiertes Dreiecksnetz fuer Punktlager (Singularitaetsstudie)
# ---------------------------------------------------------------------------
def build_point_support_mesh(
    width_mm: float,
    height_mm: float,
    mesh_size_mm: float,
    influence_radius_mm: float,
    local_mesh_mm: float,
    hinges: list[Hinge],
    pressure_mpa: float,
    min_angular_divisions: int,
) -> tuple[
    dict[tuple[float, float], int],
    dict[int, float],
    list[tuple[int, int, int, int]],
]:
    """Erzeuge ein Dreiecksnetz mit Verfeinerung um die Punktlager.

    Verwendet Scipy Delaunay-Triangulation.  Um jedes Gelenk wird ein
    feines radiales Punktgitter erzeugt; der Rest der Tafel bekommt
    ein grobes Raster.

    Parameters
    ----------
    width_mm, height_mm : float
        Abmessungen der Tafel in mm.
    mesh_size_mm : float
        Globale Netzgroesse (grobes Raster) [mm].
    influence_radius_mm : float
        Radius der Verfeinerungszone um jedes Gelenk [mm].
    local_mesh_mm : float
        Netzgroesse innerhalb der Verfeinerungszone [mm].
    hinges : list[Hinge]
        Positionen aller Gelenke.
    pressure_mpa : float
        Gleichmaessiger Druck auf die Tafel [N/mm^2].
    min_angular_divisions : int
        Minimale Winkelteilung fuer die radialen Ringe.
    """
    import numpy as np
    from scipy.spatial import Delaunay

    node_by_coord: dict[tuple[float, float], int] = {}
    nodal_loads: dict[int, float] = {}
    coord_keys: list[tuple[float, float]] = []

    def add_mesh_point(x: float, y: float) -> None:
        """Fuege Netzpunkt hinzu, wenn er innerhalb der Tafel liegt."""
        if x < -1e-9 or x > width_mm + 1e-9 or y < -1e-9 or y > height_mm + 1e-9:
            return
        key = coord_key(x, y)
        if key in node_by_coord:
            return
        add_node(node_by_coord, nodal_loads, key[0], key[1])
        coord_keys.append(key)

    def inside_influence(x: float, y: float) -> bool:
        """Pruefe, ob (x,y) im Einflussbereich eines Gelenks liegt."""
        return any(
            math.hypot(x - h.x_mm, y - h.y_mm) < influence_radius_mm - 1e-9
            for h in hinges
        )

    # Grobes Hintergrundraster (ausserhalb der Einflusszonen)
    x_count = int(round(width_mm / mesh_size_mm))
    y_count = int(round(height_mm / mesh_size_mm))
    for i in range(x_count + 1):
        x = i * mesh_size_mm
        for j in range(y_count + 1):
            y = j * mesh_size_mm
            if not inside_influence(x, y):
                add_mesh_point(x, y)

    # Randknoten sicherstellen
    for x in (0.0, width_mm):
        for j in range(y_count + 1):
            add_mesh_point(x, j * mesh_size_mm)
    for y in (0.0, height_mm):
        for i in range(x_count + 1):
            add_mesh_point(i * mesh_size_mm, y)

    # Feines radiales Gitter um jedes Gelenk
    local_mesh_mm = max(local_mesh_mm, 0.5)
    angular_count = max(min_angular_divisions, 24)
    fine_outer_radius_mm = min(influence_radius_mm, 100.0 + 100.0)
    fine_radial_count = max(1, int(math.ceil(fine_outer_radius_mm / local_mesh_mm)))
    ring_radii = [
        fine_outer_radius_mm * ring / fine_radial_count
        for ring in range(1, fine_radial_count + 1)
    ]
    if influence_radius_mm > fine_outer_radius_mm + 1e-9:
        outer_spacing_mm = max(mesh_size_mm, 10.0 * local_mesh_mm)
        outer_radial_count = max(
            1,
            int(math.ceil((influence_radius_mm - fine_outer_radius_mm) / outer_spacing_mm)),
        )
        ring_radii.extend(
            fine_outer_radius_mm
            + (influence_radius_mm - fine_outer_radius_mm) * ring / outer_radial_count
            for ring in range(1, outer_radial_count + 1)
        )

    for hinge in hinges:
        add_mesh_point(hinge.x_mm, hinge.y_mm)
        for radius in ring_radii:
            for index in range(angular_count):
                angle = 2.0 * math.pi * index / angular_count
                add_mesh_point(
                    hinge.x_mm + radius * math.cos(angle),
                    hinge.y_mm + radius * math.sin(angle),
                )

    # Delaunay-Triangulation
    coords = np.asarray(coord_keys, dtype=float)
    triangulation = Delaunay(coords)
    elements: list[tuple[int, int, int, int]] = []

    for simplex in triangulation.simplices:
        corners_xy = tuple(tuple(coords[index]) for index in simplex)
        area = polygon_area(corners_xy)
        if area <= 1e-6:
            continue
        nodes = tuple(node_by_coord[coord_key(x, y)] for x, y in corners_xy)
        # Dreieck als degeneriertes Viereck (n4 = n3) fuer SHELL181
        tri_element = (nodes[0], nodes[1], nodes[2], nodes[2])
        tri_corners = (corners_xy[0], corners_xy[1], corners_xy[2], corners_xy[2])
        elements.append(tri_element)
        append_element_load(nodal_loads, tri_element, tri_corners, pressure_mpa)

    return node_by_coord, nodal_loads, elements


# ---------------------------------------------------------------------------
# Hauptfunktion: APDL-Script erzeugen
# ---------------------------------------------------------------------------
def generate_apdl(
    path: Path,
    mesh_size_mm: float,
    total_drag_n: float,
    support_patch_mm: float,
    support_refinement_mm: float | None,
    support_influence_mm: float | None,
    support_mode: str,
    job_name: str,
    circle_angular_divisions: int = 60,
    mesh_preview_path: Path | None = None,
) -> dict[str, float | int | str]:
    """Erzeuge das ANSYS-MAPDL-Eingabefile fuer die Schalenberechnung.

    Parameters
    ----------
    path : Path
        Ausgabepfad fuer das .inp-File.
    mesh_size_mm : float
        Globale Netzgroesse [mm].
    total_drag_n : float
        Gesamte Windkraft aus der CFD-Rechnung [N].
    support_patch_mm : float
        Breite des Stuetzenbereichs [mm].
    support_refinement_mm : float | None
        Lokale Netzgroesse in der Verfeinerungszone [mm].
    support_influence_mm : float | None
        Radius der Verfeinerungszone [mm].
    support_mode : str
        "point-support" oder "line-support-full-height".
    job_name : str
        ANSYS-Jobname.
    """
    params = get_params()

    # --- Geometrie der Tafel in mm ---
    width_mm = params.sign_width_m * 1000.0      # 3000 mm
    height_mm = params.plate_height_m * 1000.0    # 2000 mm
    thickness_mm = params.sign_thickness_m * 1000.0  # 3 mm
    h_mm = params.h_m * 1000.0                    # 250 mm (Fachwerkteilung)

    # --- Gelenkpositionen ---
    # Obere Gelenke: an der Oberkante des Fachwerks (y = 1000 mm)
    # Untere Gelenke: ein Feld tiefer (y = 1000 - h = 750 mm)
    hinge_upper_y = 1000.0
    hinge_lower_y = hinge_upper_y - h_mm
    hinge_xs = [500.0, 1500.0, 2500.0]   # x-Positionen der drei Traeger

    # Linienstuetzen laufen ueber die volle Hoehe
    line_support_y_min = 0.0
    line_support_y_max = height_mm

    # --- Gleichmaessiger Druck aus CFD-Windkraft ---
    pressure_mpa = total_drag_n / (width_mm * height_mm)

    # --- Alle 6 Gelenkpositionen ---
    hinges = [
        Hinge(f"H{idx + 1}_upper", x, hinge_upper_y)
        for idx, x in enumerate(hinge_xs)
    ] + [
        Hinge(f"H{idx + 1}_lower", x, hinge_lower_y)
        for idx, x in enumerate(hinge_xs)
    ]
    patch_half_mm = support_patch_mm / 2.0

    # --- Verfeinerungszonen-Parameter ---
    if support_mode == "point-support":
        influence_radius_mm = (
            support_influence_mm if support_influence_mm is not None
            else 2.0 * support_patch_mm
        )
        collar_radius_mm = influence_radius_mm
    else:
        influence_radius_mm = patch_half_mm
        collar_radius_mm = patch_half_mm

    # =====================================================================
    # NETZ ERZEUGEN
    # =====================================================================
    if support_mode == "point-support":
        # Delaunay-Dreiecksnetz mit lokaler Verfeinerung um Punktlager
        local_mesh_mm = support_refinement_mm if support_refinement_mm is not None else 10.0
        node_by_coord, nodal_loads, elements = build_point_support_mesh(
            width_mm,
            height_mm,
            mesh_size_mm,
            influence_radius_mm,
            local_mesh_mm,
            hinges,
            pressure_mpa,
            circle_angular_divisions,
        )
    elif support_mode == "line-support-full-height":
        # Strukturiertes Vierecksnetz mit Verfeinerung an den Stuetzen
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
        # Stuetzenbereich: ganze Hoehe
        required_y.extend([line_support_y_min, line_support_y_max])

        if support_refinement_mm is not None:
            # Feinere Unterteilung im Stuetzenbereich
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
            required_y.extend(
                build_interval_coords(
                    line_support_y_min,
                    line_support_y_max,
                    support_refinement_mm,
                )
            )

        x_coords = build_coords(width_mm, mesh_size_mm, required_x)
        y_coords = build_coords(height_mm, mesh_size_mm, required_y)
        node_by_coord = {}
        nodal_loads = {}
        elements = []

        # Knoten erzeugen
        for y in y_coords:
            for x in x_coords:
                add_node(node_by_coord, nodal_loads, x, y)

        # Viereckelemente erzeugen und Last zuweisen
        for j in range(len(y_coords) - 1):
            for i in range(len(x_coords) - 1):
                corners_xy = (
                    (x_coords[i], y_coords[j]),
                    (x_coords[i + 1], y_coords[j]),
                    (x_coords[i + 1], y_coords[j + 1]),
                    (x_coords[i], y_coords[j + 1]),
                )
                nodes = tuple(node_by_coord[coord_key(x, y)] for x, y in corners_xy)
                elements.append(nodes)
                append_element_load(nodal_loads, nodes, corners_xy, pressure_mpa)
    else:
        raise ValueError(
            f"Unknown support mode: {support_mode!r}. "
            f"Use 'point-support' or 'line-support-full-height'."
        )

    # --- Gelenkknoten und Stuetzenknoten identifizieren ---
    hinge_nodes = {
        hinge.name: node_by_coord[coord_key(hinge.x_mm, hinge.y_mm)] for hinge in hinges
    }
    hinge_patch_nodes = {
        hinge.name: [
            node
            for key, node in node_by_coord.items()
            if is_inside_patch(key[0], key[1], hinge, patch_half_mm, support_mode)
        ]
        for hinge in hinges
    }
    line_support_nodes = {
        f"L{idx}": [
            node
            for key, node in node_by_coord.items()
            if abs(key[0] - support_x) <= patch_half_mm + 1e-9
            and line_support_y_min - 1e-9 <= key[1] <= line_support_y_max + 1e-9
        ]
        for idx, support_x in enumerate(hinge_xs, start=1)
    }

    # Optionale Netzvorschau (fuer Singularitaetsstudie)
    if mesh_preview_path is not None and support_mode == "point-support":
        plot_mesh_preview(
            mesh_preview_path,
            node_by_coord,
            elements,
            hinges,
            0.0,  # kein Auflagerradius bei Punktlagern
            collar_radius_mm,
            f"Punktlagernetz: lokal h = {local_mesh_mm:g} mm",
        )

    # Netzflaeche pruefen
    mesh_area_rel_error = verify_mesh_area(node_by_coord, elements, width_mm, height_mm)

    # =====================================================================
    # APDL-SCRIPT SCHREIBEN
    # =====================================================================
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="ascii", newline="\n") as file:
        # --- Preprocessing: Modellaufbau ---
        file.write("/CLEAR\n")
        file.write(f"/FILNAME,{job_name},1\n")
        file.write("/PREP7\n")

        # Elementtyp: SHELL181 (4-Knoten-Schalenelement)
        file.write("ET,1,SHELL181\n")
        file.write("KEYOPT,1,8,2\n")  # Schichtdaten-Ausgabe

        # Material: Aluminium
        file.write(f"MP,EX,1,{E_ALU_MPA:.9g}\n")
        file.write(f"MP,PRXY,1,{NU_ALU:.9g}\n")

        # Querschnitt: einschichtige Schale
        file.write("SECTYPE,1,SHELL\n")
        file.write(f"SECDATA,{thickness_mm:.9g},1\n")
        file.write("SECNUM,1\n")
        file.write("TYPE,1\n")
        file.write("MAT,1\n")

        # Knoten definieren
        for (x, y), node in sorted(node_by_coord.items(), key=lambda item: item[1]):
            file.write(f"N,{node},{x:.9g},{y:.9g},0\n")

        # Elemente definieren
        for elem_id, (n1, n2, n3, n4) in enumerate(elements, start=1):
            file.write(f"E,{n1},{n2},{n3},{n4}\n")

        file.write("ALLSEL,ALL\n")

        # --- Randbedingungen: Lagerung ---
        if support_mode == "point-support":
            # Punktlager: UZ = 0 an jedem Gelenkknoten
            support_reaction_nodes = sorted(hinge_nodes.values())
            for node in support_reaction_nodes:
                file.write(f"D,{node},UZ,0\n")
        else:
            # Linienstuetzen: UZ = 0 entlang der vertikalen Stuetzen
            support_reaction_nodes = sorted(
                {node for nodes in line_support_nodes.values() for node in nodes}
            )
            for node in support_reaction_nodes:
                file.write(f"D,{node},UZ,0\n")

        # Horizontale Verschiebung fixieren (starre Koerperbewegung verhindern)
        file.write(f"D,{hinge_nodes['H1_lower']},UX,0\n")
        file.write(f"D,{hinge_nodes['H1_lower']},UY,0\n")
        file.write(f"D,{hinge_nodes['H2_lower']},UY,0\n")

        # --- Lasten: Winddruck als Knotenkraefte ---
        for node, load in nodal_loads.items():
            if abs(load) > 1e-12:
                file.write(f"F,{node},FZ,{-load:.12g}\n")

        file.write("FINISH\n")

        # --- Solving ---
        file.write("/SOLU\n")
        file.write("ANTYPE,STATIC\n")
        file.write("NLGEOM,OFF\n")    # Linear elastisch
        file.write("OUTRES,ALL,ALL\n")
        file.write("SOLVE\n")
        file.write("FINISH\n")

        # --- Postprocessing: Ergebnisse auslesen ---
        file.write("/POST1\n")
        file.write("SET,LAST\n")

        if support_mode == "point-support":
            # Lagerreaktionen an den Punktlagern
            for hinge in hinges:
                file.write(f"*GET,R_{hinge.name},NODE,{hinge_nodes[hinge.name]},RF,FZ\n")
        else:
            # Lagerreaktionen an den Linienstuetzen
            file.write("*SET,R_line_support,0\n")
            for name, nodes in line_support_nodes.items():
                file.write(f"*SET,R_{name},0\n")
                for index, node in enumerate(nodes, start=1):
                    file.write(f"*GET,R_{name}_{index},NODE,{node},RF,FZ\n")
                    file.write(f"*SET,R_{name},R_{name}+R_{name}_{index}\n")
                file.write(f"*SET,R_line_support,R_line_support+R_{name}\n")

        # Ergebnisse in Textdatei schreiben
        file.write("*CFOPEN,plate_structural_results,txt\n")
        file.write(f"*VWRITE,{pressure_mpa:.12g}\n")
        file.write("('pressure_N_per_mm2 = ',F20.12)\n")
        file.write(f"*VWRITE,{SIGMA_ALLOW_ALU_MPA:.12g}\n")
        file.write("('allowable_stress_MPa = ',F20.8)\n")

        if support_mode == "point-support":
            for hinge in hinges:
                file.write(f"*VWRITE,R_{hinge.name}\n")
                file.write(f"('{hinge.name}_RFZ_N = ',F20.8)\n")
        else:
            for name in line_support_nodes:
                file.write(f"*VWRITE,R_{name}\n")
                file.write(f"('{name}_RFZ_N = ',F20.8)\n")
            file.write("*VWRITE,R_line_support\n")
            file.write("('line_support_RFZ_N = ',F20.8)\n")

        file.write("*CFCLOS\n")
        file.write("FINISH\n")

    # --- Statistiken zurueckgeben ---
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
        "mesh_area_rel_error": mesh_area_rel_error,
    }


# ---------------------------------------------------------------------------
# APDL-Nachbearbeitungsskripte erzeugen
# ---------------------------------------------------------------------------
def write_post_probe(path: Path, job_name: str) -> None:
    """Erzeuge ein APDL-Skript zum Auslesen von Spannungen und Verschiebungen.

    Dieses Skript wird nach dem Loesen in ANSYS ausgefuehrt, um die
    nodalen Ergebnisse tabellarisch auszugeben.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="ascii", newline="\n") as file:
        file.write("/POST1\n")
        file.write(f"FILE,{job_name},rst\n")
        file.write("SET,LAST\n")
        file.write("SHELL,TOP\n")
        file.write("PRNSOL,U,COMP\n")    # Verschiebungen
        file.write("PRNSOL,S,COMP\n")    # Spannungskomponenten
        file.write("PRNSOL,S,PRIN\n")    # Hauptspannungen + SEQV
        file.write("SHELL,BOT\n")
        file.write("PRNSOL,S,COMP\n")
        file.write("PRNSOL,S,PRIN\n")
        file.write("FINISH\n")


def write_export_plots(path: Path, job_name: str) -> None:
    """Erzeuge ein APDL-Skript zum Exportieren von Konturplots als PNG.

    Erzeugt drei Bilder:
      1. Elementplot (Netzansicht)
      2. Vergleichsspannung (von Mises)
      3. Verformung
    """
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
        # Bild 1: Netz
        file.write("/SHOW,PNG\n")
        file.write("EPLOT\n")
        file.write("/SHOW,CLOSE\n")
        # Bild 2: Vergleichsspannung
        file.write("/SHOW,PNG\n")
        file.write("SHELL,TOP\n")
        file.write("PLNSOL,S,EQV\n")
        file.write("/SHOW,CLOSE\n")
        # Bild 3: Verformung
        file.write("/SHOW,PNG\n")
        file.write("PLDISP,2\n")
        file.write("/SHOW,CLOSE\n")
        file.write("FINISH\n")


# ---------------------------------------------------------------------------
# Kommandozeilen-Hauptprogramm
# ---------------------------------------------------------------------------
def main() -> None:
    """Erzeuge APDL-Dateien fuer die Schalenberechnung der Aluminiumtafel."""
    parser = argparse.ArgumentParser(
        description="Generate APDL input for the aluminium sign plate analysis."
    )
    parser.add_argument("--summary", type=Path, default=DRAG_SUMMARY)
    parser.add_argument("--out-dir", type=Path, default=OUT_DIR)
    parser.add_argument("--mesh-size-mm", type=float, default=50.0)
    parser.add_argument("--support-patch-mm", type=float, default=None)
    parser.add_argument("--support-refinement-mm", type=float, default=None)
    parser.add_argument("--support-influence-mm", type=float, default=None)
    parser.add_argument(
        "--support-mode",
        choices=("point-support", "line-support-full-height"),
        default="line-support-full-height",
    )
    parser.add_argument("--job-name", default=None)
    parser.add_argument("--circle-angular-divisions", type=int, default=72)
    parser.add_argument("--mesh-preview", type=Path, default=None)
    args = parser.parse_args()

    # Standardwerte je nach Lagermodus
    support_patch_mm = args.support_patch_mm
    if support_patch_mm is None:
        support_patch_mm = 100.0 if args.support_mode == "point-support" else 50.0

    support_refinement_mm = args.support_refinement_mm
    if args.support_mode == "point-support" and support_refinement_mm is None:
        support_refinement_mm = 10.0

    support_influence_mm = args.support_influence_mm
    if args.support_mode == "point-support" and support_influence_mm is None:
        support_influence_mm = 2.0 * support_patch_mm

    total_drag_n = read_summary_value(args.summary, "total_drag_N")
    apdl_path = args.out_dir / "plate_structural.inp"
    job_name = args.job_name or (
        {
            "point-support": "plate_point_support",
            "line-support-full-height": "plate_line_support_full_height",
        }.get(args.support_mode, "plate_1_2")
    )
    mesh_preview = args.mesh_preview
    if mesh_preview is None and args.support_mode == "point-support":
        mesh_preview = args.out_dir / "plate_point_mesh_preview.png"

    stats = generate_apdl(
        apdl_path,
        args.mesh_size_mm,
        total_drag_n,
        support_patch_mm,
        support_refinement_mm,
        support_influence_mm,
        args.support_mode,
        job_name,
        circle_angular_divisions=args.circle_angular_divisions,
        mesh_preview_path=mesh_preview,
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
