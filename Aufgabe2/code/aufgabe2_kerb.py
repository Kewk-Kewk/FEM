from __future__ import annotations

import csv
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Circle, Rectangle


PROJECT = 27
D_MM = 70.0
L_MM = 110.0
T_MM = 4.0
NY_N_PER_MM = 10.0

LOCAL_MESH_MM = np.array([10.0, 8.0, 5.0, 3.0, 2.0, 1.0])
SIGMA_MAX_MPA = np.array([9.4565, 9.2336, 9.0780, 9.1508, 9.2112, 9.1243])

OUT_DIR = Path("Aufgabe2/out")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    sigma_nominal_mpa = NY_N_PER_MM / T_MM
    # The finest three meshes form a narrow plateau. The report uses their mean
    # instead of a single screenshot value.
    sigma_converged_mpa = float(np.mean([9.1508, 9.2112, 9.1243]))
    alpha_k = sigma_converged_mpa / sigma_nominal_mpa
    stable = SIGMA_MAX_MPA[np.isin(LOCAL_MESH_MM, [3.0, 2.0, 1.0])]
    stable_span_percent = float((stable.max() - stable.min()) / sigma_converged_mpa * 100.0)
    change_3_to_2_percent = float((9.2112 - 9.1508) / 9.1508 * 100.0)
    change_2_to_1_percent = float((9.1243 - 9.2112) / 9.2112 * 100.0)

    csv_path = OUT_DIR / "kerb_convergence.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["local_mesh_mm", "sigma_max_MPa", "alpha_k"])
        for mesh, sigma in zip(LOCAL_MESH_MM, SIGMA_MAX_MPA):
            writer.writerow([f"{mesh:.3f}", f"{sigma:.6f}", f"{sigma / sigma_nominal_mpa:.6f}"])

    summary = [
        "Aufgabe 2 Kerbformzahl",
        "=======================",
        "",
        f"project = {PROJECT}",
        f"d_mm = {D_MM:.6f}",
        f"l_mm = {L_MM:.6f}",
        f"t_mm = {T_MM:.6f}",
        f"ny_N_per_mm = {NY_N_PER_MM:.6f}",
        f"sigma_nominal_MPa = {sigma_nominal_mpa:.6f}",
        f"sigma_max_converged_MPa = {sigma_converged_mpa:.6f}",
        f"alpha_k = {alpha_k:.6f}",
        f"stable_span_3_2_1_percent = {stable_span_percent:.6f}",
        f"change_3_to_2_percent = {change_3_to_2_percent:.6f}",
        f"change_2_to_1_percent = {change_2_to_1_percent:.6f}",
        "note = The reference stress is the mean of the stable 3/2/1 mm plateau for Normalspannung in y-direction.",
        f"csv = {csv_path.as_posix()}",
    ]
    (OUT_DIR / "kerb_summary.txt").write_text("\n".join(summary) + "\n", encoding="utf-8")

    fig, ax = plt.subplots(figsize=(6.2, 3.6), constrained_layout=True)
    ax.plot(LOCAL_MESH_MM, SIGMA_MAX_MPA, "o-", linewidth=1.8, markersize=5, label="Netzstudie")
    ax.axhline(
        sigma_converged_mpa,
        color="#b00020",
        linestyle="--",
        linewidth=1.2,
        label=fr"$\sigma_{{max}}\approx {sigma_converged_mpa:.3f}$ MPa",
    )
    ax.set_xlabel("lokale Netzgroesse am Lochrand [mm]")
    ax.set_ylabel(r"$\sigma_{max}$ [MPa]")
    ax.set_title("Aufgabe 2: Konvergenz der Maximalspannung")
    ax.grid(True, linewidth=0.4, alpha=0.5)
    ax.legend()
    ax.invert_xaxis()
    fig.savefig(OUT_DIR / "kerb_convergence.png", dpi=250)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(6.2, 2.8), constrained_layout=True)
    ax.add_patch(
        Rectangle(
            (-L_MM / 2, -0.45 * L_MM),
            L_MM,
            0.9 * L_MM,
            facecolor="#dfeaf2",
            edgecolor="#24445c",
            linewidth=1.0,
        )
    )
    ax.add_patch(Circle((0, 0), D_MM / 2, facecolor="white", edgecolor="#9b1c1c", linewidth=1.5))
    for x in (-L_MM / 2, L_MM / 2):
        ax.axvline(x, color="#666666", linestyle="--", linewidth=0.8)
    ax.annotate("", xy=(-L_MM / 2, 0.45 * L_MM), xytext=(L_MM / 2, 0.45 * L_MM), arrowprops={"arrowstyle": "<->"})
    ax.text(0, 0.49 * L_MM, r"$\ell = 110$ mm", ha="center", va="bottom")
    ax.annotate("", xy=(D_MM / 2, 0), xytext=(-D_MM / 2, 0), arrowprops={"arrowstyle": "<->"})
    ax.text(0, -5, r"$d = 70$ mm", ha="center", va="top")
    ax.annotate(r"$n_y$", xy=(0, 0.45 * L_MM), xytext=(0, 0.68 * L_MM), ha="center", arrowprops={"arrowstyle": "->"})
    ax.annotate(r"$n_y$", xy=(0, -0.45 * L_MM), xytext=(0, -0.68 * L_MM), ha="center", arrowprops={"arrowstyle": "->"})
    ax.set_aspect("equal")
    ax.set_xlim(-0.65 * L_MM, 0.65 * L_MM)
    ax.set_ylim(-0.75 * L_MM, 0.75 * L_MM)
    ax.axis("off")
    fig.savefig(OUT_DIR / "kerb_geometry.png", dpi=250)
    plt.close(fig)

    print((OUT_DIR / "kerb_summary.txt").as_posix())
    print((OUT_DIR / "kerb_convergence.png").as_posix())
    print((OUT_DIR / "kerb_geometry.png").as_posix())
    print(csv_path.as_posix())


if __name__ == "__main__":
    main()
