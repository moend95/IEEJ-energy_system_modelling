from __future__ import annotations
import pandas as pd
import numpy as np
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Dict

# ========== I/O für Lastgänge ==========
class LoadIO:
    """
    Liest Lastgänge (Strom/Wärme) aus CSV ein oder lädt Standardprofile.
    Erwartetes Format:
      - Spalte 'time' als ISO-Datetime (UTC oder lokale Zeit, bitte konsistent)
      - Spalten:
          'elec_kw'   (positiv = Verbrauch)
          'heat_kw'   (optional)
          'heat_ht_kw' (optional, sehr hohe T)
    Index wird auf DatetimeIndex gesetzt. Frequenz z.B. 15min.
    """
    @staticmethod
    def read_profiles(path: Optional[str|Path]) -> pd.DataFrame:
        if path is None:
            # Fallback: Standardprofile (relativer Pfad)
            std_path = Path("data/defaults/standard_lastgang_elec_15min.csv")
            if not std_path.exists():
                raise FileNotFoundError("Standardlastgang nicht gefunden: data/defaults/standard_lastgang_elec_15min.csv")
            df = pd.read_csv(std_path)
        else:
            df = pd.read_csv(path)

        if "time" not in df.columns:
            raise ValueError("CSV muss eine Spalte 'time' enthalten.")
        df["time"] = pd.to_datetime(df["time"])
        df = df.set_index("time").sort_index()

        # Mindestspalte
        if "elec_kw" not in df.columns:
            raise ValueError("CSV muss mindestens die Spalte 'elec_kw' enthalten (kW).")

        # Optionale Spalten auffüllen
        for col in ["heat_kw", "heat_ht_kw"]:
            if col not in df.columns:
                df[col] = 0.0

        # Typen & NaNs
        df = df.astype(float)
        df = df.fillna(0.0)

        # Frequenz ableiten (z.B. '15T')
        # -> optional: Validierung, ob lückenlos
        return df

# ========== Stammdaten ==========
@dataclass
class Company:
    name: str
    dachflaeche_m2: float
    location_lat: Optional[float] = None
    location_lon: Optional[float] = None
    # Skalierungsfaktoren optional
    elec_scale: float = 1.0
    heat_scale: float = 1.0
    heat_ht_scale: float = 1.0

# ========== PV-Modell (einfach) ==========
class PVModel:
    """
    Einfache PV-Erzeugung aus spezifischem Jahresertrag oder Zeitscheibenprofil.
    Start: skaliert ein Tagesprofil (kW pro kWp) auf installierte kWp.
    Später: echte pvlib-Erzeugung (irradiance, temp, tilt, azimuth, Standort).
    """
    def __init__(self, pv_kwp: float, profile_per_kwp_kw: Optional[pd.Series] = None):
        self.pv_kwp = pv_kwp
        self.profile_per_kwp_kw = profile_per_kwp_kw  # index = time

    @staticmethod
    def from_roof(dachflaeche_m2: float, spec_kwp_per_m2: float = 0.18) -> float:
        """
        Sehr grob: 1 m² ~ 180 Wp (0.18 kWp/m²) bei moderner Belegung.
        """
        return dachflaeche_m2 * spec_kwp_per_m2

    def power_series_kw(self, index: pd.DatetimeIndex) -> pd.Series:
        if self.profile_per_kwp_kw is None:
            # Dummy: simple Glocke pro Tag (nur zum Start)
            t = np.arange(len(index))
            day_frac = (t % (24*4)) / (24*4)  # bei 15-min Daten
            bell = np.clip(np.sin(np.pi * day_frac), 0, None)  # 0..1
            per_kwp = pd.Series(bell * 0.8, index=index)  # Peak 0.8 kW/kWp
        else:
            per_kwp = self.profile_per_kwp_kw.reindex(index).fillna(0.0)

        return per_kwp * self.pv_kwp

