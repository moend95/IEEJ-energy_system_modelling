from runpy import run_path
from pathlib import Path
import json

modpath = r"c:\Users\johan\TH_Koeln_Masterprojekt\IEEJ-energy_system_modelling\Projekt_02_Energielandschaft\AA_Projekt_02_Energielandschaft\Projekt_02_Energielandschaft.py"
ns = run_path(modpath)
GeoAreaCalculator = ns['GeoAreaCalculator']
GeoAreaVerticalCalculator = ns['GeoAreaVerticalCalculator']
PVMapPlotter = ns['PVMapPlotter']

out_dir = Path(modpath).resolve().parent / 'outputs'
out_dir.mkdir(exist_ok=True)
emb = out_dir / 'embedded_area.geojson'
if not emb.exists():
    # write embedded geojson from module
    EMB = ns.get('EMBEDDED_GEOJSON')
    if EMB:
        emb.write_text(EMB, encoding='utf-8')

# build a default cfg for horizontal
cfg = {
    'pv_type': 'horizontal',
    'tractor_width': 3.0,
    'tractor_length': 5.0,
    'tractor_turn_radius': 6.0,
    'pv_row_width_m': 9.2,
}

# run calculator and plotter
calc = GeoAreaCalculator(str(emb))
calc.load_and_project()
res = calc.compute_horizontal_pv(3.0,5.0,6.0,pv_row_width_m=9.2)
print('calc res:', res)
plotter = PVMapPlotter(cfg)
out_path, plot_res = plotter.plot(str(emb), out_html=str(out_dir / 'demo_agri_pv_plot.html'), open_in_browser=False)
print('map saved to', out_path)
# save cfg
cfg.update(res)
(out_dir / 'demo_user_selection.json').write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding='utf-8')
print('cfg saved')
