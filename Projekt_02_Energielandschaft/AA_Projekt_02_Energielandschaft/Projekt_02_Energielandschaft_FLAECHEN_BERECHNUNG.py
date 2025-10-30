# Flächen_Berechnung
# Input: Fläche (GeoJSON-Datei), PV-Ausrichtung, Traktor Breite und Länge 
# Ausgabe: Maximal mögliche Fläche für PV-Module, Gesamte Fläche des Ackers, Plot HTML-Karte 

# ------------------------------------------------------------

from pathlib import Path
from Projekt_02_Energielandschaft_RUN_SKRIPT import UserInputCollector

def main():
    collector = UserInputCollector()
    cfg = collector.collect()    # cfg ist ein dict
    collector.save(cfg)          # speichert, aber überschreibt cfg NICHT

    tractor_width = cfg["tractor_width"]
    tractor_length = cfg["tractor_length"]
    tractor_turn_radius = cfg["tractor_turn_radius"]
    row_direction = cfg["row_direction"]
    tilt = cfg["tilt"]

    print("Traktorbreite:", tractor_width)
    print("Traktorlänge:", tractor_length)
    print("Traktor Wenderadius:", tractor_turn_radius)
    print("Neigung:", tilt)
    print("Reihenrichtung:", row_direction)

if __name__ == "__main__":
    main()


from typing import List, Tuple, Optional
import math
import requests
import numpy as np
import geopandas as gpd
import folium
from shapely.geometry import Polygon, LineString, Point
from pyproj import CRS, Transformer
from dataclasses import dataclass


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
        # Speichere das CRS-Objekt für spätere Reprojektionen
        self.crs_utm = target_crs
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
        # Speichere die nutzbare PV-Fläche (innerer Offset) als Attribut
        self.offset_polygon_utm = inner
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
        import folium
        import webbrowser
        from pathlib import Path
        import geopandas as gpd
        from shapely.geometry import mapping
    
        # -----------------------------------
        # Stelle sicher, dass wir eine WGS84-Polygon haben
        # -----------------------------------
        if getattr(self, "polygon_wgs84", None) is None:
            # Falls nur UTM vorhanden ist: in WGS84 transformieren
            if getattr(self, "polygon_utm", None) is not None and getattr(self, "crs_utm", None) is not None:
                poly_wgs84 = gpd.GeoSeries([self.polygon_utm], crs=self.crs_utm).to_crs(epsg=4326).iloc[0]
            else:
                raise ValueError("Kein Polygon vorhanden (weder WGS84 noch UTM).")
        else:
            poly_wgs84 = self.polygon_wgs84
    
        # -----------------------------------
        # Karte zentrieren / Bounds setzen
        # -----------------------------------
        center = [poly_wgs84.centroid.y, poly_wgs84.centroid.x]
        fmap = folium.Map(location=center, zoom_start=15, tiles="OpenStreetMap")
    
        # Originalfläche (Feldgrenze)
        folium.GeoJson(
            mapping(poly_wgs84),
            name="Feldgrenze",
            style_function=lambda feat: {
                "fillColor": "transparent",
                "color": "darkgreen",
                "weight": max(1.0, 2.5 * line_weight_scale),
            },
            tooltip="Feldfläche",
        ).add_to(fmap)

        # Optional: PV-Nutzfläche (falls als UTM übergeben)
        if offset_polygon_utm is not None and (not offset_polygon_utm.is_empty):
            # Konvertiere offset-Polygon von UTM -> WGS84 (falls nötig)
            try:
                offset_wgs84 = gpd.GeoSeries([offset_polygon_utm], crs=getattr(self, "crs_utm", "EPSG:32632")).to_crs(epsg=4326).iloc[0]
                folium.GeoJson(
                    mapping(offset_wgs84),
                    name="PV-Nutzfläche",
                    style_function=lambda feat: {
                        "fillColor": "#3186cc55",
                        "color": "#003366",
                        "weight": max(1.0, 1.5 * line_weight_scale),
                    },
                    tooltip="PV-Nutzfläche",
                ).add_to(fmap)
            except Exception as ex:
                print(f"Warnung: Offset-Polygon konnte nicht nach WGS84 transformiert werden: {ex}")

        # PV-Reihen (falls vorhanden) zeichnen
        if getattr(self, 'segments', None):
            try:
                fg_rows = folium.FeatureGroup(name="PV-Reihen")
                for seg in self.segments:
                    # seg ist typischerweise ((x1,y1),(x2,y2)) in UTM
                    coords = list(seg)
                    if getattr(self, 'transformer', None) is not None:
                        # transformer.transform(x, y) -> (lon, lat)
                        seg_latlon = [self.transformer.transform(x, y) for x, y in coords]
                        locations = [(lat, lon) for lon, lat in seg_latlon]
                    else:
                        # Falls keine Transformer vorhanden: vermute coords sind already (lon, lat)
                        locations = [(y, x) for x, y in coords]

                    folium.PolyLine(
                        locations=locations,
                        color="green",
                        weight=max(1, int(2 * line_weight_scale)),
                        opacity=0.9,
                        tooltip="PV-Reihe",
                    ).add_to(fg_rows)

                fg_rows.add_to(fmap)
            except Exception as ex:
                print(f"Warnung: PV-Reihen konnten nicht gezeichnet werden: {ex}")

        folium.LayerControl().add_to(fmap)

        # Fit bounds auf die Feldfläche (damit die Karte nicht leer/zu klein ist)
        minx, miny, maxx, maxy = poly_wgs84.bounds
        fmap.fit_bounds([[miny, minx], [maxy, maxx]])

        # Datei speichern — erst danach öffnen
        fmap.save(filename)
        print(f"→ HTML-Karte gespeichert als: {filename}")

        if show_in_browser:
            uri = Path(filename).resolve().as_uri()
            print(f"→ Öffne Karte im Browser: {uri}")
            webbrowser.open(uri, new=2)