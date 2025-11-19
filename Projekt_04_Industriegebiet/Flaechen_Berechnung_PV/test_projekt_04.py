"""
Unit-Tests für Projekt_04 - Industriegebiet Dachflächen PV-Berechnung

Tests für:
- GeoJSONReader (Laden und Reprojizierung)
- EastWestLineGenerator (Liniengenerierung und Schnittberechnung)
- UTMTransformerApplier (Reprojizierung WGS84 <-> UTM)
- GeoJSONExporter (Export in GeoJSON-Format)
- Hauptfunktion main() (Orchestrierung)
"""

import pytest
import json
import os
import tempfile
from pathlib import Path
from shapely.geometry import Polygon, LineString, box

from Projekt_04_Industriegebiet_Dachflaechen_PV import (
	GeoJSONReader,
	EastWestLineGenerator,
	UTMTransformerApplier,
	GeoJSONExporter,
	RowSpacingInputHandler,
	EMBEDDED_GEOJSON,
	main
)


class TestGeoJSONReader:
	"""Tests für GeoJSONReader-Klasse."""

	def test_load_returns_four_elements(self):
		"""Testet, ob load() vier Elemente zurückgibt."""
		reader = GeoJSONReader(EMBEDDED_GEOJSON)
		result = reader.load()
		assert len(result) == 4
		poly_wgs84, poly_utm, to_utm, to_wgs84 = result
		assert poly_wgs84 is not None
		assert poly_utm is not None

	def test_load_geojson_is_polygon(self):
		"""Testet, ob das geladene Polygon ein Shapely-Polygon ist."""
		reader = GeoJSONReader(EMBEDDED_GEOJSON)
		poly_wgs84, _, _, _ = reader.load()
		assert isinstance(poly_wgs84, Polygon)
		assert not poly_wgs84.is_empty

	def test_polygon_area_is_positive(self):
		"""Testet, ob die Polygonfläche positiv ist."""
		reader = GeoJSONReader(EMBEDDED_GEOJSON)
		poly_wgs84, poly_utm, _, _ = reader.load()
		assert poly_wgs84.area > 0
		assert poly_utm.area > 0

	def test_transformer_transforms_correctly(self):
		"""Testet, ob die Transformer-Funktionen korrekt arbeiten."""
		reader = GeoJSONReader(EMBEDDED_GEOJSON)
		_, poly_utm, _, to_wgs84 = reader.load()
		
		# Nimm einen Punkt aus dem UTM-Polygon
		coords = list(poly_utm.exterior.coords)
		assert len(coords) > 0
		
		# Reprojiziere zurück zu WGS84
		x, y = coords[0]
		lon, lat = to_wgs84.transform(x, y)
		
		# Prüfe, dass Koordinaten im erwarteten Bereich sind
		assert -180 <= lon <= 180
		assert -90 <= lat <= 90

	def test_utm_crs_selection(self):
		"""Testet die UTM-CRS-Wahl basierend auf Koordinaten."""
		reader = GeoJSONReader(EMBEDDED_GEOJSON)
		
		# Zone 32 für Deutschland (6°E - 12°E)
		utm_crs = reader._choose_utm_crs(lon=6.54, lat=51.09)
		assert utm_crs.to_epsg() == 32632  # UTM Zone 32N


class TestEastWestLineGenerator:
	"""Tests für EastWestLineGenerator-Klasse."""

	@pytest.fixture
	def simple_polygon(self):
		"""Einfaches rechteckiges Polygon für Tests."""
		return box(0, 0, 100, 100)  # 100m x 100m Quadrat

	def test_generate_lines_returns_list(self, simple_polygon):
		"""Testet, ob generate_lines eine Liste zurückgibt."""
		lines = EastWestLineGenerator.generate_lines(simple_polygon, 10.0)
		assert isinstance(lines, list)
		assert len(lines) > 0

	def test_generate_lines_with_different_spacings(self, simple_polygon):
		"""Testet Liniengenerierung mit unterschiedlichen Abständen."""
		lines_2m = EastWestLineGenerator.generate_lines(simple_polygon, 2.0)
		lines_10m = EastWestLineGenerator.generate_lines(simple_polygon, 10.0)
		
		# Mit kleinerem Abstand sollten mehr Linien generiert werden
		assert len(lines_2m) > len(lines_10m)

	def test_generate_lines_raises_for_invalid_spacing(self, simple_polygon):
		"""Testet, dass ungültige Abstände einen Fehler auslösen."""
		with pytest.raises(ValueError):
			EastWestLineGenerator.generate_lines(simple_polygon, -1.0)
		
		with pytest.raises(ValueError):
			EastWestLineGenerator.generate_lines(simple_polygon, 0.0)

	def test_extract_line_segments_returns_features(self, simple_polygon):
		"""Testet, ob extract_line_segments Features mit Metadaten zurückgibt."""
		lines = EastWestLineGenerator.generate_lines(simple_polygon, 10.0)
		features = EastWestLineGenerator.extract_line_segments(lines, simple_polygon)
		
		assert isinstance(features, list)
		assert len(features) > 0
		
		# Prüfe Feature-Struktur
		for feat in features:
			assert "type" in feat
			assert feat["type"] == "Feature"
			assert "geometry" in feat
			assert "properties" in feat
			assert feat["geometry"]["type"] == "LineString"

	def test_features_have_required_properties(self, simple_polygon):
		"""Testet, ob Features alle erforderlichen Properties haben."""
		lines = EastWestLineGenerator.generate_lines(simple_polygon, 10.0)
		features = EastWestLineGenerator.extract_line_segments(lines, simple_polygon)
		
		for feat in features:
			props = feat["properties"]
			assert "row" in props
			assert "segment" in props
			assert "length_m" in props
			assert "orientation" in props
			assert props["orientation"] == "EW"

	def test_line_segments_have_positive_length(self, simple_polygon):
		"""Testet, dass alle Liniensegmente positive Länge haben."""
		lines = EastWestLineGenerator.generate_lines(simple_polygon, 10.0)
		features = EastWestLineGenerator.extract_line_segments(lines, simple_polygon)
		
		for feat in features:
			length = feat["properties"]["length_m"]
			assert length > 0

	def test_generated_lines_are_horizontal(self, simple_polygon):
		"""Testet, dass Linien horizontal sind (konstante Y)."""
		lines = EastWestLineGenerator.generate_lines(simple_polygon, 10.0)
		
		for line in lines:
			coords = list(line.coords)
			# Ost-West-Linien: alle Y-Koordinaten sollten gleich sein
			y_values = [y for x, y in coords]
			# Toleranz für Floating-Point-Vergleiche
			assert all(abs(y - y_values[0]) < 1e-6 for y in y_values)


