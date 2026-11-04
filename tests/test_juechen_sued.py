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


# ---------------------------------------------------------------------------
# Integration (vollständige run_simulation)
# ---------------------------------------------------------------------------

JS_COLUMNS = ["Last_JS_Nutzerstrom [kW]", "Last_JS_EMob [kW]", "Last_JS_Waermepumpe [kW]",
              "Last_JS_Heizstab [kW]", "Last_JS_Kaelte [kW]"]


def js_input(concept: str):
    from core.io_types import GuiInput
    return GuiInput(
        h_highways=["A46"], h_pv_types=[0],
        el_build_state=50, el_pv_type=5,
        el_tractor_width=12.0, el_tractor_length=15.0, el_tractor_turn_radius=9.0,
        i_heat_cooling_electric=True, i_companies=[2, 3, 4, 5, 6],
        geh_variant="Keine", js_concept=concept,
    )


@pytest.fixture(scope="module")
def sims():
    import contextlib
    import io
    from Simulation import run_simulation
    with contextlib.redirect_stdout(io.StringIO()):
        return {c: run_simulation(js_input(c)) for c in ["Aus", *JS_CONCEPTS]}


@pytest.mark.slow
@pytest.mark.parametrize("concept", list(JS_CONCEPTS))
def test_integration_konzept(sims, concept):
    o = sims[concept]
    df = o.res_df
    np.testing.assert_allclose(df[JS_COLUMNS].sum(axis=1), df["Last_Juechen_Sued [kW]"], atol=1e-9)
    assert o.js_sum_energy_kwh == pytest.approx(
        o.js_household_kwh + o.js_emob_kwh + o.js_hp_el_kwh + o.js_heater_el_kwh + o.js_cooling_el_kwh, rel=1e-9)
    assert o.js_heat_unmet_kwh < 0.01 * (o.js_space_heat_kwh + o.js_dhw_kwh)
    # Netzbilanz schließt
    gen = df[[c for c in df.columns if c.startswith("Erzeugung")]].sum(axis=1)
    loads = df[["Last_Industrie [kW]", "Last_Green_Energy_Hub [kW]", "Last_Juechen_Sued [kW]"]].sum(axis=1)
    np.testing.assert_allclose(gen + df["Netzbezug [kW]"], loads + df["Netzeinspeisung [kW]"], atol=1e-6)


@pytest.mark.slow
def test_integration_aus(sims):
    o = sims["Aus"]
    for column in [*JS_COLUMNS, "Last_Juechen_Sued [kW]"]:
        assert (o.res_df[column] == 0).all(), column
    assert o.js_sum_energy_kwh == 0


@pytest.mark.slow
def test_integration_reihenfolge_strombedarf(sims):
    """Warmes Netz braucht wegen Netzverlusten und Nachheizung am meisten Strom für Wärme."""
    heat_el = {c: sims[c].js_hp_el_kwh + sims[c].js_heater_el_kwh for c in JS_CONCEPTS}
    assert heat_el["Warmes Netz"] > heat_el["Kaltes Netz"]
    assert heat_el["Warmes Netz"] > heat_el["Dezentral"]
