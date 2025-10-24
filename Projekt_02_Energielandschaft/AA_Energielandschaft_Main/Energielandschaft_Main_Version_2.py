# -- Energielandschaft Agri-PV (erweiterte Version mit OSM, uMap & manuell) --

from typing import List, Tuple, Optional
import math
import requests
import numpy as np
import geopandas as gpd
import folium
from shapely.geometry import Polygon, LineString, Point
from pyproj import CRS, Transformer


LonLat = Tuple[float, float]
XY = Tuple[float, float]


class AgriPV:
    """
    Klasse zur Analyse und Visualisierung von Agri-PV-Flächen.
    Unterstützt OSM-Way-ID, uMap-Polygon (GeoJSON) und manuelle Koordinaten.
    """

    def __init__(self, way_id: int = 168868469, utm_epsg: int = 32632):
        self.way_id = way_id
        self.utm_epsg = utm_epsg
        self.polygon_wgs84: Optional[Polygon] = None
        self.polygon_utm: Optional[Polygon] = None
        self.transformer: Optional[Transformer] = None
        self.area_m2: float = 0.0
        self.area_ha: float = 0.0
        self.segments: List[Tuple[XY, XY]] = []
        self.covered_area: float = 0.0

    # -------------------------
    # Geometrie-Quellen
    # -------------------------

    def get_osm_polygon(self, overpass_url: str = "https://overpass-api.de/api/interpreter") -> Polygon:
        """
        Lädt eine Fläche aus OpenStreetMap über die Way-ID.
        """
        query = f"""
        [out:json];
        way({self.way_id});
        (._;>;);
        out body;
        """
        resp = requests.get(overpass_url, params={"data": query.strip()})
        resp.raise_for_status()
        data = resp.json()

        nodes = {elem["id"]: (elem["lon"], elem["lat"]) for elem in data["elements"] if elem["type"] == "node"}
        way_elems = [elem for elem in data["elements"] if elem["type"] == "way"]
        if not way_elems:
            raise ValueError(f"Way {self.way_id} nicht gefunden.")
        way_nodes = way_elems[0]["nodes"]
        coords = [nodes[nid] for nid in way_nodes]
        if coords[0] != coords[-1]:
            coords.append(coords[0])

        self.polygon_wgs84 = Polygon(coords)
        return self.polygon_wgs84

    def load_umap_polygon(self, source: str) -> Polygon:
        """
        Lädt ein Polygon aus einer GeoJSON-Datei oder einer URL (z. B. uMap).
        """
        gdf = gpd.read_file(source)
        if gdf.empty:
            raise ValueError("Keine Geometrie in der angegebenen uMap-Quelle gefunden.")
        self.polygon_wgs84 = gdf.to_crs("EPSG:4326").geometry.iloc[0]
        return self.polygon_wgs84

    def set_custom_polygon(self, coords_wgs84: List[Tuple[float, float]]) -> Polygon:
        """
        Setzt ein benutzerdefiniertes Polygon anhand von WGS84-Koordinaten (Lon, Lat).
        """
        if coords_wgs84[0] != coords_wgs84[-1]:
            coords_wgs84.append(coords_wgs84[0])
        self.polygon_wgs84 = Polygon(coords_wgs84)
        return self.polygon_wgs84

    # -------------------------
    # Projektion & Flächen
    # -------------------------

    def project_to_utm(self) -> Tuple[Polygon, Transformer]:
        gdf = gpd.GeoDataFrame(index=[0], crs="EPSG:4326", geometry=[self.polygon_wgs84])
        target_crs = CRS.from_epsg(self.utm_epsg)
        gdf_utm = gdf.to_crs(target_crs)
        self.polygon_utm = gdf_utm.geometry[0]
        self.transformer = Transformer.from_crs(target_crs, "EPSG:4326", always_xy=True)
        return self.polygon_utm, self.transformer

    def calculate_area(self) -> Tuple[float, float]:
        self.area_m2 = float(self.polygon_utm.area)
        self.area_ha = self.area_m2 / 10_000.0
        return self.area_m2, self.area_ha

    # -------------------------
    # PV-Layout
    # -------------------------

    @staticmethod
    def _line_through_point_angle(point: Point, angle_rad: float, length: float = 1e6) -> LineString:
        dx = math.sin(angle_rad)
        dy = math.cos(angle_rad)
        return LineString([
            (point.x - length * dy, point.y + length * dx),
            (point.x + length * dy, point.y - length * dx),
        ])

    def calculate_pv_layout(self, Lvor: float, Bg: float, An_deg: float, Aarbeits: float, max_area_percentage: float) -> Tuple[List[Tuple[XY, XY]], float]:
        polygon = self.polygon_utm
        if polygon.is_empty:
            return [], 0.0

        offset_distance = Lvor + (Bg / 2.0)
        inner = polygon.buffer(-offset_distance)
        if inner.is_empty:
            return [], 0.0

        angle_rad = math.radians(An_deg)
        centroid = inner.centroid
        max_area = (max_area_percentage / 100.0) * polygon.area
        segments: List[Tuple[XY, XY]] = []
        total_length = 0.0

        def try_add_line(distance: float) -> bool:
            nonlocal segments, total_length
            dx = math.sin(angle_rad)
            dy = math.cos(angle_rad)
            shift_x = centroid.x + distance * dx
            shift_y = centroid.y + distance * dy
            line = AgriPV._line_through_point_angle(Point(shift_x, shift_y), angle_rad)
            inter = inner.intersection(line)

            segs = []
            if inter.is_empty or isinstance(inter, Point):
                return False
            if isinstance(inter, LineString):
                segs = [inter]
            else:
                try:
                    segs = [geom for geom in inter.geoms if isinstance(geom, LineString)]
                except Exception:
                    return False

            for s in segs:
                seg_len = s.length
                prospective_total = total_length + seg_len
                prospective_area = prospective_total * Bg
                if prospective_area > max_area:
                    remaining_len = (max_area / Bg) - total_length
                    if remaining_len <= 0:
                        return False
                    midpoint = s.interpolate(0.5, normalized=True)
                    half = remaining_len / 2.0
                    part = LineString([
                        s.interpolate(max(0, s.project(midpoint) - half)),
                        s.interpolate(min(s.length, s.project(midpoint) + half))
                    ])
                    segments.append(tuple(part.coords[:2]))
                    total_length += part.length
                    return False
                segments.append(tuple(s.coords[:2]))
                total_length += seg_len
            return True

        _ = try_add_line(0.0)
        step = Aarbeits + Bg
        multiplier = 1
        max_span = max(polygon.bounds[2] - polygon.bounds[0], polygon.bounds[3] - polygon.bounds[1]) * 1.5

        while multiplier * step < max_span:
            for sign in (1, -1):
                _ = try_add_line(sign * multiplier * step)
            multiplier += 1
            if total_length * Bg >= max_area:
                break

        self.segments = segments
        self.covered_area = total_length * Bg
        return self.segments, self.covered_area

    # # -------------------------
    # # Tracking oder Vertikale Agri-PV-Anlage
    # # -------------------------
    #     def run_tracking_simulation(self):
    #     """
    #     Führt eine energetische Simulation einer Single-Axis-Tracking-Agri-PV-Anlage mit pvlib durch.
    #     Verwendet den geografischen Schwerpunkt (Centroid) der Projektfläche als Standort.
    #     Gibt Jahresenergie, installierte Leistung und spezifischen Ertrag aus.
    #     """
    #     from pvlib.modelchain import ModelChain
    #     from pvlib.location import Location
    #     from pvlib.pvsystem import PVSystem, Array, SingleAxisTrackerMount
    #     from pvlib.temperature import TEMPERATURE_MODEL_PARAMETERS
    #     import matplotlib.pyplot as plt
    #     import pandas as pd

    #     # ------------------------------------------------------------
    #     # Standort aus der Agri-PV-Geometrie bestimmen (Centroid)
    #     # ------------------------------------------------------------
    #     if self.polygon_wgs84 is None:
    #         raise ValueError("Polygon nicht definiert. Bitte zuerst eine Fläche laden.")
    #     centroid = self.polygon_wgs84.centroid
    #     latitude, longitude = centroid.y, centroid.x

    #     print(f"\nStandort (aus Polygon ermittelt): Breite={latitude:.6f}, Länge={longitude:.6f}")

    #     location = Location(latitude=latitude,
    #                         longitude=longitude,
    #                         tz='Europe/Berlin',
    #                         altitude=80,
    #                         name='Agri-PV-Standort')

    #     # ------------------------------------------------------------
    #     # Zeitreihe und Wetterdaten
    #     # ------------------------------------------------------------
    #     times = pd.date_range(start="2021-01-01",
    #                           end="2021-12-31",
    #                           freq="h",
    #                           tz=location.tz)

    #     try:
    #         tmy = pd.read_csv("pvlib_TMY_Demoflaeche.csv", index_col=0)
    #         tmy.index = pd.to_datetime(tmy.index)
    #     except FileNotFoundError:
    #         raise FileNotFoundError("Fehler: Datei 'pvlib_TMY_Demoflaeche.csv' nicht gefunden.")

    #     # ------------------------------------------------------------
    #     # PV-Komponenten
    #     # ------------------------------------------------------------
    #     custom_module = {
    #         'A0': 0.9408, 'A1': 0.054204, 'A2': -0.011043, 'A3': 0.0008875,
    #         'A4': -2.097e-05, 'B0': 1.0, 'B1': -0.002438, 'B2': 0.0003103,
    #         'B3': -1.246e-05, 'B4': 2.11e-07, 'B5': -1.36e-09, 'C0': 1.0,
    #         'C1': 0.009, 'C2': 0.091575, 'C3': -8.79359, 'C4': 0.993,
    #         'C5': 0.007, 'C6': 1.105, 'C7': -0.105, 'FD': 1, 'IXO': 3.16,
    #         'IXXO': 4.84, 'Impo': 13.48, 'Vmpo': 41.92, 'Voco': 50.60,
    #         'Mbvoc': -0.1265, 'Mbvmp': -0.126, 'N': 1.35, 'Cells_in_Series': 24,
    #         'Parallel_Strings': 6, 'Aisc': 0.00065, 'Isco': 14.23,
    #         'Aimp': -0.0002, 'Bvoco': -0.1265, 'Bvmpo': -0.126, 'Area': 2.58
    #     }

    #     inverter = {
    #         'Name': 'Sungrow SG250HX', 'Paco': 250000, 'Pdco': 255000,
    #         'Vdco': 1160, 'C0': -2.91984e-08, 'C1': 1.3e-05, 'C2': -0.000421,
    #         'C3': -0.000925, 'Pso': 2, 'Pnt': 2, 'Vdxmax': 1500,
    #         'Idcmax': 26*12, 'Mppt_low': 600, 'Mppt_high': 1500
    #     }

    #     temperature_parameters = TEMPERATURE_MODEL_PARAMETERS['sapm']['open_rack_glass_glass']

    #     # ------------------------------------------------------------
    #     # Tracking-System konfigurieren
    #     # ------------------------------------------------------------
    #     mount = SingleAxisTrackerMount(axis_tilt=0,
    #                                    axis_azimuth=180,
    #                                    max_angle=78,
    #                                    backtrack=True)

    #     sol_pos = location.get_solarposition(times)
    #     _ = mount.get_orientation(solar_zenith=sol_pos['apparent_zenith'],
    #                               solar_azimuth=sol_pos['azimuth'])

    #     array = Array(mount=mount,
    #                   module_parameters=custom_module,
    #                   temperature_model_parameters=temperature_parameters,
    #                   modules_per_string=32,
    #                   strings=12)

    #     system_sat = PVSystem(arrays=[array], inverter_parameters=inverter)
    #     modelchain_sat = ModelChain(system_sat, location)

    #     # ------------------------------------------------------------
    #     # Simulation ausführen
    #     # ------------------------------------------------------------
    #     print("\nStarte pvlib-Simulation (Tracking-System)...")
    #     modelchain_sat.run_model(tmy)

    #     number_of_inverters = 97
    #     system_loss_factor = 0.90
    #     modelchain_sat.results.ac *= number_of_inverters * system_loss_factor

    #     # ------------------------------------------------------------
    #     # Ergebnisse berechnen
    #     # ------------------------------------------------------------
    #     total_energy_kwh = modelchain_sat.results.ac.sum() / 1000
    #     total_installed_capacity_kwp = (
    #         custom_module['Vmpo'] * custom_module['Impo'] *
    #         array.modules_per_string * array.strings *
    #         number_of_inverters / 1000
    #     )
    #     specific_performance = total_energy_kwh / total_installed_capacity_kwp

    #     print("\n--- Energetische Auswertung: Tracking-Agri-PV ---")
    #     print(f"Gesamte Energieerzeugung im Jahr: {total_energy_kwh:,.2f} kWh")
    #     print(f"Installierte Nennleistung:       {total_installed_capacity_kwp:,.2f} kWp")
    #     print(f"Spezifischer Ertrag:             {specific_performance:,.2f} kWh/kWp")

    #     # ------------------------------------------------------------
    #     # Monatliche Energieerzeugung
    #     # ------------------------------------------------------------
    #     monthly_energy_mwh = modelchain_sat.results.ac.resample('M').sum() / 1e9
    #     months = monthly_energy_mwh.index.strftime('%B')

    #     plt.figure(figsize=(16, 9))
    #     modelchain_sat.results.ac.plot()
    #     plt.title('AC-Leistung – Single-Axis Tracking System')
    #     plt.xlabel('Zeit')
    #     plt.ylabel('Leistung (W)')
    #     plt.tight_layout()
    #     plt.show()

    #     plt.figure(figsize=(16, 9))
    #     plt.bar(months, monthly_energy_mwh, color='dodgerblue')
    #     plt.title('Monatliche Energieerzeugung (MWh)')
    #     plt.xlabel('Monat')
    #     plt.ylabel('Energie [MWh]')
    #     plt.xticks(rotation=45)
    #     plt.tight_layout()
    #     plt.show()

    #     for month, energy in zip(months, monthly_energy_mwh):
    #         print(f"{month}: {energy:.2f} MWh")

    
    #         def run_vertical_simulation(self):
    #     """
    #     Führt eine energetische Simulation einer vertikalen bifazialen Agri-PV-Anlage mit pvlib durch.
    #     Verwendet den geografischen Schwerpunkt (Centroid) der Projektfläche als Standort.
    #     Gibt Jahresenergie, installierte Leistung und spezifischen Ertrag aus.
    #     """
    #     import warnings
    #     import pandas as pd
    #     import matplotlib.pyplot as plt
    #     from pvlib import pvsystem, location, modelchain
    #     from pvlib.temperature import TEMPERATURE_MODEL_PARAMETERS as PARAMS
    #     from pvlib.bifacial.pvfactors import pvfactors_timeseries

    #     warnings.filterwarnings(action='ignore', module='pvfactors')

    #     # ------------------------------------------------------------
    #     # Standort automatisch aus Polygon übernehmen
    #     # ------------------------------------------------------------
    #     if self.polygon_wgs84 is None:
    #         raise ValueError("Polygon nicht definiert. Bitte zuerst eine Fläche laden.")
    #     centroid = self.polygon_wgs84.centroid
    #     lat, lon = centroid.y, centroid.x
    #     tz = 'Europe/Berlin'
    #     altitude = 80

    #     print(f"\nStandort (aus Polygon ermittelt): Breite={lat:.6f}, Länge={lon:.6f}")

    #     # ------------------------------------------------------------
    #     # Wetterdaten laden
    #     # ------------------------------------------------------------
    #     try:
    #         weather_data = pd.read_csv("pvlib_TMY_Demoflaeche.csv")
    #     except FileNotFoundError:
    #         raise FileNotFoundError("Fehler: Datei 'pvlib_TMY_Demoflaeche.csv' nicht gefunden.")

    #     weather_data['Unnamed: 0'] = pd.to_datetime(weather_data['Unnamed: 0'])
    #     weather_data.set_index('Unnamed: 0', inplace=True)
    #     times = weather_data.index

    #     # ------------------------------------------------------------
    #     # Systemparameter
    #     # ------------------------------------------------------------
    #     axis_tilt = 90       # vertikal
    #     axis_azimuth = 90    # nach Osten ausgerichtet
    #     gcr = 0.07
    #     pvrow_height = 3
    #     pvrow_width = 300
    #     albedo = 0.4
    #     bifaciality = 0.85

    #     temp_model_parameters = PARAMS['sapm']['open_rack_glass_glass']

    #     custom_module = {
    #         'A0': 0.9428, 'A1': 0.02753, 'A2': -0.002848, 'A3': -0.0001439,
    #         'A4': 2.219e-05, 'B0': 1.0, 'B1': -0.00261, 'B2': 0.0003279,
    #         'B3': -1.458e-05, 'B4': 2.654e-07, 'B5': -1.732e-09, 'C0': 1.0116,
    #         'C1': -0.0116, 'C2': -0.07993, 'C3': -8.79359, 'C4': 0.993,
    #         'FD': 1, 'IXO': 2.22, 'IXXO': 1.37, 'Impo': 10.97, 'Vmpo': 35.1,
    #         'Voco': 42, 'Mbvoc': -0.105, 'Mbvmp': -0.105, 'N': 1,
    #         'Cells_in_Series': 12, 'Parallel_Strings': 10, 'Aisc': 0.004632,
    #         'Isco': 11.62, 'Aimp': -0.004404, 'Bvoco': -0.13048,
    #         'Bvmpo': -0.105, 'Area': 1.85
    #     }

    #     custom_inverter = {
    #         'Name': 'SUN2000-60KTL-M0', 'Paco': 60000, 'Pdco': 66000,
    #         'Vdco': 600, 'C0': -2.91984e-08, 'C1': 1.3e-05, 'C2': -0.000421,
    #         'C3': -0.000925, 'Pso': 2, 'Pnt': 2, 'Vdcmax': 1100, 'Idcmax': 132,
    #         'Mppt_low': 200, 'Mppt_high': 1000
    #     }

    #     # ------------------------------------------------------------
    #     # Standort und Solarpositionen
    #     # ------------------------------------------------------------
    #     site_location = location.Location(lat, lon, tz=tz, altitude=altitude, name='Agri-PV Standort')
    #     solar_position = site_location.get_solarposition(times)

    #     # ------------------------------------------------------------
    #     # Montagesystem und Bestrahlungsberechnung
    #     # ------------------------------------------------------------
    #     fixed_mount = pvsystem.FixedMount(surface_tilt=axis_tilt, surface_azimuth=axis_azimuth)

    #     irrad = pvfactors_timeseries(
    #         solar_position['azimuth'],
    #         solar_position['apparent_zenith'],
    #         fixed_mount.surface_azimuth,
    #         fixed_mount.surface_tilt,
    #         axis_azimuth,
    #         times,
    #         weather_data['dni'],
    #         weather_data['dhi'],
    #         gcr,
    #         pvrow_height,
    #         pvrow_width,
    #         albedo,
    #         n_pvrows=3,
    #         index_observed_pvrow=1
    #     )

    #     irrad = pd.concat(irrad, axis=1)
    #     irrad['effective_irradiance'] = irrad['total_abs_front'] + irrad['total_abs_back'] * bifaciality

    #     # ------------------------------------------------------------
    #     # Systemdefinition
    #     # ------------------------------------------------------------
    #     num_modules_per_string = 26
    #     num_strings = 6
    #     module_capacity_kwp = custom_module['Vmpo'] * custom_module['Impo'] / 1000
    #     total_per_inverter_kwp = module_capacity_kwp * num_modules_per_string * num_strings
    #     number_of_inverters = 315
    #     total_installed_capacity_kwp = total_per_inverter_kwp * number_of_inverters

    #     array = pvsystem.Array(
    #         mount=fixed_mount,
    #         module_parameters=custom_module,
    #         temperature_model_parameters=temp_model_parameters,
    #         strings=num_strings,
    #         modules_per_string=num_modules_per_string
    #     )

    #     system = pvsystem.PVSystem(arrays=[array], inverter_parameters=custom_inverter)

    #     mc_bifi = modelchain.ModelChain(system, site_location, aoi_model='no_loss')
    #     mc_bifi.run_model_from_effective_irradiance(irrad)

    #     mc_bifi.results.ac *= number_of_inverters
    #     mc_bifi.results.ac *= 0.9  # Systemverluste 10%

    #     # ------------------------------------------------------------
    #     # Ergebnisse
    #     # ------------------------------------------------------------
    #     total_energy_kwh = mc_bifi.results.ac.sum() / 1000
    #     specific_yield = total_energy_kwh / total_installed_capacity_kwp

    #     print("\n--- Energetische Auswertung: Vertikale Agri-PV ---")
    #     print(f"Installierte Nennleistung:     {total_installed_capacity_kwp:.2f} kWp")
    #     print(f"Gesamte Energieerzeugung:      {total_energy_kwh:.2f} kWh")
    #     print(f"Spezifische Energieerzeugung:  {specific_yield:.2f} kWh/kWp")

    #     # Monatliche Summen
    #     monthly_energy_mwh = mc_bifi.results.ac.resample('M').sum() / 1e9
    #     months = monthly_energy_mwh.index.strftime('%B')

    #     plt.figure(figsize=(16, 9))
    #     mc_bifi.results.ac.plot()
    #     plt.title('AC-Leistung des vertikalen Systems')
    #     plt.xlabel('Zeit')
    #     plt.ylabel('AC-Leistung (W)')
    #     plt.tight_layout()
    #     plt.show()

    #     plt.figure(figsize=(16, 9))
    #     plt.bar(months, monthly_energy_mwh, color='dodgerblue')
    #     plt.title('Monatliche Energieerzeugung (MWh)')
    #     plt.xlabel('Monat')
    #     plt.ylabel('Energie [MWh]')
    #     plt.xticks(rotation=45)
    #     plt.tight_layout()
    #     plt.show()

    #     for month, energy in zip(months, monthly_energy_mwh):
    #         print(f"{month}: {energy:.2f} MWh")


    # -------------------------
    # Export & Visualisierung
    # -------------------------

    def export_plot_to_osm_html(self, offset_polygon_utm: Optional[Polygon], filename: str = "agri_pv_plot.html", show_in_browser: bool = False, line_weight_scale: float = 1.0) -> None:
        def to_latlon_coords(coords: List[XY]) -> List[Tuple[float, float]]:
            return [self.transformer.transform(x, y) for x, y in coords]

        poly_coords_latlon = to_latlon_coords(list(self.polygon_utm.exterior.coords))
        center = np.mean(poly_coords_latlon, axis=0)[::-1].tolist()
        m = folium.Map(location=center, zoom_start=17, control_scale=True)

        folium.Polygon(
            locations=[(lat, lon) for lon, lat in poly_coords_latlon],
            color="black",
            opacity=0.3,
            fill=True,
            fill_color="#bab8b9",
            fill_opacity=0.2,
            tooltip="Feldfläche"
        ).add_to(m)

        if offset_polygon_utm is not None and not offset_polygon_utm.is_empty:
            off_coords_latlon = to_latlon_coords(list(offset_polygon_utm.exterior.coords))
            folium.Polygon(
                locations=[(lat, lon) for lon, lat in off_coords_latlon],
                color="#850296",
                opacity=0.3,
                fill=True,
                fill_color="#429925",
                fill_opacity=0.2,
                tooltip="Innenfläche (Vorgewende entfernt)"
            ).add_to(m)

        for seg in self.segments:
            seg_latlon = to_latlon_coords(list(seg))
            folium.PolyLine(
                locations=[(lat, lon) for lon, lat in seg_latlon],
                color="#0552ab",
                opacity=0.3,
                weight=max(1, int(line_weight_scale)),
                tooltip="PV-Reihe"
            ).add_to(m)

        m.save(filename)
        print(f"\nKarte gespeichert unter: {filename}")
        if show_in_browser:
            import webbrowser
            webbrowser.open(filename)

    # -------------------------
    # Ausgabe
    # -------------------------

    @staticmethod
    def print_results_table(area_m2: float, area_ha: float, covered_area: float, max_percentage: float) -> None:
        covered_pct = (covered_area / area_m2 * 100.0) if area_m2 > 0 else 0.0
        print("\nErgebnisse:")
        print("-" * 50)
        print(f"Feldfläche           : {area_m2:12.2f} m²  ({area_ha:8.4f} ha)")
        print(f"Max. PV-Anteil       : {max_percentage:6.2f} %")
        print(f"Bedeckte PV-Fläche   : {covered_area:12.2f} m²  ({covered_pct:6.2f} % der Fläche)")
        print("-" * 50)

    # -------------------------
    # Hauptprogramm
    # -------------------------

    def run(self):
        print("\n--- Geometriequelle wählen ---")
        print("1: OSM-Way-ID")
        print("2: uMap-GeoJSON (URL oder Dateipfad)")
        print("3: Manuelle Koordinaten")
        choice = input("Auswahl [1-3]: ").strip()

        if choice == "1":
            self.way_id = int(input("Way-ID eingeben (Standard 168868469): ") or 168868469)
            self.get_osm_polygon()
        elif choice == "2":
            source = input("Pfad oder URL der uMap-GeoJSON-Datei eingeben: ").strip()
            self.load_umap_polygon(source)
        elif choice == "3":
            print("Gib mindestens vier Koordinaten (Lon, Lat) an, getrennt durch Kommas.")
            coords = []
            while True:
                line = input("Koordinate (oder leer zum Beenden): ").strip()
                if not line:
                    break
                lon, lat = map(float, line.split(","))
                coords.append((lon, lat))
            self.set_custom_polygon(coords)
        else:
            print("Ungültige Auswahl. Standard: OSM-Way-ID.")
            self.get_osm_polygon()

        # Transformation und Flächenberechnung
        self.project_to_utm()
        self.calculate_area()

        Lvor = float(input("Breite Vorgewende [m] (Standard 10.0): ") or 10.0)
        Bg = float(input("Breite Grünstreifen [m] (Standard 10.0): ") or 10.0)
        An = float(input("Ausrichtungswinkel [°] (Standard 0.0): ") or 0.0)
        Aarbeits = float(input("Arbeitsbreite PV [m] (Standard 10.0): ") or 10.0)
        max_area_percentage = float(input("Maximale PV-Fläche [%] (Standard 70.0): ") or 70.0)

        self.calculate_pv_layout(Lvor, Bg, An, Aarbeits, max_area_percentage)
        AgriPV.print_results_table(self.area_m2, self.area_ha, self.covered_area, max_area_percentage)

        do_export = input("HTML-Karte erzeugen? (j/n): ").strip().lower()
        if do_export in ("", "j", "ja", "y", "yes"):
            offset_distance = Lvor + (Bg / 2.0)
            offset_poly = self.polygon_utm.buffer(-offset_distance)
            self.export_plot_to_osm_html(
                offset_polygon_utm=offset_poly if not offset_poly.is_empty else None,
                filename="agri_pv_plot.html",
                show_in_browser=True,
                line_weight_scale=max(1.0, Bg / 2.0),
            )


if __name__ == "__main__":
    app = AgriPV()
    app.run()

