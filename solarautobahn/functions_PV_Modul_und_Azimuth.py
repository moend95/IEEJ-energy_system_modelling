# azimut_berechnung.py

import geopandas as gpd
import pandas as pd
import numpy as np
import os
from shapely.geometry import Point, LineString
from shapely.ops import unary_union
import math
import matplotlib.pyplot as plt


def calculate_azimut_from_geojson(geojson_path, pv_typ, step_size, output_csv_path):
    gdf = gpd.read_file(geojson_path)
    gdf = gdf.to_crs(epsg=25832)
    merged_line = unary_union(gdf.geometry)

    total_length = merged_line.length
    points = [merged_line.interpolate(distance) for distance in range(0, int(total_length), step_size)]

    azimut_list = []
    tilt_list = []
    pv_typ_list = []
    point_list = []

    for i in range(len(points)-1):
        p1 = points[i]
        p2 = points[i+1]

        dx = p2.x - p1.x
        dy = p2.y - p1.y
        theta_rad = math.atan2(dy, dx)
        theta_deg = math.degrees(theta_rad)
        azimut_tangent = (90 - theta_deg) % 360

        if pv_typ == "dach":
            azimut = 180
            tilt = 20
            azimut_list.append(azimut)
            tilt_list.append(tilt)
            pv_typ_list.append(pv_typ)
            point_list.append(p1)

        elif pv_typ == "bifazial":
            azimut_a = (azimut_tangent + 90) % 360
            azimut_b = (azimut_tangent + 270) % 360
            for azimut in [azimut_a, azimut_b]:
                azimut_list.append(azimut)
                tilt_list.append(90)
                pv_typ_list.append("bifazial")
                point_list.append(p1)

        else:  # "senkrecht"
            azimut = (azimut_tangent + 90) % 360
            tilt = 90
            azimut_list.append(azimut)
            tilt_list.append(tilt)
            pv_typ_list.append(pv_typ)
            point_list.append(p1)

    data = [
        (pt.y, pt.x, az, tilt, typ) for pt, az, tilt, typ in zip(point_list, azimut_list, tilt_list, pv_typ_list)
    ]
    df = pd.DataFrame(data, columns=["latitude", "longitude", "azimut", "tilt", "pv_typ"])
    df.to_csv(output_csv_path, index=False)
    print(f"Azimut-Punkte gespeichert unter: {output_csv_path}")

    fig, ax = plt.subplots(figsize=(10, 8))
    ax.set_title(f"PV-Punkte mit Azimut ({pv_typ})")
    ax.set_xlabel("X [m]")
    ax.set_ylabel("Y [m]")

    for i in range(0, len(point_list), 10):
        if isinstance(azimut_list[i], (int, float)):
            dx = 5 * math.cos(math.radians(90 - azimut_list[i]))
            dy = 5 * math.sin(math.radians(90 - azimut_list[i]))
            ax.arrow(point_list[i].x, point_list[i].y, dx, dy, head_width=2, fc='blue', ec='blue')

    geo_gdf = gpd.GeoDataFrame(geometry=[Point(pt.x, pt.y) for pt in point_list], crs=gdf.crs)
    gdf.plot(ax=ax, color='gray', linewidth=2)
    geo_gdf.plot(ax=ax, color='red', markersize=5)
    plt.grid(True)
    plt.axis('equal')
    plt.show()



def run_azimut_berechnung(base_path):
    geojson_dir = os.path.join(base_path, "geometrien")
    files = [f for f in os.listdir(geojson_dir) if f.endswith(".geojson")]
    if not files:
        print("Keine GeoJSON-Dateien gefunden.")
        return

    print("Verfügbare GeoJSON-Dateien:")
    for i, f in enumerate(files):
        print(f"{i + 1}. {f}")

    auswahl = int(input("Wähle die Nummer der Datei: ")) - 1
    geojson_path = os.path.join(geojson_dir, files[auswahl])

    pv_typ = input("Welchen PV-Typ möchtest du simulieren? (dach / senkrecht / bifazial): ").strip().lower()
    step_size = int(input("Punktabstand in Metern (z.B. 4): "))

    output_csv_path = os.path.join(base_path, "punkte_mit_azimut.csv")

    calculate_azimut_from_geojson(geojson_path, pv_typ, step_size, output_csv_path)


# Optionaler Direktstart:------------------------------------------
if __name__ == "__main__":
    run_azimut_berechnung(
        base_path=r"C:\Users\sarah\Documents\GitHub\IEEJ-energy_system_modelling\Input"
    )
