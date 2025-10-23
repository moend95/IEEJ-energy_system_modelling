

"""
GreenEnergyHub – modularer Starter (15‑min Auflösung)
-----------------------------------------------------
- PV, Wind, Elektrolyseur (Adapter), H2‑Speicher, H2‑Last
- nutzt Moritz_electrolyzer.py automatisch, wenn vorhanden (sonst simples Linearmodell)
- kann CSVs einlesen (Zeitreihe + Spalte mit Leistung/Bedarf) ODER synthetische Daten erzeugen
- Ziel: Grundgerüst fürs klassenbasierte Baukasten‑System im Masterprojekt

Nutzung
-------
from green_energy_hub import (
    PVSystem, WindTurbine, ElectrolyzerAdapter,
    H2Storage, H2DemandModel, GreenEnergyHub, run_example
)

# Beispiel (synthetische Daten für 3 Tage):
df = run_example()
df.to_csv("green_energy_hub_example_results.csv")

# Eigene CSVs einlesen (Spaltennamen werden heuristisch erkannt):
# pv = PVSystem.from_csv("DE_1,5MWp.csv", scale_to_kwp=20000)
# wind = WindTurbine.from_csv("DE_5,6MW_Wind.csv", scale_to_kw=20000)
# demand = H2DemandModel.from_csv("load_h2_15min_mw.csv")
# ely = ElectrolyzerAdapter(17200)
# storage = H2Storage(capacity_kg=100000, soc_kg=50000)
# hub = GreenEnergyHub(pv, wind, ely, storage, demand, grid_import_kw_limit=0)
# results = hub.simulate()
"""
from __future__ import annotations
import os
from dataclasses import dataclass
from typing import Optional, Dict
import numpy as np
import pandas as pd
from Moritz.electrolyzer import electrolyzer as MoritzElectrolyzer

# ---------------------- Helpers ----------------------
def _ensure_dt_index(df: pd.DataFrame) -> pd.DataFrame:     # eine Hilfsfunktion, die sicherstellt, dass das DataFrame eine Zeitachse als Index hat.
    if not isinstance(df.index, pd.DatetimeIndex):
        df = df.copy()
        df.iloc[:, 0] = pd.to_datetime(df.iloc[:, 0])
        df = df.set_index(df.columns[0])
    return df

# ---------------------- Komponenten ----------------------
@dataclass
class PVSystem:
    capacity_kwp: float
    series_kw: Optional[pd.Series] = None

    @staticmethod
    def from_csv(path: str, power_col_guess: Optional[str] = None, scale_to_kwp: Optional[float] = None) -> "PVSystem":
        if not os.path.exists(path):
            raise FileNotFoundError(f"PV csv not found: {path}")
        df = pd.read_csv(path)
        df = _ensure_dt_index(df)
        cols = df.columns.str.lower()
        if power_col_guess and power_col_guess in df.columns:
            col = power_col_guess
        elif "p_pv_kw" in cols:
            col = df.columns[cols.get_loc("p_pv_kw")]
        elif "power_kw" in cols:
            col = df.columns[cols.get_loc("power_kw")]
        elif "pv_kw" in cols:
            col = df.columns[cols.get_loc("pv_kw")]
        elif "p" in cols:
            col = df.columns[cols.get_loc("p")]
        else:
            col = df.columns[-1]
        s = df[col].astype(float).rename("pv_kw").resample("15min").interpolate()
        cap = s.max() if scale_to_kwp is None else scale_to_kwp
        if scale_to_kwp is not None and s.max() > 0:
            s = s * (scale_to_kwp / s.max())
        return PVSystem(capacity_kwp=cap, series_kw=s)

    @staticmethod
    def synthetic(capacity_kwp: float, index: pd.DatetimeIndex) -> "PVSystem":
        hours = index.hour.values + index.minute.values/60.0
        day_angle = (hours - 12.0) / 6.0
        base = np.clip(1.0 - (day_angle**2), 0, 1)
        noise = np.clip(np.random.normal(1.0, 0.1, size=len(index)), 0.6, 1.2)
        s = capacity_kwp * base * noise * 0.9
        return PVSystem(capacity_kwp=capacity_kwp, series_kw=pd.Series(s, index=index, name="pv_kw"))

