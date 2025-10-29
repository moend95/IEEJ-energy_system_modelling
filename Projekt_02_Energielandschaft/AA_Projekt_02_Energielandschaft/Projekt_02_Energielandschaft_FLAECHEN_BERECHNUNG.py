# Flächen_Berechnung
# Input: Fläche (GeoJSON-Datei), PV-Ausrichtung, Traktor Breite und Länge 
# Ausgabe: Maximal mögliche Fläche für PV-Module, Gesamte Fläche des Ackers, Plot HTML-Karte 

# ------------------------------------------------------------

from pathlib import Path
from Projekt_02_Energielandschaft_RUN_SKRIPT import UserInputCollector

collector = UserInputCollector()          # Defaults können hier übergeben werden
config = collector.collect()             # interaktive Abfrage
collector.save(config)                   # speichert wie gewohnt ./outputs/user_selection.json

# jetzt weiterverwenden
print(config)

