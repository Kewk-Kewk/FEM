"""
Aufgabe 1.2 e)–h) — Eigenes Python-FEM-Programm fuer das Gelenkstabwerk.

Dieses Skript implementiert eine vollstaendige Finite-Elemente-Berechnung
fuer ein ebenes Gelenkstabwerk (Fachwerk):

  1. Aufbau der Topologie (Knoten + Stabelemente)
  2. Elementsteifigkeitsmatrix K^(e) fuer jeden Stab
  3. Assemblierung zur globalen Steifigkeitsmatrix K
  4. Einarbeitung der Randbedingungen (Lager)
  5. Loesung von K * U = F
  6. Berechnung der Stabkraefte und Spannungen
  7. Vergleich mit ANSYS-Ergebnissen

Das Fachwerk besteht aus dem maßgebenden Traeger H3 mit 7 Feldern
(7 × h Hoehe), belastet durch die Gelenkkraefte aus der Tafelberechnung.
Die Ergebnisse werden elementweise mit den ANSYS-MAPDL-Werten verglichen.
"""
from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from math import pi, sqrt
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from aufgabe1_params import get_params
from utils import read_summary_value

# ---------------------------------------------------------------------------
# Projekt-Parameter
# ---------------------------------------------------------------------------
PROJECT = 27
OUT_DIR = Path("Aufgabe1/out")
DRAG_SUMMARY = OUT_DIR / "drag_summary.txt"

# Materialparameter Stahl
E_STEEL_PA = 210_000e6              # E-Modul [Pa]
SIGMA_ALLOW_STEEL_PA = 235e6 / 1.8  # zul. Spannung [Pa] (S235, SF=1.8)
SIGMA_ALLOW_ALU_PA = 190e6 / 1.8    # zul. Spannung Alu [Pa] (fuer Bericht)

PANEL_COUNT = 7   # Anzahl der Felder im Fachwerk
TRUSS_COUNT = 3   # Anzahl der Traeger ueber die Schildbreite


# ---------------------------------------------------------------------------
# Datenklassen
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Node:
    """Ein Knoten im ebenen Fachwerk (x, y in Metern)."""
    name: str
    x: float
    y: float


@dataclass(frozen=True)
class Element:
    """Ein Stabelement zwischen zwei Knoten."""
    name: str
    node_i: int   # Index in der Knotenliste
    node_j: int   # Index in der Knotenliste
    kind: str     # "vertical", "horizontal" oder "diagonal"


@dataclass(frozen=True)
class Tube:
    """Stahlrohrquerschnitt (Aussendurchmesser × Wanddicke)."""
    outer_mm: float
    wall_mm: float

    @property
    def inner_mm(self) -> float:
        return self.outer_mm - 2.0 * self.wall_mm

    @property
    def area_m2(self) -> float:
        """Querschnittsflaeche in m^2."""
        outer_m = self.outer_mm / 1000.0
        inner_m = self.inner_mm / 1000.0
        return pi / 4.0 * (outer_m**2 - inner_m**2)

    @property
    def label(self) -> str:
        return f"{self.outer_mm:g} x {self.wall_mm:g} mm"


# Katalog verfuegbarer Stahlrohre (aufsteigend nach Flaeche)
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


