from pathlib import Path
import sys, json
p = Path(__file__).resolve().parent / 'Projekt_02_Energielandschaft' / 'AA_Projekt_02_Energielandschaft'
if str(p) not in sys.path:
    sys.path.insert(0, str(p))

from Projekt_02_Energielandschaft_RUN_SKRIPT import Application

# write a small test geojson
from shapely.geometry import mapping, Polygon
poly = Polygon([(6.49,51.08),(6.495,51.08),(6.495,51.085),(6.49,51.085)])
geo = {"type":"FeatureCollection","features":[{"type":"Feature","geometry":mapping(poly),"properties":{}}]}
geo_path = Path('test_poly_noninteractive.geojson')
with geo_path.open('w', encoding='utf-8') as f:
    json.dump(geo, f)

cfg = {
    'pv_type': 'horizontal',
    'tractor_width': 3.0,
    'tractor_length': 5.0,
    'tractor_turn_radius': 6.0,
    'pv_row_width_m': 5.2,
    'tilt': 30,
}

app = Application()
app.run(cfg=cfg, geojson_path=str(geo_path), out_html='test_agri_pv_plot_noninteractive.html', open_in_browser=False)
print('Non-interactive test done')
