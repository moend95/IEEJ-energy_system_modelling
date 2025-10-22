# simulate_solar_highway.py
# GDF-Geometrie Punkte mit Abstand der Lärmschutzwände zuweisen und Azmiut für Punkt und Zuweisen 
#

import sys
import os
import math
from shapely.geometry import LineString

# Imports aus deinen bisherigen Dateien
from solar_highway import fetch_streets

# ----- 1. Solarautobahn laden -----

# Begrenzungsrahmen definieren (wie in solar_highway.py Beispiel)
bbox = "(51.036915, 6.465730, 51.073864, 6.594162)"
#min_lat = 51.034313
#max_lat = 51.085060 # Punkte anzeigen lassen

min_lat = 51.08
max_lat = 51.085060

# 1. Straße laden
clipped_road_gdf = fetch_streets(bbox, min_lat, max_lat, ref_filter="A 44")

# 2. Projektion setzen und umwandeln
clipped_road_gdf = clipped_road_gdf.set_crs(epsg=4326)  # WGS84 (Grad)
clipped_road_gdf = clipped_road_gdf.to_crs(epsg=25832)  # UTM Zone 32N (Meter)

# 3. Linien zusammenführen
from shapely.ops import unary_union
merged_line = unary_union(clipped_road_gdf.geometry)

# 4. Jetzt Punkte setzen etc. (wie du es schon hast!)
# -----  Punkte entlang der Linie alle 2 Meter erzeugen -----

total_length = merged_line.length
print(f"Gesamtlänge der Linie: {total_length:.2f} Meter")

# Punkte alle 2 - 5 Meter
step_size = 4
points = [merged_line.interpolate(distance) for distance in range(0, int(total_length), step_size)]

print(f"Anzahl erzeugter Punkte: {len(points)}")


# ----- 5. Winkel an jedem Punkt berechnen -----
angles = []

for i in range(len(points) - 1): # Zwischen je zwei Punkten wird der Winkel berechnet, Süden = 180°
    point1 = points[i]
    point2 = points[i + 1]

    dx = point2.x - point1.x # Wie viel weiter rechts oder links ist Punkt 2 im Vergleich zu Punkt 1?
    dy = point2.y - point1.y # Wie viel höher oder tiefer liegt Punkt 2 im Vergleich zu Punkt 1?

    theta_rad = math.atan2(dy, dx) # atan2 gibt den Winkel in Bogenmaß (Radiant) zwischen der Linie und der X-Achse (Osten) an. Osten ist 0°, Norden 90°, Westen 180°, Süden 270° (im mathematischen Standard)
    theta_deg = math.degrees(theta_rad) # Umrechnung von Radiant auf Grad

    # Umrechnen, sodass Süden 180° ist, Norden = 0°, Osten = 90°, Westen = 270°
    azimut_tangent = (90 - theta_deg) % 360
    azimut_normal = (azimut_tangent + 90) % 360  # oder -90 je nach gewünschter Richtung

    angles.append(azimut_normal)


# ----- 6. Ausgabe: Punkte + Winkel -----

for idx, (pt, az) in enumerate(zip(points, angles)):
    print(f"Punkt {idx}: ({pt.x:.6f}, {pt.y:.6f}) --> Ausrichtung: {az:.2f}°")

print(f"\nInsgesamt {len(angles)} Richtungswinkel berechnet.")


# ----- 7. Punkte + Winkel speichern als CSV -----

import pandas as pd

# Punkte + Winkel kombinieren
data = []

for i in range(len(angles)):
    punkt = points[i]
    azimut = angles[i]
    latitude = punkt.y  # Achtung! In UTM ist das Nordwert (y)
    longitude = punkt.x # In UTM ist das Ostwert (x)
    data.append((latitude, longitude, azimut))

# In DataFrame umwandeln
punkte_df = pd.DataFrame(data, columns=["latitude", "longitude", "azimut"])

# Speichern als CSV in Input-Ordner
punkte_df.to_csv('../Input/punkte_mit_azimut.csv', index=False)

print("\nPunkte und Winkel wurden erfolgreich als CSV gespeichert!")




# Punkte als GeoDataFrame erstellen und anzeigen lassen:

import matplotlib.pyplot as plt
import geopandas as gpd
from shapely.geometry import Point

geo_points = gpd.GeoDataFrame(
    geometry=[Point(pt.x, pt.y) for pt in points],
    crs=clipped_road_gdf.crs
)

# Plot
fig, ax = plt.subplots(figsize=(12, 8))
clipped_road_gdf.plot(ax=ax, color='gray', linewidth=2, label='Autobahn A44')

geo_points.plot(ax=ax, color='red', markersize=5, label='Messpunkte')

# Pfeile (Richtungsvektoren) anzeigen
import numpy as np

# Richtungspfeile berechnen (Azimut → Richtung in X/Y)
arrow_length = 5  # Länge der Pfeile in Metern (anpassbar)
arrow_dx = [arrow_length * math.cos(math.radians((90 - a))) for a in angles]
arrow_dy = [arrow_length * math.sin(math.radians((90 - a))) for a in angles]

# Pfeile an jedem Punkt zeichnen (nur jeden n-ten für bessere Lesbarkeit)
for i in range(0, len(points)-1, 10):  # z. B. jeden 10. Punkt
    ax.arrow(points[i].x, points[i].y, arrow_dx[i], arrow_dy[i],
             head_width=2, head_length=3, fc='blue', ec='blue')

# Achsenbeschriftung und Titel
ax.set_title('Messpunkte entlang der Solarautobahn', fontsize=16)
ax.set_xlabel('Ostwert [m]')
ax.set_ylabel('Nordwert [m]')
ax.legend()
plt.grid(True)
plt.axis('equal')

plt.show()
