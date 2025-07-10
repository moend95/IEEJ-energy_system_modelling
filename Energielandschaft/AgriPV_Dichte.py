'''
-PV Dichte berechnen (abhängig von Traktorbreite plus Wenderadius, jede Spalte abfahren oder jede zweite wegen wenderadius)
	- Eingabe: Traktor Breite und Länge bestimmt "freien Randbereich/Randfläche"
	- Eingabe: Traktor Breite bestimmt "Spalten-Breite plus Sicherheitsabstand"

Input: Flächen aus OSM (Area_Import_OSM), Traktor Breite (und Länge?), Sicherheitsfaktor (wenn nicht intern vorgegeben)
Output: Map Plot mit Linien eingezeichnet, Anzahl an PV Modulen, Flächennutzung Anteile
'''

## Agri-PV Dichte/Flächennutzung berechnen
## Import: Koordinaten aus OSM (Koordinaten_Import_OSM), Fläche aus OSM (Area_Import_OSM)
## Input: Koordinaten der Fläche, Länge des Vorgewendes, Breite der Grünstreifen, Winkel, Arbeitsbreite, maximaler Flächenanteil mit PV-Modulen
## Output: Anzahl der PV-Modul Reihen, Fläche mit Grünstreifen bedeckt, prozentualer Anteil der Fläche Agrun zur Gesamtfläche Ag, Plot der Fläche mit eingezeichneten Linien

import matplotlib.pyplot as plt
from shapely.geometry import Polygon, LineString, Point
import numpy as np
import ast

def calculate_intersection_points(polygon, line):
    intersection_points = polygon.intersection(line)
    if isinstance(intersection_points, Point):
        return [intersection_points]
    elif isinstance(intersection_points, LineString):
        return list(intersection_points.coords)
    elif hasattr(intersection_points, 'geoms'):
        return [pt for geom in intersection_points.geoms for pt in geom.coords]
    return []

def plot_line_with_intersections(polygon, centroid, angle_radians, distance, Bg, max_area, existing_line_segments):
    dx = np.sin(angle_radians)
    dy = np.cos(angle_radians)
    new_centroid = Point(centroid.x + distance * dx, centroid.y + distance * dy)
    
    line_length = 1e5
    line = LineString([
        (new_centroid.x - line_length * dy, new_centroid.y + line_length * dx),
        (new_centroid.x + line_length * dy, new_centroid.y - line_length * dx)
    ])
    
    intersection_points = calculate_intersection_points(polygon, line)
    
    if len(intersection_points) < 2:
        return False, existing_line_segments
    
    x_vals = [pt[0] for pt in intersection_points]
    y_vals = [pt[1] for pt in intersection_points]
    
    line_segment = [(x_vals[0], y_vals[0]), (x_vals[1], y_vals[1])]
    total_length = sum(LineString(seg).length for seg in existing_line_segments) + LineString(line_segment).length
    
    if total_length * Bg > max_area:
        remaining_length = max_area / Bg - sum(LineString(seg).length for seg in existing_line_segments)
        if remaining_length <= 0:
            return False, existing_line_segments

        factor = remaining_length / LineString(line_segment).length
        mid_x = (x_vals[0] + x_vals[1]) / 2
        mid_y = (y_vals[0] + y_vals[1]) / 2
        x_vals = [
            mid_x - factor * (mid_x - x_vals[0]),
            mid_x + factor * (x_vals[1] - mid_x)
        ]
        y_vals = [
            mid_y - factor * (mid_y - y_vals[0]),
            mid_y + factor * (y_vals[1] - mid_y)
        ]
        line_segment = [(x_vals[0], y_vals[0]), (x_vals[1], y_vals[1])]
        existing_line_segments.append(line_segment)
        return False, existing_line_segments
    
    existing_line_segments.append(line_segment)
    return total_length * Bg <= max_area, existing_line_segments

