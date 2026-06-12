from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Aufgabe1Params:
    project: int
    b_cm: float
    h_cm: float
    hT_cm: float
    cwind_kmh: float

    sign_thickness_m: float = 0.003
    sign_width_m: float = 3.0
    air_density: float = 1.225
    air_dynamic_viscosity: float = 1.7894e-5
    upstream_factor: float = 5.0
    downstream_factor: float = 15.0
    vertical_factor: float = 5.0

    @property
    def b_m(self) -> float:
        return self.b_cm / 100.0

    @property
    def h_m(self) -> float:
        return self.h_cm / 100.0

    @property
    def hT_m(self) -> float:
        return self.hT_cm / 100.0

    @property
    def plate_height_m(self) -> float:
        return self.hT_m + 1.0

    @property
    def wind_speed_mps(self) -> float:
        return self.cwind_kmh / 3.6

    @property
    def frontal_area_m2(self) -> float:
        return self.sign_width_m * self.plate_height_m

    @property
    def dynamic_pressure_pa(self) -> float:
        return 0.5 * self.air_density * self.wind_speed_mps**2

    @property
    def reynolds_hT(self) -> float:
        return (
            self.air_density
            * self.wind_speed_mps
            * self.plate_height_m
            / self.air_dynamic_viscosity
        )

    @property
    def domain_m(self) -> dict[str, float]:
        upstream = self.upstream_factor * self.plate_height_m
        downstream = self.downstream_factor * self.plate_height_m
        vertical = self.vertical_factor * self.plate_height_m
        return {
            "x_min": -upstream,
            "x_max": downstream,
            "y_min": -vertical,
            "y_max": vertical,
            "plate_x_min": -0.5 * self.sign_thickness_m,
            "plate_x_max": 0.5 * self.sign_thickness_m,
            "plate_y_min": -0.5 * self.plate_height_m,
            "plate_y_max": 0.5 * self.plate_height_m,
        }

    @property
    def recommended_mesh_m(self) -> dict[str, float]:
        return {
            "far_field_max_size": 0.10 * self.plate_height_m,
            "wake_size": 0.025 * self.plate_height_m,
            "plate_edge_size": min(0.005, self.sign_thickness_m / 2.0),
            "first_layer_height": min(0.001, self.sign_thickness_m / 5.0),
            "boundary_layer_count": 8,
        }


PROJECT_TABLE: dict[int, Aufgabe1Params] = {
    1: Aufgabe1Params(1, 20, 20, 80, 90),
    2: Aufgabe1Params(2, 20, 25, 80, 100),
    3: Aufgabe1Params(3, 20, 30, 80, 110),
    4: Aufgabe1Params(4, 20, 35, 80, 120),
    5: Aufgabe1Params(5, 20, 40, 80, 130),
    6: Aufgabe1Params(6, 25, 20, 80, 140),
    7: Aufgabe1Params(7, 25, 25, 85, 90),
    8: Aufgabe1Params(8, 25, 30, 85, 100),
    9: Aufgabe1Params(9, 25, 35, 85, 110),
    10: Aufgabe1Params(10, 25, 40, 85, 120),
    11: Aufgabe1Params(11, 30, 20, 85, 130),
    12: Aufgabe1Params(12, 30, 25, 85, 140),
    13: Aufgabe1Params(13, 30, 30, 90, 90),
    14: Aufgabe1Params(14, 30, 35, 90, 100),
    15: Aufgabe1Params(15, 30, 40, 90, 110),
    16: Aufgabe1Params(16, 35, 20, 90, 120),
    17: Aufgabe1Params(17, 35, 25, 90, 130),
    18: Aufgabe1Params(18, 35, 30, 90, 140),
    19: Aufgabe1Params(19, 35, 35, 95, 90),
    20: Aufgabe1Params(20, 35, 40, 95, 100),
    21: Aufgabe1Params(21, 40, 20, 95, 110),
    22: Aufgabe1Params(22, 40, 25, 95, 120),
    23: Aufgabe1Params(23, 40, 30, 95, 130),
    24: Aufgabe1Params(24, 40, 35, 95, 140),
    25: Aufgabe1Params(25, 40, 40, 100, 90),
    26: Aufgabe1Params(26, 45, 20, 100, 100),
    27: Aufgabe1Params(27, 45, 25, 100, 110),
    28: Aufgabe1Params(28, 45, 30, 100, 120),
    29: Aufgabe1Params(29, 45, 35, 100, 130),
    30: Aufgabe1Params(30, 45, 40, 100, 140),
    31: Aufgabe1Params(31, 50, 20, 105, 90),
    32: Aufgabe1Params(32, 50, 25, 105, 100),
    33: Aufgabe1Params(33, 50, 30, 105, 110),
    34: Aufgabe1Params(34, 50, 35, 105, 120),
    35: Aufgabe1Params(35, 50, 40, 105, 130),
    36: Aufgabe1Params(36, 55, 20, 105, 140),
}


def get_params(project: int) -> Aufgabe1Params:
    try:
        return PROJECT_TABLE[project]
    except KeyError as exc:
        valid = ", ".join(str(key) for key in sorted(PROJECT_TABLE))
        raise ValueError(f"Unknown project {project}. Valid projects: {valid}") from exc
