"""Aufgabe 2: Lochscheibe und Kerbformzahl (Projekt 27)

Berechnet die Kerbformzahl alpha_k aus den Spannungen der FE-Analysen (ANSYS Workbench).
"""
from __future__ import annotations

import csv
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Circle, Rectangle

# Geometrie der gelochten Scheibe
LOCH_DURCHMESSER_D_MM = 70.0  # Lochdurchmesser d
LOCH_ABSTAND_L_MM = 110.0     # Lochabstand l
SCHEIBEN_DICKE_T_MM = 4.0     # Scheibendicke t

# Belastung und Nennspannung
LINIENLAST_NY_N_MM = 10.0     # Linienlast n_y
NENNSPANNUNG_SIGMA_N_MPA = LINIENLAST_NY_N_MM / SCHEIBEN_DICKE_T_MM # sigma_n (2.50 MPa)

# Konvergenzstudie (ANSYS Workbench Normalspannungen am Lochrand)
LOKALE_NETZGROESSEN_MM = np.array([10.0, 8.0, 6.0, 3.0, 2.0, 1.0])
MAXIMALSPANNUNGEN_SIGMA_Y_MPA = np.array([9.1539, 9.2332, 9.2341, 9.2157, 9.2263, 9.1063])
STABILE_NETZSTUFEN_MM = [3.0, 2.0, 1.0] # Netzstufen fuer das Konvergenzplateau


