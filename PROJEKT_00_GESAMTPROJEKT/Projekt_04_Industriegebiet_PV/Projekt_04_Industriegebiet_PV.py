"""
Projekt 04 - Industriegebiet Dachflächen PV-Berechnung

Dieses Skript generiert PV-Reihen auf Dachflächen des Industriegebiets:
- Einlesung einer eingebetteten GeoJSON-Fläche (Industriegebiet)
- Generierung von parallelen Linien (Ost–West-Ausrichtung)
- Benutzerabfrage für Reihenabstand
- Export der generierten Reihen als GeoJSON

Technische Hinweise:
- Shapely wird für Geometrieoperationen verwendet.
- Flächen-/Längenberechnungen erfolgen in metrischem UTM (automatische Zonenwahl).
- GeoJSON-Output ist RFC 7946 konform.
"""

EMBEDDED_GEOJSON = '''{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "geometry": {
			"coordinates": [
				[
					[
						6.536914,
						51.099439
					],
					[
						6.538587,
						51.098179
					],
					[
						6.539236,
						51.097684
					],
					[
						6.539998,
						51.097115
					],
					[
						6.540513,
						51.096741
					],
					[
						6.546258,
						51.092415
					],
					[
						6.54165,
						51.089851
					],
					[
						6.536506,
						51.09382
					],
					[
						6.536822,
						51.093988
					],
					[
						6.537107,
						51.094133
					],
					[
						6.531066,
						51.098937
					],
					[
						6.533985,
						51.099214
					],
					[
						6.535444,
						51.099348
					],
					[
						6.536914,
						51.099439
					]
				]
			],
        "type": "Polygon"
      },
      "properties": {
        "name": "Energielandschaft_Juechen_Industriegebiet",
        "description": "Dachflächen PV Industriegebiet"
      },
      "id": "AzODE"
    }
  ]
}'''

import json
from typing import Tuple, List, Dict, Any, Optional
from shapely.geometry import shape, Polygon, LineString
from shapely.ops import transform
import pyproj
import os


class GeoJSONReader:
	"""Lädt eine GeoJSON-FeatureCollection (WGS84) und liefert Shapely-Objekte."""

	def __init__(self, geojson_str: str):
		self.geojson_str = geojson_str

	def _choose_utm_crs(self, lon: float, lat: float) -> pyproj.CRS:
		"""Bestimmt die UTM-Zone basierend auf Längen-/Breitengrad."""
		zone = int((lon + 180) / 6) + 1
		if lat >= 0:
			epsg = 32600 + zone
		else:
			epsg = 32700 + zone
		return pyproj.CRS.from_epsg(epsg)

	def load(self) -> Tuple[Polygon, Polygon, pyproj.Transformer, pyproj.Transformer]:
		"""Parst das eingebettete GeoJSON und gibt zurück:
		(poly_wgs84, poly_utm, transformer_to_utm, transformer_to_wgs84)
		"""
		obj = json.loads(self.geojson_str)
		feat = obj.get("features", [])[0]
		geom = shape(feat["geometry"])  # in WGS84 (lon/lat)

		centroid = geom.representative_point()
		lon, lat = centroid.x, centroid.y
		utm_crs = self._choose_utm_crs(lon, lat)

		transformer_to_utm = pyproj.Transformer.from_crs("EPSG:4326", utm_crs, always_xy=True)
		transformer_to_wgs84 = pyproj.Transformer.from_crs(utm_crs, "EPSG:4326", always_xy=True)

		proj_to_utm = lambda x, y: transformer_to_utm.transform(x, y)
		poly_utm = transform(proj_to_utm, geom)

		return geom, poly_utm, transformer_to_utm, transformer_to_wgs84


class RowSpacingInputHandler:
	"""Fragt den Benutzer nach dem Reihenabstand ab."""

	@staticmethod
	def get_row_spacing(default: float = 2.0, interactive: bool = True) -> float:
		"""Fragt Reihenabstand in Metern ab.
		
		Parameter:
		- default: Standardwert (default: 2.0 m)
		- interactive: Falls False, wird Default zurückgegeben
		
		Rückgabe:
		- Reihenabstand in Metern (float)
		"""
		if not interactive:
			return default

		while True:
			try:
				prompt = f"Bitte Reihenabstand in Metern eingeben [Default: {default}]: "
				val = input(prompt).strip()
				if not val:
					return default
				spacing = float(val)
				if spacing <= 0:
					print("Fehler: Reihenabstand muss > 0 sein. Bitte erneut versuchen.")
					continue
				return spacing
			except ValueError:
				print("Fehler: Ungültiger Input. Bitte eine Zahl eingeben.")
				continue


