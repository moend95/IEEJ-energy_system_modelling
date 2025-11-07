# Small runner to test PVMapPlotter
import runpy
from pathlib import Path

modpath = r"c:\Users\johan\TH_Koeln_Masterprojekt\IEEJ-energy_system_modelling\Projekt_02_Energielandschaft\AA_Projekt_02_Energielandschaft\Projekt_02_Energielandschaft.py"
ns = runpy.run_path(modpath)
PVMapPlotter = ns.get('PVMapPlotter')
GeoJSONSelector = ns.get('GeoJSONSelector')

if PVMapPlotter is None:
    raise SystemExit('PVMapPlotter not found in module')

# Load or create a cfg
out_dir = Path(modpath).resolve().parent / 'outputs'
user_cfg_path = out_dir / 'user_selection.json'
if user_cfg_path.exists():
    import json
    cfg = json.loads(user_cfg_path.read_text(encoding='utf-8'))
else:
    # sensible defaults
    cfg = {
        'pv_type': 'horizontal',
        'tractor_width': 3.0,
        'tractor_length': 5.0,
        'tractor_turn_radius': 6.0,
        'pv_row_width_m': 9.2,
    }

geo_path = out_dir / 'embedded_area.geojson'
if not geo_path.exists():
    raise SystemExit(f'embedded geojson not found: {geo_path}')

plotter = PVMapPlotter(cfg)
out_html = out_dir / 'test_agri_pv_plot.html'
print('Running plot ->', out_html)
res = plotter.plot(str(geo_path), out_html=str(out_html), open_in_browser=False)
print('Plot saved to', res)
