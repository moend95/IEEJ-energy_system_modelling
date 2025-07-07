# -*- coding: utf-8 -*-
"""
Created on Mon Apr 28 09:11:07 2025

@author: Jannis Brinkmann

Erstellung des PV-Autobahn-Verlaufs
"""

import osmnx as ox
from shapely.geometry import LineString
from shapely.geometry import box
from shapely.ops import unary_union
import geopandas as gpd
import math
import folium
import webbrowser
import numpy as np



def apply_oneway_orientation(geom, oneway):
    coords = list(geom.coords)
    if oneway == -1:
        coords = coords[::-1]
    return LineString(coords)

def calculate_bearing(geom):
    # Start- und Endpunkt
    x1, y1 = geom.coords[0]
    x2, y2 = geom.coords[-1]

    # Berechne Winkel in Grad
    angle = math.degrees(math.atan2(x2 - x1, y2 - y1))  # beachte Umkehr von dx und dy
    bearing = (angle + 360) % 360  # in Bereich 0–360 bringen
    return bearing

def is_within_direction(angle, target, tolerance=30):
    delta = abs((angle - target + 180) % 360 - 180)
    return delta <= tolerance

def richtung_to_angle(richtung):
    mapping = {
        "nord": 0,
        "ost": 90,
        "süd": 180,
        "west": 270
    }
    return mapping.get(richtung, None)



def eingabe_bounding_box():  # Funktion Eingabe bounding box mit Zusatzinfos
    bounding_boxes = []
    print("Gib Bounding-Box-Koordinaten ein (Format: minx, miny, maxx, maxy). Tippe 'fertig' zum Beenden.")
    while True:
        eingabe = input("Bounding Box: ")
        if eingabe.lower() == 'fertig':
            break
        try:
            minx, miny, maxx, maxy = map(float, eingabe.split(','))
            geom = box(minx, miny, maxx, maxy)
             
            # Eingabe Zusatzinformationen zur Geometrie
            richtung = input("Fahrtrichtung (beide / nord / süd / ost / west): ").strip().lower()
            pv_installation = input("PV-Installation (böschung / wand / beides): ").strip().lower()

            info = {
                "geometry": geom,
                "richtung": richtung,
                "pv_installation": pv_installation
            }
            bounding_boxes.append(info)
        except ValueError:
            print("Ungültiges Format. Bitte nutze: minx, miny, maxx, maxy")
    return bounding_boxes   
 
def highway_gdf_in_bb(list_indiv_bb): # Autobahn GeoDataFrames werden aus Bounding Boxen herausgesucht ( Feste Filter: NRW, Autobahn, A44/A46)
    highways = ox.graph_from_place("Nordrhein-Westfalen, Germany", network_type='drive', custom_filter='["highway"~"motorway"]')
    highway_edges = ox.graph_to_gdfs(highways, nodes=False, edges=True)
    highway_edges = highway_edges[(highway_edges['ref'] == 'A 46') | (highway_edges['ref'] == 'A 44')]

    highway_edges_cut = []

    for bbox in list_indiv_bb:
        relevant_edges = []

        for _, edge in highway_edges.iterrows():
            if edge.geometry.intersects(bbox["geometry"]):
                cut_geom = edge.geometry.intersection(bbox["geometry"])
                if not cut_geom.is_empty and isinstance(cut_geom, LineString):
                    relevant_edges.append((edge, cut_geom))

        if not relevant_edges:
            continue

        richtung = bbox["richtung"]
        pv_info = bbox["pv_installation"]
        passt_edges = []

        for edge, cut_geom in relevant_edges:
            oneway = edge.get('oneway', False)
            if oneway == True:
                oneway = 1
            elif oneway == False:
                oneway = 0
            elif isinstance(oneway, str) and oneway == '-1':
                oneway = -1

            oriented_geom = apply_oneway_orientation(cut_geom, oneway)
            angle = calculate_bearing(oriented_geom)

            if richtung == "beide":
                passt_edges.append(oriented_geom)
            else:
                target_angle = richtung_to_angle(richtung)
                if target_angle is not None and is_within_direction(angle, target_angle, tolerance=45):
                    passt_edges.append(oriented_geom)

        for geom in passt_edges:
            highway_edges_cut.append({
                "geometry": geom,
                "richtung": richtung,
                "pv_installation": pv_info
            })

    if highway_edges_cut:
        return gpd.GeoDataFrame(highway_edges_cut, crs=highway_edges.crs)
    else:
        print("⚠️ Keine passenden Autobahnabschnitte in den Bounding Boxes gefunden.")
        return gpd.GeoDataFrame(columns=["geometry", "richtung", "pv_installation"])


def plot_geometry_on_map(gdf, map_filename="karte.html"): # Funktion Plotting der Geometrie auf OSM Kartenabschnitt
   # gdf -> GeoDataFrame, das dargestellt werden soll
   # map_filename -> standard: karte.html, kann verändert werden falls gewollt
   
   gdf_4326 = gdf.to_crs(epsg=4326)

   if gdf_4326.empty:
        print("⚠️ Das GeoDataFrame ist leer. Keine Geometrien zum Anzeigen.")
        return
# Mittelpunkt berechnen für Kartenfokus
   bounds = gdf.total_bounds  # [minx, miny, maxx, maxy]
   center = [(bounds[1] + bounds[3]) / 2, (bounds[0] + bounds[2]) / 2]

# Folium-Karte erstellen
   m = folium.Map(location=center, zoom_start=12, tiles='OpenStreetMap')

# Autobahnverlauf als Layer hinzufügen
   folium.GeoJson(gdf).add_to(m)

   # Karte speichern und öffnen
   m.save("autobahn_karte.html")
   webbrowser.open("autobahn_karte.html")

def calculate_azimuth(p1, p2):
    """
    Berechnet den Azimutwinkel zwischen zwei Punkten p1 und p2.
    Punkte als Shapely Point (x,y) = (longitude, latitude)
    Ergebnis in Grad (0-360°), 0° = Norden, im Uhrzeigersinn.
    """
    dx = p2.x - p1.x
    dy = p2.y - p1.y
    angle_rad = np.arctan2(dx, dy)  # Achtung Reihenfolge dx, dy!
    angle_deg = np.degrees(angle_rad)
    if angle_deg < 0:
        angle_deg += 360
    return angle_deg

def add_azimut_to_gdf(gdf):
    gdf['azimut'] = np.nan  # Spalte für Azimut anlegen

    for i in range(len(gdf)-1):
        p1 = gdf.geometry.iloc[i]
        p2 = gdf.geometry.iloc[i+1]
        gdf.at[i, 'azimut'] = calculate_azimuth(p1, p2)

    # Optional: Für letzten Punkt z.B. NaN oder 0
    gdf.at[len(gdf)-1, 'azimut'] = np.nan


#lokale run.py
bb_highway = eingabe_bounding_box()
gdf_highway = highway_gdf_in_bb(bb_highway)
gdf = gdf_highway.to_crs(epsg=4326)  # Folium braucht WGS84 (EPSG:4326)
plot_geometry_on_map(gdf) 





# Boundary Boxen für die Autobahn-Abschnitte, händisch aus OSM ermittelt verglichen mit Machbarkeitsstudie Abbildung 2   
#bb_A46 
#6.44730, 51.09131, 6.46292, 51.09533
#6.49446, 51.09495, 6.51060, 51.09845
#6.51206, 51.09495, 6.52021, 51.09786
#
#bb_A44 
#6.474917, 51.03384, 6.50147, 51.085915