# ---------------------------------------------------------------------------
# Topologie-Aufbau
# ---------------------------------------------------------------------------
def build_truss(params, panel_count: int) -> tuple[list[Node], list[Element]]:
    """Erzeuge die Knoten und Elemente des Fachwerks.

    Das Fachwerk hat zwei vertikale Gurte (links L und rechts R)
    mit panel_count Feldern. Die Diagonalen laufen von Lk nach R(k+1).

    Knotenbenennnung:
      - L0, L1, ..., L(n-1)  : linker Gurt (Festlager L0)
      - R0, R1, ..., Rn      : rechter Gurt (Loslager R0)

    Elementtypen:
      - VL1..VL(n-1) : vertikale Staebe linker Gurt
      - VR1..VRn     : vertikale Staebe rechter Gurt
      - H0..H(n-1)   : horizontale Riegel
      - D1..Dn       : Diagonalen
    """
    nodes: list[Node] = []
    left_indices: list[int] = []
    right_indices: list[int] = []

    # Knoten erzeugen (Ebene fuer Ebene)
    for level in range(panel_count):
        y = level * params.h_m
        left_indices.append(len(nodes))
        nodes.append(Node(f"L{level}", 0.0, y))
        right_indices.append(len(nodes))
        nodes.append(Node(f"R{level}", params.b_m, y))

    # Oberer rechter Knoten (G = R7, Lasteinleitungspunkt)
    right_indices.append(len(nodes))
    nodes.append(Node(f"R{panel_count}", params.b_m, panel_count * params.h_m))

    # Elemente erzeugen
    elements: list[Element] = []
    for level in range(panel_count):
        # Rechter Gurt: vertikale Staebe
        elements.append(
            Element(f"VR{level + 1}", right_indices[level], right_indices[level + 1], "vertical")
        )
        # Diagonalen: von links unten nach rechts oben
        elements.append(
            Element(f"D{level + 1}", left_indices[level], right_indices[level + 1], "diagonal")
        )
        # Linker Gurt: vertikale Staebe (nur bis zum vorletzten Feld)
        if level < panel_count - 1:
            elements.append(
                Element(
                    f"VL{level + 1}",
                    left_indices[level],
                    left_indices[level + 1],
                    "vertical",
                )
            )

    # Fest- und Loslager
    fixed_dofs = {
        "L0": {"y"},       # Loslager (vertikal gestuetzt, horizontal frei)
        "R0": {"x", "y"},  # Festlager
    }

    # Horizontale Riegel
    for level in range(panel_count):
        elements.append(
            Element(f"H{level}", left_indices[level], right_indices[level], "horizontal")
        )

    return nodes, elements


def find_node_index(nodes: list[Node], name: str) -> int:
    """Finde den Index eines Knotens anhand seines Namens."""
    for index, node in enumerate(nodes):
        if node.name == name:
            return index
    raise ValueError(f"Node {name!r} does not exist in the truss topology.")


# ---------------------------------------------------------------------------
# Elementberechnung
# ---------------------------------------------------------------------------
def element_geometry(nodes: list[Node], element: Element) -> tuple[float, float, float]:
    """Berechne Laenge und Richtungskosinus eines Stabelements.

    Returns
    -------
    length : float
        Stablaenge [m]
    c : float
        cos(alpha) = dx/L
    s : float
        sin(alpha) = dy/L
    """
    node_i = nodes[element.node_i]
    node_j = nodes[element.node_j]
    dx = node_j.x - node_i.x
    dy = node_j.y - node_i.y
    length = sqrt(dx**2 + dy**2)
    return length, dx / length, dy / length


def element_stiffness(nodes: list[Node], element: Element, area_m2: float) -> np.ndarray:
    """Berechne die Elementsteifigkeitsmatrix K^(e) im globalen System.

    Fuer ein ebenes Stabelement mit 2 Knoten und je 2 DOFs (ux, uy)
    ergibt sich die 4×4-Matrix:

        K^(e) = (EA/L) * [ c²   cs  -c²  -cs ]
                         [ cs   s²  -cs  -s² ]
                         [-c²  -cs   c²   cs ]
                         [-cs  -s²   cs   s² ]

    wobei c = cos(alpha), s = sin(alpha), alpha = Stabneigung.
    """
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
    """Globale Freiheitsgrad-Indizes fuer ein Element.

    Jeder Knoten hat 2 DOFs: (ux, uy).
    Knoten i -> DOFs [2i, 2i+1], Knoten j -> DOFs [2j, 2j+1].
    """
    return [
        2 * element.node_i,
        2 * element.node_i + 1,
        2 * element.node_j,
        2 * element.node_j + 1,
    ]


