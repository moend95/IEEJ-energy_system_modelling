"""
Tests Jüchen Süd (Energiekonzept Fraunhofer IEG, Basis-Variante)
=================================================================
Schnelle Tests: Profile, COP-Modell, Wärme-Dispatch.
Integrationstests (@pytest.mark.slow): run_simulation je Versorgungskonzept.
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.js_profiles import build_js_profiles, js_annual_demands
from core.module_juechen_sued import (
    JS_CONCEPTS,
    JSParams,
    concept_cops,
    heat_pump_cop,
    run_js_heat_dispatch,
)

DT_H = 0.25


@pytest.fixture(scope="module")
def weather_df():
    from Simulation import Simulator
    return Simulator().weather_df


@pytest.fixture(scope="module")
def profiles(weather_df):
    return build_js_profiles(weather_df.index, weather_df["temp_air"].to_numpy())


# ---------------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------------

def test_profile_jahresbedarfe(profiles):
    d = js_annual_demands()
    for col, key in [("space_heat_kw", "space_heat_kwh"), ("dhw_kw", "dhw_kwh"), ("cooling_kw", "cooling_kwh"),
                     ("household_kw", "household_kwh"), ("emob_kw", "emob_kwh")]:
        assert profiles[col].sum() * DT_H == pytest.approx(d[key], rel=0.005), col
    assert (profiles.to_numpy() >= 0).all()


def test_profile_spitzen(profiles):
    d = js_annual_demands()
    assert profiles["household_kw"].max() == pytest.approx(d["household_peak_kw"], rel=0.02)
    assert profiles["emob_kw"].max() <= d["emob_peak_kw"] + 1e-9


def test_profile_raumwaerme_im_winter(profiles, weather_df):
    month = weather_df.index.month
    winter = profiles["space_heat_kw"][(month == 1) | (month == 12)].mean()
    summer = profiles["space_heat_kw"][(month == 7)].mean()
    assert winter > 10 * max(summer, 1e-9) or summer == 0


def test_basis_drei_quartiere():
    alle = js_annual_demands(["IGA-Quartier", "Schulquartier", "Gartenquartier", "Forstquartier"])
    assert alle["space_heat_kwh"] == pytest.approx(5_664_000)
    assert js_annual_demands()["space_heat_kwh"] < alle["space_heat_kwh"]


# ---------------------------------------------------------------------------
# COP und Dispatch
# ---------------------------------------------------------------------------

def test_cop_sinkt_mit_hub():
    cops = heat_pump_cop(np.array([-10.0, 0.0, 10.0]), 35.0)
    assert cops[0] < cops[1] < cops[2]
    assert heat_pump_cop(10.0, 60.0) < heat_pump_cop(10.0, 35.0)


def _check_heat_balance(space, dhw, p, r):
    supplied = (r.hp_th_kw + r.heater_kw + r.unmet_kw).sum() * DT_H
    needed = (space + dhw + r.net_loss_kw).sum() * DT_H + (r.tank_soc_kwh[-1] - r.tank_soc_start_kwh)
    assert supplied == pytest.approx(needed, rel=1e-6)
    assert (r.hp_th_kw <= p.hp_kw + 1e-6).all()
    assert (r.heater_kw <= p.heater_kw + 1e-6).all()
    assert (r.tank_soc_kwh >= -1e-6).all() and (r.tank_soc_kwh <= p.tank_kwh + 1e-6).all()
    assert (r.unmet_kw >= -1e-9).all()


@pytest.mark.parametrize("name", list(JS_CONCEPTS))
def test_dispatch_konzepte(profiles, weather_df, name):
    concept = JS_CONCEPTS[name]
    cop_space, cop_dhw = concept_cops(concept, weather_df["temp_air"].to_numpy())
    p = JSParams.from_concept(concept)
    space, dhw = profiles["space_heat_kw"].to_numpy(), profiles["dhw_kw"].to_numpy()
    r = run_js_heat_dispatch(space, dhw, profiles["cooling_kw"].to_numpy(), cop_space, cop_dhw, p, DT_H)
    _check_heat_balance(space, dhw, p, r)
    heat = (space + dhw).sum() * DT_H
    assert r.unmet_kwh < 0.01 * heat
    assert 2.5 < r.scop < 6.0


def test_dispatch_tankspeicher_entlastet_heizstab():
    n = 8
    space = np.array([100.0, 100.0, 100.0, 100.0, 400.0, 400.0, 400.0, 400.0])
    dhw = np.zeros(n)
    cop = np.full(n, 3.0)
    base = dict(hp_kw=200.0, heater_kw=1_000.0, warm_net=False, cooling_eer=3.0, tank_soc_start=0.0)
    without = run_js_heat_dispatch(space, dhw, np.zeros(n), cop, cop, JSParams(tank_kwh=0.0, **base), DT_H)
    with_tank = run_js_heat_dispatch(space, dhw, np.zeros(n), cop, cop, JSParams(tank_kwh=500.0, **base), DT_H)
    assert with_tank.heater_kwh < without.heater_kwh
    _check_heat_balance(space, dhw, JSParams(tank_kwh=500.0, **base), with_tank)


def test_dispatch_warmes_netz_nachheizung():
    n = 4
    dhw = np.full(n, 100.0)
    cop = np.full(n, 3.0)
    p = JSParams(hp_kw=1_000.0, heater_kw=1_000.0, tank_kwh=0.0, warm_net=True, cooling_eer=3.0)
    r = run_js_heat_dispatch(np.zeros(n), dhw, np.zeros(n), cop, cop, p, DT_H)
    np.testing.assert_allclose(r.heater_kw, dhw * p.dhw_lift_share)
    np.testing.assert_allclose(r.hp_th_kw, dhw * (1 - p.dhw_lift_share) / (1 - p.net_loss))
