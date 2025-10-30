# Flächen_Berechnung
# Input: Fläche (GeoJSON-Datei), PV-Ausrichtung, Traktor Breite und Länge 
# Ausgabe: Maximal mögliche Fläche für PV-Module, Gesamte Fläche des Ackers, Plot HTML-Karte 
# Horizontale PV-Anlage (Aufgeständerte Anlage): Breite der PV-Reihe = 4 Module à 1.3 m = 5.2 m
# Vertikale PV-Anlage (Senkrechter Zaun): Breite der PV-Reihe = 0.5 m (Bodenfußabdruck), Höhe der PV-Reihe = 2 Module à 1.3 m = 2.6 m

# ------------------------------------------------------------

from pathlib import Path
import webbrowser
import math
import os
import subprocess
import sys

import geopandas as gpd
import numpy as np
from shapely.geometry import LineString
from shapely.ops import unary_union

from Projekt_02_Energielandschaft_RUN_SKRIPT import UserInputCollector


def _choose_utm_crs_from_lonlat(lon: float, lat: float):
    zone = int((lon + 180) / 6) + 1
    hemisphere = 'north' if lat >= 0 else 'south'
    if hemisphere == 'north':
        epsg = 32600 + zone
    else:
        epsg = 32700 + zone
    return epsg


