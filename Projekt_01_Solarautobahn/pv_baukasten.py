import pvlib
import geopandas as gpd
from shapely.ops import unary_union
import math
import os
import matplotlib.pyplot as plt
import pandas as pd
from pvlib.location import Location
from pvlib.pvsystem import PVSystem
from pvlib.modelchain import ModelChain
from pvlib.bifacial.pvfactors import pvfactors_timeseries
from pvlib import location as pv_location, pvsystem
from pvlib import pvsystem
from shapely.geometry import Point


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

        # NEU Tracking:
        mount_type: str = "fixed",  # "fixed" oder "singleaxis"
        axis_tilt: float = 0.0,
        axis_azimuth: float = 0.0,  # 0 = N-S Achse, 90 = E-W Achse
        max_angle: float = 60.0,
        backtrack: bool = True,

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

        #tracking
        self.mount_type = mount_type
        self.axis_tilt = axis_tilt
        self.axis_azimuth = axis_azimuth
        self.max_angle = max_angle
        self.backtrack = backtrack

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
        is_bifacial_detailed=True,
        bifaciality=0.75,
        gcr=0.35,                   # GCR = Ground Coverage Ratio (Bodenbedeckungsgrad).
        row_height=3.0,
        row_width=4.0,
        albedo=0.2,
        # Tracking
        mount_type="singleaxis",
        axis_tilt=0,
        axis_azimuth=0,
        max_angle=60,
        backtrack=True,
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

# Test


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
        try:
            self.gdf = gpd.read_file(self.geojson_path)  # nutzt fiona
        except Exception:
            # Fallback zur alten Methode falls pyogrio nicht verfügbar ist
            self.gdf = gpd.read_file(self.geojson_path)

        self.gdf = self.gdf.to_crs(epsg=25832)  # metrisches Koordinatensystem
        self.merged_line = unary_union(self.gdf.geometry)
        return self.merged_line

    def interpolate_points(self):
        # Point-GeoJSON: genau einen Punkt nutzen
        if self.merged_line.geom_type == "Point":
            self.number_of_points = [self.merged_line]
            return self.number_of_points

        total_length = self.merged_line.length
        self.number_of_points = [
            self.merged_line.interpolate(distance)
            for distance in range(0, int(total_length), self.step_size)
        ]

        # Falls Linie Länge 0 hat: einen Punkt setzen
        if not self.number_of_points and total_length == 0:
            self.number_of_points = [self.merged_line.interpolate(0)]

        return self.number_of_points

    def _append_point(self, point, azimut):
        self.point_azimut_list.append((point, azimut))

    def calculate_azimut(self):
        # 1) Geometrie laden und Punkte erzeugen
        self.load_geometry()
        self.interpolate_points()

        # Sonderfall: nur ein Punkt
        if len(self.number_of_points) == 1:
            p1 = self.number_of_points[0]
            azimut_final = 180.0 if self.pv_type.azimut == "variabel" else self.pv_type.azimut
            self._append_point(point=p1, azimut=azimut_final)
        else:
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
            print("AzimutCalculator hat ", len(self.point_azimut_list), " Punkte hinzugefügt")

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
        pv_typ = self.calc.pv_type

        # Punkte + Azimute korrekt aus point_azimut_list holen
        points = [p for p, _ in self.calc.point_azimut_list]
        azimuts = [a for _, a in self.calc.point_azimut_list]

        fig, ax = plt.subplots(figsize=(10, 8))
        ax.set_title(f"PV-Punkte mit Azimut ({pv_typ.name})")
        ax.set_xlabel("X [m]")
        ax.set_ylabel("Y [m]")

        # Linienplot
        gdf.plot(ax=ax, color="gray", linewidth=2)

        # Punkteplot
        geo_gdf = gpd.GeoDataFrame(
            geometry=[Point(pt.x, pt.y) for pt in points],
            crs=gdf.crs,
        )
        geo_gdf.plot(ax=ax, color="red", markersize=5)

        # Richtungspfeile
        for i in range(0, len(points), every_nth_arrow):
            if isinstance(azimuts[i], (int, float)):
                dx = 5 * math.cos(math.radians(90 - azimuts[i]))
                dy = 5 * math.sin(math.radians(90 - azimuts[i]))
                ax.arrow(
                    points[i].x,
                    points[i].y,
                    dx,
                    dy,
                    head_width=2,
                    fc="blue",
                    ec="blue",
                )

        plt.grid(True)
        plt.axis("equal")
        plt.tight_layout()
        plt.show()



