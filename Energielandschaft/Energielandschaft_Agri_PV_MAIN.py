# Agri-PV Fläche berechnung 
# Input: OSM Way-ID
# Agri-PV Fläche Berechnung – OSM-Way-ID Eingabe

# Import der benötigten Bibliotheken
import requests
import math
import geopandas as gpd
from shapely.geometry import Polygon, LineString, Point
from pyproj import CRS, Transformer
import numpy as np
import folium
import webbrowser

# Standard-Way-ID
default_way_id = 168868469

# Nutzereingabe mit Fallback
way_id_input = input(f"Bitte die OSM Way-ID eingeben (Oder Enter drücken für Standard OSM Way-ID: {default_way_id}): ")

if way_id_input.strip() == "":
    way_id = default_way_id
else:
    try:
        way_id = int(way_id_input)
    except ValueError:
        print("Ungültige Eingabe. Es wird der Standardwert verwendet.")
        way_id = default_way_id

# Overpass-API-Abfrage
query = f"""
[out:json];
way({way_id});
out geom;
"""

# Anfrage senden
url = "https://overpass-api.de/api/interpreter"
response = requests.get(url, params={'data': query})
response.raise_for_status()
data = response.json()

# Geometrie extrahieren und in gewünschtes Format bringen (x = lon, y = lat), "coords" sind geographische Koordianten in lon, lat
coords = [(round(node['lon'], 6), round(node['lat'], 6)) for node in data['elements'][0]['geometry']]

# Falls nicht geschlossen, Anfangspunkt am Ende anhängen
if coords[0] != coords[-1]:
    coords.append(coords[0])

# Ausgabe im gewünschten Format
coordinates_str = "coordinates = [" + ", ".join(f"({x}, {y})" for x, y in coords) + "]"

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

# Umwandlung von (lon, lat) zu (lat, lon) zur Weiterverarbeitung
lat_lon_list = [(lat, lon) for lon, lat in coords]

# Koordinaten konvertieren
xy_list = convert_coordinates(lat_lon_list)
xy_coordinates = xy_list

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

# Agri-PV Dichte/Flächennutzung berechnen
def calculate_intersection_points(polygon, line):
    intersection_points = polygon.intersection(line)
    if isinstance(intersection_points, Point):
        return [intersection_points]
    elif isinstance(intersection_points, LineString):
        return list(intersection_points.coords)
    elif hasattr(intersection_points, 'geoms'):
        return [pt for geom in intersection_points.geoms for pt in geom.coords]
    return []

def plot_line_with_intersections(polygon, centroid, angle_radians, distance, Bg, max_area, existing_line_segments):
    dx = np.sin(angle_radians)
    dy = np.cos(angle_radians)
    new_centroid = Point(centroid.x + distance * dx, centroid.y + distance * dy)
    
    line_length = 1e5
    line = LineString([
        (new_centroid.x - line_length * dy, new_centroid.y + line_length * dx),
        (new_centroid.x + line_length * dy, new_centroid.y - line_length * dx)
    ])
    
    intersection_points = calculate_intersection_points(polygon, line)
    
    if len(intersection_points) < 2:
        return False, existing_line_segments
    
    x_vals = [pt[0] for pt in intersection_points]
    y_vals = [pt[1] for pt in intersection_points]
    
    line_segment = [(x_vals[0], y_vals[0]), (x_vals[1], y_vals[1])]
    total_length = sum(LineString(seg).length for seg in existing_line_segments) + LineString(line_segment).length
    
    if total_length * Bg > max_area:
        remaining_length = max_area / Bg - sum(LineString(seg).length for seg in existing_line_segments)
        if remaining_length <= 0:
            return False, existing_line_segments

        factor = remaining_length / LineString(line_segment).length
        mid_x = (x_vals[0] + x_vals[1]) / 2
        mid_y = (y_vals[0] + y_vals[1]) / 2
        x_vals = [
            mid_x - factor * (mid_x - x_vals[0]),
            mid_x + factor * (x_vals[1] - mid_x)
        ]
        y_vals = [
            mid_y - factor * (mid_y - y_vals[0]),
            mid_y + factor * (y_vals[1] - mid_y)
        ]
        line_segment = [(x_vals[0], y_vals[0]), (x_vals[1], y_vals[1])]
        existing_line_segments.append(line_segment)
        return False, existing_line_segments
    
    existing_line_segments.append(line_segment)
    return total_length * Bg <= max_area, existing_line_segments

