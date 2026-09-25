"""
Tests Green Energy Hub (Machbarkeitsstudie „Autohof der Zukunft“)
===================================================================
Schnelle Tests: Datenmodell, Ladeprofile, Dispatch mit synthetischen Arrays.
Integrationstests (@pytest.mark.slow): einmal run_simulation je Variante.
"""

import sys
from dataclasses import fields
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.io_types import GuiInput, SimOutput
from core.geh_profiles import build_geh_load_profiles
from core.module_green_energy_hub import GEH_VARIANTS, LHV_H2_KWH_PER_KG

DT_H = 0.25
# Gleicher Zeitindex wie die Wetterdaten (2021, 15 min, tz-naiv UTC)
YEAR_INDEX = pd.date_range("2021-01-01 00:00", periods=35_040, freq="15min")

CLUSTERS = [
    ("mcs_kw", "mcs_kwh", "mcs_limit_kw"),
    ("ccs_kw", "ccs_kwh", "ccs_limit_kw"),
    ("hpc_kw", "hpc_kwh", "hpc_limit_kw"),
    ("ac_kw", "ac_kwh", "ac_limit_kw"),
    ("building_kw", "building_kwh", None),
]


@pytest.fixture(scope="module")
def profiles():
    return {name: build_geh_load_profiles(YEAR_INDEX, v) for name, v in GEH_VARIANTS.items()}


# ---------------------------------------------------------------------------
# Datenmodell
# ---------------------------------------------------------------------------

def test_guiinput_geh_felder():
    names = {f.name for f in fields(GuiInput)}
    for neu in ("geh_variant", "geh_pv_kwp", "geh_battery_kwh", "geh_battery_kw",
                "geh_h2_demand_t_per_a", "geh_h2_min_soc"):
        assert neu in names
    for alt in ("geh_h2_load_scenario", "geh_e_load_scenario",
                "geh_dispenser_demand_kg_per_h", "geh_storage_max_charge_kw"):
        assert alt not in names


def test_simoutput_geh_felder():
    names = {f.name for f in fields(SimOutput)}
    assert "geh_h2_curtailed_kwh" not in names
    for neu in ("geh_pv_sum_energy_kwh", "geh_electrolyzer_full_load_hours",
                "geh_h2_unmet_kwh", "geh_battery_full_cycles", "geh_battery_soc_df",
                "grid_import_kwh", "grid_export_kwh", "grid_max_import_kw"):
        assert neu in names


# ---------------------------------------------------------------------------
# Ladeprofile
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("variant", ["Basis", "Erweiterung"])
def test_profile_jahresenergie_und_grenzen(profiles, variant):
    v = GEH_VARIANTS[variant]
    df = profiles[variant]
    for col, energy_key, limit_key in CLUSTERS:
        energy = df[col].sum() * DT_H
        assert energy == pytest.approx(v[energy_key], rel=0.005, abs=1e-6), col
        if limit_key is not None:
            assert df[col].max() <= v[limit_key] + 1e-9, col
    h2_target = v["h2_demand_t_per_a"] * 1000 * LHV_H2_KWH_PER_KG
    assert df["h2_demand_kwh"].sum() == pytest.approx(h2_target, rel=0.005)
    assert (df.to_numpy() >= 0).all()


def test_profile_basis_ohne_parkhaus(profiles):
    assert (profiles["Basis"]["ac_kw"] == 0).all()


def test_profile_reproduzierbar():
    a = build_geh_load_profiles(YEAR_INDEX, GEH_VARIANTS["Erweiterung"], seed=7)
    b = build_geh_load_profiles(YEAR_INDEX, GEH_VARIANTS["Erweiterung"], seed=7)
    pd.testing.assert_frame_equal(a, b)


def test_profile_sonntagsfahrverbot(profiles):
    df = profiles["Erweiterung"]
    local = YEAR_INDEX.tz_localize("UTC").tz_convert("Europe/Berlin")
    sunday = local.weekday == 6
    ban = df["mcs_kw"][sunday & (local.hour < 22)].mean()
    after = df["mcs_kw"][sunday & (local.hour >= 22)].mean()
    assert after > 2 * ban


# ---------------------------------------------------------------------------
# PV am Hub
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def weather_df():
    from Simulation import Simulator
    return Simulator().weather_df


def test_geh_pv_erweiterung_ertrag(weather_df):
    from core.module_green_energy_hub import simulate_geh_pv
    pv = simulate_geh_pv(weather_df, GEH_VARIANTS["Erweiterung"]["pv_kwp"], weather_df.index)
    assert len(pv) == len(weather_df)
    assert (pv >= 0).all()
    assert pv.sum() * DT_H == pytest.approx(1_060_000, rel=0.10)


def test_geh_pv_null_kwp(weather_df):
    from core.module_green_energy_hub import simulate_geh_pv
    assert (simulate_geh_pv(weather_df, 0.0, weather_df.index) == 0).all()
