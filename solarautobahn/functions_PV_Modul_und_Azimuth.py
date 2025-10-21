# azimut_berechnung.py
# (hier fehlt noch eine Abfrage für den PV-Typ: Böschung!)

import geopandas as gpd
import pandas as pd
import numpy as np
import os
from shapely.geometry import Point, LineString
from shapely.ops import unary_union
import math
import matplotlib.pyplot as plt

# Haupt-Funktionsaufbau - läd GeoJSON-Daei, interpoliert entlang Linie Punkte im gewünschten Abstand, berechnet Azimut und speichert als CSV:
def calculate_azimut_from_geojson(geojson_path, pv_typ, step_size, output_csv_path):
    gdf = gpd.read_file(geojson_path)
    gdf = gdf.to_crs(epsg=25832)                # EPSG:25832 = UTM Zone 32N, metrisches Koordinatensystem
    merged_line = unary_union(gdf.geometry)     # unary_union verschmilzt mehere Linien in eine Linien-Geometrie

    total_length = merged_line.length
    points = [merged_line.interpolate(distance) for distance in range(0, int(total_length), step_size)]     # interpolate(distance) erzeugt Punkte im Abstand von step_size entlang dieser Linie

    # Initialisierung leerer Listen für spätere Speicherung der Ergebnisse:
    azimut_list = []
    tilt_list = []
    pv_typ_list = []
    point_list = []

    # Punkte durchlaufen und Azimut berechnen:
    for i in range(len(points)-1):
        p1 = points[i]
        p2 = points[i+1]

        dx = p2.x - p1.x
        dy = p2.y - p1.y
        theta_rad = math.atan2(dy, dx)              # atan2(dy, dx) gibt dir den Winkel in Bogenmaß
        theta_deg = math.degrees(theta_rad)         # Umwandlung in Grad
        azimut_tangent = (90 - theta_deg) % 360     # Umrechnung in Azimut: Norden = 0°, Osten = 90°, Süden = 180°, Westen = 270°

        # Azimut & Neigung je nach PV-Typ setzen:
        if pv_typ == "dach":
            azimut = 180
            tilt = 20
            azimut_list.append(azimut)
            tilt_list.append(tilt)
            pv_typ_list.append(pv_typ)
            point_list.append(p1)

        # Bifazial: zwei Richtungen (z.B. Ost/West oder Nord/Süd), 90° Tilt (senkrecht).
        # Hier startet eine Schleife, die zwei Werte durchläuft:
        # Durch Schleife = zwei Azimut-Einträge für denselben Punkt, einmal für jede Seite der bifazialen Anlage:
        elif pv_typ == "bifazial":
            azimut_a = (azimut_tangent + 90) % 360      # Bsp.: Straße verläuft von West nach Ost → azimut_tangent = 90° --> Dann: azimut_a = (90 + 90) % 360 = 180° → Süden, azimut_b = (90 + 270) % 360 = 0° → Norden
            azimut_b = (azimut_tangent + 270) % 360
            for azimut in [azimut_a, azimut_b]:
                azimut_list.append(azimut)
                tilt_list.append(90)            # Neigung liegt auf 90° (senkrecht)
                pv_typ_list.append("bifazial")  # Der Typ der Anlage wird in die Liste geschrieben
                point_list.append(p1)           # Für beide Richtungen wird derselbe Punkt verwendet

        else:  # "senkrecht"  - wenn nicht bifazial oder dach dann senkrecht mit einer Ausrichtungsseite
            azimut = (azimut_tangent + 90) % 360
            tilt = 90
            azimut_list.append(azimut)
            tilt_list.append(tilt)
            pv_typ_list.append(pv_typ)
            point_list.append(p1)


# Punkte als CSV speichern:
    data = [
        (pt.y, pt.x, az, tilt, typ) for pt, az, tilt, typ in zip(point_list, azimut_list, tilt_list, pv_typ_list)
    ]
    df = pd.DataFrame(data, columns=["latitude", "longitude", "azimut", "tilt", "pv_typ"])
    df.to_csv(output_csv_path, index=False)
    print(f"Azimut-Punkte gespeichert unter: {output_csv_path}")

# Visualisierung mit Matplotlib:
    fig, ax = plt.subplots(figsize=(10, 8))
    ax.set_title(f"PV-Punkte mit Azimut ({pv_typ})")
    ax.set_xlabel("X [m]")
    ax.set_ylabel("Y [m]")

    for i in range(0, len(point_list), 10):
        if isinstance(azimut_list[i], (int, float)):
            dx = 5 * math.cos(math.radians(90 - azimut_list[i]))
            dy = 5 * math.sin(math.radians(90 - azimut_list[i]))
            ax.arrow(point_list[i].x, point_list[i].y, dx, dy, head_width=2, fc='blue', ec='blue')

    # Punkte und Linien darstellen
    geo_gdf = gpd.GeoDataFrame(geometry=[Point(pt.x, pt.y) for pt in point_list], crs=gdf.crs)
    gdf.plot(ax=ax, color='gray', linewidth=2)
    geo_gdf.plot(ax=ax, color='red', markersize=5)
    plt.grid(True)
    plt.axis('equal')
    plt.show()


# -------------------------- Funktionsdefinition ----------------------------------------------
# steuert die Auswahl der GeoJSON-Datei, Benutzerabfragen, und ruft die Hauptfunktion: calculate_azimut_from_geojson() auf
def run_azimut_berechnung(base_path):
    geojson_dir = os.path.join(base_path, "geometrien")                             # Es wird der Unterordner "geometrien" im base_path gebildet.
    files = [f for f in os.listdir(geojson_dir) if f.endswith(".geojson")]          # Es werden alle .geojson-Dateien in diesem Ordner gesammelt.
    if not files:                                                                   # Wenn keine Dateien vorhanden sind, wird eine Meldung ausgegeben
        print("Keine GeoJSON-Dateien gefunden.")
        return

    print("Verfügbare GeoJSON-Dateien:")                                  # Ausgabe aller gefundenen Dateien
    for i, f in enumerate(files):
        print(f"{i + 1}. {f}")

    # Benutzer wählt eine Datei - Skript zieht sich dann den vollständigen Pfad zu dieser Datei
    auswahl = int(input("Wähle die Nummer der Datei: ")) - 1
    geojson_path = os.path.join(geojson_dir, files[auswahl])

    # PV-Typ und Step_size wählen:
    pv_typ = input("Welchen PV-Typ möchtest du simulieren? (dach / senkrecht / bifazial): ").strip().lower()
    step_size = int(input("Punktabstand in Metern (z.B. 4): "))
    # Zielpfad für die Ergebnisdatei
    output_csv_path = os.path.join(base_path, "punkte_mit_azimut.csv")

    # Die Hauptfunktion wird aufgerufen und bekommt: - die gewählte GeoJSON-Datei, den gewünschten PV-Typ, den Abstand der Punkt und wohin das Ergebnis gespeichert werden soll.
    calculate_azimut_from_geojson(geojson_path, pv_typ, step_size, output_csv_path)


# ------------------- Optionaler Direktstart:------------------------------------------
if __name__ == "__main__":
    run_azimut_berechnung(
        base_path=r"C:\Users\sarah\Documents\GitHub\IEEJ-energy_system_modelling\Input"
    )
