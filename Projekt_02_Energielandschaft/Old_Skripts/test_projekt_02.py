"""
Unit-Tests für Projekt 02 - Energielandschaft

Testet alle Berechnungsfunktionen:
- Berechnung Randstreifen (Wendestreifen)
- Berechnung Fahrspurbreite
- Ausrichtung und Reihenparameter
- Polygondifferenzierung mittels Buffer
- Punktgenerierung

Verwendung: pytest test_projekt_02.py -v
"""

import pytest
import math
from shapely.geometry import Polygon, box, Point
from shapely.ops import transform
import pyproj

# Import der zu testenden Funktionen
from Projekt_02_Energielandschaft import (
	TractorParameters,
	get_reihenparameter,
	compute_restflaeche,
	generate_pv_points,
	export_geojson,
	GeoJSONReader,
	EMBEDDED_GEOJSON,
)


# =====================================================================
# FIXTURES: Synthetische Test-Polygone
# =====================================================================

@pytest.fixture
def simple_square_utm():
	"""Einfaches quadratisches Testpolygon (100m x 100m) in UTM-Koordinaten."""
	return box(0, 0, 100, 100)


@pytest.fixture
def rectangular_polygon_utm():
	"""Rechteckiges Testpolygon (200m x 150m) in UTM."""
	return box(0, 0, 200, 150)


@pytest.fixture
def circular_polygon_utm():
	"""Kreisförmiges Testpolygon (Radius ~50m) in UTM."""
	center = Point(100, 100)
	return center.buffer(50)


@pytest.fixture
def large_polygon_utm():
	"""Großes Testpolygon (500m x 500m) für realistische Tests."""
	return box(0, 0, 500, 500)


@pytest.fixture
def small_polygon_utm():
	"""Kleines Testpolygon (10m x 10m) zur Prüfung von Edge-Cases."""
	return box(0, 0, 10, 10)


@pytest.fixture
def utm_transformer():
	"""UTM-Transformer (Zone 32N) für Test-Reprojektionen."""
	to_utm = pyproj.Transformer.from_crs("EPSG:4326", "EPSG:32632", always_xy=True)
	to_wgs84 = pyproj.Transformer.from_crs("EPSG:32632", "EPSG:4326", always_xy=True)
	return to_utm, to_wgs84


# =====================================================================
# TESTS: Traktor-Parameter Berechnung
# =====================================================================

class TestTractorParameters:
	"""Tests für die TractorParameters-Klasse."""

	def test_wendestreifen_width_basic(self):
		"""Test: Wendestreifen-Breite mit Standard-Werten."""
		tractor = TractorParameters(width_m=2.5, length_m=3.0, turn_radius_m=4.0)
		# Formel: length + 2*radius + 1 = 3.0 + 2*4.0 + 1.0 = 12.0
		expected = 12.0
		assert tractor.compute_wendestreifen_width() == expected

	def test_wendestreifen_width_zero_values(self):
		"""Test: Wendestreifen mit sehr kleinen Werten."""
		tractor = TractorParameters(width_m=0.5, length_m=1.0, turn_radius_m=1.0)
		# 1.0 + 2*1.0 + 1.0 = 4.0
		assert tractor.compute_wendestreifen_width() == 4.0

	def test_wendestreifen_width_large_radius(self):
		"""Test: Wendestreifen mit großem Wenderadius."""
		tractor = TractorParameters(width_m=3.0, length_m=5.0, turn_radius_m=10.0)
		# 5.0 + 2*10.0 + 1.0 = 26.0
		assert tractor.compute_wendestreifen_width() == 26.0

	def test_fahrspur_width_basic(self):
		"""Test: Fahrspur-Breite mit Standard-Werten."""
		tractor = TractorParameters(width_m=2.5, length_m=3.0, turn_radius_m=4.0)
		# Formel: width + 2.0 = 2.5 + 2.0 = 4.5
		expected = 4.5
		assert tractor.compute_fahrspur_width() == expected

	def test_fahrspur_width_various_widths(self):
		"""Test: Fahrspur-Breite mit verschiedenen Traktorbreiten."""
		for width in [1.5, 2.0, 2.5, 3.0, 3.5]:
			tractor = TractorParameters(width_m=width, length_m=3.0, turn_radius_m=4.0)
			assert tractor.compute_fahrspur_width() == width + 2.0

	def test_from_input_defaults(self):
		"""Test: TractorParameters.from_input mit Defaults (non-interactive)."""
		tractor = TractorParameters.from_input(interactive=False, defaults=(2.5, 3.0, 4.0))
		assert tractor.width_m == 2.5
		assert tractor.length_m == 3.0
		assert tractor.turn_radius_m == 4.0

	def test_from_input_custom_defaults(self):
		"""Test: TractorParameters.from_input mit benutzerdefinierten Defaults."""
		tractor = TractorParameters.from_input(interactive=False, defaults=(3.0, 4.0, 5.0))
		assert tractor.width_m == 3.0
		assert tractor.length_m == 4.0
		assert tractor.turn_radius_m == 5.0


