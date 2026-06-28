# Modularbeit FEM und CFD - Projekt Nr. 27

Dieses Repository enthält den bereinigten Code, die Daten und die Abbildungen für den Abschlussbericht der Modularbeit FEM und CFD (Projekt Nr. 27). Alle Ordner, Definitionsdateien und Ausführungsskripte wurden ins Deutsche übersetzt und umfassend kommentiert, um eine maximale Nachvollziehbarkeit für den Korrektor zu gewährleisten.

## Struktur des Repositories

```text
.
├── README.md                           # Diese Datei
├── requirements.txt                    # Python-Abhängigkeiten
├── assignment_page-2.png               # Aufgabenstellung Bild
├── bericht/
│   ├── bericht.tex                     # LaTeX-Bericht (Source of Truth für den Bericht)
│   └── bericht.pdf                     # Kompiliertes PDF des Berichts
│
├── Gemeinsamer_Code/                   # Geteilte Python-Module für Solver, Vernetzung und Visualisierung
│   ├── apdl_ergebnis_parser.py         # Parser für ANSYS-Ergebnisse
│   ├── apdl_fachwerk.py                # Vorlagen für Fachwerk-APDL-Dateien
│   ├── apdl_platte_schale.py           # Vorlagen für Platten-APDL-Dateien
│   ├── berichts_abbildungen.py         # Rendering-Logik für Berichtsabbildungen
│   ├── cfd_auswertung.py               # Postprocessing der CFD-Ergebnisse
│   ├── cfd_netz_generierung.py         # Gmsh-Netzgenerierung
│   ├── erzeuge_berichts_grafiken.py    # Hauptskript zur Regeneration aller Grafiken
│   ├── fluent_loesung_vorlage.py       # Fluent-Löser-Setup
│   ├── fluent_netz_schreiber.py        # Netzkonverter (Gmsh zu Fluent)
│   ├── fluent_umgebung.py              # Umgebungskonfiguration für Fluent
│   ├── hilfsfunktionen.py              # Gemeinsame Hilfsfunktionen
│   └── python_fem_loesung.py           # Kern-Löser der Python-FEM
│
├── Aufgabe_1_1_CFD_Stroemung/
│   ├── Definitionen_und_Ausfuehrung.py # Parameter und Ablauf für CFD (Gmsh/Fluent)
│   ├── data/                           # CFD-Netze und stationäre Druckdaten
│   └── figures/                        # CFD-Grafiken für den Bericht
│
├── Aufgabe_1_2a_Plattenstruktur/
│   ├── Definitionen_und_Ausfuehrung.py # Parameter und Ablauf für FE-Platte (SHELL181)
│   ├── Singularitaetsstudie.py         # Netzstudie zur Spannungssingularität
│   ├── data/                           # FE-Lagerkräfte und Konvergenztabelle
│   └── figures/                        # Grafiken zur Plattenbeanspruchung
│
├── Aufgabe_1_2b_d_Fachwerk_ANSYS/
│   ├── Definitionen_und_Ausfuehrung.py # Parameter und APDL-Skripte für Fachwerk (LINK180)
│   ├── data/                           # ANSYS-Kräfte und -Lagerreaktionen
│   └── figures/                        # Visualisierungen der ANSYS-Rechnung
│
├── Aufgabe_1_2e_h_Fachwerk_Python/
│   ├── Definitionen_und_Ausfuehrung.py # Parameter und Python-FE-Löser (Steifigkeitsmethode)
│   ├── data/                           # Vergleichsdaten Python vs. ANSYS
│   └── figures/                        # Deformierte Struktur aus Python
│
├── Aufgabe_2/
│   ├── Definitionen_und_Ausfuehrung.py # Nennspannung und Formzahlberechnung (alpha_k)
│   ├── data/                           # Konvergenzdaten für das Workbench-Modell
│   └── figures/                        # Diagramm der Konvergenz und Screenshots
│
└── Workbench_Creator/                  # Automatisches Setup des Workbench-Projekts (Aufgabe 1)
    ├── README_Workbench.md             # Dokumentation zur Ausführung
    ├── erzeuge_projekt.wbjn            # IronPython Workbench-Journal
    └── starte_workbench_generierung.py # Startskript für Windows-Systeme
```

## Schnellstart: Hauptskripte der Aufgaben