@dataclass
class WindTurbine:
    capacity_kw: float
    series_kw: Optional[pd.Series] = None

    @staticmethod
    def from_csv(path: str, power_col_guess: Optional[str] = None, scale_to_kw: Optional[float] = None) -> "WindTurbine":
        if not os.path.exists(path):
            raise FileNotFoundError(f"Wind csv not found: {path}")
        df = pd.read_csv(path)
        df = _ensure_dt_index(df)
        cols = df.columns.str.lower()
        if power_col_guess and power_col_guess in df.columns:
            col = power_col_guess
        elif "p_wind_kw" in cols:
            col = df.columns[cols.get_loc("p_wind_kw")]
        elif "power_kw" in cols:
            col = df.columns[cols.get_loc("power_kw")]
        elif "wind_kw" in cols:
            col = df.columns[cols.get_loc("wind_kw")]
        elif "p" in cols:
            col = df.columns[cols.get_loc("p")]
        else:
            col = df.columns[-1]
        s = df[col].astype(float).rename("wind_kw").resample("15min").interpolate()
        cap = s.max() if scale_to_kw is None else scale_to_kw
        if scale_to_kw is not None and s.max() > 0:
            s = s * (scale_to_kw / s.max())
        return WindTurbine(capacity_kw=cap, series_kw=s)

    @staticmethod
    def synthetic(capacity_kw: float, index: pd.DatetimeIndex) -> "WindTurbine":
        rnd = np.random.default_rng(42)
        base = rnd.normal(0.55, 0.12, size=len(index))
        base = pd.Series(base, index=index).rolling(4, min_periods=1).mean().clip(0, 1).values
        s = capacity_kw * base
        return WindTurbine(capacity_kw=capacity_kw, series_kw=pd.Series(s, index=index, name="wind_kw"))

@dataclass
class H2DemandModel:
    series_kg: pd.Series

    @staticmethod
    def from_csv(path: str, demand_col_guess: Optional[str] = None, unit_hint: str = "kg_per_15min") -> "H2DemandModel":
        if not os.path.exists(path):
            raise FileNotFoundError(f"H2 demand csv not found: {path}")
        df = pd.read_csv(path)
        df = _ensure_dt_index(df)
        cols = df.columns.str.lower()
        if demand_col_guess and demand_col_guess in df.columns:
            col = demand_col_guess
        elif "h2_kg" in cols:
            col = df.columns[cols.get_loc("h2_kg")]
        elif "kg" in cols:
            col = df.columns[cols.get_loc("kg")]
        elif "mw" in cols:
            col = df.columns[cols.get_loc("mw")]
            s = (df[col].astype(float) * 1000.0) * 0.25 / 33.33
            s = s.rename("h2_kg").resample("15min").interpolate()
            return H2DemandModel(series_kg=s)
        else:
            col = df.columns[-1]
        s = df[col].astype(float).rename("h2_kg").resample("15min").interpolate()
        return H2DemandModel(series_kg=s)

    @staticmethod
    def synthetic(index: pd.DatetimeIndex, daily_total_kg: float = 2000.0) -> "H2DemandModel":
        s = pd.Series(0.0, index=index, name="h2_kg")
        for day, grp in s.groupby(s.index.date):
            local = s.loc[str(day)]
            hours = local.index.hour.values + local.index.minute.values/60.0
            morning = np.exp(-0.5*((hours-8.0)/1.5)**2)
            evening = np.exp(-0.5*((hours-18.0)/1.8)**2)
            base = 0.2 + 0.9*(morning + evening)
            if pd.Timestamp(day).weekday() >= 5:
                base *= 0.6
            base = base / np.sum(base) * daily_total_kg
            s.loc[str(day)] = base
        return H2DemandModel(series_kg=s)

@dataclass
class H2Storage:
    capacity_kg: float
    soc_kg: float = 0.0
    charge_limit_kg_per_h: float = 4000.0
    discharge_limit_kg_per_h: float = 4000.0
    charge_eff: float = 0.98
    discharge_eff: float = 0.98

    def charge(self, kg: float, dt_h: float) -> float:
        limit = self.charge_limit_kg_per_h * dt_h
        accepted_in = min(kg, limit, self.capacity_kg - self.soc_kg)
        stored = accepted_in * self.charge_eff
        self.soc_kg += stored
        return accepted_in

    def discharge(self, kg: float, dt_h: float) -> float:
        limit = self.discharge_limit_kg_per_h * dt_h
        possible_out = min(kg / self.discharge_eff, limit, self.soc_kg)
        self.soc_kg -= possible_out
        return possible_out * self.discharge_eff

class ElectrolyzerAdapter:
    def __init__(self, nameplate_kw: float, p_out_bar: float = 750.0):
        self.nameplate_kw = float(nameplate_kw)
        self.p_out_bar = float(p_out_bar)
        if HAVE_MORITZ:
            self.m = MoritzElectrolyzer(P_elektrolyseur=str(int(nameplate_kw)),
                                        dt_1="15", unit_dt="min", p2=str(int(p_out_bar)))
        else:
            self.lhv_kwh_per_kg = 33.33
            self.stack_eff_at_full = 0.67

    def h2_from_power(self, p_ac_kw: float, dt_min: float = 15.0) -> float:
        p = max(0.0, min(p_ac_kw, self.nameplate_kw))
        if HAVE_MORITZ:
            self.m.dt = dt_min
            self.m.unit_dt = "min"
            h2_kg_per_h = float(self.m.calc_H2_mfr(self.m.power_dc(p)))
            kg = h2_kg_per_h * (dt_min / 60.0)
            return max(0.0, kg)
        else:
            h2_energy_kwh = p * (dt_min/60.0) * self.stack_eff_at_full
            kg = h2_energy_kwh / self.lhv_kwh_per_kg
            return max(0.0, kg)

