from pvlib.location import Location
from pvlib.pvsystem import PVSystem
from pvlib.modelchain import ModelChain
import pvlib
import geopandas as gpd
import pandas as pd
import numpy as np
import os
from shapely.geometry import Point, LineString
from shapely.ops import unary_union
import math
import matplotlib.pyplot as plt

class PVType:
    """
    Beschreibt einen vordefinierten PV-Typ mit typischen Eigenschaften
    (z. B. Bifazialität, Azimut und Neigung für bis zu zwei Modulflächen).
    """

    def __init__(self, id_: int, name: str, bifazial: float, azimut=None, tilt=None,
                 module: str = None, inverter: str = None, temp_model: str = None, modules_per_string: int = None, strings_per_inverter: int = None,
                 ):
        self.id = id_
        self.name = name
        self.bifazial = bifazial
        self.azimut = azimut
        self.tilt = tilt
        self.module = module
        self.inverter = inverter
        self.temp_model = temp_model
        self.modules_per_string = modules_per_string
        self.strings_per_inverter  = strings_per_inverter


    def __str__(self):
        """Wie das Objekt angezeigt wird, z. B. in print()."""
        return f"[{self.id}] {self.name}"

# ----------------------------------------------------------
# Globale Liste aller vordefinierten PV-Typen
# ----------------------------------------------------------
sandia_modules = pvlib.pvsystem.retrieve_sam('SandiaMod')
cec_inverters = pvlib.pvsystem.retrieve_sam('CECInverter')
temp_modules = pvlib.temperature.TEMPERATURE_MODEL_PARAMETERS['sapm']

#ANPASSEN! NOCH NICHT KORREKT
PV_TYPEN = [
    PVType(1, "Windschutzwand",                         0,   "variabel", 90, "sandia_modules['Canadian_Solar_CS6X_300M__2013_']",   "cec_inverters['ABB__PVI_3_0_OUTD_S_US__208V_']",       "temp_modules['open_rack_glass_glass']",   4, 2),
    PVType(2, "Schallschutzwand",                       0, "variabel", 90, "sandia_modules['Canadian_Solar_CS6X_300M__2013_']",   "cec_inverters['ABB__PVI_3_0_OUTD_S_US__208V_']",       "temp_modules['open_rack_glass_glass']",   4, 1),
    PVType(3, "Schallschutzwand_Dach",                  0, "variabel", 30, "sandia_modules['Canadian_Solar_CS6X_300M__2013_']",   "cec_inverters['ABB__PVI_3_0_OUTD_S_US__208V_']",       "temp_modules['open_rack_glass_glass']",   4, 2),
    PVType(4, "Böschung",                               0, "variabel", 30, "sandia_modules['Canadian_Solar_CS6X_300M__2013_']",   "cec_inverters['ABB__PVI_3_0_OUTD_S_US__208V_']",       "temp_modules['close_mount_glass_glass']", 5, 3),
    PVType(5, "Freifläche_bzw_Agri_geneigt",           0,   180,        90, "sandia_modules['Canadian_Solar_CS6X_300M__2013_']",   "cec_inverters['ABB__PVI_3_0_OUTD_S_US__208V_']",       "temp_modules['open_rack_glass_glass']",   10,5),
    PVType(6, "Agri_vertikal",                          0,   90,         90, "sandia_modules['Canadian_Solar_CS6X_300M__2013_']",   "cec_inverters['ABB__PVI_3_0_OUTD_S_US__208V_']",       "temp_modules['open_rack_glass_glass']",   10,5),        ]

class WeatherFetcher:
    def __init__(self):

   # def get_weather_data(self):

    #    return weatherdata #Jahresverlauf 10min ghi,dhi, dni


class AzimutCalculator:

    def __init__(self, geojson_path, step_size, output_csv_path):
        self.geojson_path = geojson_path
        self.step_size = step_size
        self.output_csv_path = output_csv_path

        self.gdf = None
        self.merged_line = None
        self.number_of_points = None
        self.point_azimut_list = []

    def load_geometry(self):
        self.gdf = gpd.read_file(self.geojson_path)
        self.gdf = self.gdf.to_crs(epsg=25832)  # EPSG:25832 = UTM Zone 32N, metrisches Koordinatensystem
        self.merged_line = unary_union(
            self.gdf.geometry)  # unary_union verschmilzt mehere Linien in eine Linien-Geometrie
        return self.merged_line

    def interpolate_points(self):
        total_length = self.merged_line.length
        self.number_of_points = [
            self.merged_line.interpolate(distance)
            # interpolate(distance) erzeugt Punkte im Abstand von step_size entlang dieser Linie
            for distance in range(0, int(total_length), self.step_size)
        ]
        return self.number_of_points

    # Hilfsfunktion Anhängen vn Modulinformationen zum verkürzen von calculate_azimut
    def _append_point(self, point, azimut):
        self.point_azimut_list.append((point, azimut))

    def calculate_azimut(self):
        # Punkte durchlaufen und Azimut berechnen:
        for i in range(len(self.number_of_points) - 1):
            p1 = self.number_of_points[i]
            p2 = self.number_of_points[i + 1]

        dx = p2.x - p1.x
        dy = p2.y - p1.y
        theta_rad = math.atan2(dy, dx)  # atan2(dy, dx) gibt dir den Winkel in Bogenmaß
        theta_deg = math.degrees(theta_rad)  # Umwandlung in Grad
        azimut_tangent = (90 - theta_deg) % 360  # Umrechnung in Azimut: Norden = 0°, Osten = 90°, Süden = 180°, Westen = 270°

        # Azimut & Neigung je nach PV-Typ setzen:
        if self.pv_typ == "dach":
            self._append_point(point=p1, azimut=180)

        elif self.pv_typ == "bifazial":
            azimut_a = (azimut_tangent + 90) % 360
            azimut_b = (azimut_tangent + 270) % 360
            for azimut in [azimut_a, azimut_b]:
                self._append_point(point=p1, azimut=azimut)

        else:  # senkrecht
            azimut = (azimut_tangent + 90) % 360
            self._append_point(point=p1, azimut=azimut)


class PV_System:
    # Initialisierung mit GDF als .geojason und pvtypes als Liste pvtypes = [2, 3, 4]
    def __init__(self, gdf, pvtypes, step_size):
        self.gdf = gdf
        self.pvtypes = pvtypes
        self.step_size = step_size


    #def calculatePV(self):

      #  calc = AzimutCalculator(gdf, step_size)
      #  calc.calculate_azimut()

        for

     #   fetcher = WeatherFetcher()
     #   weatherdata = get_weather_data.fetcher

            mc = ModelChain(system, location)
            mc.run_model(weatherData)
            mc.results

