'''
-OSM Flächen auslesen (Koordinaten bbox eingabe -> Flächen als Rechtecke vereinfacht)
	-Mittelpunkt für PV berechnung

Funktion definieren, die aus OSM die Flächen zieht, auf denen Agri PV stattfinden soll
Input: Koordinaten box (von bis)
Output: Fläche oder Flächen (Größe und Form Rechteck) und Plot mit markierter Fläche, die als Acker bezeichnet sind (?)
'''

import requests
import geopandas as gpd
from shapely.geometry import Polygon
from pyproj import CRS

# OSM way ID
way_id = 168868469

# Overpass API-Abfrage
overpass_url = "http://overpass-api.de/api/interpreter"
query = f"""
[out:json];
way({way_id});
(._;>;);
out body;
"""

response = requests.get(overpass_url, params={'data': query})
data = response.json()

# Knoten extrahieren
nodes = {elem['id']: (elem['lon'], elem['lat']) for elem in data['elements'] if elem['type'] == 'node'}

# Koordinatenreihenfolge des Ways ermitteln
way_nodes = [elem for elem in data['elements'] if elem['type'] == 'way'][0]['nodes']

# Polygon aufbauen
coords = [nodes[node_id] for node_id in way_nodes]

# Polygon erstellen
polygon = Polygon(coords)

# Geometrie als GeoDataFrame
gdf = gpd.GeoDataFrame(index=[0], crs="EPSG:4326", geometry=[polygon])

# In metrisches CRS transformieren (z. B. UTM Zone 32N für Süddeutschland)
gdf = gdf.to_crs(CRS.from_epsg(32632))

# Fläche berechnen in m²
area_m2 = gdf.geometry.area[0]
area_ha = area_m2 / 10_000

# Ausgabe
print(f"Fläche: {area_m2:.2f} m² ({area_ha:.4f} ha)")