# -----------------------------------------------------
# PV-System
# -----------------------------------------------------

class PV_System:
    """
    PV-System-Wrapper:
    - geojson_path: Pfad zur Linien-Geometrie (z. B. Autobahnabschnitt)
    - pvtypes: Liste von PVType-Objekten
    """

    def __init__(self, geojson_path, pvtypes, step_size, weather_df, base_output_dir, debug=True):
        self.geojson_path = geojson_path
        self.pvtypes = pvtypes
        self.step_size = step_size
        self.weather_df = weather_df      # Wetterdaten aus DWD-Skript
        self.base_output_dir = base_output_dir  # z. B. "./Input/punkte"
        self.debug = debug

    def _dbg(self, msg: str):
        if getattr(self, "debug", False):
            print(msg)

    # -------------------------------------------------
    # 1) Punkte + Azimut generieren
    # -------------------------------------------------
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

    # -------------------------------------------------
    # 2) PV Simulation der Punkte
    # -------------------------------------------------

    def _build_mount(self, pv_type: PVType, row):
        if getattr(pv_type, "mount_type", "fixed") == "singleaxis":
            if pv_type.backtrack and pv_type.gcr is None:
                raise ValueError("Tracking mit backtrack=True braucht pv_type.gcr.")
            return pvsystem.SingleAxisTrackerMount(
                axis_tilt=float(pv_type.axis_tilt),
                axis_azimuth=float(pv_type.axis_azimuth),
                max_angle=float(pv_type.max_angle),
                backtrack=bool(pv_type.backtrack),
                gcr=float(pv_type.gcr) if pv_type.gcr is not None else None,
            )
        else:
            return pvsystem.FixedMount(
                surface_tilt=float(row["tilt"]),
                surface_azimuth=float(row["azimut"]),
            )

    def _simulate_monofacial_point(self, pv_type: PVType, row):
        print("Starte Berechnung eines monofazialen Punktes (PV_System._simulate_monofacial_point)")
        module_params = sandia_modules[pv_type.module]
        inverter_params = cec_inverters[pv_type.inverter]
        temp_params = temp_models_sapm[pv_type.temp_model]

        loc = Location(row["latitude"], row["longitude"], tz="Europe/Berlin")

        mount = self._build_mount(pv_type, row)

        array = pvsystem.Array(
            mount=mount,
            module_parameters=module_params,
            temperature_model_parameters=temp_params,
            albedo=pv_type.albedo,
        )

        system = pvsystem.PVSystem(
            arrays=[array],
            inverter_parameters=inverter_params,
            modules_per_string=pv_type.modules_per_string,
            strings_per_inverter=pv_type.strings_per_inverter,
        )

        mc = ModelChain(system, loc)
        mc.run_model(self.weather_df)
        return mc.results.ac

    def _simulate_bifacial_point(self, pv_type: PVType, row):
        print("Starte Berechnung eines bifazialen Punktes (PV_System._simulate_bifacial_point)")
        loc = Location(row["latitude"], row["longitude"], tz="Europe/Berlin")
        times = self.weather_df.index
        solar_position = loc.get_solarposition(times)

        # 1) Orientierung: für Wände besser FixedMount
        print("Mount und Orientation ermitteln(PV_System._simulate_bifacial_point)")
        mount = pvsystem.FixedMount(
            surface_tilt=float(row["tilt"]),
            surface_azimuth=float(row["azimut"]),
        )
        orientation = mount.get_orientation(
            solar_zenith=solar_position["apparent_zenith"],
            solar_azimuth=solar_position["azimuth"],
        )

        import time
        t0 = time.time()


        # 2) pvfactors: nutze Wetterdaten (dni/dhi)
        print("Starte pvfactors_timeseries (PV_System._simulate_bifacial_point)")
        irrad = pvfactors_timeseries(
            solar_azimuth=solar_position["azimuth"],
            solar_zenith=solar_position["apparent_zenith"],
            surface_azimuth=orientation["surface_azimuth"],
            surface_tilt=orientation["surface_tilt"],
            axis_azimuth=float(row["azimut"]),
            timestamps=times,
            dni=self.weather_df["dni"],
            dhi=self.weather_df["dhi"],
            gcr=pv_type.gcr,
            pvrow_height=pv_type.row_height,
            pvrow_width=pv_type.row_width,
            albedo=pv_type.albedo,
            n_pvrows=3,
            index_observed_pvrow=1,
        )

        t1 = time.time()
        irrad = pd.concat(irrad, axis=1)
        self._dbg(f"[pvfactors] took {time.time() - t0:.2f}s")

        # 3) Effective Irradiance bilden
        print("Effective Irradiance bilden(PV_System._simulate_bifacial_point)")
        if pv_type.bifaciality is None:
            raise ValueError(
                f"PVType '{pv_type.name}' ist als bifacial_detailed markiert, hat aber keine bifaciality definiert."
            )
        bifaciality = pv_type.bifaciality
        irrad["effective_irradiance"] = (
            irrad["total_abs_front"] + irrad["total_abs_back"] * bifaciality
        )

        # 4) System + MC

        module_params = sandia_modules[pv_type.module]
        inverter_params = cec_inverters[pv_type.inverter]
        temp_params = temp_models_sapm[pv_type.temp_model]

        array = pvsystem.Array(
            mount=mount,
            module_parameters=module_params,
            temperature_model_parameters=temp_params,
        )
        system = pvsystem.PVSystem(
            arrays=[array],
            inverter_parameters=inverter_params,
            modules_per_string=pv_type.modules_per_string,
            strings_per_inverter=pv_type.strings_per_inverter,
        )
        print("ModelChain starten(PV_System._simulate_bifacial_point)")
        mc = ModelChain(system, loc, aoi_model="no_loss")

        # 5) DataFrame für run_model_from_effective_irradiance bauen
        #    pvlib erwartet hier eine Spalte 'effective_irradiance'
        print("DataFrame für run_model_from_effective_irradiance bauen(PV_System._simulate_bifacial_point)")
        data = pd.DataFrame(index=self.weather_df.index)
        data["effective_irradiance"] = irrad["effective_irradiance"].reindex(data.index)

        # Falls deine Wetterdaten diese Spalten haben, mitgeben:
        if "temp_air" in self.weather_df.columns:
            data["temp_air"] = self.weather_df["temp_air"]
        if "wind_speed" in self.weather_df.columns:
            data["wind_speed"] = self.weather_df["wind_speed"]

        # pvlib erwartet jetzt nur noch dieses DataFrame als Argument
        mc.run_model_from_effective_irradiance(data)

        return mc.results.ac

    # -------------------------------------------------
    # 3) Energiesimulation für PV-Typ
    # -------------------------------------------------
    def simulate_pv_type_energy(self, pv_type: PVType, points_csv_path: str):
        """
        Liest die Punkte-CSV eines PV-Typs ein, simuliert alle Punkte
        (mono- oder bifazial) und gibt zurück:
        - energy_kwh: Jahresenergie [kWh/Jahr]
        - total_ac: Zeitreihe der AC-Gesamtleistung [W]
        """
        print("Starte Funktion PV_System.simulate_pv_type_energy")
        df_points = pd.read_csv(points_csv_path)
        modules_per_point = pv_type.modules_per_string * pv_type.strings_per_inverter



        total_ac = None

        for _, row in df_points.iterrows():

            self._dbg(
                f"\n[SIM] PVType={pv_type.name} | point={_} | "
                f"lat={row['latitude']:.6f}, lon={row['longitude']:.6f} | "
                f"az={float(row['azimut']):.1f}°, tilt={float(row['tilt']):.1f}° | "
                f"mount={pv_type.mount_type} | "
                f"modules_per_point={modules_per_point} "
                f"(mps={pv_type.modules_per_string}, spi={pv_type.strings_per_inverter}) | "
                f"bifacial_detailed={getattr(pv_type, 'is_bifacial_detailed', False)}"
            )

            if getattr(pv_type, "is_bifacial_detailed", False):
                ac = self._simulate_bifacial_point(pv_type, row)
            else:
                ac = self._simulate_monofacial_point(pv_type, row)

            if total_ac is None:
                total_ac = ac
            else:
                total_ac = total_ac + ac
            print("Ein Punkt wurde berechnet")


        dt_hours = (self.weather_df.index[1] - self.weather_df.index[0]).total_seconds() / 3600.0
        energy_Wh = (total_ac * dt_hours).sum()

        # einfacher Mehrertragsfaktor nur für "nicht-detaillierte" Bifazialität
        if (not getattr(pv_type, "is_bifacial_detailed", False)) and getattr(pv_type, "bifazial", 0) > 0:
            energy_Wh *= (1 + pv_type.bifazial)

        energy_kWh = energy_Wh / 1000.0

        return energy_kWh, total_ac


