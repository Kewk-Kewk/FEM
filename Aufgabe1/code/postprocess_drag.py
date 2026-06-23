from __future__ import annotations

import argparse
from pathlib import Path

from aufgabe1_params import get_params


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compute Aufgabe 1.1 drag force and cD.")
    parser.add_argument("--drag-file", type=Path, default=Path("Aufgabe1/drag_plate.out"))
    parser.add_argument("--summary", type=Path, default=Path("Aufgabe1/out/drag_summary.txt"))
    return parser.parse_args()


def read_drag_history(path: Path) -> list[tuple[int, float]]:
    values: list[tuple[int, float]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        parts = line.strip().split()
        if len(parts) != 2:
            continue
        try:
            iteration = int(parts[0])
            drag = float(parts[1])
        except ValueError:
            continue
        values.append((iteration, drag))
    if not values:
        raise ValueError(f"No drag values found in {path}")
    return values


def write_summary(path: Path, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    args = parse_args()
    params = get_params()
    history = read_drag_history(args.drag_file)
    iteration, drag_per_depth = history[-1]

    total_drag = drag_per_depth * params.sign_width_m
    c_d = drag_per_depth / (params.dynamic_pressure_pa * params.plate_height_m)

    lines = [
        f"project = {params.project}",
        f"iteration = {iteration}",
        f"drag_2d_per_depth_N_per_m = {drag_per_depth:.6f}",
        f"sign_width_m = {params.sign_width_m:.6f}",
        f"total_drag_N = {total_drag:.6f}",
        f"dynamic_pressure_Pa = {params.dynamic_pressure_pa:.6f}",
        f"hT_m = {params.hT_m:.6f}",
        f"plate_height_m = {params.plate_height_m:.6f}",
        f"cD = {c_d:.6f}",
    ]
    write_summary(args.summary, lines)
    print("\n".join(lines))
    print(f"Wrote summary: {args.summary}")


if __name__ == "__main__":
    main()