def plot_field_with_lines(coordinates, Lvor, Bg, An, Aarbeits, max_area_percentage):
    polygon = Polygon(coordinates)
    area = polygon.area  # Fläche in Quadratmetern
    max_area = max_area_percentage / 100 * area

    centroid = polygon.centroid
    offset_distance = Lvor + (Bg / 2)
    offset_polygon = polygon.buffer(-offset_distance)

    angle_radians = np.radians(An)
    existing_line_segments = []
    num_pv_module_rows = 0

    result, existing_line_segments = plot_line_with_intersections(offset_polygon, centroid, angle_radians, 0, Bg, max_area, existing_line_segments)

    if result:
        num_pv_module_rows += 1
    else:
        total_length = sum(LineString(seg).length for seg in existing_line_segments)
        Agrun = total_length * Bg
        print(f"\nAbgefragte Variablen:")
        print(f"Anzahl der Ecken des Feldes: {len(coordinates)}")
        print("Koordinaten der Ecken:")
        for j, coord in enumerate(coordinates, start=1):
            print(f"  Ecke {j}: (x={coord[0]}, y={coord[1]})")
        print(f"Laenge vom Vorgewende: {Lvor} Meter")
        print(f"Breite der Gruenstreifen (Bg): {Bg} Meter")
        print(f"Winkel (An): {An} Grad")
        print(f"Arbeitsbreite (Aarbeits): {Aarbeits} Meter")
        print(f"Maximale Flaeche mit PV-Modulen bedeckt: {max_area_percentage} Prozent")
        print(f"Die Flaeche Ag vom Feld betraegt {area:.2f} Quadratmeter")
        print(f"Anzahl der PV-Modul Reihen: {num_pv_module_rows}")
        print(f"Flaeche mit Gruenstreifen bedeckt (Agrun): {Agrun:.2f} Quadratmeter")
        print(f"Prozentualer Anteil der Flaeche Agrun zur Gesamtflaeche Ag: {Agrun / area * 100:.2f}%")
        export_plot_to_osm_html(polygon, offset_polygon, existing_line_segments)
        return

    distance_multiplier = 1
    while distance_multiplier * (Aarbeits + Bg) < max(polygon.bounds[2] - polygon.bounds[0], polygon.bounds[3] - polygon.bounds[1]):
        distances = [(Aarbeits + Bg) * distance_multiplier, -(Aarbeits + Bg) * distance_multiplier]
        for distance in distances:
            result, existing_line_segments = plot_line_with_intersections(offset_polygon, centroid, angle_radians, distance, Bg, max_area, existing_line_segments)
            if result:
                num_pv_module_rows += 1
                total_length = sum(LineString(seg).length for seg in existing_line_segments)
                Agrun = total_length * Bg
                if Agrun / area * 100 >= max_area_percentage:
                    print("\nMaximale Flaeche erreicht")
                    export_plot_to_osm_html(polygon, offset_polygon, existing_line_segments)
                    return
        distance_multiplier += 1

# Plot auf OSM-Karte
def transform_coords_to_latlon(coords):
    transformer = Transformer.from_crs("EPSG:32632", "EPSG:4326", always_xy=True)
    return [transformer.transform(x, y) for x, y in coords]

def export_plot_to_osm_html(polygon, offset_polygon, existing_line_segments, filename="agri_pv_plot.html"):
    polygon_coords_latlon = transform_coords_to_latlon(list(polygon.exterior.coords))
    offset_coords_latlon = transform_coords_to_latlon(list(offset_polygon.exterior.coords)) if not offset_polygon.is_empty else []

    center = np.mean(polygon_coords_latlon, axis=0)[::-1]

    m = folium.Map(location=center, zoom_start=17, control_scale=True)

    # Ursprüngliches Polygon (rot)
    folium.Polygon(
        locations=[(lat, lon) for lon, lat in polygon_coords_latlon],
        color="black",
        fill=True,
        fill_color="red",
        fill_opacity=0.5,
        tooltip="Feldpolygon"
    ).add_to(m)

    # Offset-Polygon (gelb)
    if offset_coords_latlon:
        folium.Polygon(
            locations=[(lat, lon) for lon, lat in offset_coords_latlon],
            color="blue",
            fill=True,
            fill_color="yellow",
            fill_opacity=0.5,
            tooltip="Offset (Vorgewende + Grünstreifen)"
        ).add_to(m)

    # Liniensegmente (grün, dicke = Bg)
    for seg in existing_line_segments:
        seg_latlon = transform_coords_to_latlon(seg)
        folium.PolyLine(
            locations=[(lat, lon) for lon, lat in seg_latlon],
            color="green",
            weight=Bg,
            tooltip="PV-Reihe"
        ).add_to(m)

    # Speichern als HTML
    m.save(filename)
    print(f"Karte gespeichert unter: {filename}")

