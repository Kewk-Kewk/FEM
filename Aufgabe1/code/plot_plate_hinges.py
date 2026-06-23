import csv
import matplotlib.pyplot as plt
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA1 = ROOT / "Aufgabe1" / "data"
OUT1 = ROOT / "Aufgabe1" / "out"
FIG1 = ROOT / "Aufgabe1" / "figures"
REPORT_DPI = 420

def save_plate_hinges_plot() -> None:
    target = FIG1 / "plate_hinge_probes.png"
    csv_path = OUT1 / "plate_hinge_reactions.csv"
    if not csv_path.exists():
        print(f"File not found: {csv_path}")
        return
        
    forces = {}
    with csv_path.open(newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        for row in reader:
            forces[row["hinge"]] = float(row["load_on_truss_N"])
            
    # Geometrie
    width_mm = 3000.0
    height_mm = 2000.0
    hinge_xs = [500.0, 1500.0, 2500.0]
    hinge_upper_y = 1000.0
    hinge_lower_y = 750.0
    
    fig, ax = plt.subplots(figsize=(10, 6), dpi=REPORT_DPI)
    
    # Tafel zeichnen
    plate = plt.Rectangle((0, 0), width_mm, height_mm, fill=True, color="#e0e0e0", ec="black", lw=2, zorder=1)
    ax.add_patch(plate)
    
    # Traeger-Linien (gestrichelt)
    for x in hinge_xs:
        ax.axvline(x, color="gray", linestyle="--", zorder=2, alpha=0.7)
        
    # Gelenke und Probes
    for idx, x in enumerate(hinge_xs, start=1):
        for y, suffix in [(hinge_upper_y, "upper"), (hinge_lower_y, "lower")]:
            name = f"H{idx}_{suffix}"
            force = forces.get(name, 0.0)
            
            # Gelenk-Punkt
            ax.plot(x, y, "o", color="#e74c3c", markersize=10, markeredgecolor="black", zorder=3)
            
            # Text-Probe
            ax.annotate(
                f"{name}\n{force:+.1f} N",
                xy=(x, y), xytext=(x + 80, y + 80),
                arrowprops=dict(facecolor="black", arrowstyle="-|>", lw=1.5),
                bbox=dict(boxstyle="round,pad=0.4", fc="white", ec="black", lw=1),
                fontsize=10, fontweight="bold", zorder=4
            )
            
    ax.set_aspect("equal")
    ax.set_xlim(-200, width_mm + 500)
    ax.set_ylim(-200, height_mm + 200)
    ax.set_xlabel("x [mm]", fontsize=12, fontweight="bold")
    ax.set_ylabel("y [mm]", fontsize=12, fontweight="bold")
    ax.set_title("Schildplatte: Reaktionskraefte an den 6 Gelenken", fontsize=14, fontweight="bold", pad=15)
    
    plt.tight_layout()
    FIG1.mkdir(parents=True, exist_ok=True)
    fig.savefig(target, bbox_inches="tight")
    plt.close(fig)
    print(f"Generated {target}")

if __name__ == "__main__":
    save_plate_hinges_plot()
