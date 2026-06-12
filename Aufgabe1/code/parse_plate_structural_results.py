from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path


OUT_DIR = Path("Aufgabe1/out")
RESULTS_TXT = OUT_DIR / "plate_structural_results.txt"
POST_OUT = OUT_DIR / "plate_post_probe.out"


FLOAT_RE = re.compile(r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[Ee][-+]?\d+)?")


def to_float(value: str) -> float:
    return float(value.replace("D", "E"))


def parse_key_values(path: Path) -> dict[str, float]:
    values: dict[str, float] = {}
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", maxsplit=1)
        matches = FLOAT_RE.findall(value)
        if matches:
            values[key.strip()] = to_float(matches[-1])
    return values


def parse_post_output(path: Path) -> dict[str, float]:
    max_seqv = {"top": 0.0, "bottom": 0.0}
    estimated_seqv = {"top": 0.0, "bottom": 0.0}
    max_abs_uz = 0.0
    current_side: str | None = None
    reading_principal_rows = False
    reading_displacement_rows = False
    in_estimated_bounds = False
    waiting_for_estimated_value = False

    for raw_line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw_line.strip()
        upper = line.upper()

        if "SHELL NODAL RESULTS ARE AT TOP" in upper:
            current_side = "top"
        elif "SHELL NODAL RESULTS ARE AT BOTTOM" in upper:
            current_side = "bottom"

        if "ESTIMATED BOUNDS" in upper:
            in_estimated_bounds = True

        if "NODE" in upper and "UX" in upper and "UZ" in upper:
            reading_displacement_rows = True
            continue
        if reading_displacement_rows:
            if upper.startswith("MAXIMUM") or upper.startswith("MINIMUM") or upper.startswith("***"):
                reading_displacement_rows = False
            else:
                parts = line.split()
                if len(parts) >= 5 and parts[0].isdigit():
                    max_abs_uz = max(max_abs_uz, abs(to_float(parts[3])))

        if "NODE" in upper and "S1" in upper and "SEQV" in upper:
            reading_principal_rows = not in_estimated_bounds
            continue

        if reading_principal_rows:
            if upper.startswith("MINIMUM") or upper.startswith("MAXIMUM") or upper.startswith("***"):
                reading_principal_rows = False
            else:
                parts = line.split()
                if current_side and len(parts) >= 6 and parts[0].isdigit():
                    max_seqv[current_side] = max(max_seqv[current_side], abs(to_float(parts[5])))

        if in_estimated_bounds and upper.startswith("MAXIMUM VALUES"):
            waiting_for_estimated_value = True
            continue
        if waiting_for_estimated_value and upper.startswith("VALUE"):
            matches = FLOAT_RE.findall(line)
            if current_side and len(matches) >= 5:
                estimated_seqv[current_side] = max(
                    estimated_seqv[current_side], abs(to_float(matches[-1]))
                )
            waiting_for_estimated_value = False
            in_estimated_bounds = False

    return {
        "max_eqv_stress_top_MPa": max_seqv["top"],
        "max_eqv_stress_bottom_MPa": max_seqv["bottom"],
        "max_eqv_stress_MPa": max(max_seqv.values()),
        "estimated_max_eqv_stress_top_MPa": estimated_seqv["top"],
        "estimated_max_eqv_stress_bottom_MPa": estimated_seqv["bottom"],
        "estimated_max_eqv_stress_MPa": max(estimated_seqv.values()),
        "max_abs_UZ_mm": max_abs_uz,
    }


def write_reaction_csv(path: Path, values: dict[str, float]) -> list[tuple[str, float]]:
    reactions = [
        (key.removesuffix("_RFZ_N"), value)
        for key, value in values.items()
        if key.endswith("_RFZ_N")
    ]
    reactions.sort()
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["support", "reaction_FZ_N", "applied_load_N"])
        for name, reaction in reactions:
            writer.writerow([name, f"{reaction:.8f}", f"{-reaction:.8f}"])
    return reactions


