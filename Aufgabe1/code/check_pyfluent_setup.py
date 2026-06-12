from __future__ import annotations

import argparse
import os
import platform
import sys
from importlib import metadata
from pathlib import Path

from fluent_env import ensure_awp_root


DETECTED_ANSYS_ROOT: tuple[str, Path] | None = None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check the local PyFluent setup.")
    parser.add_argument(
        "--launch",
        action="store_true",
        help="Launch a minimal 2D Fluent solver session and close it again.",
    )
    parser.add_argument("--cores", type=int, default=2)
    return parser.parse_args()


def print_status(label: str, ok: bool, detail: str) -> None:
    status = "OK" if ok else "ISSUE"
    print(f"[{status}] {label}: {detail}")


def check_python() -> bool:
    version = sys.version_info
    ok = (3, 10) <= (version.major, version.minor) <= (3, 14)
    print_status(
        "Python",
        ok,
        f"{platform.python_version()} at {sys.executable}",
    )
    return ok


def check_pyfluent() -> bool:
    try:
        fluent_core_version = metadata.version("ansys-fluent-core")
    except metadata.PackageNotFoundError:
        print_status("ansys-fluent-core", False, "not installed")
        return False

    print_status("ansys-fluent-core", True, fluent_core_version)
    return True


def candidate_ansys_roots() -> list[tuple[str, Path]]:
    roots: list[tuple[str, Path]] = []
    for key, value in sorted(os.environ.items()):
        if key.startswith("AWP_ROOT"):
            roots.append((key, Path(value)))

    student_v261 = Path(r"C:\Program Files\ANSYS Inc\ANSYS Student\v261")
    default_v261 = Path(r"C:\Program Files\ANSYS Inc\v261")
    default_v252 = Path(r"C:\Program Files\ANSYS Inc\v252")
    if not any(path == student_v261 for _, path in roots):
        roots.append(("student_v261", student_v261))
    if not any(path == default_v261 for _, path in roots):
        roots.append(("default_v261", default_v261))
    if not roots or not any(path == default_v252 for _, path in roots):
        roots.append(("default_v252", default_v252))
    return roots


def check_ansys_root() -> bool:
    global DETECTED_ANSYS_ROOT

    roots = candidate_ansys_roots()
    if not roots:
        print_status("Ansys root", False, "no AWP_ROOT* variables found")
        return False

    any_ok = False
    for name, root in roots:
        fluent_exe = root / "fluent" / "ntbin" / "win64" / "fluent.exe"
        ok = root.exists() and fluent_exe.exists()
        any_ok = any_ok or ok
        print_status(name, ok, str(root))
        if root.exists():
            print(f"       Fluent executable: {fluent_exe}")
        if ok and DETECTED_ANSYS_ROOT is None:
            DETECTED_ANSYS_ROOT = (name, root)
            if root.name.startswith("v") and root.name[1:].isdigit():
                var_name = f"AWP_ROOT{root.name[1:]}"
                os.environ.setdefault(var_name, str(root))
                print(f"       Using {var_name}={root} for this Python process")

    if not any_ok:
        print()
        print("PyFluent needs a licensed Ansys Fluent installation.")
        print("For Ansys 2026 R1, set AWP_ROOT261 to the folder that contains v261.")
        print(r'Example: $env:AWP_ROOT261 = "C:\Program Files\ANSYS Inc\v261"')
        print("For Ansys 2025 R2, use AWP_ROOT252 and the v252 folder instead.")
        print(r'Check installed versions with: Get-ChildItem "C:\Program Files\ANSYS Inc"')
    return any_ok


def launch_smoke_test(cores: int) -> bool:
    ensure_awp_root()

    import ansys.fluent.core as pyfluent

    print("Launching Fluent. This can take a minute and needs a valid license.")
    solver = pyfluent.launch_fluent(
        mode=pyfluent.FluentMode.SOLVER,
        precision=pyfluent.Precision.DOUBLE,
        dimension=pyfluent.Dimension.TWO,
        processor_count=cores,
    )
    try:
        print(f"Fluent version: {solver.get_fluent_version()}")
        print(f"Health: {solver.health_check.check_health()}")
    finally:
        solver.exit()
    return True


def main() -> None:
    args = parse_args()
    checks = [check_python(), check_pyfluent(), check_ansys_root()]

    if args.launch:
        if all(checks):
            checks.append(launch_smoke_test(args.cores))
        else:
            print("Skipping launch test because one or more checks failed.")

    if not all(checks):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
