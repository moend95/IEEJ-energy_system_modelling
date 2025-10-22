import folium

# ------------------------------------------------------------
# 1. Kartenerstellung
# ------------------------------------------------------------
# Mittelpunkt (Breiten- und Längengrad) und Zoomstufe
karte = folium.Map(
    location=[51.1657, 10.4515],  # Mittelpunkt: Deutschland
    zoom_start=6,
    tiles='OpenStreetMap'
)

# ------------------------------------------------------------
# 2. Beispiel-Punkte hinzufügen
# ------------------------------------------------------------
punkte = [
    {"name": "Berlin", "coords": [52.5200, 13.4050]},
    {"name": "Hamburg", "coords": [53.5511, 9.9937]},
    {"name": "München", "coords": [48.1351, 11.5820]},
    {"name": "Köln", "coords": [50.9375, 6.9603]}
]

for punkt in punkte:
    folium.Marker(
        location=punkt["coords"],
        tooltip=punkt["name"],
        popup=f"Standort: {punkt['name']}",
        icon=folium.Icon(color='blue', icon='info-sign')
    ).add_to(karte)

# ------------------------------------------------------------
# 3. Polygon (z. B. PV-Anlage oder Untersuchungsfläche)
# ------------------------------------------------------------
polygon_koordinaten = [
    [49.0, 8.4],
    [49.0, 8.6],
    [49.1, 8.6],
    [49.1, 8.4]
]

folium.Polygon(
    locations=polygon_koordinaten,
    color='green',
    weight=2,
    fill=True,
    fill_color='green',
    fill_opacity=0.4,
    tooltip='Beispielhafte Untersuchungsfläche'
).add_to(karte)

# ------------------------------------------------------------
# 4. Layer-Steuerung aktivieren
# ------------------------------------------------------------
folium.LayerControl().add_to(karte)

# ------------------------------------------------------------
# 5. Karte speichern
# ------------------------------------------------------------
karte.save("eigene_osm_karte.html")

print("Karte wurde erstellt und als 'eigene_osm_karte.html' gespeichert.")
print("Du kannst die Datei jetzt im Browser öffnen.")

import webbrowser
webbrowser.open("eigene_osm_karte.html")
