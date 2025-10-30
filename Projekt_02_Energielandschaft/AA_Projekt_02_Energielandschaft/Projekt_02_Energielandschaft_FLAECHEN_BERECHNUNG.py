# Flächen_Berechnung
# Input: Fläche (GeoJSON-Datei), PV-Ausrichtung, Traktor Breite und Länge 
# Ausgabe: Maximal mögliche Fläche für PV-Module, Gesamte Fläche des Ackers, Plot HTML-Karte 

# ------------------------------------------------------------

from pathlib import Path
import webbrowser
import math

import geopandas as gpd
import numpy as np
from shapely.geometry import LineString
from shapely.ops import unary_union

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
    pv_row_width = cfg.get('pv_row_width_m', None)

    print("Traktorbreite:", tractor_width)
    print("Traktorlänge:", tractor_length)
    print("Traktor Wenderadius:", tractor_turn_radius)
    print("Neigung:", tilt)
    print("Reihenrichtung:", row_direction)
    if pv_row_width is not None:
        print(f"PV-Reihen Breite (m): {pv_row_width}")

    # Berechne die notwendige Breite des Grünstreifens
    # Formel: breite_grünstreifen = 2 * Wenderadius + Traktor­länge + Sicherheitszuschlag
    sicherheitszuschlag = 1.0  # Meter
    breite_gruenstreifen = 2.0 * tractor_turn_radius + tractor_length + sicherheitszuschlag
    breite_fahrspur = tractor_width + 2 * sicherheitszuschlag

    # Bestimme effektiven Reihenabstand: PV-Reihe + Fahrspur
    if pv_row_width is None:
        # Fallback: falls nicht gesetzt, verwende nur die Fahrspur als Abstand
        effective_spacing = breite_fahrspur
    else:
        effective_spacing = pv_row_width + breite_fahrspur

    print(f"Effektiver Reihenabstand (PV-Reihen-Breite + Fahrspur): {effective_spacing:.2f} m")

    print(f"Notwendige Breite der Fahrspur: {breite_fahrspur:.2f} m (inkl. {sicherheitszuschlag} m Sicherheitszuschlag auf jeder Seite)")
    print(f"Notwendige Breite des Grünstreifens: {breite_gruenstreifen:.2f} m (inkl. {sicherheitszuschlag} m Sicherheitszuschlag)")

    # Optional: speichere das Ergebnis zurück in die Konfiguration und überschreibe die JSON
    cfg['green_strip_width_m'] = round(breite_gruenstreifen, 3)
    cfg['effective_row_spacing_m'] = round(effective_spacing, 3)
    collector.save(cfg)

    # --- Interaktiver Teil: GeoJSON-Pfad abfragen und Karte erzeugen ---
    print('\nJetzt kannst du eine GeoJSON-Datei angeben, auf deren Fläche die PV-Reihen erzeugt werden sollen.')
    geojson_path = input('Pfad zur GeoJSON-Datei (.geojson) eingeben (oder ENTER zum Abbrechen): ').strip()
    if not geojson_path:
        print('Keine GeoJSON-Datei angegeben — Abbruch der Kartenerstellung.')
        return

    out_html = input('Name der Ausgabedatei (HTML) [Standard: agri_pv_plot.html]: ').strip()
    if not out_html:
        out_html = 'agri_pv_plot.html'

    # Übergib die berechneten Parameter an die Exportfunktion
    # Frage, ob die HTML-Datei direkt im Browser geöffnet werden soll
    open_answer = input('HTML-Datei direkt im Browser öffnen? (j/n) [j]: ').strip().lower()
    open_in_browser = True
    if open_answer in ('n', 'nein', 'no'):
        open_in_browser = False

    try:
        result = export_geojson_with_pv_rows(
            geojson_path,
            output_html=out_html,
            breite_fahrspur=effective_spacing,
            breite_gruenstreifen=breite_gruenstreifen,
            row_direction=row_direction,
            pv_row_width_m=pv_row_width,
            open_in_browser=open_in_browser
        )
        result_path, total_area_m2, usable_area_m2, pv_area_m2 = result
        # Speichere Flächen in cfg und persistiere
        cfg['total_area_m2'] = round(float(total_area_m2), 3)
        cfg['total_area_ha'] = round(float(total_area_m2) / 10000.0, 4)
        cfg['usable_area_m2'] = round(float(usable_area_m2), 3)
        cfg['usable_area_ha'] = round(float(usable_area_m2) / 10000.0, 4)
        cfg['max_pv_area_m2'] = round(float(pv_area_m2), 3)
        cfg['max_pv_area_ha'] = round(float(pv_area_m2) / 10000.0, 4)
        if usable_area_m2 > 0:
            cfg['pv_coverage_of_usable_percent'] = round(100.0 * (pv_area_m2 / usable_area_m2), 2)
        else:
            cfg['pv_coverage_of_usable_percent'] = 0.0
        collector.save(cfg)
        print(f'Karte erfolgreich erzeugt und gespeichert: {result_path}')
        print(f"Gesamtfläche Feld: {cfg['total_area_m2']} m² ({cfg['total_area_ha']} ha)")
        print(f"Nutzbare Fläche nach Abzug Grünstreifen: {cfg['usable_area_m2']} m² ({cfg['usable_area_ha']} ha)")
        print(f"Maximal mögliche PV-Fläche (theoretisch, Reihenbreite berücksichtigt): {cfg['max_pv_area_m2']} m² ({cfg['max_pv_area_ha']} ha)")
        print(f"Das entspricht {cfg['pv_coverage_of_usable_percent']} % der nutzbaren Fläche")
    except Exception as exc:
        print('Fehler beim Erzeugen der Karte:', exc)


