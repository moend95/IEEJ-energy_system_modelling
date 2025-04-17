import overpy
import geopandas as gpd
from shapely.geometry import LineString, MultiLineString
from shapely.ops import linemerge
import matplotlib.pyplot as plt


def fetch_streets(bbox: str, min_lat, max_lat, dtype=None, name_filter=None,
                                ref_filter=None) -> gpd.GeoDataFrame:
    """
    Lädt Straßendaten aus OSM, filtert diese, schneidet sie basierend auf Breitengradgrenzen zu und plottet die Ergebnisse.

    Args:
        bbox (str): Der Begrenzungsrahmen im Format (min_lat, min_lon, max_lat, max_lon).
        min_lat (float): Untere Breitengradgrenze zum Zuschneiden der Straßen.
        max_lat (float): Obere Breitengradgrenze zum Zuschneiden der Straßen.
        dtype (str, optional): Der Typ der Straße, z.B. "motorway", "primary". Default ist None.
        name_filter (str, optional): Der Name der Straße, die gefiltert werden soll. Default ist None.
        ref_filter (str, optional): Die Referenznummer der Straße, z.B. "A 44". Default ist None.

    Returns:
        gpd.GeoDataFrame: Ein GeoDataFrame mit den gefilterten und zugeschnittenen Straßen.
    """
    api = overpy.Overpass()

    # Schritt 1: Filtern und Laden der Straßen
    query = f"""
    way["highway"]{bbox};
    (._;>;);
    out geom;
    """
    result = api.query(query)

    road_data = []
    for way in result.ways:
        if dtype and dtype != way.tags.get("highway", ""):
            continue
        if name_filter and name_filter != way.tags.get("name", ""):
            continue
        if ref_filter and ref_filter != way.tags.get("ref", ""):
            continue

        coords = [(float(node.lon), float(node.lat)) for node in way.nodes]
        line = LineString(coords)
        road_data.append({
            "way_id": way.id,
            "name": way.tags.get("name", "Unnamed road"),
            "ref": way.tags.get("ref", "No ref"),
            "highway": way.tags.get("highway", "Unknown"),
            "geometry": line
        })

    roads_gdf = gpd.GeoDataFrame(road_data, geometry="geometry")

    # Schritt 2: Zuschneiden der Straßen basierend auf Breitengrad
    clipped_lines = []

    for _, row in roads_gdf.iterrows():
        line = row.geometry
        segments = []
        coords = list(line.coords)
        for i in range(len(coords) - 1):
            start, end = coords[i], coords[i + 1]
            if (min_lat <= start[1] <= max_lat) or (min_lat <= end[1] <= max_lat):
                segments.append(LineString([start, end]))

        if segments:
            new_line = linemerge(segments)
            clipped_lines.append({
                "way_id": row["way_id"],
                "name": row.get("name", "Unnamed road"),
                "ref": row.get("ref", "No ref"),
                "highway": row.get("highway", "Unknown"),
                "geometry": new_line
            })

    clipped_gdf = gpd.GeoDataFrame(clipped_lines, geometry="geometry")

    # Schritt 3: Plot
    ax = clipped_gdf.plot(
        figsize=(10, 10),
        color='blue',
        linewidth=2
    )
    ax.set_title('Clipped Highway Segment')
    ax.set_xlabel('Longitude')
    ax.set_ylabel('Latitude')
    plt.show()

    return clipped_gdf


# Beispielaufruf
bbox = "(51.036915, 6.465730, 51.073864, 6.594162)"
min_lat = 51.034313
max_lat = 51.085060
clipped_road_gdf = fetch_streets(bbox, min_lat, max_lat, ref_filter="A 44")
#
# import matplotlib.colors as mcolors
# # Definieren Sie eine Farbpalette
# colors = list(mcolors.TABLEAU_COLORS.values())
#
# # Plotten der Geometrien mit unterschiedlichen Farben
# fig, ax = plt.subplots(figsize=(10, 8))
# for i, (idx, row) in enumerate(road_gdf.iterrows()):
#     color = colors[i % len(colors)]  # Eine Farbe der Palette auswählen
#     label = f'Road ID: {row.way_id}'  # Beschriftung der Legende
#     # Plotten der Geometrie
#     gpd.GeoSeries([row.geometry]).plot(ax=ax, color=color, linewidth=2, label=label)
#
# # Legende und Titel konfigurieren
# ax.set_title('Farbcodierte Straßenabschnitte')
# ax.set_xlabel('Längengrad')
# ax.set_ylabel('Breitengrad')
# ax.legend(title='Straßenabschnitte')
#
# plt.show()



desired_ids = [168868466, 168868468, 232431266]
filteredgdf = clipped_road_gdf[clipped_road_gdf['way_id'].isin(desired_ids)]
print(filteredgdf)

filteredgdf.plot(figsize=(10, 10), color='blue', linewidth=2)
plt.show()


from shapely.ops import linemerge, unary_union
merged = unary_union(filteredgdf.geometry)

# Nutzen von linemerge, um bei Bedarf aus MultiLineString einen einfachen LineString zu erzeugen
# Das ist wichtig, falls die Linien nicht verbunden sind oder `unary_union` ein MultiLineString erzeugt
if isinstance(merged, MultiLineString):
    merged = linemerge(merged)

# Erstellen eines neuen GeoDataFrame mit der kombinierten Linie
merged_gdf = gpd.GeoDataFrame({'geometry': [merged]})

# Ausgabe des GeoDataFrame
print(merged_gdf)

# Plotten der zusammengeführten Linie

ax = merged_gdf.plot(figsize=(10, 5), color='blue', linewidth=2)
ax.set_title('Zusammengeführter Straßenabschnitt')
ax.set_xlabel('Längengrad')
ax.set_ylabel('Breitengrad')
plt.show()