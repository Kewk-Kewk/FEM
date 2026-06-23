# Modularbeit FEM und CFD - Projekt Nr. 27

This repository contains the code, data and figures behind the assignment
report. It was cleaned up so that only the material actually used in the
report remains in the working tree.

## Repository layout

```text
.
├── README.md                  # this file
├── assignment.pdf             # the task sheet
├── report/
│   ├── bericht_aufgabe1.tex   # the report (source of truth for all figures)
│   └── bericht_aufgabe1.pdf   # compiled report
├── Aufgabe1/
│   ├── code/
│   │   ├── run_cfd.py                     # ENTRY-POINT: Aufgabe 1.1 (CFD)
│   │   ├── run_plate.py                   # ENTRY-POINT: Aufgabe 1.2a (plate)
│   │   ├── run_truss.py                   # ENTRY-POINT: Aufgabe 1.2b-d (ANSYS truss)
│   │   ├── run_python_fem.py              # ENTRY-POINT: Aufgabe 1.2e-h (Python FEM)
│   │   ├── make_report_figures.py         # generates all report figures
│   │   ├── aufgabe1_params.py             # project parameters (all 36 variants)
│   │   ├── utils.py                       # shared helpers (read_summary_value)
│   │   ├── generate_plate_mesh.py         # Gmsh mesh generation (CFD)
│   │   ├── fluent_mesh_writer.py          # Gmsh → Fluent .msh conversion
│   │   ├── fluent_env.py                  # PyFluent environment setup
│   │   ├── solve_plate_2d_template.py     # Fluent solver driver
│   │   ├── postprocess_solution.py        # CFD post-processing (PyFluent)
│   │   ├── postprocess_drag.py            # drag history parser
│   │   ├── structural_plate_apdl.py       # APDL generator for plate (SHELL181)
│   │   ├── structural_truss_apdl.py       # APDL generator for truss (LINK180)
│   │   ├── structural_truss_1_2.py        # Python FEM truss solver
│   │   ├── parse_plate_structural_results.py  # plate results parser
│   │   ├── parse_truss_apdl_results.py    # truss results parser
│   │   └── run_plate_singularity_study.py # singularity mesh study
│   ├── data/                  # minimal inputs needed to rebuild the figures
│   ├── figures/               # final figures used by the report
│   ├── requirements.txt       # Python dependencies
│   ├── README_Workflow.md     # step-by-step CFD / ANSYS workflow
│   └── README_Setup.md        # PyFluent / environment setup
├── Aufgabe2/
│   ├── code/
│   │   └── aufgabe2_kerb.py   # notch-factor (Kerbformzahl) script
│   ├── data/                  # convergence data
│   ├── figures/               # final figures used by the report
│   └── screenshots/final_report/  # final ANSYS Workbench screenshots
└── _archive_unused/           # deprecated/test code, solver runs, ANSYS projects
```

## Quick start: entry-point scripts

Each sub-task has a dedicated entry-point script with all parameters
for **Projekt 27** set at the top:

| Sub-task | Script | Requires ANSYS? |
|---|---|---|
| 1.1 CFD | `python Aufgabe1/code/run_cfd.py` | Fluent (steps 2+3) |
| 1.2a Plate | `python Aufgabe1/code/run_plate.py` | MAPDL |
| 1.2b-d Truss (ANSYS) | `python Aufgabe1/code/run_truss.py` | MAPDL |
| 1.2e-h Truss (Python FEM) | `python Aufgabe1/code/run_python_fem.py` | **No** |
| 2 Kerbformzahl | `python Aufgabe2/code/aufgabe2_kerb.py` | **No** |
| All report figures | `python Aufgabe1/code/make_report_figures.py` | **No** |

## Rebuilding the report figures

All report figures are produced by a single script:

```bash
python Aufgabe1/code/make_report_figures.py
```

