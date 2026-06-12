from __future__ import annotations

import argparse

from aufgabe1_params import get_params


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compute baseline wind-load values for Aufgabe 1.1."
    )
    parser.add_argument(
        "--project",
        type=int,
        default=27,
        help="Project number, default: 27",
    )
    parser.add_argument(
        "--cd",
        type=float,
        default=2.0,
        help="Rough drag coefficient for order-of-magnitude estimate",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    params = get_params(args.project)

    force_estimate = args.cd * params.dynamic_pressure_pa * params.frontal_area_m2
    force_per_depth = force_estimate / params.sign_width_m

    print(f"Project: {params.project}")
    print(f"b: {params.b_m:.3f} m (side-frame spacing, structural part)")
    print(f"h: {params.h_m:.3f} m (truss segment height, structural part)")
    print(f"hT: {params.hT_m:.3f} m")
    print(f"CFD plate height hT + 1.0 m: {params.plate_height_m:.3f} m")
    print(f"t: {params.sign_thickness_m:.4f} m")
    print(f"sign width: {params.sign_width_m:.3f} m")
    print(f"wind speed: {params.wind_speed_mps:.3f} m/s")
    print(f"air density: {params.air_density:.3f} kg/m^3")
    print(f"dynamic pressure q: {params.dynamic_pressure_pa:.2f} Pa")
    print(f"Re_hT: {params.reynolds_hT:.3e}")
    print(f"frontal area: {params.frontal_area_m2:.3f} m^2")
    print()
    print(f"Using cD = {args.cd:.3f}:")
    print(f"estimated total drag: {force_estimate:.2f} N")
    print(f"estimated 2D drag per unit depth: {force_per_depth:.2f} N/m")
    print()
    print("Recommended domain extents [m], plate centered at origin:")
    for name, value in params.domain_m.items():
        print(f"  {name}: {value:.6g}")
    print()
    print("Initial mesh sizes [m]:")
    for name, value in params.recommended_mesh_m.items():
        print(f"  {name}: {value}")


if __name__ == "__main__":
    main()
