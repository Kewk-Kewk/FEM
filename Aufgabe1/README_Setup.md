# Aufgabe 1 PyFluent Setup

This folder is a starting point for Aufgabe 1.1. The idea is to make the
Fluent run reproducible instead of rebuilding the mesh by hand every time.

> Note on the folder layout (after the cleanup): the Python scripts now live in
> `Aufgabe1/code/`. Prefix the script paths in the commands below with `code\`
> (for example `Aufgabe1\code\check_pyfluent_setup.py`). `Aufgabe1\requirements.txt`
> and the regenerated working directory `Aufgabe1\out\` keep their paths.

## Geometry Interpretation

For the CFD part only the aluminium sign plate is modeled.

- 2D side view: rectangle with height `hT + 1.0 m` and thickness `t = 0.003 m`
- Wind flows normal to the plate
- The fixed sign width from the front view is `0.5 + 1.0 + 1.0 + 0.5 = 3.0 m`
- The table value `b` is the truss spacing in the side view and is not used
  for the 2D CFD mesh

Fluent gives the 2D force per unit depth. Multiply by `3.0 m` to get the
total force on the sign:

```text
F_total = F_2D_per_depth * 3.0
cD = F_total / (0.5 * rho * U^2 * 3.0 * (hT + 1.0))
```

The factor `3.0` cancels in `cD`, so equivalently:

```text
cD = F_2D_per_depth / (0.5 * rho * U^2 * (hT + 1.0))
```

## Python Environment

Ansys 2025 R2 was visible in the Aufgabe 2 solver output, so the matching
environment variable should be `AWP_ROOT252`. On a default Windows install it
usually points to:

```powershell
C:\Program Files\ANSYS Inc\v252
```

Create and activate a virtual environment from the project root:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r Aufgabe1\requirements.txt
```

If PowerShell blocks `Activate.ps1` with an execution-policy error, either
allow scripts only for the current terminal:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

or skip activation entirely and call the virtual-environment Python directly:

```powershell
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r Aufgabe1\requirements.txt
.\.venv\Scripts\python.exe Aufgabe1\check_pyfluent_setup.py
```

If the Microsoft Store Python alias acts weird, install Python from
python.org and repeat the commands with that Python.

Run the setup check:

```powershell
python Aufgabe1\check_pyfluent_setup.py
```

If it passes, try a Fluent launch smoke test:

```powershell
python Aufgabe1\check_pyfluent_setup.py --launch
```

If the setup check reports `default_v261` or `default_v252` as missing,
PyFluent cannot find Ansys Fluent at that default location. Check the
installed versions and environment variables:

```powershell
Get-ChildItem "C:\Program Files\ANSYS Inc" -ErrorAction SilentlyContinue
Get-ChildItem Env:AWP_ROOT*
```

For Ansys 2026 R1, set `AWP_ROOT261` to the `v261` installation folder:

```powershell
$env:AWP_ROOT261 = "C:\Program Files\ANSYS Inc\ANSYS Student\v261"
```

To make that permanent for your Windows user:

```powershell
[Environment]::SetEnvironmentVariable("AWP_ROOT261", "C:\Program Files\ANSYS Inc\ANSYS Student\v261", "User")
```

For Ansys 2025 R2, use `AWP_ROOT252` and `v252` instead.

## Baseline Numbers

Your project number is 27:

- `b = 45 cm = 0.45 m`
- `h = 25 cm = 0.25 m`
- `hT = 100 cm = 1.00 m`
- side-view CFD plate height `hT + 1.0 m = 2.00 m`
- `cwind = 110 km/h = 30.56 m/s`

Before running CFD, get the expected order of magnitude:

```powershell
python Aufgabe1\aufgabe1_wind_baseline.py
```

Use `--project` only if you want to compare another table row.

## Meshing Route

The primary route is now fully scripted:

```powershell
.\.venv\Scripts\python.exe Aufgabe1\generate_plate_mesh.py
```

This writes:

- `Aufgabe1\out\plate_2d_gmsh.msh` for inspection in Gmsh
- `Aufgabe1\out\plate_2d.msh` as the solver-ready Fluent mesh

Then run a short smoke solve:

```powershell
.\.venv\Scripts\python.exe Aufgabe1\solve_plate_2d_template.py --mesh Aufgabe1\out\plate_2d.msh --iterations 10 --output Aufgabe1\out\plate_2d_test.cas.h5
```

For a real result, increase the iterations, for example:

```powershell
.\.venv\Scripts\python.exe Aufgabe1\solve_plate_2d_template.py --mesh Aufgabe1\out\plate_2d.msh --iterations 500 --output Aufgabe1\out\plate_2d_solution.cas.h5
```

The solver writes:

- `Aufgabe1\out\drag_plate.out`
- `Aufgabe1\out\drag_summary.txt`
- `Aufgabe1\out\plate_2d_solution.cas.h5`
- `Aufgabe1\out\plate_2d_solution.dat.h5`

The older Fluent Meshing `.fmd` template remains as a fallback:

```powershell
python Aufgabe1\mesh_plate_2d_template.py --geometry path\to\plate_domain.fmd
```

The geometry file should be exported from SpaceClaim/DesignModeler/Fluent
Meshing as an `.fmd` or compatible CAD file with useful labels:

- `plate_wall` for the sign edges
- `inlet`
- `outlet`
- `top`
- `bottom`
- optional `wake_boi` face for a wake refinement body of influence

If labels differ, pass them explicitly with the script arguments.

## CFD Settings to Document

For the report, document these choices:

- Flow domain for project 27: `x = -10 m` to `x = 30 m` (40 m long),
  `y = -10 m` to `y = +10 m` (20 m high), with the plate centered at
  `x = 0`; that is `5 x plate height` upstream, `15 x plate height`
  downstream, and `5 x plate height` above/below the plate centerline
  (plate height `hT + 1.0 m = 2.0 m`)
- Refinement at plate edges because separation and pressure gradients are
  strongest there
- Refinement in the downstream wake because velocity and pressure gradients
  remain large after separation
- Velocity inlet with the assignment wind speed
- Pressure outlet at `0 Pa` gauge
- Slip/symmetry or far-field style top/bottom boundaries to avoid artificial
  wall boundary layers
- No-slip wall on the sign plate
- Turbulence model such as SST k-omega for the high-Reynolds-number separated
  flow
