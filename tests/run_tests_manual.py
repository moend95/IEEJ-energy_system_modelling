import sys
from pathlib import Path
p = Path(__file__).resolve().parents[1] / 'Projekt_02_Energielandschaft' / 'AA_Projekt_02_Energielandschaft'
if str(p) not in sys.path:
    sys.path.insert(0, str(p))

from test_field_processor import test_field_processor_basic
from test_pvlib_horizontal import test_pvlib_horizontal_fallback

print('Running test_field_processor_basic...')
try:
    test_field_processor_basic(Path(__file__).resolve().parents[1] / 'tmp_test')
    print('test_field_processor_basic: PASS')
except Exception as e:
    print('test_field_processor_basic: FAIL', e)

print('Running test_pvlib_horizontal_fallback...')
try:
    # create a tmp_path-like object using pathlib.Path
    tmp_dir = Path(__file__).resolve().parents[1] / 'tmp_weather'
    tmp_dir.mkdir(exist_ok=True)
    test_pvlib_horizontal_fallback(tmp_dir)
    print('test_pvlib_horizontal_fallback: PASS')
except Exception as e:
    print('test_pvlib_horizontal_fallback: FAIL', e)