def plot_field_with_lines(coordinates, Lvor, Bg, An, Aarbeits, max_area_percentage):
    polygon = Polygon(coordinates)
    
    from Area_Import_OSM import area_m2  # Import "area_m2" aus Area_Import_OSM
    area = area_m2 # Fläche des Feldes in Quadratmetern
    
    max_area = max_area_percentage / 100 * area

    centroid = polygon.centroid
    offset_distance = Lvor + (Bg / 2)
    offset_polygon = polygon.buffer(-offset_distance)

    angle_radians = np.radians(An)
    existing_line_segments = []
    num_pv_module_rows = 0

    result, existing_line_segments = plot_line_with_intersections(offset_polygon, centroid, angle_radians, 0, Bg, max_area, existing_line_segments)

    if result:
        num_pv_module_rows += 1
    else:
        total_length = sum(LineString(seg).length for seg in existing_line_segments)
        Agrun = total_length * Bg
        print(f"\nAbgefragte Variablen:")
        print(f"Anzahl der Ecken des Feldes: {len(coordinates)}")
        print("Koordinaten der Ecken:")
        for j, coord in enumerate(coordinates, start=1):
            print(f"  Ecke {j}: (x={coord[0]}, y={coord[1]})")
        print(f"Laenge vom Vorgewende: {Lvor} Meter")
        print(f"Breite der Gruenstreifen (Bg): {Bg} Meter")
        print(f"Winkel (An): {An} Grad")
        print(f"Arbeitsbreite (Aarbeits): {Aarbeits} Meter")
        print(f"Maximale Flaeche mit PV-Modulen bedeckt: {max_area_percentage} Prozent")
        print(f"Die Flaeche Ag vom Feld betraegt {area:.2f} Quadratmeter")
        print(f"Anzahl der PV-Modul Reihen: {num_pv_module_rows}")
        print(f"Flaeche mit Gruenstreifen bedeckt (Agrun): {Agrun:.2f} Quadratmeter")
        print(f"Prozentualer Anteil der Flaeche Agrun zur Gesamtflaeche Ag: {Agrun / area * 100:.2f}%")
        return

    distance_multiplier = 1
    while distance_multiplier * (Aarbeits + Bg) < max(polygon.bounds[2] - polygon.bounds[0], polygon.bounds[3] - polygon.bounds[1]):
        distances = [(Aarbeits + Bg) * distance_multiplier, -(Aarbeits + Bg) * distance_multiplier]
        for distance in distances:
            result, existing_line_segments = plot_line_with_intersections(offset_polygon, centroid, angle_radians, distance, Bg, max_area, existing_line_segments)
            if result:
                num_pv_module_rows += 1
                total_length = sum(LineString(seg).length for seg in existing_line_segments)
                Agrun = total_length * Bg
                print(f"Anzahl der Linien: {num_pv_module_rows}")
                print(f"Flaeche der Gruenstreifen: {Agrun:.2f} Quadratmeter")
                print(f"Prozentualer Anteil der Flaeche Agrun zur Gesamtflaeche Ag: {Agrun / area * 100:.2f}%")
                if Agrun / area * 100 >= max_area_percentage:
                    print("\nMaximale Flaeche erreicht")
                    plot_polygons_and_lines(polygon, offset_polygon, centroid, existing_line_segments, Bg)
                    return
        distance_multiplier += 1

    total_length = sum(LineString(seg).length for seg in existing_line_segments)
    Agrun = total_length * Bg
    print(f"\nAbgefragte Variablen:")
    print(f"Anzahl der Ecken des Feldes: {len(coordinates)}")
    print("Koordinaten der Ecken:")
    for j, coord in enumerate(coordinates, start=1):
        print(f"  Ecke {j}: (x={coord[0]}, y={coord[1]})")
    print(f"Laenge vom Vorgewende: {Lvor} Meter")
    print(f"Breite der Gruenstreifen (Bg): {Bg} Meter")
    print(f"Winkel (An): {An} Grad")
    print(f"Arbeitsbreite (Aarbeits): {Aarbeits} Meter")
    print(f"Maximale Flaeche mit PV-Modulen bedeckt: {max_area_percentage} Prozent")
    print(f"Die Flaeche Ag vom Feld betraegt {area:.2f} Quadratmeter")
    print(f"Anzahl der PV-Modul Reihen: {num_pv_module_rows}")
    print(f"Gesamtlänge der PV-Modul Reihen: {total_length} Meter")
    print(f"Flaeche mit Gruenstreifen bedeckt (Agrun): {Agrun:.2f} Quadratmeter")
    print(f"Prozentualer Anteil der Flaeche Agrun zur Gesamtflaeche Ag: {Agrun / area * 100:.2f}%")
    plot_polygons_and_lines(polygon, offset_polygon, centroid, existing_line_segments, Bg)

def plot_polygons_and_lines(polygon, offset_polygon, centroid, existing_line_segments, Bg):
    plt.figure()
    x, y = polygon.exterior.xy
    plt.plot(x, y, color='black')
    plt.fill(x, y, alpha=0.5, fc='red', ec='black')

    if not offset_polygon.is_empty:
        ox, oy = offset_polygon.exterior.xy
        plt.plot(ox, oy, color='blue')
        plt.fill(ox, oy, alpha=0.5, fc='yellow', ec='blue')

    for seg in existing_line_segments:
        plt.plot([seg[0][0], seg[1][0]], [seg[0][1], seg[1][1]], color='green', linewidth=Bg)

    plt.legend()
    plt.axis("equal")
    plt.show()

## Parameter für Berechnung festlegen 
## Per Abfrage oder direkt im Code

from Area_Import_OSM import xy_coordinates  # Koordinaten laden
coordinates = xy_coordinates
Lvor = 5 # Länge des Vorgewendes in Metern (Äußerer rosa Rand auf Plot-Darstellung)
Bg = 5 # Breite der Grünstreifen in Metern (Hellgrüner Bereich auf Plot-Darstellung)
An = 0 # Winkel in Grad (Ausrichtung PV, bzw. Grünstreifen)
Aarbeits = 50 # Arbeitsbreite in Metern (Breite der PV-Module)
max_area_percentage = 30 # Maximale Fläche mit PV-Modulen in Prozent 
#plot_field_with_lines(coordinates, Lvor, Bg, An, Aarbeits, max_area_percentage)
if __name__ == "__main__":
    main()

# if __name__ == "__main__":
#     from Area_Import_OSM import xy_coordinates  # Koordinaten laden
#     coordinates = xy_coordinates

#     Lvor = 20
#     Bg = 30
#     An = 0
#     Aarbeits = 20
#     max_area_percentage = 30
#     plot_field_with_lines(coordinates, Lvor, Bg, An, Aarbeits, max_area_percentage)

# # Parameter per Eingabe abfragen
# def get_parameters():
#     coordinates = xy_coordinates
#     Lvor = float(input("Laenge Vorgewende: "))
#     Bg = float(input("Breite Gruenstreifen: "))
#     An = float(input("Winkel: "))
#     Aarbeits = float(input("Arbeitsbreite: "))
#     max_area_percentage = float(input("Maximaler Flaechenanteil: "))
#     return coordinates, Lvor, Bg, An, Aarbeits, max_area_percentage
