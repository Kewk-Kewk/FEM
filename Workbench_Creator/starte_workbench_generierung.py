import os
import subprocess
import sys
from pathlib import Path

DEFAULT_ANSYS_PATHS = [
    r"C:\Program Files\ANSYS Inc\ANSYS Student\v261\Framework\bin\Win64\RunWB2.exe",
    r"C:\Program Files\ANSYS Inc\v261\Framework\bin\Win64\RunWB2.exe",
    r"C:\Program Files\ANSYS Inc\v252\Framework\bin\Win64\RunWB2.exe",
    r"C:\Program Files\ANSYS Inc\v251\Framework\bin\Win64\RunWB2.exe",
    r"C:\Program Files\ANSYS Inc\v242\Framework\bin\Win64\RunWB2.exe",
    r"C:\Program Files\ANSYS Inc\v241\Framework\bin\Win64\RunWB2.exe",
]


def find_runwb2():
    for path in DEFAULT_ANSYS_PATHS:
        if os.path.exists(path):
            return path
    for var in sorted(os.environ.keys(), reverse=True):
        if var.startswith("AWP_ROOT"):
            awp_root = os.environ[var]
            path = os.path.join(awp_root, "Framework", "bin", "Win64", "RunWB2.exe")
            if os.path.exists(path):
                return path
    return None


def run_workbench(wb_path: str, journal_path: Path, repo_root: Path) -> int:
    log_dir = journal_path.parent
    stdout_path = log_dir / "wb_stdout.txt"
    stderr_path = log_dir / "wb_stderr.txt"

    print(f"\nStarte RunWB2.exe -R {journal_path.name}")
    result = subprocess.run(
        [wb_path, "-R", str(journal_path)],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
    )
    stdout_path.write_text(result.stdout or "", encoding="utf-8")
    stderr_path.write_text(result.stderr or "", encoding="utf-8")

    if result.stdout:
        print(result.stdout.rstrip())
    if result.stderr:
        print(result.stderr.rstrip(), file=sys.stderr)

    return result.returncode


def main():
    print("=" * 60)
    print("ANSYS Workbench Gesamtprojekt-Generator")
    print("=" * 60)

    wb_path = find_runwb2()
    if not wb_path:
        print("Fehler: RunWB2.exe nicht gefunden.")
        print("Bitte ANSYS installieren oder den Pfad manuell setzen.")
        return 1

    repo_root = Path(__file__).resolve().parent.parent
    creator_dir = Path(__file__).resolve().parent

    print(f"ANSYS:   {wb_path}")
    print(f"Projekt: {repo_root}")

    cas_path = repo_root / "Aufgabe_1_1_CFD_Stroemung" / "out" / "plate_2d_solution.cas.h5"
    msh_path = repo_root / "Aufgabe_1_1_CFD_Stroemung" / "data" / "plate_2d_fluent.msh"
    plate_inp_path = repo_root / "Aufgabe_1_2a_Plattenstruktur" / "out" / "plate_structural.inp"
    truss_inp_path = repo_root / "Aufgabe_1_2b_d_Fachwerk_ANSYS" / "out" / "truss_structural.inp"

    if cas_path.exists():
        fluent_import_path = str(cas_path).replace("\\", "/")
        fluent_import_type = "Case"
        print(f"\n[Fluent]  Geloeste Case-Datei: {cas_path.name}")
    elif msh_path.exists():
        fluent_import_path = str(msh_path).replace("\\", "/")
        fluent_import_type = "Mesh"
        print(f"\n[Fluent]  WARNUNG: Nur Mesh, keine Loesung! Bitte zuerst CFD-Skript ausfuehren.")
        print(f"          {msh_path.name}")
    else:
        print("\nFehler: Weder Case noch Mesh gefunden.")
        return 1

    missing = []
    for path, label in [(plate_inp_path, "Platte"), (truss_inp_path, "Fachwerk")]:
        if path.exists():
            print(f"[MAPDL]   {label}: {path.name}")
        else:
            missing.append(str(path))

    if missing:
        print("\nFehler: Folgende Eingabedateien fehlen:")
        for path in missing:
            print(f"  - {path}")
        print("\nBitte zuerst die jeweiligen Definitionen_und_Ausfuehrung.py ausfuehren.")
        return 1

    template_path = creator_dir / "erzeuge_projekt.wbjn"
    temp_journal_path = creator_dir / "erzeuge_projekt_temp.wbjn"

    content = template_path.read_text(encoding="utf-8")
    content = content.replace("__FLUENT_IMPORT_PATH__", fluent_import_path)
    content = content.replace("__FLUENT_IMPORT_TYPE__", fluent_import_type)
    content = content.replace("__PLATE_INP_PATH__", str(plate_inp_path).replace("\\", "/"))
    content = content.replace("__TRUSS_INP_PATH__", str(truss_inp_path).replace("\\", "/"))
    temp_journal_path.write_text(content, encoding="utf-8")

    print(f"\nJournal: {temp_journal_path.name}")
    print(f"Ziel:    {repo_root / 'Aufgabe_1.wbpj'}")
    print("-" * 60)
    print("Hinweis: Schliesse alle offenen ANSYS-Fenster vor dem Start.")
    print("Die Generierung kann mehrere Minuten dauern (MAPDL-Loesungen).")
    print("-" * 60)

    returncode = run_workbench(wb_path, temp_journal_path, repo_root)

    wbpj_path = repo_root / "Aufgabe_1.wbpj"
    if returncode == 0 and wbpj_path.exists():
        print("\nErfolg: Aufgabe_1.wbpj wurde erstellt.")
        if fluent_import_type == "Case":
            print("  - Fluent:  geloeste Case-Datei (korrekte 110 km/h Simulation)")
        print("  - Platte:  plate_structural.inp ausgefuehrt")
        print("  - Fachwerk: truss_structural.inp ausgefuehrt")
    else:
        print(f"\nFehler: RunWB2 beendet mit Code {returncode}.")
        print(f"Log: {creator_dir / 'wb_stdout.txt'}")
        print(f"Log: {creator_dir / 'wb_stderr.txt'}")
        if temp_journal_path.exists():
            print(f"Journal zur Fehlersuche: {temp_journal_path}")
        return returncode

    # Temp-Journal nur bei Erfolg loeschen
    try:
        temp_journal_path.unlink(missing_ok=True)
    except OSError:
        pass

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
