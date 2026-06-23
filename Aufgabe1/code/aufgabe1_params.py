"""Projektparameter fuer Aufgabe 1.

Diese Datei enthaelt die Eingabedaten aller 36 Projektvarianten der
Studienarbeit.  Fuer Projekt 27 gelten:
  b = 0.45 m  (Fachwerkbreite)
  h = 0.25 m  (Feldhoehe)
  hT = 1.00 m (Tafelhoehe ueber dem Fachwerk)
  cWind = 110 km/h (Windgeschwindigkeit)

Die abgeleiteten Groessen (Staudruck, Re, Domain-Abmessungen,
empfohlene Netzgroessen) werden als Properties berechnet.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Aufgabe1Params:
    """Alle Projektparameter fuer eine Variante der Studienarbeit."""
    project: int
    b_cm: float       # Fachwerkbreite [cm]
    h_cm: float       # Feldhoehe [cm]
    hT_cm: float      # Tafelhoehe (Oberkante Fachwerk bis Oberkante Tafel) [cm]
    cwind_kmh: float  # Windgeschwindigkeit [km/h]

    sign_thickness_m: float = 0.003    # Schilddicke [m]
    sign_width_m: float = 3.0          # Schildbreite [m]
    air_density: float = 1.225         # Luftdichte [kg/m^3]
    air_dynamic_viscosity: float = 1.7894e-5  # dyn. Viskositaet [Pa*s]
    upstream_factor: float = 5.0       # Domain-Ausdehnung stromauf / Plattenhoehe
    downstream_factor: float = 15.0    # Domain-Ausdehnung stromab / Plattenhoehe
    vertical_factor: float = 5.0       # Domain-Ausdehnung vertikal / Plattenhoehe

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
        """Gesamte Plattenhoehe fuer die CFD-Rechnung: hT + 1.0 m."""
        return self.hT_m + 1.0

    @property
    def wind_speed_mps(self) -> float:
        """Windgeschwindigkeit in m/s."""
        return self.cwind_kmh / 3.6

    @property
    def frontal_area_m2(self) -> float:
        """Anstroemflaeche der Tafel [m^2]."""
        return self.sign_width_m * self.plate_height_m

    @property
    def dynamic_pressure_pa(self) -> float:
        """Staudruck q = 0.5 * rho * v^2 [Pa]."""
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


def get_params() -> Aufgabe1Params:
    return Aufgabe1Params(project=27, b_cm=45, h_cm=25, hT_cm=100, cwind_kmh=110)