def _choose_utm_crs_from_lonlat(lon: float, lat: float):
    """Bestimme eine passende UTM-CRS (EPSG) aus Lon/Lat (WGS84)."""
    # UTM zone calculation
    zone = int((lon + 180) / 6) + 1
    hemisphere = 'north' if lat >= 0 else 'south'
    # EPSG codes: northern hemisphere UTM zones are 32601..32660, southern 32701..32760
    if hemisphere == 'north':
        epsg = 32600 + zone
    else:
        epsg = 32700 + zone
    return epsg


def export_geojson_with_pv_rows(geojson_path: str,
                                output_html: str = "agri_pv_plot.html",
                                breite_fahrspur: float = 3.0,
                                breite_gruenstreifen: float = 10.0,
                                row_direction: str = "N-S",
                                pv_row_width_m: float = None,
                                open_in_browser: bool = True):
    """
    Liest eine GeoJSON-Fläche ein, legt innerhalb der Fläche (abzüglich Randstreifen)
    parallele Fahrspuren an und exportiert die Visualisierung als HTML (OpenStreetMap / folium).

    Parameter:
    - geojson_path: Pfad zur GeoJSON-Datei (WGS84 erwartet)
    - output_html: Pfad zur Ausgabedatei (HTML)
    - breite_fahrspur: Abstand zwischen den Mittellinien der Fahrspuren (Meter)
    - breite_gruenstreifen: Randstreifen, der zum Wenden freigehalten wird (Meter)
    - row_direction: "N-S" oder "E-W" (Ausrichtung der PV-Reihen)

    Rückgabe: Path zum gespeicherten HTML
    """
    geojson_path = Path(geojson_path)
    if not geojson_path.exists():
        raise FileNotFoundError(f"GeoJSON nicht gefunden: {geojson_path}")

    # 1) GeoJSON lesen (WGS84 angenommen)
    gdf = gpd.read_file(str(geojson_path))
    if gdf.empty:
        raise ValueError("GeoJSON enthält keine Geometrien")

    # vereinige alle Polygone zu einer Fläche
    gdf = gdf.to_crs(epsg=4326)
    geom = unary_union(gdf.geometry)
    if geom.geom_type == 'GeometryCollection':
        # nimm nur Polygone
        polys = [g for g in geom.geoms if g.geom_type in ('Polygon', 'MultiPolygon')]
        geom = unary_union(polys)

    centroid = geom.centroid
    lon, lat = centroid.x, centroid.y

    # 2) Projektieren in eine lokale metrische CRS (UTM)
    utm_epsg = _choose_utm_crs_from_lonlat(lon, lat)
    gdf_utm = gpd.GeoDataFrame(geometry=[geom], crs='EPSG:4326').to_crs(epsg=utm_epsg)
    poly_utm = gdf_utm.geometry.iloc[0]

    # Gesamtfläche des Feldes in m^2 (projiziertes Polygon liefert Meter)
    total_area_m2 = poly_utm.area
    total_area_ha = total_area_m2 / 10000.0

    # 3) Innenfläche erzeugen (abzüglich Grünstreifen)
    inner = poly_utm.buffer(-breite_gruenstreifen)
    if inner.is_empty:
        raise ValueError("Nach Abzug des Grünstreifens bleibt keine nutzbare Fläche übrig.")

    usable_area_m2 = inner.area
    usable_area_ha = usable_area_m2 / 10000.0

    # Gib Flächenwerte aus (m^2 und ha)
    print(f"Gesamtfläche Feld: {total_area_m2:.2f} m² ({total_area_ha:.4f} ha)")
    print(f"Nutzbare Fläche nach Abzug Grünstreifen: {usable_area_m2:.2f} m² ({usable_area_ha:.4f} ha)")

    # 4) Erzeuge parallele Linien über die Bounding Box und schneide mit inner
    minx, miny, maxx, maxy = inner.bounds

    lines = []
    # row_direction: 'N-S' -> Linien parallel zur y-Achse (konstante x),
    # 'E-W' -> Linien parallel zur x-Achse (konstante y)
    if row_direction.upper() in ('N-S', 'NS', 'NORTH-SOUTH', 'NORD-SUED', 'NORD_SUED'):
        start = minx - breite_fahrspur
        stop = maxx + breite_fahrspur
        xs = np.arange(start, stop + breite_fahrspur, breite_fahrspur)
        for x in xs:
            line = LineString([(x, miny - 10 * breite_fahrspur), (x, maxy + 10 * breite_fahrspur)])
            seg = line.intersection(inner)
            if not seg.is_empty:
                # seg kann LineString, MultiLineString oder andere Geometrietypen sein
                if seg.geom_type == 'LineString':
                    if seg.length > 0:
                        lines.append(seg)
                elif seg.geom_type == 'MultiLineString':
                    for s in seg.geoms:
                        if s.length > 0:
                            lines.append(s)
                else:
                    # Punkt- oder andere Schnittergebnisse werden ignoriert
                    continue
    else:
        # E-W (default)
        start = miny - breite_fahrspur
        stop = maxy + breite_fahrspur
        ys = np.arange(start, stop + breite_fahrspur, breite_fahrspur)
        for y in ys:
            line = LineString([(minx - 10 * breite_fahrspur, y), (maxx + 10 * breite_fahrspur, y)])
            seg = line.intersection(inner)
            if not seg.is_empty:
                if seg.geom_type == 'LineString':
                    if seg.length > 0:
                        lines.append(seg)
                elif seg.geom_type == 'MultiLineString':
                    for s in seg.geoms:
                        if s.length > 0:
                            lines.append(s)
                else:
                    # Punkt- oder andere Schnittergebnisse werden ignoriert
                    continue

    # 5) Konvertiere die Linien zurück nach WGS84 für die Anzeige
    if not lines:
        raise ValueError("Keine Fahrspuren innerhalb der nutzbaren Fläche erzeugt.")

    rows_gdf = gpd.GeoDataFrame(geometry=lines, crs=f"EPSG:{utm_epsg}")
    # rows_gdf ist in UTM (Meter) -> Länge in Metern verfügbar
    total_row_length_m = float(rows_gdf.length.sum())
    rows_wgs = rows_gdf.to_crs(epsg=4326)
    poly_wgs = gpd.GeoDataFrame(geometry=[poly_utm], crs=f"EPSG:{utm_epsg}").to_crs(epsg=4326).geometry.iloc[0]
    inner_wgs = gpd.GeoDataFrame(geometry=[inner], crs=f"EPSG:{utm_epsg}").to_crs(epsg=4326).geometry.iloc[0]

    # 6) Erstelle die Folium-Karte
    import folium

    center = [lat, lon]
    m = folium.Map(location=center, zoom_start=17)

    # Randfläche (original)
    folium.GeoJson(data=gpd.GeoSeries([geom], crs='EPSG:4326').__geo_interface__,
                   name='Feldrand').add_to(m)

    # Nutzbare Fläche (inner)
    folium.GeoJson(data=gpd.GeoSeries([inner_wgs], crs='EPSG:4326').__geo_interface__,
                   style_function=lambda x: {'fillColor': "#1ca728", 'color': "#1ca728", 'weight': 1, 'fillOpacity': 0.3},
                   name='PV-nutzfläche').add_to(m)

    # Reihen hinzufügen
    rows_fg = folium.FeatureGroup(name='PV-Reihen')
    for _, row in rows_wgs.iterrows():
        geom_row = row.geometry
        # row.geometry.coords liefert (lon, lat) Punkte; folium erwartet (lat, lon)
        try:
            coords_latlon = [(y, x) for x, y in geom_row.coords]
        except Exception:
            # Falls MultiLineString oder anderes, versuche einzelne Geometrien
            coords_latlon = []
            if hasattr(geom_row, 'geoms'):
                for part in geom_row.geoms:
                    if hasattr(part, 'coords'):
                        coords_latlon.extend([(y, x) for x, y in part.coords])
        if coords_latlon:
            folium.PolyLine(locations=coords_latlon, color="#ffee00", weight=2).add_to(rows_fg)
    rows_fg.add_to(m)

    # Fit bounds
    try:
        # Verwende die WGS84-Bounds der inneren Fläche für fit_bounds
        b_minx, b_miny, b_maxx, b_maxy = inner_wgs.bounds
        # fit_bounds expects [[southwest_lat, southwest_lon], [northeast_lat, northeast_lon]]
        m.fit_bounds([[b_miny, b_minx], [b_maxy, b_maxx]])
    except Exception:
        pass

    out_path = Path(output_html)
    m.save(str(out_path))

    # Berechne maximale PV-Fläche: Summe der Längen der Reihen * Breite pro Reihe
    pv_area_m2 = 0.0
    if pv_row_width_m is not None and total_row_length_m > 0:
        pv_area_m2 = total_row_length_m * float(pv_row_width_m)

    # Öffne im Browser (optional) — robust: mehrere Fallbacks
    if open_in_browser:
        opened = False
        try:
            opened = webbrowser.open(out_path.as_uri(), new=2)
        except Exception:
            opened = False

        if not opened:
            # Platform-specific fallbacks
            try:
                import os
                import subprocess
                import sys
                p = str(out_path.resolve())
                if sys.platform.startswith('win'):
                    # Windows: os.startfile öffnet die Datei mit Standardanwendung
                    os.startfile(p)
                    opened = True
                elif sys.platform.startswith('darwin'):
                    subprocess.run(['open', p], check=False)
                    opened = True
                else:
                    # Linux/Unix
                    subprocess.run(['xdg-open', p], check=False)
                    opened = True
            except Exception:
                opened = False

        if not opened:
            print(f"Karte gespeichert unter: {out_path} (Öffnen im Browser fehlgeschlagen)")
    else:
        print(f"Karte gespeichert unter: {out_path}")

    return out_path, total_area_m2, usable_area_m2, pv_area_m2


if __name__ == "__main__":
    main()