# Parameter für Berechnung festlegen 
coordinates = xy_coordinates

def get_float_input(prompt, default):
    try:
        value = input(f"{prompt} (Standard: {default}): ")
        return float(value) if value else default
    except ValueError:
        print("Ungültige Eingabe. Standardwert wird verwendet.")
        return default

# Parameterabfrage mit Standardwerten
Lvor = get_float_input("Länge des Vorgewendes in Metern", 5)
Bg = get_float_input("Breite der Grünstreifen in Metern", 5)
An = get_float_input("Ausrichtungswinkel in Grad", 0)
Aarbeits = get_float_input("Arbeitsbreite der PV-Module in Metern", 50)
max_area_percentage = get_float_input("Maximale PV-Fläche in Prozent", 50)

# Output: Plot, Werte für PV-Dichte, Fläche, Anzahl der Module
coordinates = xy_coordinates
plot_field_with_lines(coordinates, Lvor, Bg, An, Aarbeits, max_area_percentage)

# coords: Liste aus (lon, lat), direkt aus Overpass-API
polygon_wgs84 = Polygon(coords)

# GeoDataFrame mit WGS84-Koordinaten (EPSG:4326)
gdf_wgs84 = gpd.GeoDataFrame(index=[0], crs="EPSG:4326", geometry=[polygon_wgs84])

# In metrisches Koordinatensystem (UTM Zone 32N → EPSG:32632)
gdf_utm = gdf_wgs84.to_crs(CRS.from_epsg(32632))
polygon_utm = gdf_utm.geometry[0]

# Fläche berechnen
area_m2 = polygon_utm.area
area_ha = area_m2 / 10_000

# Für weitere Berechnungen: polygon_utm verwenden
coordinates = list(polygon_utm.exterior.coords)

# Plot und Analyse
plot_field_with_lines(coordinates, Lvor, Bg, An, Aarbeits, max_area_percentage)

# EPSG:32632 zu EPSG:4326
transformer = Transformer.from_crs("EPSG:32632", "EPSG:4326", always_xy=True)

def transform_coords_to_latlon(coords):
    return [transformer.transform(x, y) for x, y in coords]

def export_plot_to_osm_html(polygon, offset_polygon, existing_line_segments, filename="agri_pv_plot.html"):
    polygon_coords_latlon = transform_coords_to_latlon(list(polygon.exterior.coords))
    offset_coords_latlon = transform_coords_to_latlon(list(offset_polygon.exterior.coords)) if not offset_polygon.is_empty else []

    center = np.mean(polygon_coords_latlon, axis=0)[::-1]
    m = folium.Map(location=center, zoom_start=17, control_scale=True)

    # Ursprüngliches Polygon
    folium.Polygon(
        locations=[(lat, lon) for lon, lat in polygon_coords_latlon],
        color="black",
        fill=True,
        fill_color="red",
        fill_opacity=0.5,
        tooltip="Feldpolygon"
    ).add_to(m)

    # Offset-Polygon
    if offset_coords_latlon:
        folium.Polygon(
            locations=[(lat, lon) for lon, lat in offset_coords_latlon],
            color="blue",
            fill=True,
            fill_color="yellow",
            fill_opacity=0.5,
            tooltip="Offset (Vorgewende + Grünstreifen)"
        ).add_to(m)

    # PV-Reihen
    for seg in existing_line_segments:
        seg_latlon = transform_coords_to_latlon(seg)
        folium.PolyLine(
            locations=[(lat, lon) for lon, lat in seg_latlon],
            color="green",
            weight=Bg,
            tooltip="PV-Reihe"
        ).add_to(m)

    m.save(filename)
    print(f"Karte gespeichert unter: {filename}")

webbrowser.open("agri_pv_plot.html")