It reads the curated inputs in `Aufgabe1/data`, `Aufgabe2/data` and
`Aufgabe2/screenshots/final_report`, and writes the final PNGs into
`Aufgabe1/figures` and `Aufgabe2/figures`. Rebuilding the CFD contour/mesh
figures additionally needs the `h5dump` command-line tool on the PATH.

## Compiling the report

The report uses repository-root-relative image paths together with
`\graphicspath{{../}}`, so compile it from inside `report/`:

```bash
cd report
pdflatex bericht_aufgabe1.tex
```

## Reproducing the full simulations

To run the python scripts, it is highly recommended to use the provided virtual environment:
```bash
source .venv/bin/activate
```

Here are the complete commands to run the pipelines end-to-end on Linux (using `wine` for ANSYS MAPDL):

### 1. CFD Pipeline (Requires Windows PyFluent)
```bash
python Aufgabe1/code/run_cfd.py
```
*(Note: Running PyFluent through Wine is currently not supported. This step requires a native Windows environment or a native Linux ANSYS installation.)*

### 2. Structural Plate Pipeline
Generate the APDL scripts:
```bash
python Aufgabe1/code/run_plate.py
```
Run ANSYS MAPDL via Wine:
```bash
export ANSYS_EXE="$HOME/.wine/drive_c/Program Files/ANSYS Inc/ANSYS Student/v261/ansys/bin/winx64/ansys261.exe"
wine "$ANSYS_EXE" -b -i Aufgabe1/out/plate_structural.inp -o Aufgabe1/out/plate_structural_solver.out -dir Aufgabe1/out -j plate_1_2
wine "$ANSYS_EXE" -b -i Aufgabe1/out/plate_post_probe.inp -o Aufgabe1/out/plate_post_probe.out -dir Aufgabe1/out -j plate_1_2_post
wine "$ANSYS_EXE" -b -i Aufgabe1/out/plate_export_plots.inp -o Aufgabe1/out/plate_export_plots.out -dir Aufgabe1/out -j plate_1_2_plots
```
Extract the results:
```bash
python Aufgabe1/code/parse_plate_structural_results.py --results Aufgabe1/out/plate_structural_results.txt --post-output Aufgabe1/out/plate_post_probe.out --apdl Aufgabe1/out/plate_structural.inp --out-dir Aufgabe1/out
```

### 3. Truss Pipeline (ANSYS)
Generate the APDL scripts (Requires `plate_hinge_reactions.csv` from a point-support plate run):
```bash
python Aufgabe1/code/run_truss.py
```
Run ANSYS MAPDL via Wine:
```bash
wine "$ANSYS_EXE" -b -i Aufgabe1/out/structural_truss.inp -o Aufgabe1/out/structural_truss_solver.out -dir Aufgabe1/out -j truss_1_2
wine "$ANSYS_EXE" -b -i Aufgabe1/out/truss_export_plots.inp -o Aufgabe1/out/truss_export_plots.out -dir Aufgabe1/out -j truss_1_2_plots
```
Extract the results:
```bash
python Aufgabe1/code/parse_truss_apdl_results.py --element-table Aufgabe1/out/truss_element_table.txt --summary Aufgabe1/out/truss_summary.txt
```

### 4. Truss Pipeline (Python FEM)
```bash
python Aufgabe1/code/run_python_fem.py
```

### 5. Aufgabe 2 (Kerbformzahl)
```bash
python Aufgabe2/code/aufgabe2_kerb.py
```

## Code overview for the Python FEM solver

The Python FEM implementation (`structural_truss_1_2.py`) follows the
standard direct stiffness method:

1. **Topology**: Build nodes and bar elements for the 7-panel truss
2. **Element stiffness**: Compute K^(e) = (EA/L) * [c²  cs  ...] for each bar
3. **Assembly**: K[I[a], I[b]] += Ke[a, b]  (loop over element DOF pairs)
4. **BCs**: Fix DOFs 0, 1, 3 (L0 in x/y, R0 in y)
5. **Solve**: U = K_ff^{-1} * F_f
6. **Post-process**: Axial forces N = (EA/L) * [-c, -s, c, s] · u_e
