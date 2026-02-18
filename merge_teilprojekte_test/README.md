# Merge Teilprojekte Test

Dieses Verzeichnis enthält Skripte zur Integration und Simulation verschiedener Teilprojekte des IEEJ Energiesystem-Modellierungsprojekts.

## Übersicht

Das Hauptskript `run_merge.py` kombiniert verschiedene Teilprojekte des Innovationsparks Erneuerbare Energien Jüchen:

- **Solarautobahn**: PV-Systeme entlang von Autobahnen (Windschutz, Schallschutz, Böschungen)
- **Industriegebiet**: Aggregation von Lastgängen industrieller Verbraucher
- **Energielandschaft**: Agri-PV Simulationen für landwirtschaftliche Flächen

## Hauptskripte

### `run_merge.py`

Das Hauptintegrationsskript, das folgende Funktionen bietet:

1. **Wetterdatenbeschaffung**
   - Lädt Wetterdaten vom DWD (Deutscher Wetterdienst) oder aus vorhandenen CSV-Dateien
   - Konfigurierbar über `USE_EXISTING_WEATHER` Flag
   - Standardkoordinaten: (51.08579, 6.47554)
   - Zeitraum: 2022

2. **PV-System Simulation (Energielandschaft/Agri-PV)**
   - Verarbeitet GeoJSON-Geometrien für Agri-PV Anlagen
   - Berechnet die Gesamtlänge der PV-Reihen
   - Unterstützt verschiedene Agri-PV Konfigurationen:
     - Horizontal (geneigt)
     - Horizontal mit Tracking
     - Vertikal (bifazial)
   - Generiert Zeitreihen der Energieproduktion
   - Berechnet Gesamtjahresenergieproduktion

3. **Optionale Module** (aktuell auskommentiert):
   - Solarautobahn PV-Simulation
   - Industriegebiet Lastgangaggregation

### `run_pv_baukasten.py`

Standalone-Skript für PV-Baukastensimulationen mit ähnlicher Wetterdaten-Integration.

## Verzeichnisstruktur

```
merge_teilprojekte_test/
├── run_merge.py                 # Hauptintegrationsskript
├── run_pv_baukasten.py          # Standalone PV-Simulation
├── functions/                   # Funktionsmodule
│   ├── Energielandschaft.py     # Agri-PV Funktionen
│   ├── functions_weather_data.py # Wetterdaten vom DWD
│   ├── hilfsfunktionen.py       # Hilfsfunktionen
│   ├── Industriegebiet.py       # Industrie-Lastgänge
│   ├── pv_baukasten.py          # PV-System Klassen
│   └── inputs/                  # Eingabedaten
│       ├── geometrien/          # GeoJSON-Dateien
│       ├── punkte/              # Generierte Punktdaten
│       └── wetter_daten.csv     # Wetterdaten Cache
└── outputs/                     # Ausgabedateien
    ├── *.geojson                # Geometrie-Ausgaben
    └── *.csv                    # Zeitreihen-Ausgaben
```

## Verwendung

### Voraussetzungen

Installiere die erforderlichen Pakete:

```bash
pip install -r ../requirements_final.txt
```

Hauptabhängigkeiten:
- pandas
- matplotlib
- pvlib (für PV-Simulationen)
- shapely, geopandas (für Geometrieverarbeitung)
- wetterdienst (für DWD-Daten)

### Ausführung

1. **Energielandschaft Simulation ausführen**:

```bash
python run_merge.py
```

Das Skript wird interaktiv:
- Nach der GeoJSON-Datei für die Agri-PV Fläche fragen
- Die gewünschte PV-Ausrichtung erfragen
- Wetterdaten laden (oder vom DWD abrufen)
- PV-Simulation durchführen
- Ergebnisse plotten und ausgeben

2. **Konfigurationsoptionen**:

Im Skript anpassen:
- `USE_EXISTING_WEATHER`: `True` für CSV, `False` für DWD-Abruf
- `weather_csv`: Pfad zur Wetterdaten-CSV
- `geojson_path_2`: Pfad zur Geometriedatei
- `step_size_default`: Schrittweite für Punktgenerierung (in Metern)

### Weitere Teilprojekte aktivieren

Um Solarautobahn oder Industriegebiet zu aktivieren, entferne die Kommentarzeichen (`'''`) um die entsprechenden Codeabschnitte.

## PV-Typen

Das System unterstützt verschiedene PV-Typen (definiert in `pv_baukasten.py`):

- **PV_TYPEN[0]**: Windschutzwand
- **PV_TYPEN[1]**: Schallschutzwand
- **PV_TYPEN[2]**: Schallschutzwand mit Dach
- **PV_TYPEN[3]**: Böschung
- **PV_TYPEN[4]**: Horizontal mit Tracking (Agri-PV)
- **PV_TYPEN[5]**: Vertikal bifazial (Agri-PV)
- **PV_TYPEN[6]**: Horizontal geneigt (Agri-PV)

## Ausgaben

Das Skript erzeugt:

1. **Konsolen-Ausgaben**:
   - Berechnete Jahresenergie in kWh
   - Länge der PV-Reihen in Metern
   - Ausgewählte PV-Typen

2. **Dateien**:
   - CSV-Dateien mit Punktkoordinaten und Azimut
   - GeoJSON-Dateien mit Agri-PV Geometrien
   - Zeitreihen der AC-Leistung

3. **Plots**:
   - Zeitreihen der Energieproduktion (matplotlib)

## Beispiel-Workflow

```python
# 1. Wetterdaten laden
weather_df = pd.read_csv("./functions/inputs/wetter_daten.csv")

# 2. Agri-PV Geometrie verarbeiten
result = main(interactive=True, output_dir="./outputs")

# 3. PV-System konfigurieren
pv_system = PV_System(
    geojson_path="path/to/geometry.geojson",
    pvtypes=[PV_TYPEN[6]],
    step_size=1000,
    weather_df=weather_df,
    base_output_dir="./outputs"
)

# 4. Simulation durchführen
results = pv_system.generate_pv_points()
energy_kwh, total_ac = pv_system.simulate_pv_type_energy(...)

# 5. Ergebnisse anzeigen
print(f"Jahresenergie: {energy_kwh:.1f} kWh")
total_ac.plot()
```

## Hinweise

- Die Wetterdaten werden für das Jahr 2022 abgerufen
- Koordinaten beziehen sich auf den Raum Jüchen (NRW)
- GeoJSON-Dateien müssen im WGS84-Koordinatensystem vorliegen
- Die PV-Simulation verwendet pvlib für präzise Berechnungen
- Module pro Meter werden automatisch basierend auf der Ausrichtung gewählt

## Entwicklung

### Module erweitern

Neue Funktionen können in den entsprechenden Modulen unter `functions/` hinzugefügt werden:

- `Energielandschaft.py`: Agri-PV Logik
- `pv_baukasten.py`: Neue PV-Typen oder Simulationsmethoden
- `Industriegebiet.py`: Lastgang-Aggregationslogik
- `hilfsfunktionen.py`: Allgemeine Hilfsfunktionen

### Debugging

Bei Problemen:
1. Überprüfe, ob alle GeoJSON-Dateien im richtigen Verzeichnis liegen
2. Stelle sicher, dass Wetterdaten verfügbar sind
3. Aktiviere Debugging-Ausgaben in den Modulen
4. Überprüfe die Koordinatensysteme der Geometrien

## Lizenz

Siehe Hauptprojekt-Repository.

## Kontakt

Teil des IEEJ (Innovationspark Erneuerbare Energien Jüchen) Masterprojekts der TH Köln.
