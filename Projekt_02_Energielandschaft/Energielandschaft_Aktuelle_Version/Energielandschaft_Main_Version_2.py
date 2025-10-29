# Keine Abfrage nach "Vertikal" oder "Tracking" Agri-PV-Anlage. 
# Abfrage ist in Version 3 implementiert.



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