# ---------------------------------------------------------------------------
# Assemblierung und Loesung
# ---------------------------------------------------------------------------
def assemble_global(
    nodes: list[Node],
    elements: list[Element],
    areas_by_kind: dict[str, float],
) -> np.ndarray:
    """Assembliere die globale Steifigkeitsmatrix K.

    Der Assembly-Algorithmus:
      for each element e:
        for a in range(4):
          for b in range(4):
            K[index[e,a], index[e,b]] += Ke[e][a,b]

    wobei index[e,:] die 4 globalen DOF-Indizes des Elements sind.
    """
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
    """Loese das Gleichungssystem K * U = F.

    1. Assembliere K
    2. Partitioniere in freie und fixierte DOFs
    3. Loese K_ff * U_f = F_f
    4. Berechne Lagerreaktionen R = K * U - F
    5. Berechne Stabkraefte aus den Verschiebungen

    Parameters
    ----------
    fixed_dofs : list[int]
        Liste der fixierten Freiheitsgrade.
        Fuer unser Modell: [0, 1, 3] = UL0_x, UL0_y, UR0_y

    Returns
    -------
    displacement : Verschiebungsvektor U
    reactions : Lagerreaktionsvektor R
    element_rows : Stabkraefte und Spannungen je Element
    """
    stiffness = assemble_global(nodes, elements, areas_by_kind)
    all_dofs = np.arange(len(force))
    free_dofs = np.array([dof for dof in all_dofs if dof not in fixed_dofs])

    # Loesung nur fuer freie DOFs
    displacement = np.zeros_like(force)
    displacement[free_dofs] = np.linalg.solve(
        stiffness[np.ix_(free_dofs, free_dofs)], force[free_dofs]
    )

    # Lagerreaktionen
    reactions = stiffness @ displacement - force

    # Stabkraefte berechnen: N = (EA/L) * [-c, -s, c, s] · u_e
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


# ---------------------------------------------------------------------------
# Rohrdimensionierung
# ---------------------------------------------------------------------------
def choose_tube(required_area_m2: float) -> Tube:
    """Waehle das kleinste Rohr aus dem Katalog, das die Mindestflaeche erfuellt."""
    for tube in TUBE_CATALOG:
        if tube.area_m2 >= required_area_m2:
            return tube
    return TUBE_CATALOG[-1]


# ---------------------------------------------------------------------------
# Ausgabe-Funktionen
# ---------------------------------------------------------------------------
def write_index_table(path: Path, nodes: list[Node], elements: list[Element]) -> None:
    """Schreibe die Indextafel (Element → Knoten → globale DOFs) als CSV.

    Diese Tabelle wird auch im Bericht als Auszug dargestellt.
    """
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
    """Schreibe die Stabkraefte und Spannungen als CSV."""
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_displacements(path: Path, nodes: list[Node], displacement: np.ndarray) -> None:
    disp_xy = displacement.reshape((-1, 2))
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["node", "ux_m", "uy_m"])
        for idx, node in enumerate(nodes):
            writer.writerow([node.name, disp_xy[idx, 0], disp_xy[idx, 1]])