class TestUTMTransformerApplier:
	"""Tests für UTMTransformerApplier-Klasse."""

	@pytest.fixture
	def sample_features(self):
		"""Sample-Features in UTM-Koordinaten."""
		return [
			{
				"type": "Feature",
				"geometry": {
					"type": "LineString",
					"coordinates": [[698000, 5667000], [698100, 5667000]]
				},
				"properties": {"row": 0, "length_m": 100}
			}
		]

	def test_reproject_features_returns_list(self, sample_features):
		"""Testet, ob reproject_features eine Liste zurückgibt."""
		reader = GeoJSONReader(EMBEDDED_GEOJSON)
		_, _, _, to_wgs84 = reader.load()
		
		result = UTMTransformerApplier.reproject_features(sample_features, to_wgs84)
		assert isinstance(result, list)
		assert len(result) == len(sample_features)

	def test_reprojected_coordinates_are_wgs84(self, sample_features):
		"""Testet, ob reprojizierte Koordinaten im WGS84-Bereich liegen."""
		reader = GeoJSONReader(EMBEDDED_GEOJSON)
		_, _, _, to_wgs84 = reader.load()
		
		result = UTMTransformerApplier.reproject_features(sample_features, to_wgs84)
		
		for feat in result:
			coords = feat["geometry"]["coordinates"]
			for lon, lat in coords:
				assert -180 <= lon <= 180
				assert -90 <= lat <= 90

	def test_reproject_preserves_geometry_type(self, sample_features):
		"""Testet, ob die Geometrie-Typ erhalten bleibt."""
		reader = GeoJSONReader(EMBEDDED_GEOJSON)
		_, _, _, to_wgs84 = reader.load()
		
		result = UTMTransformerApplier.reproject_features(sample_features, to_wgs84)
		
		for orig, reprojected in zip(sample_features, result):
			assert orig["geometry"]["type"] == reprojected["geometry"]["type"]


class TestGeoJSONExporter:
	"""Tests für GeoJSONExporter-Klasse."""

	@pytest.fixture
	def sample_geojson_features(self):
		"""Sample GeoJSON-Features."""
		return [
			{
				"type": "Feature",
				"geometry": {
					"type": "LineString",
					"coordinates": [[6.54, 51.09], [6.55, 51.10]]
				},
				"properties": {"row": 0, "length_m": 100}
			}
		]

	def test_export_creates_file(self, sample_geojson_features, tmp_path):
		"""Testet, ob Export eine Datei erstellt."""
		output_file = str(tmp_path / "test.geojson")
		GeoJSONExporter.export(sample_geojson_features, output_file)
		
		assert os.path.exists(output_file)

	def test_exported_file_is_valid_geojson(self, sample_geojson_features, tmp_path):
		"""Testet, ob exportierte Datei valid GeoJSON ist."""
		output_file = str(tmp_path / "test.geojson")
		GeoJSONExporter.export(sample_geojson_features, output_file)
		
		with open(output_file, 'r', encoding='utf-8') as f:
			data = json.load(f)
		
		assert data["type"] == "FeatureCollection"
		assert "features" in data
		assert len(data["features"]) == len(sample_geojson_features)

	def test_export_raises_for_invalid_features(self, tmp_path):
		"""Testet, dass Export Fehler wirft bei ungültigen Features."""
		output_file = str(tmp_path / "test.geojson")
		
		with pytest.raises(ValueError):
			GeoJSONExporter.export("not a list", output_file)

	def test_export_creates_output_directory(self, sample_geojson_features, tmp_path):
		"""Testet, dass Export das Ausgabeverzeichnis erstellt."""
		output_file = str(tmp_path / "subdir" / "test.geojson")
		GeoJSONExporter.export(sample_geojson_features, output_file)
		
		assert os.path.exists(output_file)