class PVFieldProcessor:
    """
    Objektorientierte Umsetzung der Flächen- und Reihenberechnung.
    Initialisierung mit cfg (dict) aus UserInputCollector.
    """

    def __init__(self, cfg: dict):
        self.collector = UserInputCollector()
        self.cfg = cfg
        # defaults / synchronisieren
        if self.cfg.get('pv_type') == 'vertical':
            self.cfg.setdefault('pv_row_height_m', 2.5)
            self.cfg.setdefault('pv_row_width_m', 0.5)
        else:
            self.cfg.setdefault('pv_row_width_m', 5.2)
        self.geo_geom = None
        self.utm_epsg = None
        self.poly_utm = None
        self.inner = None
        self.rows_gdf = None
        self.total_row_length_m = 0.0
        self.pv_footprint_m2 = 0.0
        self.pv_vertical_front_m2 = 0.0
        self.total_area_m2 = 0.0
        self.usable_ground_area_m2 = 0.0

    def compute_green_and_spacing(self):
        tractor_width = float(self.cfg.get("tractor_width", 3.0))
        tractor_length = float(self.cfg.get("tractor_length", 4.5))
        tractor_turn_radius = float(self.cfg.get("tractor_turn_radius", 6.0))
        sicherheitszuschlag = 1.0
        breite_gruenstreifen = 2.0 * tractor_turn_radius + tractor_length + sicherheitszuschlag
        breite_fahrspur = tractor_width + 2 * sicherheitszuschlag
        pv_row_width = float(self.cfg.get('pv_row_width_m', 0.0))
        if pv_row_width <= 0:
            effective_spacing = breite_fahrspur
        else:
            effective_spacing = pv_row_width + breite_fahrspur

        # speichern
        self.cfg['green_strip_width_m'] = round(breite_gruenstreifen, 3)
        self.cfg['effective_row_spacing_m'] = round(effective_spacing, 3)
        return breite_gruenstreifen, breite_fahrspur, effective_spacing

    def load_geojson_and_project(self, geojson_path: str):
        geojson_path = Path(geojson_path)
        if not geojson_path.exists():
            raise FileNotFoundError(f"GeoJSON nicht gefunden: {geojson_path}")
        gdf = gpd.read_file(str(geojson_path))
        if gdf.empty:
            raise ValueError("GeoJSON enthält keine Geometrien")
        gdf = gdf.to_crs(epsg=4326)
        geom = unary_union(gdf.geometry)
        if geom.geom_type == 'GeometryCollection':
            polys = [g for g in geom.geoms if g.geom_type in ('Polygon', 'MultiPolygon')]
            geom = unary_union(polys)
        self.geo_geom = geom
        centroid = geom.centroid
        lon, lat = centroid.x, centroid.y
        utm_epsg = _choose_utm_crs_from_lonlat(lon, lat)
        self.utm_epsg = utm_epsg
        gdf_utm = gpd.GeoDataFrame(geometry=[geom], crs='EPSG:4326').to_crs(epsg=utm_epsg)
        self.poly_utm = gdf_utm.geometry.iloc[0]
        self.total_area_m2 = float(self.poly_utm.area)
        return lon, lat

    def create_inner_area(self, breite_gruenstreifen: float):
        inner = self.poly_utm.buffer(-breite_gruenstreifen)
        if inner.is_empty:
            raise ValueError("Nach Abzug des Grünstreifens bleibt keine nutzbare Fläche übrig.")
        self.inner = inner
        self.usable_ground_area_m2 = float(inner.area)
        return self.inner

    def generate_rows(self, row_direction: str, breite_fahrspur: float):
        minx, miny, maxx, maxy = self.inner.bounds
        lines = []
        step = breite_fahrspur
        if row_direction.upper() in ('N-S', 'NS', 'NORTH-SOUTH', 'NORD-SUED', 'NORD_SUED'):
            start = minx - step
            stop = maxx + step
            xs = np.arange(start, stop + step, step)
            for x in xs:
                line = LineString([(x, miny - 10 * step), (x, maxy + 10 * step)])
                seg = line.intersection(self.inner)
                if not seg.is_empty:
                    if seg.geom_type == 'LineString':
                        if seg.length > 0:
                            lines.append(seg)
                    elif seg.geom_type == 'MultiLineString':
                        for s in seg.geoms:
                            if s.length > 0:
                                lines.append(s)
        else:
            start = miny - step
            stop = maxy + step
            ys = np.arange(start, stop + step, step)
            for y in ys:
                line = LineString([(minx - 10 * step, y), (maxx + 10 * step, y)])
                seg = line.intersection(self.inner)
                if not seg.is_empty:
                    if seg.geom_type == 'LineString':
                        if seg.length > 0:
                            lines.append(seg)
                    elif seg.geom_type == 'MultiLineString':
                        for s in seg.geoms:
                            if s.length > 0:
                                lines.append(s)

        if not lines:
            raise ValueError("Keine Fahrspuren innerhalb der nutzbaren Fläche erzeugt.")
        self.rows_gdf = gpd.GeoDataFrame(geometry=lines, crs=f"EPSG:{self.utm_epsg}")
        self.total_row_length_m = float(self.rows_gdf.length.sum())
        return self.rows_gdf

    def compute_pv_areas(self, pv_row_width_m: float = None, pv_row_height_m: float = None):
        self.pv_footprint_m2 = 0.0
        self.pv_vertical_front_m2 = 0.0
        if self.total_row_length_m > 0:
            if pv_row_width_m:
                self.pv_footprint_m2 = float(self.total_row_length_m) * float(pv_row_width_m)
            if pv_row_height_m:
                self.pv_vertical_front_m2 = float(self.total_row_length_m) * float(pv_row_height_m)
        return self.pv_footprint_m2, self.pv_vertical_front_m2

    def export_map(self, lon: float, lat: float, output_html: str, open_in_browser: bool = True):
        import folium
        rows_wgs = self.rows_gdf.to_crs(epsg=4326)
        poly_wgs = gpd.GeoDataFrame(geometry=[self.poly_utm], crs=f"EPSG:{self.utm_epsg}").to_crs(epsg=4326).geometry.iloc[0]
        inner_wgs = gpd.GeoDataFrame(geometry=[self.inner], crs=f"EPSG:{self.utm_epsg}").to_crs(epsg=4326).geometry.iloc[0]

        m = folium.Map(location=[lat, lon], zoom_start=17)
        folium.GeoJson(data=gpd.GeoSeries([poly_wgs], crs='EPSG:4326').__geo_interface__, name='Feldrand').add_to(m)
        folium.GeoJson(data=gpd.GeoSeries([inner_wgs], crs='EPSG:4326').__geo_interface__,
                       style_function=lambda x: {'fillColor': "#1ca728", 'color': "#1ca728", 'weight': 1, 'fillOpacity': 0.3},
                       name='PV-nutzfläche').add_to(m)

        rows_fg = folium.FeatureGroup(name='PV-Reihen')
        for _, row in rows_wgs.iterrows():
            geom_row = row.geometry
            coords_latlon = []
            if geom_row.geom_type == 'LineString':
                coords_latlon = [(y, x) for x, y in geom_row.coords]
                folium.PolyLine(locations=coords_latlon, color="#ffee00", weight=2).add_to(rows_fg)
            elif geom_row.geom_type == 'MultiLineString':
                for part in geom_row.geoms:
                    coords = [(y, x) for x, y in part.coords]
                    folium.PolyLine(locations=coords, color="#ffee00", weight=2).add_to(rows_fg)
        rows_fg.add_to(m)

        try:
            b_minx, b_miny, b_maxx, b_maxy = inner_wgs.bounds
            m.fit_bounds([[b_miny, b_minx], [b_maxy, b_maxx]])
        except Exception:
            pass

        out_path = Path(output_html)
        m.save(str(out_path))

        # browser open with fallbacks
        opened = False
        if open_in_browser:
            try:
                opened = webbrowser.open(out_path.as_uri(), new=2)
            except Exception:
                opened = False
            if not opened:
                try:
                    p = str(out_path.resolve())
                    if sys.platform.startswith('win'):
                        os.startfile(p)
                        opened = True
                    elif sys.platform.startswith('darwin'):
                        subprocess.run(['open', p], check=False)
                        opened = True
                    else:
                        subprocess.run(['xdg-open', p], check=False)
                        opened = True
                except Exception:
                    opened = False
            if not opened:
                print(f"Karte gespeichert unter: {out_path} (Öffnen im Browser fehlgeschlagen)")
        else:
            print(f"Karte gespeichert unter: {out_path}")
        return out_path

    def run(self, geojson_path: str, output_html: str = "agri_pv_plot.html", open_in_browser: bool = True):
        lon, lat = self.load_geojson_and_project(geojson_path)
        breite_gruenstreifen, breite_fahrspur, effective_spacing = self.compute_green_and_spacing()
        self.create_inner_area(breite_gruenstreifen)
        row_direction = self.cfg.get('row_direction', 'N-S')
        # use effective_spacing as step for rows (already includes pv width)
        self.generate_rows(row_direction=row_direction, breite_fahrspur=effective_spacing)
        # compute areas
        pv_row_width = self.cfg.get('pv_row_width_m', None)
        pv_row_height = self.cfg.get('pv_row_height_m', None)
        self.compute_pv_areas(pv_row_width_m=pv_row_width, pv_row_height_m=pv_row_height)
        out_path = self.export_map(lon, lat, output_html, open_in_browser=open_in_browser)
        # store results in cfg
        self.cfg['total_area_m2'] = round(float(self.total_area_m2), 3)
        self.cfg['total_area_ha'] = round(float(self.total_area_m2) / 10000.0, 4)
        self.cfg['usable_ground_area_m2'] = round(float(self.usable_ground_area_m2), 3)
        self.cfg['usable_ground_area_ha'] = round(float(self.usable_ground_area_m2) / 10000.0, 4)
        self.cfg['pv_footprint_m2'] = round(float(self.pv_footprint_m2), 3) if hasattr(self, 'pv_footprint_m2') else round(float(self.pv_footprint_m2), 3)
        self.cfg['pv_footprint_ha'] = round(float(self.pv_footprint_m2) / 10000.0, 4)
        self.cfg['pv_vertical_front_m2'] = round(float(self.pv_vertical_front_m2), 3)
        self.cfg['pv_vertical_front_ha'] = round(float(self.pv_vertical_front_m2) / 10000.0, 4)
        self.cfg['usable_after_pv_m2'] = round(float(self.usable_ground_area_m2) - float(self.pv_footprint_m2), 3)
        self.cfg['usable_after_pv_ha'] = round((float(self.usable_ground_area_m2) - float(self.pv_footprint_m2)) / 10000.0, 4)
        if float(self.usable_ground_area_m2) > 0:
            self.cfg['pv_coverage_of_usable_percent'] = round(100.0 * (float(self.pv_footprint_m2) / float(self.usable_ground_area_m2)), 2)
        else:
            self.cfg['pv_coverage_of_usable_percent'] = 0.0
        # persist
        self.collector.save(self.cfg)
        return out_path, self.total_area_m2, self.usable_ground_area_m2, self.pv_footprint_m2, self.pv_vertical_front_m2