class EastWestLineGenerator:
	"""Generiert parallele Linien in Ost–West-Richtung (konstante Y, variable X)."""

	@staticmethod
	def generate_lines(polygon: Polygon, row_spacing: float) -> List[LineString]:
		"""Generiert parallele Ost–West-Linien mit dem angegebenen Abstand.
		
		Parameter:
		- polygon: Shapely-Polygon (vorzugsweise in metrischen Einheiten, z. B. UTM)
		- row_spacing: Abstand zwischen parallelen Linien in Metern
		
		Rückgabe:
		- Liste von LineString-Objekten
		"""
		if polygon is None or polygon.is_empty:
			return []

		try:
			r = float(row_spacing)
		except Exception:
			raise ValueError("row_spacing muss eine positive Zahl sein")
		
		if r <= 0:
			raise ValueError("row_spacing muss > 0 sein")

		minx, miny, maxx, maxy = polygon.bounds
		lines: List[LineString] = []

		# Generiere Ost–West-Linien (konstante Y, variable X)
		y = miny + r / 2.0
		while y <= maxy:
			lines.append(LineString([(minx - 1.0, y), (maxx + 1.0, y)]))
			y += r

		return lines

	@staticmethod
	def extract_line_segments(lines: List[LineString], polygon: Polygon) -> List[Dict[str, Any]]:
		"""Schneidet Linien mit dem Polygon und generiert Features mit Metadaten.
		
		Parameter:
		- lines: Liste von LineString-Objekten
		- polygon: Shapely-Polygon zur Schnittberechnung
		
		Rückgabe:
		- Liste von Feature-Dictionaries (mit Geometrie und Properties)
		"""
		features: List[Dict[str, Any]] = []
		row_idx = 0

		for line in lines:
			inter = line.intersection(polygon)

			if inter.is_empty:
				row_idx += 1
				continue

			# Behandle verschiedene Geometry-Typen
			segments: List[LineString] = []
			if inter.geom_type == 'LineString':
				segments = [inter]
			elif inter.geom_type == 'MultiLineString':
				segments = list(inter.geoms)
			else:
				row_idx += 1
				continue

			# Konvertiere jedes Segment in ein Feature
			for seg_idx, seg in enumerate(segments):
				if seg.length <= 0:
					continue

				coords = [[x, y] for x, y in seg.coords]

				features.append({
					"type": "Feature",
					"geometry": {
						"type": "LineString",
						"coordinates": coords
					},
					"properties": {
						"row": row_idx,
						"segment": seg_idx,
						"length_m": round(seg.length, 3),
						"orientation": "EW"
					}
				})

			row_idx += 1

		return features


class UTMTransformerApplier:
	"""Wendet UTM-zu-WGS84-Reprojizierung auf Features an."""

	@staticmethod
	def reproject_features(features: List[Dict[str, Any]], transformer: pyproj.Transformer) -> List[Dict[str, Any]]:
		"""Reprojiziert Feature-Koordinaten von UTM zu WGS84.
		
		Parameter:
		- features: Liste von Feature-Dictionaries (mit UTM-Koordinaten)
		- transformer: pyproj.Transformer (UTM zu WGS84)
		
		Rückgabe:
		- Liste von Feature-Dictionaries (mit WGS84-Koordinaten)
		"""
		reprojected = []

		for feature in features:
			coords_utm = feature["geometry"]["coordinates"]
			coords_wgs84 = []

			for x, y in coords_utm:
				lon, lat = transformer.transform(x, y)
				coords_wgs84.append([lon, lat])

			feature["geometry"]["coordinates"] = coords_wgs84
			reprojected.append(feature)

		return reprojected


class GeoJSONExporter:
	"""Exportiert GeoJSON-FeatureCollections in Dateien (RFC 7946 konform)."""

	@staticmethod
	def export(features: List[Dict[str, Any]], output_file: str) -> None:
		"""Exportiert Features als GeoJSON-Datei.
		
		Parameter:
		- features: Liste von Feature-Dictionaries
		- output_file: Ausgabedatei-Pfad
		"""
		if not isinstance(features, list):
			raise ValueError("features muss eine Liste sein")

		geojson = {
			"type": "FeatureCollection",
			"features": features
		}

		try:
			outdir = os.path.dirname(output_file)
			if outdir and not os.path.exists(outdir):
				os.makedirs(outdir, exist_ok=True)

			with open(output_file, 'w', encoding='utf-8') as f:
				json.dump(geojson, f, ensure_ascii=False, indent=2)

			print(f"  ✓ GeoJSON erfolgreich exportiert: {output_file}")

		except (IOError, OSError) as e:
			raise IOError(f"Fehler beim Schreiben von {output_file}: {e}")


