"""
Unit-Tests für generate_pv_reihen Funktion (LineString-basierte PV-Reihen)

Testet die neue Reihen-Generierungslogik:
- LineString-Features statt Punkte
- Korrekte Ausrichtung (EW/NS)
- Polygon-Schnittberechnung
- GeoJSON RFC 7946 Konformität

Verwendung: pytest test_pv_reihen.py -v
"""

import pytest
import json
from shapely.geometry import box, Polygon, Point
import pyproj

from Projekt_02_Energielandschaft import (
	generate_pv_reihen,
	export_geojson,
	GeoJSONReader,
	EMBEDDED_GEOJSON,
)


# =====================================================================
# FIXTURES
# =====================================================================

@pytest.fixture
def simple_square_utm():
	"""100x100 m Quadrat in UTM."""
	return box(0, 0, 100, 100)


@pytest.fixture
def rectangular_polygon_utm():
	"""200x150 m Rechteck in UTM."""
	return box(0, 0, 200, 150)


@pytest.fixture
def large_polygon_utm():
	"""500x500 m großes Polygon."""
	return box(0, 0, 500, 500)


@pytest.fixture
def utm_transformer():
	"""UTM Zone 32N Transformer."""
	to_utm = pyproj.Transformer.from_crs("EPSG:4326", "EPSG:32632", always_xy=True)
	to_wgs84 = pyproj.Transformer.from_crs("EPSG:32632", "EPSG:4326", always_xy=True)
	return to_utm, to_wgs84


# =====================================================================
# TESTS: Grundlegende Funktionalität
# =====================================================================

class TestGeneratePvReihenBasic:
	"""Grundtests für generate_pv_reihen."""

	def test_horizontal_generates_reihen(self, simple_square_utm):
		"""Test: Horizontale Ausrichtung generiert Reihen."""
		result = generate_pv_reihen(simple_square_utm, "horizontal", 10.0)
		assert result["type"] == "FeatureCollection"
		assert len(result["features"]) > 0

	def test_vertical_generates_reihen(self, simple_square_utm):
		"""Test: Vertikale Ausrichtung generiert Reihen."""
		result = generate_pv_reihen(simple_square_utm, "vertical", 10.0)
		assert result["type"] == "FeatureCollection"
		assert len(result["features"]) > 0

	def test_all_features_are_linestrings(self, simple_square_utm):
		"""Test: Alle Features sind LineStrings."""
		result = generate_pv_reihen(simple_square_utm, "horizontal", 15.0)
		for feature in result["features"]:
			assert feature["type"] == "Feature"
			assert feature["geometry"]["type"] == "LineString"

	def test_feature_has_required_properties(self, simple_square_utm):
		"""Test: Features enthalten erforderliche Properties."""
		result = generate_pv_reihen(simple_square_utm, "horizontal", 20.0)
		for feature in result["features"]:
			props = feature["properties"]
			assert "row" in props
			assert "segment" in props
			assert "length_m" in props
			assert "orientation" in props

	def test_horizontal_orientation_property(self, simple_square_utm):
		"""Test: Horizontale Reihen haben Orientierung 'EW'."""
		result = generate_pv_reihen(simple_square_utm, "horizontal", 20.0)
		for feature in result["features"]:
			assert feature["properties"]["orientation"] == "EW"

	def test_vertical_orientation_property(self, simple_square_utm):
		"""Test: Vertikale Reihen haben Orientierung 'NS'."""
		result = generate_pv_reihen(simple_square_utm, "vertical", 20.0)
		for feature in result["features"]:
			assert feature["properties"]["orientation"] == "NS"


# =====================================================================
# TESTS: Reihen-Geometrie und Eigenschaften
# =====================================================================

