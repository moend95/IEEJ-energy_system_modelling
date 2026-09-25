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


# ---------------------------------------------------------------------------
# Dispatch mit synthetischen Arrays
# ---------------------------------------------------------------------------

from core.module_green_energy_hub import GEHParams, run_geh_dispatch


def _check_invariants(net, demand, p, r):
    eta = np.sqrt(p.battery_eff_rt)
    tol = 1e-6
    # Batterie
    assert (r.battery_soc_kwh >= -tol).all() and (r.battery_soc_kwh <= p.battery_kwh + tol).all()
    assert not ((r.battery_charge_kw > tol) & (r.battery_discharge_kw > tol)).any()
    assert r.battery_charge_kw.max() <= p.battery_kw + tol
    assert r.battery_discharge_kw.max() <= p.battery_kw + tol
    batt = (r.battery_charge_kw.sum() * eta - r.battery_discharge_kw.sum() / eta) * DT_H
    assert batt == pytest.approx(r.battery_soc_kwh[-1] - r.battery_soc_start_kwh, abs=1.0)
    # H2
    assert (r.h2_soc_kwh >= -tol).all() and (r.h2_soc_kwh <= p.h2_storage_kwh + tol).all()
    assert r.electrolyzer_kw.max() <= p.electrolyzer_kw + tol
    h2 = r.h2_production_kwh - r.h2_delivered_total_kwh
    assert h2 == pytest.approx(r.h2_soc_kwh[-1] - r.h2_soc_start_kwh, abs=1.0)
    assert r.h2_delivered_total_kwh + r.unmet_kwh == pytest.approx(demand.sum(), abs=1e-6)
    # Speicher voll → Produktion ≤ Nachfrage
    prod = r.electrolyzer_kw * p.electrolyzer_eff * DT_H
    prev_soc = np.concatenate(([r.h2_soc_start_kwh], r.h2_soc_kwh[:-1]))
    full = prev_soc >= p.h2_storage_kwh - tol
    assert (prod[full] <= demand[full] + tol).all()
    # Leistungsbilanz je Zeitschritt
    lhs = net + r.grid_import_kw + r.battery_discharge_kw
    rhs = r.electrolyzer_kw + r.compressor_kw + r.grid_export_kw + r.battery_charge_kw
    np.testing.assert_allclose(lhs, rhs, atol=1e-6)
    assert not ((r.grid_import_kw > tol) & (r.grid_export_kw > tol)).any()


@pytest.fixture(scope="module")
def synthetic():
    rng = np.random.default_rng(1)
    n = 4 * 24 * 60
    t = np.arange(n)
    net = 3000 * np.sin(2 * np.pi * t / 96) + rng.normal(0, 1500, n) - 500
    demand = np.full(n, 150.0) + rng.uniform(0, 300, n)
    return net, demand


def test_dispatch_invarianten(synthetic):
    net, demand = synthetic
    p = GEHParams.from_variant(GEH_VARIANTS["Erweiterung"])
    _check_invariants(net, demand, p, run_geh_dispatch(net, demand, p, DT_H))


def test_dispatch_kleiner_speicher_und_batterie(synthetic):
    net, demand = synthetic
    p = GEHParams.from_variant({**GEH_VARIANTS["Basis"], "h2_storage_kwh": 2_000.0,
                                "battery_kwh": 500.0, "battery_kw": 200.0})
    _check_invariants(net, demand, p, run_geh_dispatch(net, demand, p, DT_H))


def test_dispatch_mindestfuellstand_nutzt_netz():
    n = 96
    net = np.full(n, -1000.0)   # dauerhaftes Defizit, kein Überschuss
    demand = np.zeros(n)
    p = GEHParams.from_variant({**GEH_VARIANTS["Basis"], "soc_start": 0.0, "battery_kwh": 0.0})
    r = run_geh_dispatch(net, demand, p, DT_H)
    assert r.electrolyzer_kw[0] == pytest.approx(p.electrolyzer_kw)
    assert r.grid_import_kw[0] == pytest.approx(1000 + p.electrolyzer_kw * (1 + p.compressor_factor * p.electrolyzer_eff))
    # oberhalb des Mindestfüllstands ohne Überschuss aus
    above = r.h2_soc_kwh >= p.h2_min_soc * p.h2_storage_kwh
    idx = np.argmax(above)
    assert (r.electrolyzer_kw[idx + 1:] == 0).all()