# ========== KPIs ==========
class KPIs:
    @staticmethod
    def compute(results: pd.DataFrame) -> Dict[str, float]:
        """
        Erwartet DataFrame mit Spalten:
          'load_elec_kw', 'pv_kw', 'grid_kw' (+/-), 'step_h'
        """
        step_h = float(results["step_h"].iloc[0])
        # kWh
        cons_kwh = (results["load_elec_kw"] * step_h).sum()
        pv_kwh   = (results["pv_kw"]         * step_h).sum()
        grid_pos_kwh = (results["grid_kw"].clip(lower=0) * step_h).sum()   # Bezug
        grid_neg_kwh = ((-results["grid_kw"]).clip(lower=0) * step_h).sum() # Einspeisung

        eigenverbrauch_kwh = cons_kwh - grid_pos_kwh
        ev_quote = eigenverbrauch_kwh / pv_kwh if pv_kwh > 1e-9 else 0.0
        autarkie = 1.0 - grid_pos_kwh / cons_kwh if cons_kwh > 1e-9 else 0.0

        # Simple Kostenüberschlag (€/kWh, Invest €/kWp)
        strompreis = 0.25  # €/kWh (Annahme)
        einspeise = 0.07   # €/kWh (Annahme)
        pv_invest_per_kwp = 900  # €/kWp (Annahme grob)
        pv_invest = pv_invest_per_kwp * results.attrs.get("pv_kwp", 0.0)

        grid_cost = grid_pos_kwh * strompreis - grid_neg_kwh * einspeise

        return {
            "consumption_kwh": round(cons_kwh, 1),
            "pv_kwh": round(pv_kwh, 1),
            "grid_import_kwh": round(grid_pos_kwh, 1),
            "grid_export_kwh": round(grid_neg_kwh, 1),
            "eigenverbrauchsquote": round(ev_quote, 3),
            "autarkiegrad": round(autarkie, 3),
            "pv_invest_eur": round(pv_invest, 0),
            "grid_cost_eur": round(grid_cost, 0),
        }

# ========== Hauptklasse ==========
class IndustrieSim:
    """
    Orchestriert:
      - Lastgänge laden (Strom/Wärme)
      - PV-Erzeugung berechnen
      - Bilanz & KPIs
    """
    def __init__(self, company: Company, loads: pd.DataFrame, step_h: float = 0.25,
                 pv_kwp: Optional[float] = None, pv_profile_per_kwp_kw: Optional[pd.Series] = None):
        self.company = company
        self.loads = loads.copy()
        self.step_h = step_h

        # Skalierungen anwenden
        self.loads["elec_kw"]     = self.loads["elec_kw"] * company.elec_scale
        self.loads["heat_kw"]     = self.loads["heat_kw"] * company.heat_scale
        self.loads["heat_ht_kw"]  = self.loads["heat_ht_kw"] * company.heat_ht_scale

        if pv_kwp is None:
            pv_kwp = PVModel.from_roof(company.dachflaeche_m2)
        self.pv = PVModel(pv_kwp=pv_kwp, profile_per_kwp_kw=pv_profile_per_kwp_kw)

    def run(self) -> pd.DataFrame:
        idx = self.loads.index
        pv_kw = self.pv.power_series_kw(idx)

        # Bilanz (nur Strom)
        load_kw = self.loads["elec_kw"]
        residual_kw = load_kw - pv_kw     # +Bedarf, -Überschuss
        grid_kw = residual_kw             # noch ohne Speicher/Steuerung

        df = pd.DataFrame({
            "load_elec_kw": load_kw,
            "pv_kw": pv_kw,
            "grid_kw": grid_kw,
        }, index=idx)
        df["step_h"] = self.step_h

        # Attach Meta
        df.attrs["pv_kwp"] = self.pv.pv_kwp
        df.attrs["company"] = self.company.name
        return df

    def compute_kpis(self, results: pd.DataFrame) -> Dict[str, float]:
        return KPIs.compute(results)
