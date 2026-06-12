# Modularbeit FEM und CFD - Projekt Nr. 27

This repository contains the code, data and figures behind the assignment
report. It was cleaned up so that only the material actually used in the
report remains in the working tree; everything deprecated was moved (not
deleted) into [`_archive_unused/`](_archive_unused/).

## Repository layout

```text
.
├── README.md                  # this file
├── assignment.pdf             # the task sheet
├── assignment_page-2.png
├── report/
│   ├── bericht_aufgabe1.tex   # the report (source of truth for all figures)
│   └── bericht_aufgabe1.pdf   # compiled report
├── Aufgabe1/
│   ├── code/                  # CFD + structural + figure scripts (Python, APDL)
│   ├── data/                  # minimal inputs needed to rebuild the figures
│   ├── figures/               # final figures used by the report
│   ├── requirements.txt       # Python dependencies
│   ├── README_Workflow.md     # step-by-step CFD / ANSYS workflow
│   └── README_Setup.md        # PyFluent / environment setup
├── Aufgabe2/
│   ├── code/                  # notch-factor (Kerbformzahl) script
│   ├── data/                  # convergence data
│   ├── figures/               # final figures used by the report
│   └── screenshots/           # ANSYS Workbench screenshots used in the panels
└── _archive_unused/           # deprecated/test code, solver runs, ANSYS projects
```

## Rebuilding the report figures

All report figures are produced by a single script:

```bash
python Aufgabe1/code/make_report_figures.py
```

It reads the curated inputs in `Aufgabe1/data`, `Aufgabe2/data` and
`Aufgabe2/screenshots`, and writes the final PNGs into `Aufgabe1/figures` and
`Aufgabe2/figures`. Rebuilding the CFD contour/mesh figures additionally needs
the `h5dump` command-line tool on the PATH.

## Compiling the report

The report uses repository-root-relative image paths together with
`\graphicspath{{../}}`, so compile it from inside `report/`:

```bash
cd report
pdflatex bericht_aufgabe1.tex
```

## Reproducing the full simulations

`Aufgabe1/README_Workflow.md` and `Aufgabe1/README_Setup.md` document the full
PyFluent and ANSYS/MAPDL pipeline. The Python scripts now live in
`Aufgabe1/code/`; prefix the script paths in those guides with `code/`
accordingly. A complete re-run regenerates a scratch `Aufgabe1/out/` working
directory; only the curated subset under `data/` and `figures/` is kept here.

The original ANSYS Workbench projects (`ansys/`, `Aufgabe2/finalaufgabe2_files/`)
and the raw solver output are preserved under `_archive_unused/`.
