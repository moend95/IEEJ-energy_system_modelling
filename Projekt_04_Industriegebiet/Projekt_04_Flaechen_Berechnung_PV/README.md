# Projekt 04 - Industriegebiet Dachflächen PV-Berechnung

Generierung von PV-Reihen auf Dachflächen des Jüchener Industriegebiets mit benutzerdefinierten Abständen.

## Überblick

Dieses Projekt implementiert eine modulare Python-Anwendung zur Generierung von parallelen Ost–West-Linien auf einer eingebetteten Polygonfläche. Die Lösung nutzt Klassen-basierte Architektur und ist vollständig getestet.

## Struktur

### Hauptdatei: `Projekt_04_Industriegebiet_Dachflaechen_PV.py`

Enthält folgende Klassen:

| Klasse | Beschreibung | Methoden |
|--------|-------------|----------|
| `GeoJSONReader` | Lädt eingebettete GeoJSON-Fläche und handhabt Reprojizierung | `load()`, `_choose_utm_crs()` |
| `EastWestLineGenerator` | Generiert parallele Linien in Ost–West-Richtung | `generate_lines()`, `extract_line_segments()` |
| `UTMTransformerApplier` | Reprojiziert Features zwischen UTM und WGS84 | `reproject_features()` |
| `GeoJSONExporter` | Exportiert Features als RFC 7946 konforme GeoJSON-Dateien | `export()` |
| `RowSpacingInputHandler` | Verarbeitet Benutzerabfrage für Reihenabstand | `get_row_spacing()` |

### Testdatei: `test_projekt_04.py`

28 umfangreiche Unit-Tests:
- **GeoJSONReader**: 5 Tests (Laden, Reprojizierung, CRS-Wahl)
- **EastWestLineGenerator**: 7 Tests (Liniengenerierung, Validierung, Eigenschaften)
- **UTMTransformerApplier**: 3 Tests (Reprojizierung, Koordinatenbereiche)
- **GeoJSONExporter**: 4 Tests (Dateioperationen, Format-Validierung)
- **RowSpacingInputHandler**: 2 Tests (Input-Verarbeitung)
- **Main-Funktion**: 4 Tests (Orchestrierung, Metadaten)
- **Integration**: 3 Tests (End-to-End-Workflows)

**Status**: ✅ 28/28 Tests PASSED

## Verwendung

### Interaktives Programm (mit Benutzer-Eingabe)

```bash
cd Projekt_04_Industriegebiet/Flaechen_Berechnung_PV
python Projekt_04_Industriegebiet_Dachflaechen_PV.py
```

Prompt: `Bitte Reihenabstand in Metern eingeben [Default: 2.0]: `

### Programmatische Nutzung (non-interaktiv)

```python
from Projekt_04_Industriegebiet_Dachflaechen_PV import main

# Mit Default-Abstand 2.0 m
result = main(interactive=False, output_dir="outputs")

# Mit benutzerdefiniertem Abstand
from Projekt_04_Industriegebiet_Dachflaechen_PV import (
    GeoJSONReader, EastWestLineGenerator, 
    UTMTransformerApplier, GeoJSONExporter, EMBEDDED_GEOJSON
)

reader = GeoJSONReader(EMBEDDED_GEOJSON)
geom_wgs84, geom_utm, to_utm, to_wgs84 = reader.load()

spacing = 5.0  # 5 Meter Abstand
lines = EastWestLineGenerator.generate_lines(geom_utm, spacing)
features_utm = EastWestLineGenerator.extract_line_segments(lines, geom_utm)
features_wgs84 = UTMTransformerApplier.reproject_features(features_utm, to_wgs84)

GeoJSONExporter.export(features_wgs84, f"outputs/Projekt_04_..._Reihen_{spacing}m.geojson")
```

## Eingabedaten

Die Polygonfläche ist als `EMBEDDED_GEOJSON` eingebettet:
- **Name**: "Energielandschaft_Juechen_Industriegebiet"
- **Beschreibung**: "Dachflächen PV Industriegebiet"
- **Koordinaten**: 14 Punkte (WGS84)
- **Fläche**: ~478.000 m² (UTM)
- **UTM-Zone**: 32N (ca. 6.53°E, 51.09°N)

## Ausgabedaten

Output-Format: GeoJSON FeatureCollection mit LineString-Geometrien

