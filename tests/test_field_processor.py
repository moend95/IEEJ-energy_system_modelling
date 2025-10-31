import sys
from pathlib import Path
import json

# ensure module path
p = Path(__file__).resolve().parents[1] / 'Projekt_02_Energielandschaft' / 'AA_Projekt_02_Energielandschaft'
if str(p) not in sys.path:
    sys.path.insert(0, str(p))

from Projekt_02_Energielandschaft_FLAECHEN_BERECHNUNG import PVFieldProcessor
from shapely.geometry import mapping, Polygon


def test_field_processor_basic(tmp_path):
    # small polygon around lon~6.49, lat~51.08
    poly = Polygon([(6.49,51.08),(6.495,51.08),(6.495,51.085),(6.49,51.085)])
    geo = {"type":"FeatureCollection","features":[{"type":"Feature","geometry":mapping(poly),"properties":{}}]}
    geo_path = tmp_path / 'test_poly.geojson'
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

    processor = PVFieldProcessor(cfg)
    out_path, total_area_m2, usable_ground_area_m2, pv_footprint_m2, pv_vertical_front_m2 = processor.run(str(geo_path), output_html=str(tmp_path / 'out.html'), open_in_browser=False)

    assert Path(out_path).exists()
    assert total_area_m2 > 0
    assert usable_ground_area_m2 > 0
    assert pv_footprint_m2 > 0
