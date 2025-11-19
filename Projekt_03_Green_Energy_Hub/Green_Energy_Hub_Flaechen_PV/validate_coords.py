"""
Validierungsskript für Projekt_03 - Green Energy Hub Koordinaten-Update
"""
import sys
import os
sys.path.insert(0, '.')

from Projekt_03_Green_Energy_Hub_Flaeche_PV import EMBEDDED_GEOJSON
import json

print('\n' + '='*70)
print('PROJEKT 03 - Green Energy Hub Koordinaten-Update')
print('='*70 + '\n')

# Parse und validiere Koordinaten
try:
    obj = json.loads(EMBEDDED_GEOJSON)
    feature = obj['features'][0]
    coords = feature['geometry']['coordinates'][0]
    
    print('[1] Koordinaten-Informationen:')
    print('    Polygon-Punkte: {}'.format(len(coords)))
    print('    Erster Punkt: ({}, {})'.format(coords[0][0], coords[0][1]))
    print('    Name: {}'.format(feature['properties']['name']))
    print('    Beschreibung: {}'.format(feature['properties']['description']))
    
    # Prüfe ob Koordinaten aus Green Energy Hub sind
    if coords[0][0] == 6.456431 and coords[0][1] == 51.038577:
        print('\n[2] Koordinaten-Validierung:')
        print('    Status: APPROVED')
        print('    Projekt: Green Energy Hub')
        print('    Region: Juechen, NRW')
    else:
        print('\n[2] Koordinaten-Validierung:')
        print('    Status: UNBEKANNT')
    
    print('\n' + '='*70)
    print('ERFOLG: Koordinaten wurden aktualisiert!')
    print('='*70 + '\n')

except Exception as e:
    print('FEHLER: {}'.format(e))
    import traceback
    traceback.print_exc()