def main(interactive: bool = True, output_dir: str = "outputs") -> Dict[str, Any]:
	"""Hauptfunktion: Orchestriert die Generierung von PV-Reihen für Dachflächen.
	
	Schritte:
	1. Einlesen der eingebetteten GeoJSON-Fläche
	2. Abfrage des Reihenabstands vom Benutzer
	3. Generierung von Ost–West-Linien
	4. Schnittberechnung mit Polygon
	5. Reprojizierung zu WGS84
	6. Export als GeoJSON
	
	Parameter:
	- interactive: Falls True, fragt die Funktion Benutzereingaben ab
	- output_dir: Verzeichnis für Ausgabedateien
	
	Rückgabe:
	- Dictionary mit Ergebnissen und Metadaten
	"""
	print("\n" + "="*70)
	print("Industriegebiet Dachflächen PV-Reihen Generierung")
	print("="*70 + "\n")

	# Schritt 1: Einlesen der GeoJSON
	print("[1/6] Einlesen der eingebetteten GeoJSON-Fläche...")
	try:
		reader = GeoJSONReader(EMBEDDED_GEOJSON)
		geom_wgs84, geom_utm, to_utm, to_wgs84 = reader.load()
		print(f"  ✓ Polygon geladen")
		print(f"    - Fläche (WGS84): {geom_wgs84.area:.6f} deg²")
		print(f"    - Fläche (UTM): {geom_utm.area:.2f} m²\n")
	except Exception as e:
		print(f"  ✗ Fehler beim Laden: {e}\n")
		raise

	# Schritt 2: Abfrage des Reihenabstands
	print("[2/6] Abfrage des Reihenabstands...")
	try:
		row_spacing = RowSpacingInputHandler.get_row_spacing(default=2.0, interactive=interactive)
		print(f"  ✓ Reihenabstand: {row_spacing} m\n")
	except Exception as e:
		print(f"  ✗ Fehler bei Eingabe: {e}\n")
		raise

	# Schritt 3: Generierung von Ost–West-Linien
	print("[3/6] Generierung von Ost–West-Linien...")
	try:
		lines = EastWestLineGenerator.generate_lines(geom_utm, row_spacing)
		print(f"  ✓ {len(lines)} Linien generiert\n")
	except Exception as e:
		print(f"  ✗ Fehler bei Liniengenerierung: {e}\n")
		raise

	# Schritt 4: Schnittberechnung und Feature-Generierung
	print("[4/6] Schnittberechnung und Feature-Generierung...")
	try:
		features_utm = EastWestLineGenerator.extract_line_segments(lines, geom_utm)
		n_features = len(features_utm)
		print(f"  ✓ {n_features} Features generiert\n")
	except Exception as e:
		print(f"  ✗ Fehler bei Feature-Generierung: {e}\n")
		raise

	# Schritt 5: Reprojizierung zu WGS84
	print("[5/6] Reprojizierung zu WGS84...")
	try:
		features_wgs84 = UTMTransformerApplier.reproject_features(features_utm, to_wgs84)
		print(f"  ✓ {len(features_wgs84)} Features reprojiziert\n")
	except Exception as e:
		print(f"  ✗ Fehler bei Reprojizierung: {e}\n")
		raise

	# Schritt 6: Export als GeoJSON
	print("[6/6] Export als GeoJSON...")
	try:
		if not os.path.exists(output_dir):
			os.makedirs(output_dir, exist_ok=True)

		output_filename = f"Projekt_04_Industriegebiet_Dachflaechen_PV_Reihen_{row_spacing}m.geojson"
		output_file = os.path.join(output_dir, output_filename)

		GeoJSONExporter.export(features_wgs84, output_file)
		print()
	except Exception as e:
		print(f"  ✗ Fehler beim Export: {e}\n")
		raise

	# Zusammenfassung
	print("="*70)
	print("ZUSAMMENFASSUNG")
	print("="*70)
	result = {
		"success": True,
		"metadata": {
			"area_wgs84_deg2": round(geom_wgs84.area, 6),
			"area_utm_m2": round(geom_utm.area, 2),
			"row_spacing_m": row_spacing,
			"n_lines_total": len(lines),
			"n_features": n_features,
			"output_file": output_file
		}
	}

	print(f"Fläche (WGS84): {geom_wgs84.area:.6f} deg²")
	print(f"Fläche (UTM): {geom_utm.area:.2f} m²")
	print(f"Reihenabstand: {row_spacing} m")
	print(f"Generierte Linien: {len(lines)}")
	print(f"Generierte Features: {n_features}")
	print(f"Output: {output_file}")
	print("="*70 + "\n")

	return result


if __name__ == "__main__":
	try:
		result = main(interactive=True, output_dir="outputs")
		if result.get("success"):
			print("✓ Verarbeitung erfolgreich abgeschlossen!")
		else:
			print("✗ Verarbeitung abgebrochen")
	except Exception as e:
		print(f"✗ Kritischer Fehler: {e}")
		import traceback
		traceback.print_exc()
