import sys
from pathlib import Path

# ensure module path
p = Path(__file__).resolve().parents[1] / 'Projekt_02_Energielandschaft' / 'AA_Projekt_02_Energielandschaft'
if str(p) not in sys.path:
    sys.path.insert(0, str(p))

from Projekt_02_Energielandschaft_PVLIB import run_simulation_from_cfg

import pandas as pd
import numpy as np


def test_pvlib_horizontal_fallback(tmp_path):
    # create a small hourly weather CSV with Unnamed: 0 timestamps
    times = pd.date_range('2020-06-01', periods=24, freq='H')
    df = pd.DataFrame({
        'Unnamed: 0': times,
        'dni': np.linspace(0, 800, 24),
        'dhi': np.linspace(0, 200, 24),
        'ghi': np.linspace(0, 1000, 24),
    })
    csv = tmp_path / 'weather.csv'
    df.to_csv(csv, index=False)

    cfg = {
        'pv_type': 'horizontal',
        # ensure at least 2 modules (default module area 1.85 m2)
        'pv_footprint_m2': 1.85 * 2,
        'tilt': 30,
        'lat': 51.08,
        'lon': 6.49,
    }

    summary = run_simulation_from_cfg(cfg, weather_csv=csv)
    assert summary is not None
    assert isinstance(summary, dict)
    assert 'number_of_modules' in summary
    assert summary['number_of_modules'] >= 1
    assert 'total_energy_kwh' in summary
