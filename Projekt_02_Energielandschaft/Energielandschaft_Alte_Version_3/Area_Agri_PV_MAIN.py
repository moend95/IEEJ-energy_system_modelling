## Agri-PV Fläche berechnung 
## MAIN Script
## Import: OSM Way-ID
## Output: Plot, Werte für PV-Dichte, Fläche, Anzahl der Module

## Input: OSM Way-ID
# way_id = 822428142
way_id = 168868469

## Output: Plot, Werte für PV-Dichte, Fläche, Anzahl der Module
if __name__ == "__main__":
    from Area_Import_OSM import xy_coordinates
    coordinates = xy_coordinates
    from AgriPV_Dichte import plot_field_with_lines, Lvor, Bg, An, Aarbeits, max_area_percentage
    plot_field_with_lines(coordinates, Lvor, Bg, An, Aarbeits, max_area_percentage)

