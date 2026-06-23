"""
Shared utility functions for the FEM/CFD assignment.

Used by multiple scripts across Aufgabe 1 (CFD + structural) to avoid
code duplication.
"""
from __future__ import annotations

from pathlib import Path


def read_summary_value(path: Path, key: str) -> float:
    """Read a single 'key = value' line from a plain-text summary file.

    These summary files are written by the CFD post-processing
    (drag_summary.txt) and structural post-processing scripts.  Each
    line has the format ``key = numeric_value``.

    Parameters
    ----------
    path : Path
        Path to the summary file (e.g. ``Aufgabe1/data/drag_summary.txt``).
    key : str
        The key to look up, e.g. ``"total_drag_N"``.

    Returns
    -------
    float
        The numeric value associated with *key*.

    Raises
    ------
    KeyError
        If *key* is not found in the file.
    """
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith(f"{key} ="):
            continue
        return float(line.split("=", maxsplit=1)[1].strip())
    raise KeyError(f"Could not find {key!r} in {path}")
