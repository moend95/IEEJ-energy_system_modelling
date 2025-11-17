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
class AzimutCalculator:

    def __init__(self, geojson_path, pv_typ, step_size, output_csv_path):
        self.geojson_path = geojson_path
        self.pv_typ = pv_typ.lower()
        self.step_size = step_size
        self.output_csv_path = output_csv_path

        self.gdf = None
        self.merged_line = None
        self.number_of_points = None
        self.azimut_list = []
        self.tilt_list = []
        self.pv_typ_list = []
        self.point_list = []

    def load_geometry(self):
        self.gdf = gpd.read_file(self.geojson_path)
        self.gdf = self.gdf.to_crs(epsg=25832)              # EPSG:25832 = UTM Zone 32N, metrisches Koordinatensystem
        self.merged_line = unary_union(self.gdf.geometry)   # unary_union verschmilzt mehere Linien in eine Linien-Geometrie
        return self.merged_line

    def interpolate_points(self):
        total_length = self.merged_line.length
        self.number_of_points = [
            self.merged_line.interpolate(distance)              # interpolate(distance) erzeugt Punkte im Abstand von step_size entlang dieser Linie
            for distance in range(0, int(total_length), self.step_size)
        ]
        return self.number_of_points

    #Hilfsfunktion Anhängen vn Modulinformationen zum verkürzen von calculate_azimut
    def _append_point(self, point, azimut, tilt):
        self.azimut_list.append(azimut)
        self.tilt_list.append(tilt)
        self.pv_typ_list.append(self.pv_typ)
        self.point_list.append(point)

    def calculate_azimut(self):
        # Punkte durchlaufen und Azimut berechnen:
        for i in range(len(self.number_of_points) - 1):
            p1 = self.number_of_points[i]
            p2 = self.number_of_points[i + 1]

        dx = p2.x - p1.x
        dy = p2.y - p1.y
        theta_rad = math.atan2(dy, dx)  # atan2(dy, dx) gibt dir den Winkel in Bogenmaß
        theta_deg = math.degrees(theta_rad)  # Umwandlung in Grad
        azimut_tangent = ( 90 - theta_deg) % 360  # Umrechnung in Azimut: Norden = 0°, Osten = 90°, Süden = 180°, Westen = 270°

        # Azimut & Neigung je nach PV-Typ setzen:
        if self.pv_typ == "dach":
            self._append_point(point = p1, azimut = 180, tilt = 20)

        elif self.pv_typ == "bifazial":
            azimut_a = (azimut_tangent + 90) % 360
            azimut_b = (azimut_tangent + 270) % 360
            for azimut in [azimut_a, azimut_b]:
                self._append_point(point = p1, azimut = azimut, tilt = 90)

        else:  # senkrecht
            azimut = (azimut_tangent + 90) % 360
            self._append_point(point = p1, azimut = azimut,tilt = 90)


    def export_to_csv(self):
        # Punkte als CSV speichern:
        data = [
            (pt.y, pt.x, az, tilt, typ) for pt, az, tilt, typ in zip(self.point_list, self.azimut_list, self.tilt_list, self.pv_typ_list)
        ]
        df = pd.DataFrame(data, columns=["latitude", "longitude", "azimut", "tilt", "pv_typ"])
        df.to_csv(self.output_csv_path, index=False)
        print(f"Azimut-Punkte gespeichert unter: {self.output_csv_path}")
        return df

class AzimutVisualizer:
    def __init__(self, calculator: AzimutCalculator):
        self.calc = calculator

    def plot(self, every_nth_arrow = 10):  #Funktionsinformation: nur jeden x-ten (=10) Richtungspfeil anzeigen
        gdf = self.calc.gdf
        points = self.calc.point_list
        azimuts = self.calc.azimut_list
        pv_typ = self.calc.pv_typ

        fig, ax = plt.subplots(figsize=(10, 8))
        ax.set_title(f"PV-Punkte mit Azimut ({pv_typ})")
        ax.set_xlabel("X [m]")
        ax.set_ylabel("Y [m]")

        # Richtungspfeile zeichnen
        for i in range(0, len(points), every_nth_arrow):
            if isinstance(azimuts[i], (int, float)):
                dx = 5 * math.cos(math.radians(90 - azimuts[i]))
                dy = 5 * math.sin(math.radians(90 - azimuts[i]))
                ax.arrow(points[i].x, points[i].y, dx, dy, head_width=2, fc="blue", ec="blue")

        # Linien & Punkte
        geo_gdf = gpd.GeoDataFrame(geometry=[Point(pt.x, pt.y) for pt in points], crs=gdf.crs)
        gdf.plot(ax=ax, color="gray", linewidth=2)
        geo_gdf.plot(ax=ax, color="red", markersize=5)
        plt.grid(True)
        plt.axis("equal")
        plt.show()

class AzimutRunner:
    def __init__(self, base_path):
        self.base_path = base_path

    def run(self):
        geojson_dir = os.path.join(self.base_path, "geometrien")
        files = [f for f in os.listdir(geojson_dir) if f.endswith(".geojson")]

        if not files:
            print("❌ Keine GeoJSON-Dateien gefunden.")
            return

        print("Verfügbare GeoJSON-Dateien:")
        for i, f in enumerate(files, start=1):
            print(f"{i}. {f}")

        # Benutzer wählt eine Datei - Skript zieht sich dann den vollständigen Pfad zu dieser Datei
        auswahl = int(input("Wähle die Nummer der Datei: ")) - 1
        geojson_path = os.path.join(geojson_dir, files[auswahl])

        # PV-Typ und Step_size wählen:
        pv_typ = input("Welchen PV-Typ möchtest du simulieren? (dach / senkrecht / bifazial): ").strip().lower()
        step_size = int(input("Punktabstand in Metern (z.B. 4): "))
        # Zielpfad für die Ergebnisdatei
        output_csv_path = os.path.join(self.base_path, "punkte_mit_azimut.csv")

        #Hauptlogik
        calc = AzimutCalculator(geojson_path, pv_typ, step_size, output_csv_path)
        calc.load_geometry()
        calc.interpolate_points()
        calc.calculate_azimut()
        calc.export_to_csv()

        vis = AzimutVisualizer(calc)
        vis.plot()




# ------------------- Optionaler Direktstart:------------------------------------------
if __name__ == "__main__":
        base_path= "../Input"
        runner = AzimutRunner(base_path)
        runner.run()

