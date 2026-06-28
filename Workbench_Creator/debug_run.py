import os
import subprocess
from pathlib import Path

DEFAULT_ANSYS_PATHS = [
    r"C:\Program Files\ANSYS Inc\ANSYS Student\v261\Framework\bin\Win64\RunWB2.exe",
    r"C:\Program Files\ANSYS Inc\v261\Framework\bin\Win64\RunWB2.exe",
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

def main():
    wb_path = find_runwb2()
    if not wb_path:
        print("RunWB2.exe nicht gefunden!")
        return

    repo_root = Path(__file__).resolve().parent.parent
    
    # Pfade
    cas_path = repo_root / "Aufgabe_1_1_CFD_Stroemung" / "out" / "plate_2d_solution.cas.h5"
    msh_path = repo_root / "Aufgabe_1_1_CFD_Stroemung" / "data" / "plate_2d_fluent.msh"
    plate_inp_path = repo_root / "Aufgabe_1_2a_Plattenstruktur" / "out" / "plate_structural.inp"
    truss_inp_path = repo_root / "Aufgabe_1_2b_d_Fachwerk_ANSYS" / "out" / "truss_structural.inp"
    
    if cas_path.exists():
        fluent_path = str(cas_path).replace("\\", "/")
        fluent_type = "Case"
    else:
        fluent_path = str(msh_path).replace("\\", "/")
        fluent_type = "Mesh"

    plate_dir = str(plate_inp_path.parent).replace("\\", "/") + "/"
    truss_dir = str(truss_inp_path.parent).replace("\\", "/") + "/"
    plate_cmd = f"/INPUT,{plate_inp_path.stem},inp,{plate_dir}"
    truss_cmd = f"/INPUT,{truss_inp_path.stem},inp,{truss_dir}"
    
    # Template laden und ersetzen
    template = Path(__file__).resolve().parent / "erzeuge_projekt.wbjn"
    temp_journal = Path(__file__).resolve().parent / "erzeuge_projekt_temp.wbjn"
    
    content = template.read_text(encoding="utf-8")
    content = content.replace("__FLUENT_IMPORT_PATH__", fluent_path)
    content = content.replace("__FLUENT_IMPORT_TYPE__", fluent_type)
    content = content.replace("__PLATE_INPUT_CMD__", plate_cmd)
    content = content.replace("__TRUSS_INPUT_CMD__", truss_cmd)
    
    temp_journal.write_text(content, encoding="utf-8")
    
    print("=== Generiertes Journal ===")
    print(content)
    print("=== Ende Journal ===\n")
    
    print(f"Starte: {wb_path} -R {temp_journal}")
    result = subprocess.run(
        [wb_path, "-R", str(temp_journal)],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
    )
    
    print(f"\nReturn code: {result.returncode}")
    if result.stdout:
        print(f"STDOUT:\n{result.stdout}")
    if result.stderr:
        print(f"STDERR:\n{result.stderr}")
    
    # Temp-Datei NICHT loeschen bei Fehler
    if result.returncode == 0:
        temp_journal.unlink(missing_ok=True)
        print("\nErfolgreich! Temp-Journal geloescht.")
    else:
        print(f"\nFehler! Temp-Journal bleibt: {temp_journal}")

if __name__ == "__main__":
    main()
