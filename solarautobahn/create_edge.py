# -*- coding: utf-8 -*-
"""
Created on Mon Apr 28 09:11:07 2025

@author: brink

Erstellung des PV-Autobahn-Verlaufs
"""

import osmnx as ox
from shapely.geometry import LineString
from shapely.geometry import box
import geopandas as gpd
import math
import matplotlib.pyplot as plt



# Funktion Fahrtrichtung in Kompassrichtung ermitteln
def bearing_line(line: LineString):
    x1, y1 = line.coords[0] #Startpunk
    x2, y2 = line.coords[-1] #Endpunkt

    # Umrechung Grad in Bogenmaß (nötig für trig-Funktionen)
    x1 = math.radians(x1) 
    y1 = math.radians(y1)
    x2 = math.radians(x2)
    y2 = math.radians(y2)

    # Vektorielle Richtung der Linie
    dLon = x2 - x1
    x = math.sin(dLon) * math.cos(y2)
    y = math.cos(y1) * math.sin(y2) - (math.sin(y1) * math.cos(y2) * math.cos(dLon))

    
    initial_bearing = math.atan2(x, y) # Winkelberechung Bogenmaß
    initial_bearing = math.degrees(initial_bearing) # Umrechnung in Grad
    bearing = (initial_bearing + 360) % 360 # Umrechnung in Kompeasrichtung
    return bearing
 
def eingabe_bounding_box():
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



# Boundary Boxen für A46 Abschnitte, händisch aus OSM ermittelt verglichen mit Machbarkeitsstudie Abbildung 2   
#bb_A46 =[ 
#    box(6.44730, 51.09131, 6.46292, 51.09533),
#    box(6.49446, 51.09495, 6.51060, 51.09845),
#    box(6.51206, 51.09495, 6.52021, 51.09786)
#]

# Nutzung der Funktion eingabe_bounding_box() zur manuellen Eingabe 
bb_A46 = eingabe_bounding_box()


place = "Nordrhein-Westfalen, Germany" 

# Lade nur Autobahnen (highway=motorway)
highways = ox.graph_from_place(place, network_type='drive', custom_filter='["highway"~"motorway"]')

# Extrahiere nur die Kanten (Streckenabschnitte)
edges = ox.graph_to_gdfs(highways, nodes=False)

# Nur A46 herausfiltern
a46_edges = edges[edges['ref'] == 'A 46']

# Liste Kanten in Boundary Box
a46_edges_cut = []

# Gehe durch jede vorher gefilterte Kante und sucht nach Schnittpunkten mit der Boundary Box
for _, edge in a46_edges.iterrows():
    
    for bbox in bb_A46:
            
        if edge.geometry.intersects(bbox["geometry"]):
            richtung = bbox["richtung"]

         # Prüfen, ob die Richtung des Edges zur Bounding Box passt
            bearing = bearing_line(edge.geometry)
         
         # Prüflogik abhängig von der Richtung
            passt = False
            if richtung == "beide":
                passt = True
            elif richtung == "west":
                passt = (bearing <= 225 or bearing >= 315)
            elif richtung == "ost":
                passt = (bearing >= 45 and bearing <= 135)
            elif richtung == "nord":
                passt = (bearing >= 315 or bearing <= 45)
            elif richtung == "süd":
                passt = (bearing >= 135 and bearing <= 225)

            if passt:
                cut_edge = edge.geometry.intersection(bbox["geometry"])
                if not cut_edge.is_empty:
                    a46_edges_cut.append(cut_edge)

if a46_edges_cut:
    a46_edges_cut_gdf = gpd.GeoDataFrame(geometry=a46_edges_cut, crs=edges.crs)
    a46_edges_cut_gdf.plot()
    plt.show()
else:
    print("⚠️ Keine Autobahn mit passender Fahrtrichtung in den angegebenen Bounding Boxes gefunden.")




