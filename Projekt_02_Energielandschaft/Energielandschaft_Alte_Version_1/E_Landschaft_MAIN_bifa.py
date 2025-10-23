# === SCRIPT 2: Vertikale Bifaciale PV-Simulation ===
# Dieser Script-Block benötigt Shapely==1.8.5
# Installation: pip install shapely==1.8.5

import pandas as pd
from shapely.geometry import box, LineString
import matplotlib.pyplot as plt
from pvfactors.run import pvfactors_timeseries
from pvlib.location import Location
from pvlib.pvsystem import PVSystem
from pvlib.modelchain import ModelChain

# Funktionen import_osm_areas und compute_pv_density aus Script 1 kopiert

def import_osm_areas(bbox):
    tags = {"landuse": "farmland"}
    gdf = ox.geometries_from_bbox(*bbox, tags)
    fields = gdf[gdf.geometry.type.isin(["Polygon","MultiPolygon"])].copy()
    fields["geometry"] = fields.geometry.apply(lambda p: box(*p.bounds))
    ax = fields.plot(edgecolor="green", facecolor="none")
    ax.set_title("OSM: Ackerflächen")
    plt.show()
    return fields


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

# Ende Kopie

# Funktion: Bifaciale PV-Simulation

def simulate_bifacial(fields, lines, module_params, weather, lat, lon, tz, bifac_params):
    loc = Location(lat, lon, tz)
    sol = loc.get_solarposition(weather.index)
    irr = pvfactors_timeseries(
        sol['apparent_zenith'], sol['azimuth'],
        weather['dni'], weather['ghi'], weather['dhi'],
        gcr=bifac_params['gcr'],
        albedo=bifac_params['albedo'],
        pvrow_height=bifac_params['pvrow_height'],
        pvrow_width=bifac_params['pvrow_width'],
        max_angle=bifac_params['max_angle']
    )
    eff = irr['front'] + bifac_params['bifaciality'] * irr['back']
    system = PVSystem(
        module_parameters=module_params['module'],
        inverter_parameters=module_params['inverter'],
        surface_tilt=90, surface_azimuth=90
    )
    mc = ModelChain(system, loc)
    mc.run_model_from_effective_irradiance(eff, weather['temp_air'], weather['wind_speed'])
    ac = mc.results.ac.sum()
    print(f"Jahresertrag bifacial (kWh): {ac:.0f}")
    mc.results.ac.plot(title="AC-Leistung bifacial")
    plt.show()
    return ac

# Main-Block Script 2
if __name__=="__main__":
    weather = pd.read_csv(
        '../Input/dwd_data_solar_10min_koeln_2020-2023.csv',
        index_col='datetime', parse_dates=['datetime']
    ).loc['2022-01-01':'2022-12-31'].resample('h').mean()
    weather.index = weather.index.tz_localize('Europe/Berlin')
    bifac_params = {'gcr':0.35, 'albedo':0.2, 'bifaciality':0.75, 'pvrow_height':3, 'pvrow_width':4, 'max_angle':60}
    module_params = {'module':{'pdc0':300,'gamma_pdc':-0.003}, 'inverter':{'pdc0':5000}}
    fields = import_osm_areas((51.0,6.4,51.1,6.5))
    lines, n_mod = compute_pv_density(fields, 2.5, 4.0, 0.1)
    module_params['n_modules'] = n_mod
    simulate_bifacial(fields, lines, module_params, weather, 50.9375, 6.9603, 'Europe/Berlin', bifac_params)