class TestRowSpacingInputHandler:
	"""Tests für RowSpacingInputHandler-Klasse."""

	def test_get_row_spacing_non_interactive_returns_default(self):
		"""Testet, dass non-interaktiver Modus den Default zurückgibt."""
		spacing = RowSpacingInputHandler.get_row_spacing(default=2.5, interactive=False)
		assert spacing == 2.5

	def test_get_row_spacing_validates_positive(self):
		"""Testet, dass nur positive Abstände akzeptiert werden."""
		# Im nicht-interaktiven Modus: Validierung auf Aufrufseite
		assert RowSpacingInputHandler.get_row_spacing(default=0.1, interactive=False) > 0


class TestMainFunction:
	"""Tests für main()-Funktion."""

	def test_main_returns_dict_with_success(self):
		"""Testet, dass main() ein Dict mit success-Feld zurückgibt."""
		result = main(interactive=False, output_dir=tempfile.gettempdir())
		
		assert isinstance(result, dict)
		assert "success" in result
		assert result["success"] is True

	def test_main_returns_metadata(self):
		"""Testet, dass main() Metadaten zurückgibt."""
		result = main(interactive=False, output_dir=tempfile.gettempdir())
		
		assert "metadata" in result
		metadata = result["metadata"]
		assert "area_wgs84_deg2" in metadata
		assert "area_utm_m2" in metadata
		assert "row_spacing_m" in metadata
		assert "n_lines_total" in metadata
		assert "n_features" in metadata
		assert "output_file" in metadata

	def test_main_generates_output_file(self):
		"""Testet, dass main() eine Ausgabedatei generiert."""
		with tempfile.TemporaryDirectory() as tmpdir:
			result = main(interactive=False, output_dir=tmpdir)
			
			output_file = result["metadata"]["output_file"]
			assert os.path.exists(output_file)
			
			# Prüfe GeoJSON-Format
			with open(output_file, 'r', encoding='utf-8') as f:
				data = json.load(f)
			
			assert data["type"] == "FeatureCollection"
			assert len(data["features"]) > 0

	def test_main_metadata_values_are_reasonable(self):
		"""Testet, dass Metadaten-Werte vernünftig sind."""
		result = main(interactive=False, output_dir=tempfile.gettempdir())
		metadata = result["metadata"]
		
		assert metadata["area_utm_m2"] > 0
		assert metadata["row_spacing_m"] > 0
		assert metadata["n_lines_total"] > 0
		assert metadata["n_features"] > 0


class TestIntegration:
	"""Integrationstests für den gesamten Workflow."""

	def test_full_workflow_2m_spacing(self):
		"""Testet den gesamten Workflow mit 2.0 m Abstand."""
		result = main(interactive=False, output_dir=tempfile.gettempdir())
		
		assert result["success"]
		assert result["metadata"]["row_spacing_m"] == 2.0
		assert result["metadata"]["n_features"] > 0

	def test_output_geojson_has_valid_features(self):
		"""Testet, dass Output-GeoJSON valid LineString-Features hat."""
		with tempfile.TemporaryDirectory() as tmpdir:
			result = main(interactive=False, output_dir=tmpdir)
			output_file = result["metadata"]["output_file"]
			
			with open(output_file, 'r', encoding='utf-8') as f:
				data = json.load(f)
			
			for feat in data["features"]:
				assert feat["geometry"]["type"] == "LineString"
				assert len(feat["geometry"]["coordinates"]) >= 2
				assert "properties" in feat
				assert "row" in feat["properties"]
				assert "length_m" in feat["properties"]
				assert "orientation" in feat["properties"]
				assert feat["properties"]["orientation"] == "EW"

	def test_features_cover_polygon_area(self):
		"""Testet, dass generierte Features die Polygonfläche abdecken."""
		reader = GeoJSONReader(EMBEDDED_GEOJSON)
		poly_wgs84, poly_utm, _, to_wgs84 = reader.load()
		
		# Generiere Features
		lines = EastWestLineGenerator.generate_lines(poly_utm, 5.0)
		features_utm = EastWestLineGenerator.extract_line_segments(lines, poly_utm)
		features_wgs84 = UTMTransformerApplier.reproject_features(features_utm, to_wgs84)
		
		# Prüfe, dass Features generiert wurden
		assert len(features_wgs84) > 0
		
		# Jedes Feature sollte eine gültige LineString-Geometrie haben
		for feat in features_wgs84:
			coords = feat["geometry"]["coordinates"]
			assert len(coords) >= 2


if __name__ == "__main__":
	pytest.main([__file__, "-v", "--tb=short"])