# =====================================================================
# TESTS: Reihenparameter und Ausrichtung
# =====================================================================

class TestReihenparameter:
	"""Tests für die get_reihenparameter-Funktion."""

	def test_horizontal_orientation(self):
		"""Test: Horizontale Ausrichtung."""
		result = get_reihenparameter("horizontal")
		assert result["orientation"] == "EW"
		assert result["reihenbreite_m"] == 9.2

	def test_vertical_orientation(self):
		"""Test: Vertikale Ausrichtung."""
		result = get_reihenparameter("vertical")
		assert result["orientation"] == "NS"
		assert result["reihenbreite_m"] == 0.5

	def test_case_insensitive_horizontal(self):
		"""Test: Großschreibung bei horizontaler Ausrichtung."""
		result = get_reihenparameter("HORIZONTAL")
		assert result["orientation"] == "EW"
		assert result["reihenbreite_m"] == 9.2

	def test_case_insensitive_vertical(self):
		"""Test: Großschreibung bei vertikaler Ausrichtung."""
		result = get_reihenparameter("VERTICAL")
		assert result["orientation"] == "NS"
		assert result["reihenbreite_m"] == 0.5

	def test_invalid_orientation(self):
		"""Test: Ungültige Ausrichtung wirft ValueError."""
		with pytest.raises(ValueError, match="Ungültige Ausrichtung"):
			get_reihenparameter("diagonal")

	def test_none_orientation(self):
		"""Test: None als Ausrichtung wirft ValueError."""
		with pytest.raises(ValueError, match="Ausrichtung darf nicht None sein"):
			get_reihenparameter(None)

	def test_whitespace_handling(self):
		"""Test: Whitespace wird korrekt behandelt."""
		result = get_reihenparameter("  horizontal  ")
		assert result["orientation"] == "EW"


# =====================================================================
# TESTS: Polygondifferenzierung (Buffer)
# =====================================================================