def write_legacy_hinge_csv(path: Path, reactions: list[tuple[str, float]]) -> None:
    hinge_reactions = [
        (name, reaction)
        for name, reaction in reactions
        if name.endswith("_upper") or name.endswith("_lower")
    ]
    if not hinge_reactions:
        return
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["hinge", "reaction_FZ_N", "load_on_truss_N"])
        for name, reaction in hinge_reactions:
            writer.writerow([name, f"{reaction:.8f}", f"{-reaction:.8f}"])


def write_summary(
    path: Path,
    values: dict[str, float],
    stress: dict[str, float],
    reactions: list[tuple[str, float]],
) -> None:
    allowable = values.get("allowable_stress_MPa", 190.0 / 1.8)
    upper = [(name, force) for name, force in reactions if "upper" in name]
    lower = [(name, force) for name, force in reactions if "lower" in name]
    carrier_totals: dict[str, float] = {}
    for name, force in reactions:
        carrier = name.split("_")[0]
        carrier_totals[carrier] = carrier_totals.get(carrier, 0.0) + force
    governing = (
        max(carrier_totals.items(), key=lambda item: abs(item[1]))
        if carrier_totals
        else None
    )

    with path.open("w", encoding="utf-8") as file:
        file.write("Aufgabe 1.2 plate structural summary\n")
        file.write("=====================================\n\n")
        file.write(f"pressure_N_per_mm2 = {values['pressure_N_per_mm2']:.12f}\n")
        file.write(f"allowable_stress_MPa = {allowable:.8f}\n")
        file.write(f"max_eqv_stress_top_MPa = {stress['max_eqv_stress_top_MPa']:.6f}\n")
        file.write(f"max_eqv_stress_bottom_MPa = {stress['max_eqv_stress_bottom_MPa']:.6f}\n")
        file.write(f"max_eqv_stress_MPa = {stress['max_eqv_stress_MPa']:.6f}\n")
        file.write(
            f"estimated_max_eqv_stress_MPa = {stress['estimated_max_eqv_stress_MPa']:.6f}\n"
        )
        file.write(f"stress_utilization = {stress['max_eqv_stress_MPa'] / allowable:.6f}\n")
        file.write(f"max_abs_UZ_mm = {stress['max_abs_UZ_mm']:.6f}\n")
        file.write("\nSupport reactions RFZ from support on plate:\n")
        for name, force in reactions:
            file.write(f"- {name}: {force:.6f} N\n")
        file.write("\nCarrier reaction sums:\n")
        for carrier, force in sorted(carrier_totals.items()):
            file.write(f"- {carrier}: {force:.6f} N\n")
        if governing:
            file.write(
                f"\nGoverning support group by absolute reaction sum: {governing[0]} "
                f"with {governing[1]:.6f} N\n"
            )
        if upper or lower:
            file.write("\nUpper hinge reactions:\n")
            for name, force in upper:
                file.write(f"- {name}: {force:.6f} N\n")
            file.write("\nLower hinge reactions:\n")
            for name, force in lower:
                file.write(f"- {name}: {force:.6f} N\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", type=Path, default=RESULTS_TXT)
    parser.add_argument("--post-output", type=Path, default=POST_OUT)
    parser.add_argument("--out-dir", type=Path, default=OUT_DIR)
    args = parser.parse_args()

    values = parse_key_values(args.results)
    stress = parse_post_output(args.post_output)
    reactions = write_reaction_csv(args.out_dir / "plate_support_reactions.csv", values)
    write_legacy_hinge_csv(args.out_dir / "plate_hinge_reactions.csv", reactions)
    write_summary(args.out_dir / "plate_structural_summary.txt", values, stress, reactions)
    print((args.out_dir / "plate_structural_summary.txt").as_posix())
    print((args.out_dir / "plate_support_reactions.csv").as_posix())


if __name__ == "__main__":
    main()
