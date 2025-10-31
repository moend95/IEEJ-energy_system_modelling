from pathlib import Path
import json, sys
p = Path(__file__).resolve().parent / 'Projekt_02_Energielandschaft' / 'AA_Projekt_02_Energielandschaft'
if str(p) not in sys.path:
    sys.path.insert(0, str(p))

from Projekt_02_Energielandschaft_RUN_SKRIPT import Application
from shapely.geometry import mapping, Polygon

# write a small test geojson
poly = Polygon([(6.49,51.08),(6.495,51.08),(6.495,51.085),(6.49,51.085)])
geo = {"type":"FeatureCollection","features":[{"type":"Feature","geometry":mapping(poly),"properties":{}}]}
geo_path = Path('test_poly.geojson')
with geo_path.open('w', encoding='utf-8') as f:
    json.dump(geo, f)

app = Application()
# call run programmatically (non-interactive)
app.run(geojson_path=str(geo_path), out_html='test_agri_pv_plot.html', open_in_browser=False)
print('Done')