def plot_truss(
    path: Path,
    nodes: list[Node],
    elements: list[Element],
    displacement: np.ndarray,
    rows: list[dict[str, float | str]],
) -> None:
    """Zeichne das verformte Fachwerk mit professioneller Farbkodierung und Kraftanzeige."""
    max_force = max(abs(float(row["axial_N"])) for row in rows)
    disp_xy = displacement.reshape((-1, 2))
    max_disp = float(np.max(np.linalg.norm(disp_xy, axis=1)))
    scale = 0.15 / max_disp if max_disp > 0 else 1.0

    row_by_name = {row["name"]: row for row in rows}
    fig, ax = plt.subplots(figsize=(8, 10), dpi=250)
    
    # Colormap fuer Stabkraefte (Druck = Blau, Zug = Rot)
    cmap = plt.cm.coolwarm
    norm = plt.Normalize(vmin=-max_force, vmax=max_force)

    for element in elements:
        node_i = nodes[element.node_i]
        node_j = nodes[element.node_j]
        axial = float(row_by_name[element.name]["axial_N"])
        color = cmap(norm(axial))
        linewidth = 2.0
        
        # Unverformte Lage (grau, gestrichelt)
        ax.plot([node_i.x, node_j.x], [node_i.y, node_j.y], color="#b0b5b9", linewidth=1.0, linestyle="--", zorder=1)
        
        # Verformte Lage (farbig)
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
            zorder=2,
        )
        
        # Elementname am Mittelpunkt anzeigen
        mid_x = (node_i.x + scale * disp_xy[element.node_i, 0] + node_j.x + scale * disp_xy[element.node_j, 0]) / 2.0
        mid_y = (node_i.y + scale * disp_xy[element.node_i, 1] + node_j.y + scale * disp_xy[element.node_j, 1]) / 2.0
        ax.text(mid_x, mid_y, element.name, fontsize=7, color="#555555", ha="center", va="center", 
                bbox=dict(boxstyle="round,pad=0.1", fc="white", ec="none", alpha=0.7), zorder=6)

    # Knoten zeichnen
    for idx, node in enumerate(nodes):
        nx = node.x + scale * disp_xy[idx, 0]
        ny = node.y + scale * disp_xy[idx, 1]
        ax.scatter(nx, ny, s=30, color="#2c3e50", zorder=3, edgecolors="white", linewidth=0.5)
        ax.text(nx + 0.02, ny + 0.02, node.name, fontsize=8, fontweight="bold", color="#34495e", zorder=4)

    # Lager symbolisieren (unverformte Position)
    for idx, node in enumerate(nodes):
        if node.name == "R0": # Festlager (jetzt rechts)
            ax.plot([node.x, node.x-0.05, node.x+0.05, node.x], [node.y, node.y-0.05, node.y-0.05, node.y], color="black", linewidth=1.5, zorder=5)
            ax.plot([node.x-0.06, node.x+0.06], [node.y-0.05, node.y-0.05], color="black", linewidth=2.0, zorder=5)
        elif node.name == "L0": # Loslager (jetzt links)
            ax.plot([node.x, node.x-0.05, node.x+0.05, node.x], [node.y, node.y-0.05, node.y-0.05, node.y], color="black", linewidth=1.5, zorder=5)
            ax.scatter([node.x-0.025, node.x+0.025], [node.y-0.065, node.y-0.065], s=15, color="white", edgecolors="black", zorder=5)
            ax.plot([node.x-0.06, node.x+0.06], [node.y-0.08, node.y-0.08], color="black", linewidth=2.0, zorder=5)

    # Lasteinleitung zeichnen (Pfeile fuer Windkraft)
    panel_count = max(int(node.name[1:]) for node in nodes if node.name.startswith("R"))
    for node in nodes:
        if node.name in [f"R{panel_count}", f"R{panel_count-1}"]:
            nx = node.x + scale * disp_xy[find_node_index(nodes, node.name), 0]
            ny = node.y + scale * disp_xy[find_node_index(nodes, node.name), 1]
            ax.annotate("", xy=(nx, ny), xytext=(nx + 0.2, ny),
                        arrowprops=dict(facecolor='#e74c3c', edgecolor='none', shrink=0.0, width=3, headwidth=8), zorder=4)

    # Colorbar hinzufuegen
    sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
    sm.set_array([])
    cbar = fig.colorbar(sm, ax=ax, fraction=0.046, pad=0.04)
    cbar.set_label("Stabnormalkraft [N]", fontsize=10, fontweight="bold")
    cbar.ax.tick_params(labelsize=9)

    ax.set_aspect("equal", adjustable="box")
    ax.set_xlim(-0.15, 1.2)
    ax.set_xlabel("x [m]", fontsize=10, fontweight="bold")
    ax.set_ylabel("y [m]", fontsize=10, fontweight="bold")
    ax.set_title(f"Python-FEM: Verformtes Fachwerk (Skalierung {scale:.1f}x)", fontsize=12, fontweight="bold", pad=15)
    
    # Schoenes Grid
    ax.grid(True, color="#ecf0f1", linewidth=0.8, linestyle="-")
    ax.set_axisbelow(True)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['bottom'].set_color('#bdc3c7')
    ax.spines['left'].set_color('#bdc3c7')

    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
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
    """Schreibe eine Zusammenfassung der Fachwerkberechnung."""
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


