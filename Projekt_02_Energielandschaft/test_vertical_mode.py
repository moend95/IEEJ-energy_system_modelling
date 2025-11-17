#!/usr/bin/env python
"""Test-Skript für vertical-Modus mit Reihenabstands-Berechnung."""

from Projekt_02_Energielandschaft import main, PVTypeSelector

# Monkey-patch to override the selector for vertical mode
original_select = PVTypeSelector.select
PVTypeSelector.select = lambda default="horizontal", interactive=True: "vertical"

try:
    result = main(interactive=False)
    print(f"\n✓ Erfolgreich mit vertical!" if result['success'] else "✗ Fehler")
    
    # Überprüfe die Metadata
    if result['success']:
        meta = result['metadata']
        print(f"\n📊 Reihenparameter:")
        print(f"   Orientierung: {meta['orientation']} (Nord-Süd)")
        print(f"   Reihenbreite: {meta['reihenbreite_m']} m")
        print(f"   Reihenabstand: {meta['row_spacing_m']} m")
        print(f"   Fahrspur: {meta['fahrspur_m']} m")
        print(f"   Berechnung: {meta['fahrspur_m']} + 0.5 = {meta['row_spacing_m']}")
finally:
    PVTypeSelector.select = original_select
