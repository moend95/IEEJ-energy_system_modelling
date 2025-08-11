# -- Energielandschaft Agri-PV --


# -- Importe -- #
from typing import List, Tuple, Optional
import math
import requests
import numpy as np
import geopandas as gpd
import folium
from shapely.geometry import Polygon, LineString, Point
from pyproj import CRS, Transformer


# -- Typen --
LonLat = Tuple[float, float]
XY = Tuple[float, float]


# -- OSM / Geometrie-Funktionen -- #
def get_osm_polygon(way_id: int, overpass_url: str = "https://overpass-api.de/api/interpreter") -> Polygon:
    """
    Holt Way-Element (Polygon) aus Overpass API und liefert ein Shapely-Polygon in WGS84-Koordinaten zurück.

    Parameter
    ----------
    way_id :
        OSM Way-ID des zu ladenden Polygons.
    overpass_url :
        URL der Overpass-API (Default: offizielle API).

    Rückgabe
    -------
    Polygon
        Polygon in EPSG:4326 (lon, lat) Reihenfolge.
    """
    query = f"""
    [out:json];
    way({way_id});
    (._;>;);
    out body;
    """
    resp = requests.get(overpass_url, params={"data": query.strip()})
    resp.raise_for_status()
    data = resp.json()

    # Knoten sammeln
    nodes = {elem["id"]: (elem["lon"], elem["lat"]) for elem in data["elements"] if elem["type"] == "node"}
    # Way-Knotenreihenfolge
    way_elems = [elem for elem in data["elements"] if elem["type"] == "way"]
    if not way_elems:
        raise ValueError(f"Way {way_id} nicht gefunden.")
    way_nodes = way_elems[0]["nodes"]
    coords = [nodes[nid] for nid in way_nodes]

    # Sicherstellen, dass Polygon geschlossen ist
    if coords[0] != coords[-1]:
        coords.append(coords[0])

    return Polygon(coords)


def project_to_utm(polygon_wgs84: Polygon, utm_epsg: int = 32632) -> Tuple[Polygon, Transformer]:
    """
    Projektiert ein WGS84-Polygon in ein metrisches UTM-CRS und gibt Polygon + Transformer zurück.

    Parameter
    ----------
    polygon_wgs84 :
        Input-Polygon in EPSG:4326.
    utm_epsg :
        EPSG-Code des Ziel-CRS (Default: 32632 = UTM Zone 32N).

    Rückgabe
    -------
    polygon_utm, transformer
        Polygon in metrischen Koordinaten (m) und der Transformer für Rückprojektion.
    """
    gdf = gpd.GeoDataFrame(index=[0], crs="EPSG:4326", geometry=[polygon_wgs84])
    target_crs = CRS.from_epsg(utm_epsg)
    gdf_utm = gdf.to_crs(target_crs)
    polygon_utm = gdf_utm.geometry[0]
    transformer = Transformer.from_crs(target_crs, "EPSG:4326", always_xy=True)
    return polygon_utm, transformer


def calculate_area(polygon_utm: Polygon) -> Tuple[float, float]:
    """
    Berechnet Fläche in Quadratmetern und Hektar.

    Parameter
    ----------
    polygon_utm :
        Polygon im metrischen CRS (z. B. UTM, Meter).

    Rückgabe
    -------
    area_m2, area_ha
    """
    area_m2 = float(polygon_utm.area)
    area_ha = area_m2 / 10_000.0
    return area_m2, area_ha


# -- PV-Layout-Funktionen -- #
def _line_through_point_angle(point: Point, angle_rad: float, length: float = 1e6) -> LineString:
    """
    Erzeugt eine sehr lange Linie durch 'point' mit Winkel 'angle_rad'.
    Winkel 0 = Ausrichtung in y-Richtung (aufsteigend).
    """
    dx = math.sin(angle_rad)
    dy = math.cos(angle_rad)
    # Linie senkrecht zur Ausrichtung erzeugen (damit Schnittlänge über Polygon berechnet werden kann)
    return LineString([
        (point.x - length * dy, point.y + length * dx),
        (point.x + length * dy, point.y - length * dx),
    ])