class TestComputeRestflaeche:
	"""Tests für die compute_restflaeche-Funktion."""

	def test_zero_buffer(self, simple_square_utm):
		"""Test: Buffer von 0m ändert Polygon nicht."""
		result = compute_restflaeche(simple_square_utm, 0.0)
		assert result.equals(simple_square_utm)

	def test_positive_buffer_reduces_area(self, simple_square_utm):
		"""Test: Positiver Buffer reduziert Fläche."""
		original_area = simple_square_utm.area
		result = compute_restflaeche(simple_square_utm, 10.0)
		assert result.area < original_area
		# 100x100 - buffer(10) sollte etwa 80x80 = 6400 sein
		assert result.area < 6500

	def test_exact_buffer_calculation(self, simple_square_utm):
		"""Test: Genaue Buffer-Berechnung für einfaches Quadrat."""
		# 100x100 Quadrat mit 10m Buffer sollte ~(80x80) = 6400 sein
		result = compute_restflaeche(simple_square_utm, 10.0)
		# Erlauben wir ±100 m² für Rund- und Shape-Effekte
		assert 6300 < result.area < 6500

	def test_buffer_larger_than_polygon(self, small_polygon_utm):
		"""Test: Buffer größer als Polygon führt zu leerer Geometrie."""
		result = compute_restflaeche(small_polygon_utm, 20.0)
		assert result.is_empty

	def test_buffer_half_dimension(self, simple_square_utm):
		"""Test: Buffer von 50m bei 100x100 Quadrat (halbe Dimension)."""
		result = compute_restflaeche(simple_square_utm, 50.0)
		assert result.is_empty

	def test_invalid_polygon(self):
		"""Test: None als Polygon wirft ValueError."""
		with pytest.raises(ValueError, match="poly_utm darf nicht None sein"):
			compute_restflaeche(None, 10.0)

	def test_invalid_buffer_negative(self, simple_square_utm):
		"""Test: Negativer Buffer wirft ValueError."""
		with pytest.raises(ValueError, match="nicht-negative"):
			compute_restflaeche(simple_square_utm, -5.0)

	def test_invalid_buffer_non_numeric(self, simple_square_utm):
		"""Test: Non-numerischer Buffer wirft ValueError."""
		with pytest.raises(ValueError, match="numerisch"):
			compute_restflaeche(simple_square_utm, "abc")

	def test_buffer_on_large_polygon(self, large_polygon_utm):
		"""Test: Buffer auf großem Polygon (500x500)."""
		original_area = large_polygon_utm.area
		result = compute_restflaeche(large_polygon_utm, 50.0)
		# Erwartete Fläche: (500-100)² = 400² = 160000
		assert not result.is_empty
		assert 155000 < result.area < 165000

	def test_buffer_realistic_margin(self, rectangular_polygon_utm):
		"""Test: Realistischer Randstreifen (18m auf 200x150 Polygon)."""
		result = compute_restflaeche(rectangular_polygon_utm, 18.0)
		# Restfläche sollte etwa (200-36) x (150-36) = 164 x 114 ≈ 18696
		assert not result.is_empty
		assert result.area > 10000


# =====================================================================
# TESTS: Punktgenerierung
# =====================================================================