Beispiel-Dateiname: `Projekt_04_Industriegebiet_Dachflaechen_PV_Reihen_2.0m.geojson`

Struktur jedes Features:
```json
{
  "type": "Feature",
  "geometry": {
    "type": "LineString",
    "coordinates": [[lon, lat], [lon, lat], ...]
  },
  "properties": {
    "row": 0,
    "segment": 0,
    "length_m": 123.456,
    "orientation": "EW"
  }
}
```

### Generierte Dateien

| Datei | Linien | Features | Größe |
|-------|--------|----------|-------|
| `..._Reihen_2.0m.geojson` | 539 | 578 | 262 KB |
| `..._Reihen_5.0m.geojson` | 215 | 231 | 105 KB |

## Technische Spezifikation

### Koordinatensysteme
- **Input/Output**: WGS84 (EPSG:4326) mit [lon, lat]-Reihenfolge (RFC 7946)
- **Arbeitsraum**: UTM mit automatischer Zonenwahl basierend auf Polygon-Zentroid
- Transformationen mit pyproj für höchste Genauigkeit

### Geometrie
- **Linien**: Parallele Ost–West-Linien (konstante Y, variable X in UTM)
- **Schnittberechnung**: Intersection zwischen generierten Linien und Polygon
- **Handling**: MultiLineString-Geometrien werden als separate Features exportiert

### Algorithmus
1. Lade GeoJSON mit `GeoJSONReader` (WGS84 → UTM)
2. Generiere Ost–West-Linien mit benutzerdefinierten Abständen
3. Schneide Linien mit Polygon (extract_line_segments)
4. Konvertiere zurück zu WGS84 (UTMTransformerApplier)
5. Exportiere als RFC 7946 GeoJSON

## Tests

### Ausführung

```bash
# Alle Tests
pytest test_projekt_04.py -v

# Spezifische Test-Klasse
pytest test_projekt_04.py::TestEastWestLineGenerator -v

# Mit Coverage
pytest test_projekt_04.py --cov=. --cov-report=html
```

### Testabdeckung

- **Unit Tests**: Alle Klassenmethoden isoliert getestet
- **Integration Tests**: End-to-End-Workflows mit echten Geometrien
- **Edge Cases**: Ungültige Eingaben, Boundary-Bedingungen, verschiedene Abstände

## Abhängigkeiten

```
shapely>=2.0
pyproj>=3.4
pytest>=7.0 (nur für Tests)
```

Installation:
```bash
pip install shapely pyproj pytest
```

## Konfiguration

### Benutzerparameter

- **Reihenabstand**: 0.1 m bis 100+ m (positiver Float)
- **Default**: 2.0 m
- **Output-Verzeichnis**: `outputs/` (wird erstellt wenn nicht vorhanden)

### Konstanten

- **EMBEDDED_GEOJSON**: Definiert in Hauptdatei – kann aktualisiert werden
- **UTM Zone**: Automatisch bestimmt basierend auf Polygon-Position

## Vergleich Projekt_02 vs Projekt_04

| Aspekt | Projekt_02 (Agri-PV) | Projekt_04 (Dach-PV) |
|--------|----------------------|----------------------|
| **Zweck** | Landwirtschaftliche PV-Fläche | Dachflächen PV |
| **Linien-Typ** | Vertikal + Horizontal | Nur Ost–West |
| **Abstand-Berechnung** | Abhängig von Traktor-Parametern | Benutzer-Input |
| **Polygon-Größe** | 24.32 km² | ~478.000 m² |
| **Generierte Reihen** | 972 (H) / 2477 (V) | 539 (2m) / 215 (5m) |
| **Komplexität** | Hoch (Margins, Traktor-Physik) | Mittel (Benutzer-gesteuert) |

## Erweiterungsmöglichkeiten

Mögliche zukünftige Features:
- Nord–Süd-Linien zusätzlich zu Ost–West
- Flächenkapazität basierend auf Modulabmessungen
- GeoJSON-Import statt Embedded-Strings
- Multi-Polygon-Unterstützung
- Visualisierung in QGIS/Leaflet
- Performance-Optimierung für große Flächen

## Lizenz & Kontext

Projekt im Rahmen des TH Köln Masterprojekts "IEEJ Energy System Modelling"