Jede Aufgabe verfügt in ihrem Verzeichnis über eine zentrale Datei `Definitionen_und_Ausfuehrung.py`. Am Anfang dieser Skripte sind alle geometrischen und physikalischen Parameter für das **Projekt Nr. 27** explizit definiert und ausführlich auf Deutsch dokumentiert.

| Aufgabe | Skript | Benötigt ANSYS? | Beschreibung |
|---|---|---|---|
| **1.1 CFD Strömung** | `Aufgabe_1_1_CFD_Stroemung/Definitionen_und_Ausfuehrung.py` | Nur für Fluent-Lösung (Schritte 2+3) | Erzeugt die Gmsh- und Fluent-Netze der Platte |
| **1.2a Platte** | `Aufgabe_1_2a_Plattenstruktur/Definitionen_und_Ausfuehrung.py` | Nur für MAPDL-Löser | Schreibt APDL-Inp-Dateien für die Schalenberechnung |
| **1.2b-d Fachwerk ANSYS** | `Aufgabe_1_2b_d_Fachwerk_ANSYS/Definitionen_und_Ausfuehrung.py` | Nur für MAPDL-Löser | Schreibt APDL-Inp-Skripte für die Fachwerkberechnung |
| **1.2e-h Fachwerk Python** | `Aufgabe_1_2e_h_Fachwerk_Python/Definitionen_und_Ausfuehrung.py` | **Nein** | Berechnet das Fachwerk komplett autark mit Python |
| **2 Kerbformzahl** | `Aufgabe_2/Definitionen_und_Ausfuehrung.py` | **Nein** | Berechnet Formzahl und Nennspannungsvergleich |
| **Workbench-Erstellung** | `Workbench_Creator/starte_workbench_generierung.py` | **Ja** (ANSYS Workbench) | Erstellt das gesamte Workbench-Projekt für Aufgabe 1 |

## Einrichtung der Python-Umgebung

Um die Python-Skripte lokal auszuführen, wird die Einrichtung einer virtuellen Umgebung empfohlen:

```bash
# 1. Virtuelle Umgebung erstellen
python -m venv .venv

# 2. Aktivierung der Umgebung
# Unter Windows (PowerShell):
.\.venv\Scripts\activate
# Unter Linux / macOS:
source .venv/bin/activate

# 3. Python-Bibliotheken installieren
pip install -r requirements.txt
```

## Regeneration aller Berichtsabbildungen

Die im LaTeX-Bericht verwendeten Abbildungen können gesammelt über das zentrale Skript neu generiert werden:

```bash
python Gemeinsamer_Code/erzeuge_berichts_grafiken.py
```

Das Skript liest die Ergebnisdaten aus den Aufgabenschritten und schreibt die fertigen PNGs in die jeweiligen `figures/`-Ordner.

## Kompilieren des LaTeX-Berichts

Der Bericht befindet sich im Verzeichnis `bericht/` und kann über folgenden Aufruf gebaut werden:

```bash
cd bericht
pdflatex bericht.tex
```
*(Hinweis: Für die korrekte Generierung des Inhaltsverzeichnisses und der Referenzen sollte der Befehl zweimal ausgeführt werden).*

## Alles durchlaufen lassen:

# 1. Virtuelle Umgebung aktivieren
.\.venv\Scripts\activate

# 2. Ausführen der fünf Aufgabenskripte und der Singularitätsstudie
python Aufgabe_1_1_CFD_Stroemung/Definitionen_und_Ausfuehrung.py
python Aufgabe_1_2a_Plattenstruktur/Definitionen_und_Ausfuehrung.py
python Aufgabe_1_2a_Plattenstruktur/Singularitaetsstudie.py
python Aufgabe_1_2b_d_Fachwerk_ANSYS/Definitionen_und_Ausfuehrung.py
python Aufgabe_1_2e_h_Fachwerk_Python/Definitionen_und_Ausfuehrung.py
python Aufgabe_2/Definitionen_und_Ausfuehrung.py

# 3. Alle Abbildungen und Tabellen für den Bericht generieren
python Gemeinsamer_Code/erzeuge_berichts_grafiken.py

# 4. LaTeX-Bericht kompilieren (zweimal ausführen für korrektes Inhaltsverzeichnis)
cd bericht
pdflatex bericht.tex
pdflatex bericht.tex
cd ..