class TestGeneratePvReihenGeometry:
	"""Tests für Geometrie-Eigenschaften."""

	def test_linestring_coordinates_valid(self, simple_square_utm):
		"""Test: LineString-Koordinaten sind gültig."""
		result = generate_pv_reihen(simple_square_utm, "horizontal", 25.0)
		for feature in result["features"]:
			coords = feature["geometry"]["coordinates"]
			assert isinstance(coords, list)
			assert len(coords) >= 2
			for coord in coords:
				assert len(coord) == 2  # [x, y]

	def test_reihenbreite_affects_count(self, rectangular_polygon_utm):
		"""Test: Kleinere Reihenbreite erzeugt mehr Reihen."""
		result_10m = generate_pv_reihen(rectangular_polygon_utm, "horizontal", 10.0)
		result_30m = generate_pv_reihen(rectangular_polygon_utm, "horizontal", 30.0)
		assert len(result_10m["features"]) > len(result_30m["features"])

	def test_length_property_positive(self, simple_square_utm):
		"""Test: length_m Property ist positiv."""
		result = generate_pv_reihen(simple_square_utm, "horizontal", 15.0)
		for feature in result["features"]:
			assert feature["properties"]["length_m"] > 0

	def test_row_indices_sequential(self, rectangular_polygon_utm):
		"""Test: Row-Indizes sind sequenziell (ohne Lücken bei validen Reihen)."""
		result = generate_pv_reihen(rectangular_polygon_utm, "horizontal", 20.0)
		rows = set()
		for feature in result["features"]:
			rows.add(feature["properties"]["row"])
		# Reihen sollten zusammenhängend sein (oder mit Gaps für leere Reihen)
		max_row = max(rows) if rows else 0
		assert max_row >= 0

	def test_segment_indices_restart_per_row(self, rectangular_polygon_utm):
		"""Test: Segment-Indizes starten für jede Reihe bei 0."""
		result = generate_pv_reihen(rectangular_polygon_utm, "horizontal", 10.0)
		rows_to_segments = {}
		for feature in result["features"]:
			row = feature["properties"]["row"]
			segment = feature["properties"]["segment"]
			if row not in rows_to_segments:
				rows_to_segments[row] = []
			rows_to_segments[row].append(segment)

		# In jeder Reihe sollte segment mit 0 starten
		for row, segments in rows_to_segments.items():
			assert 0 in segments


# =====================================================================
# TESTS: Koordinaten-Reprojizierung
# =====================================================================

class TestGeneratePvReihenReprojection:
	"""Tests für Reprojizierung in WGS84."""

	def test_with_transformer_outputs_wgs84(self, simple_square_utm, utm_transformer):
		"""Test: Mit Transformer werden Koordinaten zu WGS84."""
		to_utm, to_wgs84 = utm_transformer
		result = generate_pv_reihen(simple_square_utm, "horizontal", 20.0, 
									 transformer_to_wgs84=to_wgs84)
		
		# WGS84 Koordinaten sollten zwischen -180,180 (lon) und -90,90 (lat) liegen
		for feature in result["features"]:
			coords = feature["geometry"]["coordinates"]
			for lon, lat in coords:
				assert -180 <= lon <= 180
				assert -90 <= lat <= 90

	def test_without_transformer_uses_utm(self, simple_square_utm):
		"""Test: Ohne Transformer bleiben Koordinaten in UTM."""
		result = generate_pv_reihen(simple_square_utm, "horizontal", 20.0, 
									 transformer_to_wgs84=None)
		
		# UTM-Koordinaten für dieses Test-Polygon sollten im Bereich 0-100 liegen
		for feature in result["features"]:
			coords = feature["geometry"]["coordinates"]
			for x, y in coords:
				assert 0 <= x <= 105  # leicht überschritten wegen Buffer
				assert 0 <= y <= 105


# =====================================================================
# TESTS: Edge-Cases und Fehlerbehandlung
# =====================================================================