def test_dispatch_nullkomponenten():
    net = np.array([500.0, -300.0, 0.0, 1200.0])
    demand = np.array([10.0, 0.0, 5.0, 0.0])
    r = run_geh_dispatch(net, demand, GEHParams.from_variant(None), DT_H)
    np.testing.assert_allclose(r.grid_export_kw, np.maximum(net, 0))
    np.testing.assert_allclose(r.grid_import_kw, np.maximum(-net, 0))
    np.testing.assert_allclose(r.balance_after_kw, net)
    assert r.electrolyzer_kwh == 0 and r.battery_charge_kwh == 0


# ---------------------------------------------------------------------------
# Integration (vollständige run_simulation)
# ---------------------------------------------------------------------------

GEH_COLUMNS = [
    "Last_GEH_MCS [kW]", "Last_GEH_CCS [kW]", "Last_GEH_HPC [kW]", "Last_GEH_AC [kW]",
    "Last_GEH_Gebaeude [kW]", "Last_GEH_Elektrolyseur [kW]", "Last_GEH_Kompressor [kW]",
    "Erzeugung_GEH_PV [kW]", "GEH_Batterie_Laden [kW]", "GEH_Batterie_Entladen [kW]",
    "Last_Green_Energy_Hub [kW]",
]
GENERATION = ["Erzeugung_Solarautobahn [kW]", "Erzeugung_Energielandschaft [kW]", "Erzeugung_GEH_PV [kW]"]
LOADS = ["Last_Industrie [kW]", "Last_Juechen_Sued [kW]", "Last_Green_Energy_Hub [kW]"]


def standard_input(variant: str) -> GuiInput:
    """Standardkonfiguration: A46 + Wand, Energielandschaft 50 %, Unternehmen [2–6], Jüchen-Süd 1000."""
    return GuiInput(
        h_highways=["A46"], h_pv_types=[0],
        el_build_state=50, el_pv_type=5,
        el_tractor_width=12.0, el_tractor_length=15.0, el_tractor_turn_radius=9.0,
        i_heat_cooling_electric=True, i_companies=[2, 3, 4, 5, 6],
        js_scenario="1000 Bewohner",
        geh_variant=variant,
    )


@pytest.fixture(scope="module")
def sim_erweiterung():
    from Simulation import run_simulation
    return run_simulation(standard_input("Erweiterung"))


@pytest.fixture(scope="module")
def sim_keine():
    from Simulation import run_simulation
    return run_simulation(standard_input("Keine"))


def _col_kwh(df, column):
    return df[column].sum() * DT_H if column in df.columns else 0.0


@pytest.mark.slow
def test_integration_energiebilanz(sim_erweiterung):
    df = sim_erweiterung.res_df
    supply = sum(_col_kwh(df, c) for c in GENERATION) + _col_kwh(df, "Netzbezug [kW]") \
        + _col_kwh(df, "GEH_Batterie_Entladen [kW]")
    use = sum(_col_kwh(df, c) for c in LOADS) + _col_kwh(df, "Netzeinspeisung [kW]") \
        + _col_kwh(df, "GEH_Batterie_Laden [kW]")
    assert supply == pytest.approx(use, rel=0.001)
    # Last_Green_Energy_Hub enthält alle GEH-Lasten inkl. Elektrolyseur und Kompressor
    parts = [c for c in GEH_COLUMNS if c.startswith("Last_GEH")]
    np.testing.assert_allclose(df[parts].sum(axis=1), df["Last_Green_Energy_Hub [kW]"], atol=1e-6)


@pytest.mark.slow
def test_integration_ladeenergie(sim_erweiterung):
    v = GEH_VARIANTS["Erweiterung"]
    for attr, key in [("geh_charging_mcs_kwh", "mcs_kwh"), ("geh_charging_ccs_kwh", "ccs_kwh"),
                      ("geh_charging_hpc_kwh", "hpc_kwh"), ("geh_charging_ac_kwh", "ac_kwh"),
                      ("geh_building_kwh", "building_kwh")]:
        assert getattr(sim_erweiterung, attr) == pytest.approx(v[key], rel=0.005), attr


