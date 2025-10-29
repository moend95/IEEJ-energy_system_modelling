# Vertikal und Tracking funktioniert
# Ausgabe der OpenStreetMap Karte als HTML-Datei im Browser funktioniert nicht. 


# Python ≥ 3.10
# Notwendige Pakete: geopandas, shapely, folium, numpy, matplotlib, pandas, pvlib

# -- Energielandschaft Agri-PV (erweiterte Version mit OSM, uMap, pvlib-Simulation & HTML) --

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
    Klasse zur Analyse, Visualisierung und energetischen Simulation von Agri-PV-Flächen.
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

    # ------------------------------------------------------------
    # Geometriequellen
    # ------------------------------------------------------------
    def get_osm_polygon(self, overpass_url: str = "https://overpass-api.de/api/interpreter") -> Polygon:
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
        gdf = gpd.read_file(source)
        if gdf.empty:
            raise ValueError("Keine Geometrie in der angegebenen uMap-Quelle gefunden.")
        self.polygon_wgs84 = gdf.to_crs("EPSG:4326").geometry.iloc[0]
        return self.polygon_wgs84

    def set_custom_polygon(self, coords_wgs84: List[Tuple[float, float]]) -> Polygon:
        if coords_wgs84[0] != coords_wgs84[-1]:
            coords_wgs84.append(coords_wgs84[0])
        self.polygon_wgs84 = Polygon(coords_wgs84)
        return self.polygon_wgs84

    # ------------------------------------------------------------
    # Projektion und Flächen
    # ------------------------------------------------------------
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

    # ------------------------------------------------------------
    # PV-Layout
    # ------------------------------------------------------------
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


    def export_plot_to_osm_html(
        self,
        offset_polygon_utm=None,
        filename="agri_pv_plot.html",
        show_in_browser=True,
        line_weight_scale=1.0,
    ):
        """
        Erstellt eine interaktive HTML-Karte (OpenStreetMap) mit der Fläche und optionaler PV-Abstandszone.

        Parameter
        ----------
        offset_polygon_utm : shapely.Polygon oder None
            Polygon der PV-Abstandszone (z. B. durch Pufferung erzeugt)
        filename : str
            Dateiname der HTML-Datei.
        show_in_browser : bool
            Wenn True, wird die HTML-Karte nach Erstellung im Standardbrowser geöffnet.
        line_weight_scale : float
            Skalierungsfaktor für die Linienbreite der Darstellung.
        """

        import folium
        import webbrowser
        from shapely.geometry import mapping
        import geopandas as gpd

        if self.polygon_wgs84 is None:
            raise ValueError("Kein Polygon vorhanden. Bitte zuerst Geometrie laden.")

        # Mittelpunkt für Kartenfokus
        centroid = self.polygon_wgs84.centroid
        map_center = [centroid.y, centroid.x]

        # Grundkarte
        fmap = folium.Map(location=map_center, zoom_start=15, tiles="OpenStreetMap")

        # Originalfläche (Grenze)
        folium.GeoJson(
            mapping(self.polygon_wgs84),
            name="Feldgrenze",
            style_function=lambda x: {
                "fillColor": "transparent",
                "color": "darkgreen",
                "weight": 2.5 * line_weight_scale,
            },
            tooltip="Feldfläche",
        ).add_to(fmap)

        # Optional: PV-Fläche (Offset)
        if offset_polygon_utm is not None and not offset_polygon_utm.is_empty:
            offset_poly_wgs84 = gpd.GeoSeries([offset_polygon_utm], crs=self.crs_utm).to_crs(epsg=4326).iloc[0]
            folium.GeoJson(
                mapping(offset_poly_wgs84),
                name="PV-Nutzfläche",
                style_function=lambda x: {
                    "fillColor": "#3186cc55",
                    "color": "#003366",
                    "weight": 1.5 * line_weight_scale,
                },
                tooltip="PV-Nutzfläche",
            ).add_to(fmap)

        folium.LayerControl().add_to(fmap)

        # Datei speichern
        fmap.save(filename)
        print(f"→ HTML-Karte gespeichert als: {filename}")

        # Karte im Browser öffnen (kompatibel zu Windows / alte Version)
        if show_in_browser:
            import os, webbrowser
            abs_path = os.path.abspath(filename)
            file_url = 'file:///' + abs_path.replace('\\', '/')
            print(f"→ Öffne Karte im Browser: {file_url}")
            webbrowser.open(file_url, new=2)


    # ------------------------------------------------------------
    # Simulation: Tracking-Agri-PV
    # ------------------------------------------------------------
    def run_tracking_simulation(self):
        """
        Führt eine energetische Simulation einer Single-Axis-Tracking-Agri-PV-Anlage mit pvlib (PVWatts-Modell) durch.
        Verwendet den geografischen Schwerpunkt der Fläche als Standort.
        """
        from pvlib.modelchain import ModelChain
        from pvlib.location import Location
        from pvlib.pvsystem import PVSystem, Array, SingleAxisTrackerMount
        from pvlib.temperature import TEMPERATURE_MODEL_PARAMETERS
        import matplotlib.pyplot as plt
        import pandas as pd

        # -------------------------------
        # Standort aus Polygon
        # -------------------------------
        if self.polygon_wgs84 is None:
            raise ValueError("Polygon nicht definiert. Bitte zuerst eine Fläche laden.")
        centroid = self.polygon_wgs84.centroid
        latitude, longitude = centroid.y, centroid.x

        print(f"\nStandort (aus Polygon ermittelt): Breite={latitude:.6f}, Länge={longitude:.6f}")

        location = Location(latitude=latitude,
                            longitude=longitude,
                            tz='Europe/Berlin',
                            altitude=80,
                            name='Agri-PV Standort')

        # -------------------------------
        # Wetterdaten
        # -------------------------------
        try:
            tmy = pd.read_csv("C:\\Users\\johan\\TH_Koeln_Masterprojekt\\IEEJ-energy_system_modelling\\Projekt_02_Energielandschaft\\AA_Energielandschaft_Main\\pvlib_TMY_Demoflaeche.csv", index_col=0)
        except FileNotFoundError:
            raise FileNotFoundError("Fehler: Datei 'pvlib_TMY_Demoflaeche.csv' nicht gefunden.")
        tmy.index = pd.to_datetime(tmy.index)

        # -------------------------------
        # Modulparameter (PVWatts)
        # -------------------------------
        custom_module = {
            'pdc0': 217728,       # Nennleistung (DC) in W
            'gamma_pdc': -0.0045  # Temperaturkoeffizient 1/°C
        }

        # -------------------------------
        # Wechselrichterparameter (PVWatts)
        # -------------------------------
        inverter = {
            'paco': 250000,  # Nennleistung AC in W
            'pdc0': 217728   # muss gleich oder größer als Modul-pdc0 sein
        }

        temperature_parameters = TEMPERATURE_MODEL_PARAMETERS['sapm']['open_rack_glass_glass']

        # -------------------------------
        # Tracking-System
        # -------------------------------
        mount = SingleAxisTrackerMount(axis_tilt=0,
                                       axis_azimuth=180,
                                       max_angle=78,
                                       backtrack=True)

        array = Array(mount=mount,
                      module_parameters=custom_module,
                      temperature_model_parameters=temperature_parameters,
                      modules_per_string=32,
                      strings=12)

        system = PVSystem(arrays=[array], inverter_parameters=inverter)

        # -------------------------------
        # ModelChain mit explizitem DC- und AC-Modell
        # -------------------------------
        mc = ModelChain(system,
                location,
                dc_model='pvwatts',
                ac_model='pvwatts',
                aoi_model='no_loss',
                spectral_model='no_loss')


        print("\nStarte Simulation (PVWatts Tracking)...")
        mc.run_model(tmy)

        # -------------------------------
        # Skalierung & Verluste
        # -------------------------------
        number_of_inverters = 97
        system_loss_factor = 0.9
        mc.results.ac *= number_of_inverters * system_loss_factor

        # -------------------------------
        # Auswertung
        # -------------------------------
        total_energy_kwh = mc.results.ac.sum() / 1000
        total_installed_capacity_kwp = custom_module['pdc0'] * number_of_inverters / 1000
        specific_performance = total_energy_kwh / total_installed_capacity_kwp

        print("\n--- Energetische Auswertung: Tracking-Agri-PV ---")
        print(f"Gesamte Energieerzeugung im Jahr: {total_energy_kwh:,.2f} kWh")
        print(f"Installierte Nennleistung:       {total_installed_capacity_kwp:,.2f} kWp")
        print(f"Spezifische Leistung:            {specific_performance:,.2f} kWh/kWp")

        # -------------------------------
        # Monatliche Erträge
        # -------------------------------
        monthly_energy_mwh = mc.results.ac.resample('M').sum() / 1e9
        months = monthly_energy_mwh.index.strftime('%B')

        plt.figure(figsize=(16, 9))
        mc.results.ac.plot()
        plt.title('AC-Leistung – Single-Axis Tracking System')
        plt.xlabel('Zeit')
        plt.ylabel('Leistung (W)')
        plt.tight_layout()
        plt.show()

        plt.figure(figsize=(16, 9))
        plt.bar(months, monthly_energy_mwh, color='dodgerblue')
        plt.title('Monatliche Energieerzeugung (MWh)')
        plt.xlabel('Monat')
        plt.ylabel('Energie [MWh]')
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.show()

        for month, energy in zip(months, monthly_energy_mwh):
            print(f"{month}: {energy:.2f} MWh")


    # ------------------------------------------------------------
    # Simulation: Vertikale Agri-PV (OHNE pvfactors)
    # ------------------------------------------------------------
    def run_vertical_simulation(self):
        """
        Energetische Simulation einer vertikalen bifacialen Agri-PV-Anlage.
        Verwendet vereinfachte bifaciale Berechnung ohne pvfactors-Abhängigkeit.
        """
        import pandas as pd
        import matplotlib.pyplot as plt
        from pvlib import pvsystem, location, modelchain, irradiance
        from pvlib.temperature import TEMPERATURE_MODEL_PARAMETERS as PARAMS

        if self.polygon_wgs84 is None:
            raise ValueError("Polygon nicht definiert. Bitte zuerst eine Fläche laden.")
        
        centroid = self.polygon_wgs84.centroid
        lat, lon = centroid.y, centroid.x
        tz = 'Europe/Berlin'
        altitude = 80

        print(f"\nStandort (aus Polygon ermittelt): Breite={lat:.6f}, Länge={lon:.6f}")

        # Wetterdaten laden
        try:
            weather_data = pd.read_csv(
                "C:\\Users\\johan\\TH_Koeln_Masterprojekt\\IEEJ-energy_system_modelling\\Projekt_02_Energielandschaft\\AA_Energielandschaft_Main\\pvlib_TMY_Demoflaeche.csv"
            )
        except FileNotFoundError:
            raise FileNotFoundError("Fehler: Datei 'pvlib_TMY_Demoflaeche.csv' nicht gefunden.")
            
        weather_data['Unnamed: 0'] = pd.to_datetime(weather_data['Unnamed: 0'])
        weather_data.set_index('Unnamed: 0', inplace=True)
        times = weather_data.index

        site_location = location.Location(lat, lon, tz=tz, altitude=altitude, name='Agri-PV Standort')
        solar_position = site_location.get_solarposition(times)

        # Vertikale Montage (90° Neigung, Ost-West bifacial)
        fixed_mount_east = pvsystem.FixedMount(surface_tilt=90, surface_azimuth=90)
        fixed_mount_west = pvsystem.FixedMount(surface_tilt=90, surface_azimuth=270)

        print("\nBerechne bifaciale Einstrahlung (Ost + West)...")

        # POA-Berechnung für Ost-Seite (Vorderseite)
        poa_east = irradiance.get_total_irradiance(
            surface_tilt=fixed_mount_east.surface_tilt,
            surface_azimuth=fixed_mount_east.surface_azimuth,
            solar_zenith=solar_position['apparent_zenith'],
            solar_azimuth=solar_position['azimuth'],
            dni=weather_data['dni'],
            ghi=weather_data['ghi'],
            dhi=weather_data['dhi'],
            albedo=0.2
        )
        
        # POA-Berechnung für West-Seite (Rückseite)
        poa_west = irradiance.get_total_irradiance(
            surface_tilt=fixed_mount_west.surface_tilt,
            surface_azimuth=fixed_mount_west.surface_azimuth,
            solar_zenith=solar_position['apparent_zenith'],
            solar_azimuth=solar_position['azimuth'],
            dni=weather_data['dni'],
            ghi=weather_data['ghi'],
            dhi=weather_data['dhi'],
            albedo=0.2
        )

        # Bifaciale Berechnung: Kombination von Vorder- und Rückseite
        # Bifacialitätsfaktor: 0.85 (typisch für bifaciale Module)
        bifaciality_factor = 0.85
        effective_irradiance = poa_east['poa_global'] + (poa_west['poa_global'] * bifaciality_factor)

        # Temperaturmodell
        temp_model_parameters = PARAMS['sapm']['open_rack_glass_glass']

        # Modulparameter - PVWatts-Modell (vereinfacht)
        # Pmp = Vmpo * Impo = 35.1 * 10.97 = 385.03 W
        custom_module = {
            'pdc0': 385.03,        # Nennleistung DC in W
            'gamma_pdc': -0.0045   # Temperaturkoeffizient pro °C
        }
        
        custom_inverter = {
            'pdc0': 70000,  # DC-Eingangsleistung des Wechselrichters
            'paco': 60000   # AC-Ausgangsleistung des Wechselrichters
        }

        num_modules_per_string, num_strings = 26, 6
        number_of_inverters = 315
        
        # Gesamtleistung: Module pro String × Strings × Wechselrichter × Modulleistung
        total_installed_capacity_kwp = (
            custom_module['pdc0'] * 
            num_modules_per_string * num_strings * number_of_inverters / 1000
        )

        print(f"Installierte Nennleistung: {total_installed_capacity_kwp:.2f} kWp")
        print("Starte Simulation...")

        # System definieren
        array = pvsystem.Array(
            mount=fixed_mount_east,
            module_parameters=custom_module,
            temperature_model_parameters=temp_model_parameters,
            strings=num_strings,
            modules_per_string=num_modules_per_string
        )
        
        system = pvsystem.PVSystem(arrays=[array], inverter_parameters=custom_inverter)
        
        # ModelChain mit explizitem DC- und AC-Modell (PVWatts)
        mc = modelchain.ModelChain(
            system, 
            site_location, 
            aoi_model='no_loss',
            spectral_model='no_loss',
            dc_model='pvwatts',
            ac_model='pvwatts'
        )
        
        # Simulation mit effektiver Einstrahlung
        effective_irrad_df = pd.DataFrame({'effective_irradiance': effective_irradiance}, index=times)
        mc.run_model_from_effective_irradiance(effective_irrad_df)
        
        # Skalierung: Anzahl Wechselrichter und Systemverluste
        mc.results.ac *= number_of_inverters * 0.9

        # Auswertung
        total_energy_kwh = mc.results.ac.sum() / 1000
        specific_yield = total_energy_kwh / total_installed_capacity_kwp

        print("\n--- Energetische Auswertung: Vertikale Agri-PV ---")
        print(f"Installierte Nennleistung: {total_installed_capacity_kwp:.2f} kWp")
        print(f"Gesamte Energieerzeugung:  {total_energy_kwh:,.2f} kWh")
        print(f"Spezifischer Ertrag:       {specific_yield:.2f} kWh/kWp")
        print(f"Bifacialitätsfaktor:       {bifaciality_factor}")

        # Monatliche Auswertung
        monthly_energy_mwh = mc.results.ac.resample('M').sum() / 1e6
        months = monthly_energy_mwh.index.strftime('%B')

        # Plots
        plt.figure(figsize=(16, 9))
        mc.results.ac.plot()
        plt.title('AC-Leistung – Vertikale bifaciale Agri-PV')
        plt.xlabel('Zeit')
        plt.ylabel('Leistung (W)')
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.show()

        plt.figure(figsize=(16, 9))
        plt.bar(months, monthly_energy_mwh, color='dodgerblue', edgecolor='navy')
        plt.title('Monatliche Energieerzeugung (MWh)')
        plt.xlabel('Monat')
        plt.ylabel('Energie [MWh]')
        plt.xticks(rotation=45)
        plt.grid(True, alpha=0.3, axis='y')
        plt.tight_layout()
        plt.show()

        print("\n--- Monatliche Erträge ---")
        for month, energy in zip(months, monthly_energy_mwh):
            print(f"{month}: {energy:.2f} MWh")

    # ------------------------------------------------------------
    # Ergebnisse
    # ------------------------------------------------------------
    @staticmethod
    def print_results_table(area_m2: float, area_ha: float, covered_area: float, max_percentage: float) -> None:
        covered_pct = (covered_area / area_m2 * 100.0) if area_m2 > 0 else 0.0
        print("\nErgebnisse:")
        print("-" * 50)
        print(f"Feldfläche           : {area_m2:12.2f} m²  ({area_ha:8.4f} ha)")
        print(f"Max. PV-Anteil       : {max_percentage:6.2f} %")
        print(f"Bedeckte PV-Fläche   : {covered_area:12.2f} m²  ({covered_pct:6.2f} %)")
        print("-" * 50)

    # ------------------------------------------------------------
    # Hauptprogramm
    # ------------------------------------------------------------
    def run(self):
        print("\n--- Geometriequelle wählen ---")
        print("1: OSM-Way-ID")
        print("2: uMap-GeoJSON (URL oder Datei)")
        print("3: Manuelle Koordinaten")
        choice = input("Auswahl [1-3]: ").strip()

        if choice == "1":
            self.way_id = int(input("Way-ID eingeben (Standard 168868469): ") or 168868469)
            self.get_osm_polygon()
        elif choice == "2":
            source = input("Pfad oder URL der uMap-GeoJSON-Datei eingeben: ").strip()
            self.load_umap_polygon(source)
        elif choice == "3":
            coords = []
            print("Gib mindestens vier Koordinaten (Lon, Lat) an, getrennt durch Kommas.")
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

        self.project_to_utm()
        self.calculate_area()

        print("\n--- Typ der Agri-PV-Anlage wählen ---")
        print("1: Tracking-Agri-PV-Anlage")
        print("2: Vertikale Agri-PV-Anlage (bifacial)")
        pv_type = input("Auswahl [1-2]: ").strip()

        if pv_type == "1":
            print("Tracking-Agri-PV-Anlage ausgewählt.")
            Lvor = float(input("Vorgewende [m] (12.0): ") or 12.0)
            Bg = float(input("Reihenabstand [m] (6.0): ") or 6.0)
            An = float(input("Ausrichtung [°] (0.0): ") or 0.0)
            Aarbeits = float(input("Modulbreite [m] (4.0): ") or 4.0)
            max_area_percentage = float(input("Maximale PV-Fläche [%] (75.0): ") or 75.0)

            self.calculate_pv_layout(Lvor, Bg, An, Aarbeits, max_area_percentage)
            AgriPV.print_results_table(self.area_m2, self.area_ha, self.covered_area, max_area_percentage)
            self.run_tracking_simulation()

        elif pv_type == "2":
            print("Vertikale bifaciale Agri-PV-Anlage ausgewählt.")
            Lvor = float(input("Vorgewende [m] (10.0): ") or 10.0)
            Bg = float(input("Modulreihenabstand [m] (8.0): ") or 8.0)
            An = float(input("Ausrichtung [°] (90.0): ") or 90.0)
            Aarbeits = float(input("Modulbreite [m] (1.6): ") or 1.6)
            max_area_percentage = float(input("Maximale PV-Fläche [%] (60.0): ") or 60.0)

            self.calculate_pv_layout(Lvor, Bg, An, Aarbeits, max_area_percentage)
            AgriPV.print_results_table(self.area_m2, self.area_ha, self.covered_area, max_area_percentage)
            self.run_vertical_simulation()

        else:
            print("Ungültige Auswahl, Standard: Vertikal.")
            self.run_vertical_simulation()


if __name__ == "__main__":
    app = AgriPV()
    app.run()