def calculate_pv_layout(
    polygon: Polygon,
    Lvor: float,
    Bg: float,
    An_deg: float,
    Aarbeits: float,
    max_area_percentage: float,
) -> Tuple[List[Tuple[XY, XY]], float]:
    """
    Berechnet die PV-Reihen als Liniensegmente innerhalb des Polygons unter Berücksichtigung
    von Vorgewende (Lvor), Grünstreifenbreite (Bg), Ausrichtung (An_deg), Arbeitsbreite (Aarbeits)
    und maximalem Flächenanteil (max_area_percentage).

    Parameter
    ----------
    polygon :
        Polygon im metrischen CRS (m).
    Lvor :
        Länge des Vorgewendes in Metern (Abstand zum Rand).
    Bg :
        Breite der Grünstreifen (Meter).
    An_deg :
        Ausrichtungswinkel in Grad.
    Aarbeits :
        Abstand zwischen Reihen (Arbeitsbreite) in Metern.
    max_area_percentage :
        Maximale Flächenabdeckung durch Module in Prozent (0-100).

    Rückgabe
    -------
    line_segments, covered_area
        Liste der Liniensegmente (je Segment: ((x1,y1),(x2,y2))) und die tatsächlich bedeckte Fläche (m²).
    """
    if polygon.is_empty:
        return [], 0.0

    # Reduziertes Polygon (Vorgewende + halb Grünstreifen)
    offset_distance = Lvor + (Bg / 2.0)
    inner = polygon.buffer(-offset_distance)
    if inner.is_empty:
        return [], 0.0

    angle_rad = math.radians(An_deg)
    centroid = inner.centroid

    max_area = (max_area_percentage / 100.0) * polygon.area
    segments: List[Tuple[XY, XY]] = []
    total_length = 0.0

    # zentrale Linie (distance = 0)
    def try_add_line(distance: float) -> bool:
        nonlocal segments, total_length
        # Verschobenen Punkt entlang Ausrichtungsnormal verschieben
        dx = math.sin(angle_rad)
        dy = math.cos(angle_rad)
        shift_x = centroid.x + distance * dx
        shift_y = centroid.y + distance * dy
        line = _line_through_point_angle(Point(shift_x, shift_y), angle_rad)
        inter = inner.intersection(line)

        # mögliche Geometrieformen behandeln
        segs = []
        if inter.is_empty:
            return False
        if isinstance(inter, Point):
            return False
        if isinstance(inter, LineString):
            segs = [inter]
        else:
            # MultiLineString oder Collection
            try:
                segs = [geom for geom in inter.geoms if isinstance(geom, LineString)]
            except Exception:
                return False

        # Aus gewählten Segmenten das längste (oder Summe) verwenden — hier werden jeweils die ersten beiden Endpunkte genommen
        for s in segs:
            seg_len = s.length
            prospective_total = total_length + seg_len
            prospective_area = prospective_total * Bg
            if prospective_area > max_area:
                remaining_len = (max_area / Bg) - total_length
                if remaining_len <= 0:
                    return False
                # Teilsegment zentriert schneiden
                midpoint = s.interpolate(0.5, normalized=True)
                half = remaining_len / 2.0
                part = LineString([s.interpolate(max(0, s.project(midpoint) - half)),
                                   s.interpolate(min(s.length, s.project(midpoint) + half))])
                segments.append(tuple(part.coords[:2]))
                total_length += part.length
                return False
            segments.append(tuple(s.coords[:2]))
            total_length += seg_len
        return True

    # zentrale Linie
    _ = try_add_line(0.0)

    # iterativ nach beiden Seiten Linien setzen
    step = Aarbeits + Bg
    multiplier = 1
    max_span = max(polygon.bounds[2] - polygon.bounds[0], polygon.bounds[3] - polygon.bounds[1]) * 1.5
    while multiplier * step < max_span:
        for sign in (1, -1):
            cont = try_add_line(sign * multiplier * step)
            # Wenn try_add_line gibt False zurück, bedeutet maximale Fläche erreicht oder kein Schnitt
            # Die Schleife wird trotzdem fortgesetzt bis Grenzen erreicht werden können.
        multiplier += 1
        # Abbruchbedingung: falls bereits maximale Fläche erreicht
        if total_length * Bg >= max_area:
            break

    covered_area = total_length * Bg
    return segments, covered_area


# -- Export / Visualisierung -- #
def export_plot_to_osm_html(
    polygon_utm: Polygon,
    offset_polygon_utm: Optional[Polygon],
    segments: List[Tuple[XY, XY]],
    transformer: Transformer,
    filename: str = "agri_pv_plot.html",
    show_in_browser: bool = False,
    line_weight_scale: float = 1.0,
) -> None:
    """
    Exportiert das Polygon, Offset-Polygon und Liniensegmente als interaktive Folium-Karte (HTML).
    Die übergebenen Geometrien müssen im metrischen CRS vorliegen; transformer wandelt in EPSG:4326 zurück.

    Parameter
    ----------
    polygon_utm :
        Originalpolygon in UTM (m).
    offset_polygon_utm :
        Offset/inneres Polygon (kann None oder leer sein).
    segments :
        Liste von Liniensegmenten (je Segment: ((x1,y1),(x2,y2)) ).
    transformer :
        Pyproj Transformer von UTM -> EPSG:4326 (always_xy=True).
    filename :
        Ausgabedateiname für HTML.
    show_in_browser :
        Wenn True, wird der erzeugte HTML im Standard-Browser geöffnet (optional).
    line_weight_scale :
        Skalenfaktor für die Darstellungslinie (standard 1.0).
    """
    def to_latlon_coords(coords: List[XY]) -> List[Tuple[float, float]]:
        return [transformer.transform(x, y) for x, y in coords]

    poly_coords_latlon = to_latlon_coords(list(polygon_utm.exterior.coords))
    center = np.mean(poly_coords_latlon, axis=0)[::-1].tolist()

    m = folium.Map(location=center, zoom_start=17, control_scale=True)

    # Originalpolygon
    folium.Polygon(
        locations=[(lat, lon) for lon, lat in poly_coords_latlon],
        color="black",
        fill=True,
        fill_color="red",
        fill_opacity=0.35,
        tooltip="Feldpolygon"
    ).add_to(m)

    # Offset polygon
    if offset_polygon_utm is not None and not offset_polygon_utm.is_empty:
        off_coords_latlon = to_latlon_coords(list(offset_polygon_utm.exterior.coords))
        folium.Polygon(
            locations=[(lat, lon) for lon, lat in off_coords_latlon],
            color="blue",
            fill=True,
            fill_color="yellow",
            fill_opacity=0.25,
            tooltip="Offset (Vorgewende + Grünstreifen)"
        ).add_to(m)

    # Liniensegmente
    for seg in segments:
        seg_latlon = to_latlon_coords(list(seg))
        folium.PolyLine(
            locations=[(lat, lon) for lon, lat in seg_latlon],
            color="green",
            weight=max(1, int(line_weight_scale)),  # mind. 1
            tooltip="PV-Reihe"
        ).add_to(m)

    m.save(filename)
    print(f"Karte gespeichert unter: {filename}")

    if show_in_browser:
        import webbrowser
        webbrowser.open(filename)


