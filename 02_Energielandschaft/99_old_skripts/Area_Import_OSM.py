## Import Koordinaten aus OSM
## Input: OSM Way-ID
## Output: Koordinaten der Fläche in xy-Koordinaten (Umwandlung von Längen- und Breitengraden in xy-Koordinaten)

import requests

# OSM Way-ID der Fläche
from Area_Agri_PV_MAIN import way_id
way_id_1 = way_id

# Overpass-API-Abfrage
query = f"""
[out:json];
way({way_id_1});
out geom;
"""

# Anfrage senden
url = "https://overpass-api.de/api/interpreter"
response = requests.get(url, params={'data': query})
response.raise_for_status()
data = response.json()

# Geometrie extrahieren und in gewünschtes Format bringen (x = lon, y = lat)
coords = [(round(node['lon'], 6), round(node['lat'], 6)) for node in data['elements'][0]['geometry']]

# Falls nicht geschlossen, Anfangspunkt am Ende anhängen
if coords[0] != coords[-1]:
    coords.append(coords[0])

# Ausgabe im gewünschten Format
coordinates_str = "coordinates = [" + ", ".join(f"({x}, {y})" for x, y in coords) + "]"
print(coordinates_str)

## Koordinaten Umwandlung in xy-Koordianten

import math

# Funktion zur Umwandlung von Längen- und Breitengraden in xy-Koordinaten
def lat_lon_to_xy(lat1, lon1, lat2, lon2):
    R = 6371000  # Radius der Erde in Metern
    x = R * math.radians(lon2 - lon1) * math.cos(math.radians(lat1))
    y = R * math.radians(lat2 - lat1)
    return x, y

# Funktion zur Umwandlung einer Liste von Längen- und Breitengraden in eine Liste von xy-Koordinaten
def convert_coordinates(lat_lon_list):
    xy_list = []
    for i in range(len(lat_lon_list)):
        if i == 0:
            xy_list.append((0, 0))
        else:
            x, y = lat_lon_to_xy(lat_lon_list[0][0], lat_lon_list[0][1], lat_lon_list[i][0], lat_lon_list[i][1])
            xy_list.append((x, y))
    return xy_list

# Umwandlung von (lon, lat) → (lat, lon) zur Weiterverarbeitung
lat_lon_list = [(lat, lon) for lon, lat in coords]

# Koordinaten konvertieren
xy_list = convert_coordinates(lat_lon_list)

xy_coordinates = xy_list

# Ausgabe der XY-Koordinaten
print("\nXY-Koordinaten (in Metern, Ursprung = erster Punkt):")
for x, y in xy_list:
    print(f"({x:.2f}, {y:.2f})")

## Berechnung der Fläche eines Agri-PV-Feldes aus OSM-Daten
## Input: OSM Way-ID
## Output: Fläche in Quadratmetern und Hektar

import requests
import geopandas as gpd
from shapely.geometry import Polygon
from pyproj import CRS

# OSM way ID
from Area_Agri_PV_MAIN import way_id
way_id_2 = way_id

# Overpass API-Abfrage
overpass_url = "http://overpass-api.de/api/interpreter"
query = f"""
[out:json];
way({way_id_2});
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
