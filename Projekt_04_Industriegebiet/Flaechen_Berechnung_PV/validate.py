"""
Validierungsskript für Projekt_04
"""
import json
import os
from Projekt_04_Industriegebiet_Dachflaechen_PV import main, GeoJSONReader, EMBEDDED_GEOJSON

print('\nFINAL VALIDATION für Projekt_04\n')

# 1. Check Python files
print('[1/3] Python-Dateien:')
files = ['Projekt_04_Industriegebiet_Dachflaechen_PV.py', 'test_projekt_04.py', 'demo.py', 'README.md']
for f in files:
	if os.path.exists(f):
		size = os.path.getsize(f)
		print(f'  ✓ {f} ({size} bytes)')

# 2. Check main function
print('\n[2/3] Hauptfunktion:')
try:
	result = main(interactive=False, output_dir='outputs')
	if result.get('success'):
		print('  ✓ main() wurde ausgeführt')
		metadata = result['metadata']
		print(f'    - Fläche: {metadata["area_utm_m2"]:.0f} m²')
		print(f'    - Reihenabstand: {metadata["row_spacing_m"]} m')
		print(f'    - Generierte Features: {metadata["n_features"]}')
		print(f'    - Output: {os.path.basename(metadata["output_file"])}')
except Exception as e:
	print(f'  ✗ Fehler: {e}')

# 3. Check GeoJSON validity
print('\n[3/3] GeoJSON-Dateien:')
output_dir = 'outputs'
count = 0
for f in os.listdir(output_dir):
	if 'Projekt_04' in f and f.endswith('.geojson'):
		try:
			with open(os.path.join(output_dir, f), 'r', encoding='utf-8') as fp:
				data = json.load(fp)
				n_features = len(data.get('features', []))
				geom_type = data['type']
				print(f'  ✓ {f}')
				print(f'    - Type: {geom_type}, Features: {n_features}')
				count += 1
		except Exception as e:
			print(f'  ✗ {f}: {e}')

print(f'\n✅ Validierung abgeschlossen! ({count} GeoJSON-Dateien gefunden)\n')
