# -*- coding: utf-8 -*-
"""
Created on Mon Apr 28 09:11:07 2025
@author: Jannis Brinkmann, Sarah Maxara
Ziel: Automatische Auswahl und Zusammenführung vordefinierter Autobahnabschnitte
als aufrufbare Funktion für das Hauptskript.
"""

import os
import osmnx as ox
import geopandas as gpd
import numpy as np
from shapely.geometry import LineString, box
from shapely.ops import unary_union
import math
import folium
import webbrowser

# ------------------------ Hilfsfunktionen ------------------------ #
def apply_oneway_orientation(geom, oneway):
    coords = list(geom.coords)
    if oneway == -1:
        coords = coords[::-1]
    return LineString(coords)

def calculate_bearing(geom):
    x1, y1 = geom.coords[0]
    x2, y2 = geom.coords[-1]
    angle = math.degrees(math.atan2(x2 - x1, y2 - y1))
    return (angle + 360) % 360

def is_within_direction(angle, target, tolerance=30):
    delta = abs((angle - target + 180) % 360 - 180)
    return delta <= tolerance

def richtung_to_angle(richtung):
    mapping = {"nord": 0, "ost": 90, "süd": 180, "west": 270}
    return mapping.get(richtung, None)

# ------------------------ GeoDataFrame-Erzeugung ------------------------ #
def highway_gdf_in_bb(list_indiv_bb):
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

        richtung = bbox["richtung"]
        passt_edges = []

        for edge, cut_geom in relevant_edges:
            oneway = edge.get('oneway', False)
            oneway = -1 if str(oneway) == '-1' else (1 if oneway is True else 0)
            oriented_geom = apply_oneway_orientation(cut_geom, oneway)
            angle = calculate_bearing(oriented_geom)
            if richtung == "beide" or (richtung_to_angle(richtung) is not None and is_within_direction(angle, richtung_to_angle(richtung), tolerance=45)):
                passt_edges.append({
                    "geometry": oriented_geom,
                    "richtung": richtung,
                    "ref": edge.get("ref", "")
                })

        highway_edges_cut.extend(passt_edges)

    return gpd.GeoDataFrame(highway_edges_cut, crs=highway_edges.crs) if highway_edges_cut else gpd.GeoDataFrame(columns=["geometry", "richtung", "ref"])

# ------------------------ Karte anzeigen ------------------------ #
def plot_geometry_on_map(gdf, map_filename="karte.html"):
    gdf_4326 = gdf.to_crs(epsg=4326)
    if gdf_4326.empty:
        print("Das GeoDataFrame ist leer. Keine Geometrien zum Anzeigen.")
        return
    bounds = gdf.total_bounds
    center = [(bounds[1] + bounds[3]) / 2, (bounds[0] + bounds[2]) / 2]
    m = folium.Map(location=center, zoom_start=12, tiles='OpenStreetMap')
    folium.GeoJson(gdf_4326).add_to(m)
    m.save(map_filename)
    webbrowser.open(map_filename)

# ------------------------ Speicherfunktion ------------------------ #
def save_geometry(gdf, base_path):
    autobahn = gdf["ref"].iloc[0].replace(" ", "").lower()
    richtung = gdf["richtung"].iloc[0].lower()
    filename = f"{autobahn}_{richtung}.geojson"
    output_path = os.path.join(base_path, "geometrien", filename)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    gdf.to_file(output_path, driver="GeoJSON")
    print(f"GeoDataFrame gespeichert unter: {output_path}")
    return output_path

# ------------------------ Vordefinierte Abschnitte ------------------------ #
vordefinierte_abschnitte = {
    "A46": {
        "abschnitte": [
            (6.44730, 51.09131, 6.46292, 51.09533),
            (6.49446, 51.09495, 6.51060, 51.09845),
            (6.51206, 51.09495, 6.52021, 51.09786),
        ]
    },
    "A44": {
        "abschnitte": [
            (6.474917, 51.03384, 6.50147, 51.085915),
        ]
    }
}

# ------------------------ Hauptfunktion zum Aufruf ------------------------ #
def run_autobahn_geometrie(base_path):
    print("Verfügbare vordefinierte Abschnitte:")
    for i, name in enumerate(vordefinierte_abschnitte):
        print(f"{i + 1}. {name}")
    auswahl = int(input("Wähle hier die Nummer des zu untersuchenden Autobahn: ")) - 1
    key = list(vordefinierte_abschnitte.keys())[auswahl]
    info = vordefinierte_abschnitte[key]
    richtung = input("Welche Richtung willst du untersuchen? (nord/sued/ost/west/beide): ").strip().lower()

    bbox_liste = [{
        "geometry": box(*coords),
        "richtung": richtung
    } for coords in info["abschnitte"]]

    gdf = highway_gdf_in_bb(bbox_liste)
    if not gdf.empty:
        gdf = gdf.to_crs(epsg=4326)
        plot_geometry_on_map(gdf)
        save_geometry(gdf, base_path=base_path)
    else:
        print("Keine Daten gefunden.")


# # um funktions-skript hier zu testen: muss man rausnehmen wenn run skript steht
# if __name__ == "__main__":
#     run_autobahn_geometrie(
#         base_path=r"C:\Users\sarah\Documents\GitHub\IEEJ-energy_system_modelling\Input"
#     )