def step_1_berechnen_und_plotten(out_dir: Path, data_dir: Path) -> None:
    """Wertet die Konvergenzstudie aus und erzeugt Abbildungen."""
    print("Schritt 1: Auswertung und Diagrammerstellung...")
    
    stabile_werte = MAXIMALSPANNUNGEN_SIGMA_Y_MPA[np.isin(LOKALE_NETZGROESSEN_MM, STABILE_NETZSTUFEN_MM)]
    sigma_max_konvergiert = float(np.mean(stabile_werte))
    
    # Kerbformzahl alpha_k = sigma_max / sigma_n
    alpha_k = sigma_max_konvergiert / NENNSPANNUNG_SIGMA_N_MPA
    spanne_prozent = float((stabile_werte.max() - stabile_werte.min()) / sigma_max_konvergiert * 100.0)
    
    sigma_pro_netz = dict(zip(LOKALE_NETZGROESSEN_MM, MAXIMALSPANNUNGEN_SIGMA_Y_MPA))
    aenderung_3_zu_2 = float((sigma_pro_netz[2.0] - sigma_pro_netz[3.0]) / sigma_pro_netz[3.0] * 100.0)
    aenderung_2_zu_1 = float((sigma_pro_netz[1.0] - sigma_pro_netz[2.0]) / sigma_pro_netz[2.0] * 100.0)

    # CSV schreiben
    for csv_pfad in [out_dir / "kerb_convergence.csv", data_dir / "kerb_convergence.csv"]:
        with csv_pfad.open("w", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            writer.writerow(["local_mesh_mm", "sigma_max_MPa", "alpha_k"])
            for mesh, sigma in zip(LOKALE_NETZGROESSEN_MM, MAXIMALSPANNUNGEN_SIGMA_Y_MPA):
                writer.writerow([f"{mesh:.3f}", f"{sigma:.6f}", f"{sigma / NENNSPANNUNG_SIGMA_N_MPA:.6f}"])

    # Zusammenfassender Text
    zusammenfassung = [
        "Aufgabe 2 Kerbformzahl Zusammenfassung",
        "=====================================",
        "",
        f"Lochdurchmesser d [mm]   = {LOCH_DURCHMESSER_D_MM:.3f}",
        f"Lochabstand l [mm]       = {LOCH_ABSTAND_L_MM:.3f}",
        f"Scheibendicke t [mm]     = {SCHEIBEN_DICKE_T_MM:.3f}",
        f"Linienlast n_y [N/mm]    = {LINIENLAST_NY_N_MM:.3f}",
        f"Nennspannung sigma_n [MPa] = {NENNSPANNUNG_SIGMA_N_MPA:.3f}",
        f"Konvergierte Maximalspannung sigma_max [MPa] = {sigma_max_konvergiert:.6f}",
        f"Kerbformzahl alpha_k     = {alpha_k:.6f}",
        f"Stabile Netzstufen [mm]  = {','.join(f'{m:g}' for m in STABILE_NETZSTUFEN_MM)}",
        f"Plateau-Schwankung [%]   = {spanne_prozent:.4f}%",
        f"Aenderung 3 mm -> 2 mm [%] = {aenderung_3_zu_2:.4f}%",
        f"Aenderung 2 mm -> 1 mm [%] = {aenderung_2_zu_1:.4f}%",
    ]
    (out_dir / "kerb_summary.txt").write_text("\n".join(zusammenfassung) + "\n", encoding="utf-8")

    # Diagramm 1: Konvergenz
    fig, ax = plt.subplots(figsize=(6.2, 3.6), constrained_layout=True)
    ax.plot(LOKALE_NETZGROESSEN_MM, MAXIMALSPANNUNGEN_SIGMA_Y_MPA, "o-", linewidth=1.8, markersize=5, label="Netzstudie")
    ax.axhline(
        sigma_max_konvergiert,
        color="#b00020",
        linestyle="--",
        linewidth=1.2,
        label=rf"$\sigma_{{max}}\approx {sigma_max_konvergiert:.3f}$ MPa",
    )
    ax.set_xlabel("lokale Netzgroesse am Lochrand [mm]")
    ax.set_ylabel(r"$\sigma_{max}$ [MPa]")
    ax.set_title("Aufgabe 2: Konvergenz der Maximalspannung")
    ax.grid(True, linewidth=0.4, alpha=0.5)
    ax.legend()
    ax.invert_xaxis()
    fig.savefig(out_dir / "kerb_convergence.png", dpi=250)
    plt.close(fig)

    # Diagramm 2: Geometrieskizze
    fig, ax = plt.subplots(figsize=(6.2, 2.8), constrained_layout=True)
    ax.add_patch(
        Rectangle(
            (-LOCH_ABSTAND_L_MM / 2, -0.45 * LOCH_ABSTAND_L_MM),
            LOCH_ABSTAND_L_MM,
            0.9 * LOCH_ABSTAND_L_MM,
            facecolor="#dfeaf2",
            edgecolor="#24445c",
            linewidth=1.0,
        )
    )
    ax.add_patch(Circle((0, 0), LOCH_DURCHMESSER_D_MM / 2, facecolor="white", edgecolor="#9b1c1c", linewidth=1.5))
    for x in (-LOCH_ABSTAND_L_MM / 2, LOCH_ABSTAND_L_MM / 2):
        ax.axvline(x, color="#666666", linestyle="--", linewidth=0.8)
    ax.annotate("", xy=(-LOCH_ABSTAND_L_MM / 2, 0.45 * LOCH_ABSTAND_L_MM), xytext=(LOCH_ABSTAND_L_MM / 2, 0.45 * LOCH_ABSTAND_L_MM), arrowprops={"arrowstyle": "<->"})
    ax.text(0, 0.49 * LOCH_ABSTAND_L_MM, rf"$\ell = {LOCH_ABSTAND_L_MM:g}$ mm", ha="center", va="bottom")
    ax.annotate("", xy=(LOCH_DURCHMESSER_D_MM / 2, 0), xytext=(-LOCH_DURCHMESSER_D_MM / 2, 0), arrowprops={"arrowstyle": "<->"})
    ax.text(0, -5, rf"$d = {LOCH_DURCHMESSER_D_MM:g}$ mm", ha="center", va="top")
    ax.annotate(r"$n_y$", xy=(0, 0.45 * LOCH_ABSTAND_L_MM), xytext=(0, 0.68 * LOCH_ABSTAND_L_MM), ha="center", arrowprops={"arrowstyle": "->"})
    ax.annotate(r"$n_y$", xy=(0, -0.45 * LOCH_ABSTAND_L_MM), xytext=(0, -0.68 * LOCH_ABSTAND_L_MM), ha="center", arrowprops={"arrowstyle": "->"})
    ax.set_aspect("equal")
    ax.set_xlim(-0.65 * LOCH_ABSTAND_L_MM, 0.65 * LOCH_ABSTAND_L_MM)
    ax.set_ylim(-0.75 * LOCH_ABSTAND_L_MM, 0.75 * LOCH_ABSTAND_L_MM)
    ax.axis("off")
    fig.savefig(out_dir / "kerb_geometry.png", dpi=250)
    plt.close(fig)
    
    print("\nAuswertung abgeschlossen.")
    print(f"  Nennspannung: {NENNSPANNUNG_SIGMA_N_MPA:.2f} MPa")
    print(f"  Maximalspannung (konvergiert): {sigma_max_konvergiert:.4f} MPa")
    print(f"  Kerbformzahl alpha_k: {alpha_k:.3f}")


def main() -> None:
    task_dir = Path(__file__).resolve().parent
    data_dir = task_dir / "data"
    out_dir = task_dir / "out"
    out_dir.mkdir(parents=True, exist_ok=True)
    
    print("Aufgabe 2: Ermittlung der Kerbformzahl (Projekt 27)")
    print(f"  Geometrie: Lochdurchmesser d={LOCH_DURCHMESSER_D_MM} mm, Lochabstand l={LOCH_ABSTAND_L_MM} mm")
    print(f"  Dicke: t={SCHEIBEN_DICKE_T_MM} mm, Linienlast n_y={LINIENLAST_NY_N_MM} N/mm\n")
    
    step_1_berechnen_und_plotten(out_dir, data_dir)


if __name__ == "__main__":
    main()
