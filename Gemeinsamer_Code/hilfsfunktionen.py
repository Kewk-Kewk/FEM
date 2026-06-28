"""Gemeinsamer_Code/hilfsfunktionen.py

Gemeinsame Hilfsfunktionen für die Auswertung von Simulationsergebnissen.
"""
from __future__ import annotations

from pathlib import Path


def read_summary_value(path: Path, key: str) -> float:
    """Liest einen einzelnen 'key = value' Wert aus einer Text-Zusammenfassungsdatei."""
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith(f"{key} ="):
            continue
        return float(line.split("=", maxsplit=1)[1].strip())
    raise KeyError(f"Could not find {key!r} in {path}")