# ---------------------------------------------------------------------------
# Hauptprogramm
# ---------------------------------------------------------------------------
def main() -> None:
    """Fuehre die Python-FEM-Berechnung des Fachwerks durch.

    Workflow:
      1. Lese Windkraft aus drag_summary.txt
      2. Baue Fachwerkstopologie auf
      3. Erstloesung mit Einheitsquerschnitten → max. Kraefte bestimmen
      4. Rohrquerschnitte aus Katalog waehlen
      5. Endgueltige Loesung mit gewaehlten Querschnitten
      6. Ergebnisse schreiben (CSV, Plot, Summary)
    """
    parser = argparse.ArgumentParser(
        description="Python FEM solver for the truss (Aufgabe 1.2 e-h)."
    )
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

    params = get_params()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    # --- Windkraft lesen und auf Traeger verteilen ---
    total_drag_n = read_summary_value(args.summary, "total_drag_N")
    pressure_pa = total_drag_n / params.frontal_area_m2
    force_per_truss_n = total_drag_n / args.truss_count

    if args.upper_load_n is None and args.lower_load_n is None:
        # Ohne explizite Gelenkkraefte: gleichmaessige Aufteilung
        upper_joint_load_n = force_per_truss_n / 2.0
        lower_joint_load_n = force_per_truss_n / 2.0
    elif args.upper_load_n is not None and args.lower_load_n is not None:
        upper_joint_load_n = args.upper_load_n
        lower_joint_load_n = args.lower_load_n
        force_per_truss_n = upper_joint_load_n + lower_joint_load_n
    else:
        raise ValueError("Provide both --upper-load-n and --lower-load-n, or neither.")

    # --- Fachwerk aufbauen ---
    nodes, elements = build_truss(params, args.panel_count)
    dof_count = 2 * len(nodes)
    force = np.zeros(dof_count)

    # Lasten an den oberen Gelenken (Wind wirkt horizontal = negativ x)
    top_right = find_node_index(nodes, f"R{args.panel_count}")
    lower_right = find_node_index(nodes, f"R{args.panel_count - 1}")
    force[2 * top_right] = -upper_joint_load_n
    force[2 * lower_right] = -lower_joint_load_n

    # Randbedingungen: L0 Loslager (UY=0), R0 fest (UX=UY=0)
    # DOF 1 = L0_UY, DOF 2 = R0_UX, DOF 3 = R0_UY
    fixed_dofs = [1, 2, 3]

    # --- Erstloesung: Einheitsquerschnitte fuer Kraftermittlung ---
    trial_areas = {"vertical": 1e-4, "horizontal": 1e-4, "diagonal": 1e-4}
    _, _, trial_rows = solve_truss(nodes, elements, trial_areas, force, fixed_dofs)

    # Maximale Kraefte je Stabgruppe bestimmen
    max_by_kind = {
        kind: max(abs(float(row["axial_N"])) for row in trial_rows if row["kind"] == kind)
        for kind in ["vertical", "horizontal", "diagonal"]
    }

    # --- Rohrquerschnitte waehlen ---
    tubes_by_kind = {
        kind: choose_tube(max_force / SIGMA_ALLOW_STEEL_PA)
        for kind, max_force in max_by_kind.items()
    }
    selected_areas = {kind: tube.area_m2 for kind, tube in tubes_by_kind.items()}

    # --- Endgueltige Loesung mit gewaehlten Querschnitten ---
    displacement, reactions, rows = solve_truss(
        nodes, elements, selected_areas, force, fixed_dofs
    )

    # --- Ergebnisse schreiben ---
    write_index_table(args.out_dir / "truss_index_table.csv", nodes, elements)
    write_element_rows(args.out_dir / "truss_element_forces.csv", rows)
    write_displacements(args.out_dir / "truss_displacements.csv", nodes, displacement)
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
    print((args.out_dir / "truss_displacements.csv").as_posix())
    print((args.out_dir / "truss_deformed.png").as_posix())


if __name__ == "__main__":
    main()