def main():
    collector = UserInputCollector()
    cfg = collector.collect()
    # ensure pv_row_height for vertical available early
    if cfg.get('pv_type') == 'vertical':
        cfg.setdefault('pv_row_height_m', 2.5)
    collector.save(cfg)

    geojson_path = input('Pfad zur GeoJSON-Datei (.geojson) eingeben (oder ENTER zum Abbrechen): ').strip()
    if not geojson_path:
        print('Keine GeoJSON-Datei angegeben — Abbruch.')
        return

    out_html = input('Name der Ausgabedatei (HTML) [Standard: agri_pv_plot.html]: ').strip() or 'agri_pv_plot.html'
    open_answer = input('HTML-Datei direkt im Browser öffnen? (j/n) [j]: ').strip().lower()
    open_in_browser = not (open_answer in ('n', 'nein', 'no'))

    processor = PVFieldProcessor(cfg)
    try:
        result = processor.run(geojson_path, output_html=out_html, open_in_browser=open_in_browser)
        out_path, total_area_m2, usable_ground_area_m2, pv_footprint_m2, pv_vertical_front_m2 = result
        print(f'Karte erfolgreich erzeugt und gespeichert: {out_path}')
        print(f"Gesamtfläche Feld: {cfg['total_area_m2']} m² ({cfg['total_area_ha']} ha)")
        print(f"Fläche des Feldes abzüglich Grünstreifen: {cfg['usable_ground_area_m2']} m² ({cfg['usable_ground_area_ha']} ha)")
        print(f"Fläche abzüglich Grünstreifen und PV-Reihen: {cfg['usable_after_pv_m2']} m² ({cfg['usable_after_pv_ha']} ha)")
        if cfg.get('pv_type') == 'horizontal':
            print(f"Fläche für horizontale PV-Anlage (Reihenbreite {cfg.get('pv_row_width_m')} m): {cfg['pv_footprint_m2']} m² ({cfg['pv_footprint_ha']} ha)")
        else:
            print(f"Boden-Fußabdruck der PV-Reihen (Reihenbreite {cfg.get('pv_row_width_m')} m): {cfg['pv_footprint_m2']} m² ({cfg['pv_footprint_ha']} ha)")
            print(f"PV-Fläche (Länge der Reihen × Höhe {cfg.get('pv_row_height_m')} m): {cfg['pv_vertical_front_m2']} m² ({cfg['pv_vertical_front_ha']} ha)")
        print(f"Das entspricht {cfg['pv_coverage_of_usable_percent']} % der nutzbaren Bodenfläche")
    except Exception as exc:
        print('Fehler beim Erzeugen der Karte:', exc)


if __name__ == "__main__":
    main()


