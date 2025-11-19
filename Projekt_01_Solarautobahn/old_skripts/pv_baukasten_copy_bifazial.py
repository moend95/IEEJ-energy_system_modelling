import pvlib
import geopandas as gpd
from shapely.ops import unary_union
import math
import os
import matplotlib.pyplot as plt


sandia_modules = pvlib.pvsystem.retrieve_sam('SandiaMod')
cec_inverters = pvlib.pvsystem.retrieve_sam('CECInverter')
temp_models_sapm = pvlib.temperature.TEMPERATURE_MODEL_PARAMETERS['sapm']


class PVType:
    """
    Beschreibt einen vordefinierten PV-Typ mit typischen Eigenschaften.
    - azimut: entweder fester Winkel (z. B. 180) oder "variabel" (= entlang der Geometrie)
    - tilt: fester Neigungswinkel (in °)
    - module, inverter, temp_model: Namen/Keys, um später die Parameter zu holen
    """

    def __init__(
        self,
        id_: int,
        name: str,
        bifazial: float,              # einfacher Mehrertragsfaktor (0.0 = aus)
        azimut=None,
        tilt=None,
        module: str = None,
        inverter: str = None,
        temp_model: str = None,
        modules_per_string: int = None,
        strings_per_inverter: int = None,
        # NEU:
        is_bifacial_detailed: bool = False,   # True = pvlib/pvfactors benutzen
        bifaciality: float | None = None,     # z.B. 0.75
        gcr: float | None = None,             # ground coverage ratio
        row_height: float | None = None,      # m
        row_width: float | None = None,       # m
        albedo: float | None = None,          # 0.2–0.3 etc.
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
        self.strings_per_inverter = strings_per_inverter

        # neu:
        self.is_bifacial_detailed = is_bifacial_detailed
        self.bifaciality = bifaciality
        self.gcr = gcr
        self.row_height = row_height
        self.row_width = row_width
        self.albedo = albedo

    def __str__(self):
        return f"[{self.id}] {self.name}"


PV_TYPEN = [
    PVType(
        1,
        "Windschutzwand",
        bifazial=0,                 # Faktor für prozentual mehr erzeugung dadurch das es bifazial ist
        azimut="variabel",
        tilt=90,
        module="Canadian_Solar_CS6X_300M__2013_",
        inverter="ABB__PVI_3_0_OUTD_S_US__208V_",
        temp_model="open_rack_glass_glass",
        modules_per_string=4,
        strings_per_inverter=1,
        # NEU:
        is_bifacial_detailed=True,
        bifaciality=0.75,
        gcr=0.35,
        row_height=3.0,
        row_width=4.0,
        albedo=0.2,
    ),

    PVType(
        2,
        "Schallschutzwand",
        bifazial=0.0,
        azimut="variabel",
        tilt=90,
        module="Canadian_Solar_CS6X_300M__2013_",
        inverter="ABB__PVI_3_0_OUTD_S_US__208V_",
        temp_model="open_rack_glass_glass",
        modules_per_string=4,
        strings_per_inverter=1,
    ),
    PVType(
        3,
        "Schallschutzwand_Dach",
        bifazial=0.0,
        azimut="variabel",
        tilt=30,
        module="Canadian_Solar_CS6X_300M__2013_",
        inverter="ABB__PVI_3_0_OUTD_S_US__208V_",
        temp_model="open_rack_glass_glass",
        modules_per_string=4,
        strings_per_inverter=2,
    ),
    PVType(
        4,
        "Böschung",
        bifazial=0.0,
        azimut="variabel",
        tilt=30,
        module="Canadian_Solar_CS6X_300M__2013_",
        inverter="ABB__PVI_3_0_OUTD_S_US__208V_",
        temp_model="close_mount_glass_glass",
        modules_per_string=5,
        strings_per_inverter=3,
    ),
    PVType(
        5,
        "Freifläche_bzw_Agri_geneigt",
        bifazial=0.0,
        azimut=180,
        tilt=30,  # 90 war hier eher ein Vertikal-Wert – kannst du anpassen, wie ihr wollt
        module="Canadian_Solar_CS6X_300M__2013_",
        inverter="ABB__PVI_3_0_OUTD_S_US__208V_",
        temp_model="open_rack_glass_glass",
        modules_per_string=10,
        strings_per_inverter=5,
        # NEU:
        is_bifacial_detailed=True,  # <- WICHTIG
        bifaciality=0.75,
        gcr=0.35,
        row_height=3.0,
        row_width=4.0,
        albedo=0.2,
    ),
    PVType(
        6,
        "Agri_vertikal",
        bifazial=0.0,
        azimut=90,  # oder "variabel", je nach späterem Konzept
        tilt=90,
        module="Canadian_Solar_CS6X_300M__2013_",
        inverter="ABB__PVI_3_0_OUTD_S_US__208V_",
        temp_model="open_rack_glass_glass",
        modules_per_string=10,
        strings_per_inverter=5,
    ),

    PVType(
        7,
        "Haus_Dach",
        bifazial=0.0,
        azimut=180,  # Süddach
        tilt=30,
        module="Canadian_Solar_CS6X_300M__2013_",
        inverter="ABB__PVI_3_0_OUTD_S_US__208V_",
        temp_model="open_rack_glass_glass",
        modules_per_string=10,
        strings_per_inverter=5,
    ),
]



# Azimut
# -----------------------------------------------------


class AzimutCalculator:
    def __init__(self, geojson_path, step_size, pv_type: PVType, output_csv_path):
        self.geojson_path = geojson_path
        self.step_size = step_size  # in Metern
        self.pv_type = pv_type
        self.output_csv_path = output_csv_path

        self.gdf = None
        self.merged_line = None
        self.number_of_points = None
        self.point_azimut_list = []

    def load_geometry(self):
        self.gdf = gpd.read_file(self.geojson_path)
        self.gdf = self.gdf.to_crs(epsg=25832)  # metrisches Koordinatensystem
        self.merged_line = unary_union(self.gdf.geometry)
        return self.merged_line

    def interpolate_points(self):
        total_length = self.merged_line.length
        self.number_of_points = [
            self.merged_line.interpolate(distance)
            for distance in range(0, int(total_length), self.step_size)
        ]
        return self.number_of_points

    def _append_point(self, point, azimut):
        self.point_azimut_list.append((point, azimut))

    def calculate_azimut(self):
        # 1) Geometrie laden und Punkte erzeugen
        self.load_geometry()
        self.interpolate_points()

        # 2) Punkte durchlaufen und Azimut berechnen
        for i in range(len(self.number_of_points) - 1):
            p1 = self.number_of_points[i]
            p2 = self.number_of_points[i + 1]

            dx = p2.x - p1.x
            dy = p2.y - p1.y
            theta_rad = math.atan2(dy, dx)
            theta_deg = math.degrees(theta_rad)
            azimut_tangent = (90 - theta_deg) % 360  # Norden = 0°, Osten = 90°, ...

            if self.pv_type.azimut == "variabel":
                azimut_final = azimut_tangent
            else:
                azimut_final = self.pv_type.azimut

            self._append_point(point=p1, azimut=azimut_final)

        # 3) Ergebnis nach WGS84 zurückprojizieren und speichern
        points_geom = [p for p, _ in self.point_azimut_list]
        azimuts = [a for _, a in self.point_azimut_list]

        # GeoDataFrame im UTM-System
        gdf_points = gpd.GeoDataFrame(
            {"azimut": azimuts},
            geometry=points_geom,
            crs="EPSG:25832",
        )
        # zurück in lat/lon
        gdf_points = gdf_points.to_crs(epsg=4326)
        gdf_points["latitude"] = gdf_points.geometry.y
        gdf_points["longitude"] = gdf_points.geometry.x
        gdf_points["pv_type_id"] = self.pv_type.id
        gdf_points["pv_type_name"] = self.pv_type.name
        gdf_points["tilt"] = self.pv_type.tilt

        gdf_points[["latitude", "longitude", "azimut", "tilt", "pv_type_id", "pv_type_name"]].to_csv(
            self.output_csv_path,
            index=False,
        )

        return gdf_points

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

# PV-System
# -----------------------------------------------------
# PV-System
# -----------------------------------------------------

class PV_System:
    """
    PV-System-Wrapper:
    - geojson_path: Pfad zur Linien-Geometrie (z. B. Autobahnabschnitt)
    - pvtypes: Liste von PVType-Objekten
    """

    def __init__(self, geojson_path, pvtypes, step_size, weather_df, base_output_dir):
        self.geojson_path = geojson_path
        self.pvtypes = pvtypes
        self.step_size = step_size
        self.weather_df = weather_df      # Wetterdaten aus DWD-Skript
        self.base_output_dir = base_output_dir  # z. B. "./Input/punkte"

    def generate_pv_points(self):
        """
        Für jeden PV-Typ werden Punkte + Azimut berechnet und
        getrennt als CSV gespeichert.
        """
        results = {}
        for pv_type in self.pvtypes:
            output_csv = os.path.join(
                self.base_output_dir,
                f"punkte_{pv_type.id}_{pv_type.name}.csv".replace(" ", "_"),
            )
            calc = AzimutCalculator(
                geojson_path=self.geojson_path,
                step_size=self.step_size,
                pv_type=pv_type,
                output_csv_path=output_csv,
            )
            gdf_points = calc.calculate_azimut()
            results[pv_type.id] = gdf_points

        return results


