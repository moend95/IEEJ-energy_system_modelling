"""
Tests Ladevorgangsmodell Green Energy Hub (core/geh_sessions.py)
================================================================
Schnelle Tests auf einem vollen Jahr (ohne Datei-Zwischenspeicher):
Jahresenergie, Ladepunkte, Cluster-Grenze, Determinismus, Vorgänge pro Tag.
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core import geh_profiles as gp  # noqa: E402
from core.geh_sessions import SESSION_CLUSTERS, _run_queue, simulate_charging_sessions  # noqa: E402
from core.module_green_energy_hub import GEH_VARIANTS  # noqa: E402

YEAR_INDEX = pd.date_range("2021-01-01 00:00", periods=35_040, freq="15min")
TOL = 1e-6

# Cluster → (Tagesform, Tagesfaktoren, Sonntagsfahrverbot, Jahresenergie)
SPECS = {
    "mcs": (gp.SHAPE_MCS, gp.DAY_FACTORS_MCS, True, GEH_VARIANTS["Basis"]["mcs_kwh"]),
    "hpc": (gp.SHAPE_HPC, gp.DAY_FACTORS_HPC, False, GEH_VARIANTS["Basis"]["hpc_kwh"]),
}


def _arrival_shape(name):
    local = gp._local_time(YEAR_INDEX)
    weekday = local.weekday.to_numpy()
    day_type = np.where(weekday == 6, 2, np.where(weekday == 5, 1, 0))
    shape, day_factors, ban, _ = SPECS[name]
    return gp._base_shape(local.hour.to_numpy(), day_type, shape, day_factors, ban)


def _simulate(name, seed=42):
    return simulate_charging_sessions(
        YEAR_INDEX, SESSION_CLUSTERS[name], _arrival_shape(name), SPECS[name][3], seed=seed, cache_dir=None
    )


@pytest.fixture(scope="module", params=["mcs", "hpc"])
def session_run(request):
    return request.param, _simulate(request.param)


def test_jahresenergie(session_run):
    name, r = session_run
    assert r.kw.sum() * 0.25 == pytest.approx(SPECS[name][3], rel=0.005)
    assert r.kw_1min.sum() / 60 == pytest.approx(r.kw.sum() * 0.25, rel=1e-9)


def test_ladepunkte_und_cluster_grenze(session_run):
    name, r = session_run
    cluster = SESSION_CLUSTERS[name]
    assert r.max_concurrent <= cluster["points"]
    assert r.kw_1min.max() <= cluster["limit_kw"] + TOL
    assert r.kw.max() <= cluster["limit_kw"] + TOL
    assert (r.kw >= 0).all()
    print(f"\n[{name}] {r.sessions} Vorgänge, max. {r.max_concurrent} gleichzeitig, "
          f"Spitze {r.peak_kw:.0f} kW (1 min {r.peak_1min_kw:.0f} kW), "
          f"mittlere Wartezeit {r.mean_wait_min:.1f} min, Laufzeit {r.runtime_s:.2f} s")


def test_determinismus():
    a = _simulate("hpc", seed=42)
    b = simulate_charging_sessions(YEAR_INDEX, dict(SESSION_CLUSTERS["hpc"]), _arrival_shape("hpc"),
                                   SPECS["hpc"][3], seed=42, cache_dir=None)
    np.testing.assert_array_equal(a.kw, b.kw)
    c = _simulate("hpc", seed=7)
    assert not np.array_equal(a.kw, c.kw)
    assert c.kw.sum() == pytest.approx(a.kw.sum(), rel=0.005)


def test_hpc_vorgaenge_pro_tag():
    r = _simulate("hpc")
    per_day = r.sessions / (len(YEAR_INDEX) / 96)
    assert 190 <= per_day <= 230


def test_warteschlange_fifo_und_drosselung():
    # 3 Fahrzeuge à 100 kWh, 2 Ladepunkte, Wunschleistung 600 kW, Grenze 600 kW
    kw, wait, concurrent = _run_queue(
        np.array([0, 0, 0]), np.array([100.0, 100.0, 100.0]), np.array([600.0, 600.0, 600.0]),
        points=2, limit_kw=600.0, n_minutes=60,
    )
    assert concurrent == 2
    assert kw.max() == pytest.approx(600.0)                     # proportional gedrosselt
    assert kw.sum() / 60 == pytest.approx(300.0)                # nichts geht verloren
    # Erste zwei laden je 300 kW → 20 min; das dritte wartet 20 min
    assert wait == pytest.approx(20 / 3)


def test_profile_modell_bleibt_verfuegbar():
    v = GEH_VARIANTS["Basis"]
    smooth = gp.build_geh_load_profiles(YEAR_INDEX, v, charging_model="profile")
    sessions = gp.build_geh_load_profiles(YEAR_INDEX, v, charging_model="sessions")
    assert "sessions" not in smooth.attrs and set(sessions.attrs["sessions"]) == {"mcs", "hpc"}
    # übrige Profile in beiden Modellen identisch
    for col in ("ccs_kw", "ac_kw", "building_kw", "h2_demand_kwh"):
        np.testing.assert_array_equal(smooth[col].to_numpy(), sessions[col].to_numpy())
    with pytest.raises(ValueError):
        gp.build_geh_load_profiles(YEAR_INDEX, v, charging_model="unbekannt")