class TestGeneratePvPoints:
	"""Tests für die generate_pv_points-Funktion."""

	def test_empty_polygon(self):
		"""Test: Leeres Polygon liefert keine Punkte."""
		empty = Polygon()
		result = generate_pv_points(empty, "horizontal", 10.0)
		assert result["type"] == "FeatureCollection"
		assert len(result["features"]) == 0

	def test_none_polygon(self):
		"""Test: None als Polygon liefert leere FeatureCollection."""
		result = generate_pv_points(None, "horizontal", 10.0)
		assert result["type"] == "FeatureCollection"
		assert len(result["features"]) == 0

	def test_horizontal_orientation_generates_points(self, simple_square_utm):
		"""Test: Horizontale Ausrichtung generiert Punkte."""
		result = generate_pv_points(simple_square_utm, "horizontal", 20.0, module_spacing_m=10.0)
		assert result["type"] == "FeatureCollection"
		assert len(result["features"]) > 0

	def test_vertical_orientation_generates_points(self, simple_square_utm):
		"""Test: Vertikale Ausrichtung generiert Punkte."""
		result = generate_pv_points(simple_square_utm, "vertical", 20.0, module_spacing_m=10.0)
		assert result["type"] == "FeatureCollection"
		assert len(result["features"]) > 0

	def test_point_structure(self, simple_square_utm):
		"""Test: Punkte haben korrekte GeoJSON-Struktur."""
		result = generate_pv_points(simple_square_utm, "horizontal", 20.0, module_spacing_m=10.0)
		for feature in result["features"]:
			assert feature["type"] == "Feature"
			assert feature["geometry"]["type"] == "Point"
			assert "coordinates" in feature["geometry"]
			assert "properties" in feature
			assert "row" in feature["properties"]

	def test_points_within_polygon(self, simple_square_utm):
		"""Test: Alle generierten Punkte liegen im Polygon."""
		result = generate_pv_points(simple_square_utm, "horizontal", 20.0, module_spacing_m=10.0)
		# Mit Transformer wird zu WGS84 konvertiert; wir testen ohne
		result_utm = generate_pv_points(simple_square_utm, "horizontal", 20.0, 
										module_spacing_m=10.0, transformer_to_wgs84=None)
		for feature in result_utm["features"]:
			coords = feature["geometry"]["coordinates"]
			pt = Point(coords[0], coords[1])
			assert pt.within(simple_square_utm) or pt.touches(simple_square_utm)

	def test_different_row_spacings(self, rectangular_polygon_utm):
		"""Test: Unterschiedliche Reihenabstände produzieren unterschiedliche Punktanzahl."""
		result_10m = generate_pv_points(rectangular_polygon_utm, "horizontal", 10.0, module_spacing_m=5.0)
		result_20m = generate_pv_points(rectangular_polygon_utm, "horizontal", 20.0, module_spacing_m=5.0)
		# Größerer Reihenabstand sollte weniger Punkte liefern
		assert len(result_10m["features"]) > len(result_20m["features"])

	def test_invalid_orientation(self, simple_square_utm):
		"""Test: Ungültige Ausrichtung wirft ValueError."""
		with pytest.raises(ValueError, match="ausrichtung muss"):
			generate_pv_points(simple_square_utm, "diagonal", 10.0)

	def test_invalid_reihenbreite_zero(self, simple_square_utm):
		"""Test: Reihenbreite von 0 wirft ValueError."""
		with pytest.raises(ValueError, match="reihenbreite muss > 0"):
			generate_pv_points(simple_square_utm, "horizontal", 0.0)

	def test_invalid_reihenbreite_negative(self, simple_square_utm):
		"""Test: Negative Reihenbreite wirft ValueError."""
		with pytest.raises(ValueError, match="reihenbreite muss > 0"):
			generate_pv_points(simple_square_utm, "horizontal", -5.0)

	def test_invalid_module_spacing_zero(self, simple_square_utm):
		"""Test: Modul-Abstand von 0 wirft ValueError."""
		with pytest.raises(ValueError, match="module_spacing_m muss > 0"):
			generate_pv_points(simple_square_utm, "horizontal", 10.0, module_spacing_m=0.0)

	def test_large_polygon_point_count(self, large_polygon_utm):
		"""Test: Großes Polygon produziert viele Punkte."""
		result = generate_pv_points(large_polygon_utm, "horizontal", 10.0, module_spacing_m=5.0)
		# 500x500 mit 10m Reihenabstand sollte ~50 Reihen haben
		# Mit 5m Modul-Abstand ~100 Punkte pro Reihe = ~5000 Punkte (grob)
		assert len(result["features"]) > 1000

	def test_row_property_assigned(self, simple_square_utm):
		"""Test: Jeder Punkt hat eine row-Eigenschaft."""
		result = generate_pv_points(simple_square_utm, "horizontal", 20.0, module_spacing_m=10.0)
		for feature in result["features"]:
			assert "row" in feature["properties"]
			assert isinstance(feature["properties"]["row"], int)


# =====================================================================
# TESTS: GeoJSON-Export
# =====================================================================

class TestExportGeojson:
	"""Tests für die export_geojson-Funktion."""

	def test_export_valid_geojson(self, tmp_path):
		"""Test: Export einer gültigen GeoJSON FeatureCollection."""
		geojson = {
			"type": "FeatureCollection",
			"features": [
				{
					"type": "Feature",
					"geometry": {"type": "Point", "coordinates": [1.0, 2.0]},
					"properties": {"id": 1}
				}
			]
		}
		output_file = tmp_path / "test.geojson"
		export_geojson(geojson, str(output_file))
		assert output_file.exists()

		# Verifiziere Datei-Inhalt
		import json
		with open(output_file, 'r', encoding='utf-8') as f:
			loaded = json.load(f)
		assert loaded["type"] == "FeatureCollection"
		assert len(loaded["features"]) == 1

	def test_export_creates_directory(self, tmp_path):
		"""Test: Export erstellt Parent-Verzeichnis falls nötig."""
		output_file = tmp_path / "subdir" / "test.geojson"
		geojson = {"type": "FeatureCollection", "features": []}
		export_geojson(geojson, str(output_file))
		assert output_file.exists()

	def test_export_invalid_type(self):
		"""Test: Export mit ungültigem Typ wirft ValueError."""
		invalid = {"type": "Point", "features": []}
		with pytest.raises(ValueError, match="type muss 'FeatureCollection' sein"):
			export_geojson(invalid, "dummy.geojson")

	def test_export_missing_features(self):
		"""Test: Export ohne 'features'-Feld wirft ValueError."""
		invalid = {"type": "FeatureCollection"}
		with pytest.raises(ValueError, match="'features'"):
			export_geojson(invalid, "dummy.geojson")

	def test_export_non_dict_input(self):
		"""Test: Non-Dictionary-Input wirft ValueError."""
		with pytest.raises(ValueError, match="Dictionary sein"):
			export_geojson([1, 2, 3], "dummy.geojson")

	def test_export_empty_filename(self):
		"""Test: Leerer Dateiname wirft ValueError."""
		valid_geojson = {"type": "FeatureCollection", "features": []}
		with pytest.raises(ValueError, match="nicht-leerer String"):
			export_geojson(valid_geojson, "")

	def test_export_multiple_features(self, tmp_path):
		"""Test: Export mehrerer Features."""
		geojson = {
			"type": "FeatureCollection",
			"features": [
				{"type": "Feature", "geometry": {"type": "Point", "coordinates": [0, 0]}, "properties": {}},
				{"type": "Feature", "geometry": {"type": "Point", "coordinates": [1, 1]}, "properties": {}},
				{"type": "Feature", "geometry": {"type": "Point", "coordinates": [2, 2]}, "properties": {}},
			]
		}
		output_file = tmp_path / "multi.geojson"
		export_geojson(geojson, str(output_file))
		
		import json
		with open(output_file, 'r') as f:
			loaded = json.load(f)
		assert len(loaded["features"]) == 3


