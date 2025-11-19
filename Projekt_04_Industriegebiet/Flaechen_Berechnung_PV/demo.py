#!/usr/bin/env python
"""
Demonstrationsskript für Projekt_04 - Industriegebiet Dachflächen PV-Reihen

Dieses Skript zeigt verschiedene Abstände und deren Auswirkungen.
"""

import json
from Projekt_04_Industriegebiet_Dachflaechen_PV import (
	GeoJSONReader,
	EastWestLineGenerator,
	UTMTransformerApplier,
	GeoJSONExporter,
	EMBEDDED_GEOJSON
)

def demo():
	"""Demonstriert die Erzeugung von PV-Reihen mit verschiedenen Abständen."""
	
	print("\n" + "="*70)
	print("DEMO: Projekt_04 - Dachflächen PV-Reihen mit verschiedenen Abständen")
	print("="*70 + "\n")
	
	# Lade Fläche
	print("Schritt 1: Fläche laden...")
	reader = GeoJSONReader(EMBEDDED_GEOJSON)
	geom_wgs84, geom_utm, to_utm, to_wgs84 = reader.load()
	print(f"  ✓ Fläche geladen: {geom_utm.area:.0f} m²")
	print(f"    Koordinaten: {geom_wgs84.bounds}\n")
	
	# Teste verschiedene Abstände
	spacings = [1.5, 2.0, 3.0, 5.0, 10.0]
	results = []
	
	print("Schritt 2: Generiere Reihen mit verschiedenen Abständen...\n")
	print(f"{'Abstand':>8} | {'Linien':>6} | {'Features':>8} | {'Durchschn. Länge':>17}")
	print("-" * 58)
	
	for spacing in spacings:
		# Generiere Linien
		lines = EastWestLineGenerator.generate_lines(geom_utm, spacing)
		features_utm = EastWestLineGenerator.extract_line_segments(lines, geom_utm)
		features_wgs84 = UTMTransformerApplier.reproject_features(features_utm, to_wgs84)
		
		# Berechne Statistiken
		n_lines = len(lines)
		n_features = len(features_utm)
		
		if n_features > 0:
			avg_length = sum(f["properties"]["length_m"] for f in features_utm) / n_features
		else:
			avg_length = 0
		
		results.append({
			"spacing": spacing,
			"n_lines": n_lines,
			"n_features": n_features,
			"avg_length": avg_length,
			"features": features_wgs84
		})
		
		print(f"{spacing:>7.1f}m | {n_lines:>6} | {n_features:>8} | {avg_length:>16.1f}m")
	
	print("\nSchritt 3: Exportiere beste Varianten...\n")
	
	# Exportiere einige Varianten
	export_spacings = [2.0, 5.0]
	for spacing in export_spacings:
		result = next(r for r in results if r["spacing"] == spacing)
		output_file = f"outputs/demo_Projekt_04_Reihen_{spacing}m.geojson"
		
		try:
			GeoJSONExporter.export(result["features"], output_file)
			print(f"  ✓ Exportiert: {output_file}")
		except Exception as e:
			print(f"  ✗ Fehler beim Export: {e}")
	
	print("\n" + "="*70)
	print("ZUSAMMENFASSUNG")
	print("="*70)
	print(f"Fläche: {geom_utm.area:.0f} m²")
	print(f"Getestete Abstände: {spacings}")
	print(f"Effizienz-Analyse:")
	print(f"  - Kleiner Abstand (1.5 m): {results[0]['n_features']} Features (mehr Details)")
	print(f"  - Großer Abstand (10 m): {results[-1]['n_features']} Features (weniger Details)")
	print("\nNutzungsempfehlung:")
	print("  - Präzisionsplanung: 1.5–2.0 m")
	print("  - Standard-Planung: 2.5–3.0 m")
	print("  - Grobplanung: 5.0–10.0 m")
	print("="*70 + "\n")

if __name__ == "__main__":
	demo()