# -- Hilfsfunktionen für Benutzereingabe / Ausgabe -- #
def ask_int(prompt: str, default: int) -> int:
    val = input(f"{prompt} (Standard: {default}): ").strip()
    if val == "":
        return default
    try:
        return int(val)
    except ValueError:
        print("Ungültige Eingabe. Standardwert verwendet.")
        return default


def ask_float(prompt: str, default: float) -> float:
    val = input(f"{prompt} (Standard: {default}): ").strip()
    if val == "":
        return default
    try:
        return float(val)
    except ValueError:
        print("Ungültige Eingabe. Standardwert verwendet.")
        return default


def print_results_table(area_m2: float, area_ha: float, covered_area: float, max_percentage: float) -> None:
    """
    Strukturierte Ausgabe der wichtigsten Resultate.
    """
    covered_pct = (covered_area / area_m2 * 100.0) if area_m2 > 0 else 0.0
    print("\nErgebnisse:")
    print("-" * 50)
    print(f"Feldfläche         : {area_m2:12.2f} m²  ({area_ha:8.4f} ha)")
    print(f"Max. gewünschter Anteil : {max_percentage:6.2f} %")
    print(f"Bedeckte Fläche     : {covered_area:12.2f} m²  ({covered_pct:6.2f} % der Fläche)")
    print("-" * 50)


# -- Main Ablauf -- #
def main():
    """
    Ablaufsteuerung: OSM laden, Projektion, Flächenberechnung, PV-Layout, Export.
    """
    # Way-ID abfragen (Standard gesetzt)
    default_way_id = 168868469
    way_id = ask_int("Bitte die OSM Way-ID eingeben", default_way_id)

    # OSM laden (EPSG:4326)
    polygon_wgs84 = get_osm_polygon(way_id)

    # Projektion in UTM (metrisch)
    utm_epsg = 32632  # Standard: UTM Zone 32N, kann bei Bedarf angepasst werden
    polygon_utm, transformer = project_to_utm(polygon_wgs84, utm_epsg=utm_epsg)

    # Fläche berechnen
    area_m2, area_ha = calculate_area(polygon_utm)

    # Parameter abfragen
    Lvor = ask_float("Länge des Vorgewendes in Metern", 10.0)
    Bg = ask_float("Breite der Grünstreifen in Metern (Bg)", 10.0)
    An = ask_float("Ausrichtungswinkel in Grad (An)", 0.0)
    Aarbeits = ask_float("Arbeitsbreite der PV-Module in Metern (Aarbeits)", 10.0)
    max_area_percentage = ask_float("Maximale PV-Fläche in Prozent", 70.0)

    # PV-Layout berechnen
    segments, covered_area = calculate_pv_layout(
        polygon_utm,
        Lvor=Lvor,
        Bg=Bg,
        An_deg=An,
        Aarbeits=Aarbeits,
        max_area_percentage=max_area_percentage,
    )

    # Ausgabe
    print_results_table(area_m2, area_ha, covered_area, max_area_percentage)
    print(f"Anzahl der PV-Reihen (Segments): {len(segments)}")
    if len(segments) > 0:
        total_length = sum(LineString(s).length for s in segments)
        print(f"Gesamtlänge aller Reihen: {total_length:.2f} m")

    # Export (standardmäßig aktiv)
    do_export = input("HTML-Karte erzeugen? (J/n): ").strip().lower()
    if do_export in ("", "j", "ja", "y", "yes"):
        # Offset-Polygon zur Visualisierung berechnen
        offset_distance = Lvor + (Bg / 2.0)
        offset_poly = polygon_utm.buffer(-offset_distance)
        export_plot_to_osm_html(
            polygon_utm=polygon_utm,
            offset_polygon_utm=offset_poly if not offset_poly.is_empty else None,
            segments=segments,
            transformer=transformer,
            filename="agri_pv_plot.html",
            show_in_browser=True,
            line_weight_scale=max(1.0, Bg / 2.0),
        )


if __name__ == "__main__":
    main()