# =====================================================================
# INTEGRATION TESTS
# =====================================================================

class TestIntegration:
	"""Integrationstests für den kompletten Workflow."""

	def test_full_workflow_simple_polygon(self, simple_square_utm, tmp_path):
		"""Test: Kompletter Workflow mit einfachem Polygon."""
		# 1. Traktorparameter
		tractor = TractorParameters(2.5, 3.0, 4.0)
		wendestreifen = tractor.compute_wendestreifen_width()
		fahrspur = tractor.compute_fahrspur_width()
		margin = max(wendestreifen, fahrspur)

		# 2. Restfläche
		rest_poly = compute_restflaeche(simple_square_utm, margin)
		assert not rest_poly.is_empty

		# 3. Reihenparameter
		reihen_info = get_reihenparameter("horizontal")
		reihenbreite = reihen_info["reihenbreite_m"]

		# 4. PV-Punkte generieren
		geojson_points = generate_pv_points(rest_poly, "horizontal", reihenbreite, 1.0)
		assert len(geojson_points["features"]) > 0

		# 5. Export
		output_file = tmp_path / "workflow_test.geojson"
		export_geojson(geojson_points, str(output_file))
		assert output_file.exists()

	def test_full_workflow_large_polygon(self, large_polygon_utm, tmp_path):
		"""Test: Kompletter Workflow mit großem Polygon."""
		tractor = TractorParameters(3.0, 4.0, 5.0)
		wendestreifen = tractor.compute_wendestreifen_width()
		fahrspur = tractor.compute_fahrspur_width()
		margin = max(wendestreifen, fahrspur)

		rest_poly = compute_restflaeche(large_polygon_utm, margin)
		assert rest_poly.area > 100000  # sollte großer sein

		reihen_info = get_reihenparameter("vertical")
		reihenbreite = reihen_info["reihenbreite_m"]

		geojson_points = generate_pv_points(rest_poly, "vertical", reihenbreite, 2.0)
		assert len(geojson_points["features"]) > 100

		output_file = tmp_path / "large_workflow_test.geojson"
		export_geojson(geojson_points, str(output_file))
		assert output_file.exists()

	def test_geojson_reader_embedded(self):
		"""Test: GeoJSONReader mit eingebettetem GeoJSON."""
		reader = GeoJSONReader(EMBEDDED_GEOJSON)
		geom_wgs84, geom_utm, to_utm, to_wgs84 = reader.load()
		
		assert geom_wgs84 is not None
		assert geom_utm is not None
		assert geom_wgs84.area > 0
		assert geom_utm.area > 0
		# UTM sollte deutlich größer sein (Meter vs. Grad)
		assert geom_utm.area > geom_wgs84.area


# =====================================================================
# Ausführung
# =====================================================================

if __name__ == "__main__":
	pytest.main([__file__, "-v", "--tb=short"])