class GreenEnergyHub:
    def __init__(self,
                 pv: PVSystem,
                 wind: WindTurbine,
                 electrolyzer: ElectrolyzerAdapter,
                 h2_storage: H2Storage,
                 h2_demand: H2DemandModel,
                 grid_import_kw_limit: float = 0.0):
        self.pv = pv
        self.wind = wind
        self.electrolyzer = electrolyzer
        self.h2_storage = h2_storage
        self.h2_demand = h2_demand
        self.grid_import_kw_limit = grid_import_kw_limit

    def simulate(self) -> pd.DataFrame:
        idx = self._common_index()
        pv = self.pv.series_kw.reindex(idx, method="nearest").fillna(0.0)
        wind = self.wind.series_kw.reindex(idx, method="nearest").fillna(0.0)
        demand = self.h2_demand.series_kg.reindex(idx, method="nearest").fillna(0.0)

        results = []
        dt_min = 15.0
        dt_h = dt_min / 60.0

        for t in idx:
            p_pv = float(pv.loc[t])
            p_wind = float(wind.loc[t])
            p_res = p_pv + p_wind

            grid = 0.0
            if self.grid_import_kw_limit > 0 and p_res < self.electrolyzer.nameplate_kw:
                grid = min(self.electrolyzer.nameplate_kw - p_res, self.grid_import_kw_limit)

            p_el_in = p_res + grid
            h2_prod = self.electrolyzer.h2_from_power(p_el_in, dt_min=dt_min)

            need = float(demand.loc[t])
            direct = min(need, h2_prod)
            remaining_need = need - direct

            from_storage = 0.0
            if remaining_need > 0:
                from_storage = self.h2_storage.discharge(remaining_need, dt_h=dt_h)
            unmet = max(0.0, remaining_need - from_storage)

            surplus = h2_prod - direct
            stored_in = 0.0
            if surplus > 0:
                before = self.h2_storage.soc_kg
                _consumed = self.h2_storage.charge(surplus, dt_h=dt_h)
                stored_in = max(0.0, self.h2_storage.soc_kg - before)

            results.append({
                "time": t,
                "pv_kw": p_pv,
                "wind_kw": p_wind,
                "grid_kw": grid,
                "p_el_in_kw": p_el_in,
                "h2_prod_kg": h2_prod,
                "h2_direct_to_load_kg": direct,
                "h2_from_storage_kg": from_storage,
                "h2_to_storage_kg": stored_in,
                "h2_unmet_kg": unmet,
                "h2_storage_soc_kg": self.h2_storage.soc_kg
            })

        df = pd.DataFrame(results).set_index("time")
        return df

    def _common_index(self) -> pd.DatetimeIndex:
        idx = (self.pv.series_kw.index.union(self.wind.series_kw.index)
                                  .union(self.h2_demand.series_kg.index))
        start = idx.min().floor("15min")
        end = idx.max().ceil("15min")
        return pd.date_range(start, end, freq="15min")

# Convenience: schneller Einstieg mit synthetischen Daten

def run_example(config: Optional[Dict] = None) -> pd.DataFrame:
    cfg = dict(
        start="2019-01-01 00:00", end="2019-01-03 23:45",
        pv_capacity_kwp=20000,
        wind_capacity_kw=20000,
        electrolyzer_kw=17200,
        storage_capacity_kg=100000,
        grid_import_kw_limit=0.0,
        pv_csv=None, wind_csv=None, h2_csv=None
    )
    if config: cfg.update(config)

    idx = pd.date_range(cfg["start"], cfg["end"], freq="15min")

    if cfg["pv_csv"] and os.path.exists(cfg["pv_csv"]):
        pv = PVSystem.from_csv(cfg["pv_csv"], scale_to_kwp=cfg["pv_capacity_kwp"])
    else:
        pv = PVSystem.synthetic(cfg["pv_capacity_kwp"], idx)

    if cfg["wind_csv"] and os.path.exists(cfg["wind_csv"]):
        wind = WindTurbine.from_csv(cfg["wind_csv"], scale_to_kw=cfg["wind_capacity_kw"])
    else:
        wind = WindTurbine.synthetic(cfg["wind_capacity_kw"], idx)

    if cfg["h2_csv"] and os.path.exists(cfg["h2_csv"]):
        demand = H2DemandModel.from_csv(cfg["h2_csv"])
    else:
        demand = H2DemandModel.synthetic(idx, daily_total_kg=2000.0)

    ely = ElectrolyzerAdapter(cfg["electrolyzer_kw"], p_out_bar=750.0)
    storage = H2Storage(capacity_kg=cfg["storage_capacity_kg"], soc_kg=0.5*cfg["storage_capacity_kg"])

    geh = GreenEnergyHub(pv, wind, ely, storage, demand, grid_import_kw_limit=cfg["grid_import_kw_limit"])
    return geh.simulate()
