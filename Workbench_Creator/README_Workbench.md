# Workbench Creator - Automatische Projekterstellung für Aufgabe 1

Dieses Verzeichnis enthält Skripte zur automatischen Erstellung und Konfiguration eines ANSYS Workbench-Projekts aus dem Code heraus.

## Funktionsweise

ANSYS Workbench verfügt über eine Scripting-Schnittstelle auf Basis von **IronPython**. Das Skript `erzeuge_projekt.wbjn` (Workbench Journal) automatisiert die Schritte, die man normalerweise manuell in der Workbench-Oberfläche durchführt.

1. **`erzeuge_projekt.wbjn`**:
   - Erstellt ein **Fluid Flow (Fluent)**-System für Aufgabe 1.1 (CFD).
   - Erstellt ein **Static Structural**-System für Aufgabe 1.2a (Plattenstruktur).
   - Erstellt ein **Static Structural**-System für Aufgabe 1.2b-d (Fachwerk).
   - Definiert die Materialdaten für **Aluminium** (Platte) und **Stahl S235** (Fachwerk) in den jeweiligen *Engineering Data* Containern.
   - Speichert das fertige Projekt als `Aufgabe_1.wbpj`.

2. **`starte_workbench_generierung.py`**:
   - Sucht auf Ihrem Windows-System automatisch nach der installierten ANSYS Workbench-Version (z. B. v241, v251, v261).
   - Startet Workbench im Hintergrund und führt das Journal-Skript aus.

## Ausführung

Stellen Sie sicher, dass ANSYS auf Ihrem System installiert ist. Führen Sie dann das Python-Skript aus:

```bash
python Workbench_Creator/starte_workbench_generierung.py
```

Das Skript sucht nach der Datei `RunWB2.exe` und baut das Projekt im Hintergrund auf. Nach Abschluss finden Sie die Projektdatei `Aufgabe_1.wbpj` (und den Ordner `Aufgabe_1_files`) ganz außen im Hauptverzeichnis des Repositories.