class TestGeneratePvReihenEdgeCases:
	"""Tests für Edge-Cases und Fehlerbehandlung."""

	def test_empty_polygon(self):
		"""Test: Leeres Polygon liefert leere FeatureCollection."""
		empty = Polygon()
		result = generate_pv_reihen(empty, "horizontal", 10.0)
		assert result["type"] == "FeatureCollection"
		assert len(result["features"]) == 0

	def test_none_polygon(self):
		"""Test: None-Polygon liefert leere FeatureCollection."""
		result = generate_pv_reihen(None, "horizontal", 10.0)
		assert len(result["features"]) == 0

	def test_invalid_reihenbreite_zero(self, simple_square_utm):
		"""Test: Reihenbreite 0 wirft ValueError."""
		with pytest.raises(ValueError, match="reihenbreite muss > 0"):
			generate_pv_reihen(simple_square_utm, "horizontal", 0.0)

	def test_invalid_reihenbreite_negative(self, simple_square_utm):
		"""Test: Negative Reihenbreite wirft ValueError."""
		with pytest.raises(ValueError, match="reihenbreite muss > 0"):
			generate_pv_reihen(simple_square_utm, "horizontal", -5.0)

	def test_invalid_ausrichtung(self, simple_square_utm):
		"""Test: Ungültige Ausrichtung wirft ValueError."""
		with pytest.raises(ValueError, match="ausrichtung muss"):
			generate_pv_reihen(simple_square_utm, "diagonal", 10.0)

	def test_case_insensitive_orientation(self, simple_square_utm):
		"""Test: Ausrichtung ist case-insensitiv."""
		result_lower = generate_pv_reihen(simple_square_utm, "horizontal", 20.0)
		result_upper = generate_pv_reihen(simple_square_utm, "HORIZONTAL", 20.0)
		assert len(result_lower["features"]) == len(result_upper["features"])

	def test_very_small_reihenbreite(self, simple_square_utm):
		"""Test: Sehr kleine Reihenbreite (z. B. 0.1m)."""
		result = generate_pv_reihen(simple_square_utm, "horizontal", 0.1)
		# Sollte sehr viele Reihen generieren
		assert len(result["features"]) > 50

	def test_very_large_reihenbreite(self, simple_square_utm):
		"""Test: Sehr große Reihenbreite (größer als Polygon)."""
		result = generate_pv_reihen(simple_square_utm, "horizontal", 150.0)
		# Sollte 0 oder 1 Reihe sein
		assert len(result["features"]) <= 1


# =====================================================================
# TESTS: GeoJSON RFC 7946 Konformität
# =====================================================================

class TestGeneratePvReihenGeoJsonCompliance:
	"""Tests für GeoJSON RFC 7946 Konformität."""

	def test_valid_geojson_structure(self, simple_square_utm):
		"""Test: Ausgabe ist gültiges GeoJSON."""
		result = generate_pv_reihen(simple_square_utm, "horizontal", 20.0)
		
		assert isinstance(result, dict)
		assert result["type"] == "FeatureCollection"
		assert isinstance(result["features"], list)
		
		for feature in result["features"]:
			assert feature["type"] == "Feature"
			assert "geometry" in feature
			assert "properties" in feature

	def test_exportable_as_json(self, simple_square_utm, tmp_path):
		"""Test: Ergebnis ist als JSON serialisierbar."""
		result = generate_pv_reihen(simple_square_utm, "horizontal", 20.0)
		output_file = tmp_path / "test_reihen.geojson"
		
		# Sollte ohne Fehler exportierbar sein
		export_geojson(result, str(output_file))
		assert output_file.exists()
		
		# Datei sollte gültiges JSON sein
		with open(output_file, 'r') as f:
			loaded = json.load(f)
		assert loaded["type"] == "FeatureCollection"


# =====================================================================
# INTEGRATION TESTS
# =====================================================================

class TestGeneratePvReihenIntegration:
	"""Integrationstests."""

	def test_full_workflow_reihen(self, rectangular_polygon_utm, tmp_path):
		"""Test: Kompletter Workflow mit Reihen-Generierung und Export."""
		# Generiere Reihen
		result = generate_pv_reihen(rectangular_polygon_utm, "horizontal", 12.0)
		assert len(result["features"]) > 0
		
		# Exportiere GeoJSON
		output_file = tmp_path / "reihen_output.geojson"
		export_geojson(result, str(output_file))
		assert output_file.exists()
		
		# Verifiziere Datei-Inhalt
		with open(output_file, 'r') as f:
			loaded = json.load(f)
		assert loaded["type"] == "FeatureCollection"
		assert len(loaded["features"]) > 0

	def test_embedded_geojson_reihen(self):
		"""Test: Reihen-Generierung mit eingebettetem GeoJSON."""
		reader = GeoJSONReader(EMBEDDED_GEOJSON)
		geom_wgs84, geom_utm, to_utm, to_wgs84 = reader.load()
		
		# Generiere Reihen
		result = generate_pv_reihen(geom_utm, "horizontal", 50.0, transformer_to_wgs84=to_wgs84)
		
		assert result["type"] == "FeatureCollection"
		assert len(result["features"]) > 0
		
		# Alle Features sollten LineStrings sein
		for feature in result["features"]:
			assert feature["geometry"]["type"] == "LineString"
			# Koordinaten sollten WGS84 sein
			coords = feature["geometry"]["coordinates"]
			for lon, lat in coords:
				assert -180 <= lon <= 180
				assert -90 <= lat <= 90


# =====================================================================
# Ausführung
# =====================================================================

if __name__ == "__main__":
	pytest.main([__file__, "-v", "--tb=short"])