@pytest.mark.slow
def test_integration_plausibilitaet(sim_erweiterung):
    o = sim_erweiterung
    assert 4_500 <= o.geh_electrolyzer_full_load_hours <= 5_500
    assert o.geh_h2_unmet_kwh < 0.01 * o.geh_h2_demand_kwh
    assert o.geh_pv_sum_energy_kwh == pytest.approx(1_060_000, rel=0.10)
    soc_h2 = o.geh_storage_soc_df["soc_kwh"]
    assert soc_h2.min() >= 0 and soc_h2.max() <= GEH_VARIANTS["Erweiterung"]["h2_storage_kwh"] + 1e-6
    soc_b = o.geh_battery_soc_df["soc_kwh"]
    assert soc_b.min() >= 0 and soc_b.max() <= GEH_VARIANTS["Erweiterung"]["battery_kwh"] + 1e-6


@pytest.mark.slow
def test_integration_keine(sim_keine):
    df = sim_keine.res_df
    for column in GEH_COLUMNS:
        assert (df[column] == 0).all(), column
    np.testing.assert_allclose(df["Netzbezug [kW]"], np.maximum(-df["Bilanz [kW]"], 0), atol=1e-9)
    np.testing.assert_allclose(df["Netzeinspeisung [kW]"], np.maximum(df["Bilanz [kW]"], 0), atol=1e-9)
    assert sim_keine.geh_sum_energy_kwh == 0


@pytest.mark.slow
def test_integration_allgemeine_batterie_ueberschreibt_netz():
    from dataclasses import replace
    from Simulation import run_simulation
    inp = replace(standard_input("Basis"), bs_energy_kwh=10_000.0, bs_efficiency=0.9, bs_c_rate=1.0)
    o = run_simulation(inp)
    new_balance = o.bs_df["new_balance_kw"].to_numpy()
    np.testing.assert_allclose(o.res_df["Netzbezug [kW]"], np.maximum(-new_balance, 0))
    np.testing.assert_allclose(o.res_df["Netzeinspeisung [kW]"], np.maximum(new_balance, 0))
    assert o.grid_max_import_kw == pytest.approx(max(-new_balance.min(), 0))
    assert o.grid_import_kwh == pytest.approx(o.bs_stats["grid_import_kwh"])


# ---------------------------------------------------------------------------
# Export und GUI-Helfer
# ---------------------------------------------------------------------------

def test_geh_variant_table():
    from core.functions_web_support import geh_variant_table
    table = geh_variant_table(GEH_VARIANTS["Basis"])
    assert "Lkw MCS" in table.index
    assert table.loc["Pkw Parkhaus AC", "Auslegung"] == "entfällt"


@pytest.mark.slow
def test_export_json(sim_erweiterung, tmp_path):
    import json
    from core.export_utils import export_scenario_flows_to_json
    path = export_scenario_flows_to_json(standard_input("Erweiterung"), sim_erweiterung, "t01", tmp_path,
                                         timeseries_mode="none")
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    assert payload["metadata"]["schema_version"] == "1.1.0"
    geh = payload["annual_summary"]["green_energy_hub"]
    assert "h2_curtailed_kwh" not in geh
    assert geh["variant"] == "Erweiterung"
    assert geh["electrolyzer_full_load_hours"] == pytest.approx(sim_erweiterung.geh_electrolyzer_full_load_hours)
    grid = payload["annual_summary"]["grid"]
    assert grid["import_kwh"] == pytest.approx(sim_erweiterung.grid_import_kwh)
    assert grid["max_import_kw"] == pytest.approx(sim_erweiterung.grid_max_import_kw)


@pytest.mark.slow
def test_synergy_diagram(sim_erweiterung):
    from core.functions_web_support import build_synergy_diagram
    fig = build_synergy_diagram(standard_input("Erweiterung"), sim_erweiterung)
    hover = " ".join(str(t.hovertemplate or "") for t in fig.data)
    assert "Variante: Erweiterung" in hover
    assert "Volllaststunden" in hover
