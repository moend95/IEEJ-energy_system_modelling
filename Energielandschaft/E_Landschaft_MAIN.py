# === SCRIPT 1: Single-Axis Tracking PV-Simulation ===
# Dieser Script-Block benötigt Shapely ≥2.0
# Installationsbefehl: pip install --upgrade shapely==2.0

import osmnx as ox
import geopandas as gpd
from shapely.geometry import box, LineString
import matplotlib.pyplot as plt
import pandas as pd
from pvlib.location import Location
from pvlib.pvsystem import PVSystem
from pvlib.modelchain import ModelChain

# Funktion: OSM-Felder importieren

def import_osm_areas(bbox):
    tags = {"landuse": "farmland"}
    gdf = ox.features_from_bbox(*bbox, tags)
    fields = gdf[gdf.geometry.type.isin(["Polygon","MultiPolygon"])].copy()
    fields["geometry"] = fields.geometry.apply(lambda p: box(*p.bounds))
    ax = fields.plot(edgecolor="green", facecolor="none")
    ax.set_title("OSM: Ackerflächen")
    plt.show()
    return fields

# Funktion: PV-Zeilenlayout und Dichte berechnen

def compute_pv_density(fields, tractor_width, tractor_length, safety_factor=0.1):
    features, total_modules, total_area, occupied_area = [],0,0,0
    for _, row in fields.iterrows():
        poly = row.geometry
        inner = poly.buffer(-tractor_length)
        spacing = tractor_width*(1+safety_factor)
        minx,miny,maxx,maxy = inner.bounds
        y = miny
        while y<=maxy:
            seg = LineString([(minx,y),(maxx,y)]).intersection(inner)
            if seg.length>0:
                features.append({"geometry":seg})
                total_modules += int(seg.length)
                occupied_area += seg.length*tractor_width
            total_area += poly.area
            y += spacing
    lines = gpd.GeoDataFrame(features, crs=fields.crs)
    usage = occupied_area/total_area
    ax = fields.plot(edgecolor="black", facecolor="none")
    lines.plot(ax=ax, color="blue")
    ax.set_title(f"Module: {total_modules}, Belegung: {usage:.1%}")
    plt.show()
    return lines, total_modules

# Funktion: Single-Axis Tracking Simulation

def simulate_tracking(fields, lines, module_params, weather, lat, lon, tz, track_params):
    loc = Location(lat, lon, tz)
    system = PVSystem(
        module_parameters=module_params['module'],
        inverter_parameters=module_params['inverter'],
        axis_tilt=track_params['axis_tilt'],
        axis_azimuth=track_params['axis_azimuth'],
        max_angle=track_params['max_angle'],
        backtrack=True,
        gcr=track_params['gcr']
    )
    mc = ModelChain(system, loc, orientation_strategy='single_axis')
    mc.run_model(weather)
    ac = mc.results.ac.sum()
    print(f"Jahresertrag Single-Axis Tracking (kWh): {ac:.0f}")
    mc.results.ac.plot(title="AC-Leistung Single-Axis Tracking")
    plt.show()
    return ac

# Main-Block
if __name__=="__main__":
    # Bounding Box und Traktorparameter
    bbox = (51.0, 6.4, 51.1, 6.5)
    tractor_w, tractor_l, safety = 2.5, 4.0, 0.1

    # Wetterdaten einlesen & resamplen
    weather = pd.read_csv(
        '../Input/dwd_data_solar_10min_koeln_2020-2023.csv',
        index_col='datetime', parse_dates=['datetime']
    ).loc['2022-01-01':'2022-12-31'].resample('h').mean()
    #weather.index = weather.index.tz_localize('Europe/Berlin')
    weather.index = weather.index.tz_localize(
        'Europe/Berlin',
        nonexistent='shift_forward',
        ambiguous='NaT'
    )

    # Tracking-Parameter
    track_params = {
        'axis_tilt': 0,
        'axis_azimuth': 180,
        'max_angle': 60,
        'gcr': 0.35
    }

    # Modul- und Inverter-Parameter
    module_params = {
        'module': {'pdc0':300, 'gamma_pdc':-0.003},
        'inverter': {'pdc0':5000}
    }

    # Pipeline
    fields = import_osm_areas(bbox)
    lines, n_mod = compute_pv_density(fields, tractor_w, tractor_l, safety)
    module_params['n_modules'] = n_mod
    simulate_tracking(fields, lines, module_params, weather, 50.9375, 6.9603, 'Europe/Berlin', track_params)
