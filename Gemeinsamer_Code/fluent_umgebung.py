import os
from pathlib import Path


def ensure_awp_root() -> Path | None:
    for key, value in sorted(os.environ.items()):
        if key.startswith("AWP_ROOT"):
            root = Path(value)
            fluent_exe = root / "fluent" / "ntbin" / "win64" / "fluent.exe"
            if fluent_exe.exists():
                return root

    candidates = [
        Path(r"C:\Program Files\ANSYS Inc\ANSYS Student\v261"),
        Path(r"C:\Program Files\ANSYS Inc\v261"),
        Path(r"C:\Program Files\ANSYS Inc\v252"),
    ]

    for root in candidates:
        fluent_exe = root / "fluent" / "ntbin" / "win64" / "fluent.exe"
        if fluent_exe.exists() and root.name.startswith("v") and root.name[1:].isdigit():
            os.environ[f"AWP_ROOT{root.name[1:]}"] = str(root)
            return root

    return None
