"""
Elektroladesäule Klasse
Author: Jannis Brinkmann
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Dict, Any
import pandas as pd

# ===== Elektroladesäule =======================================================
@dataclass
class ElectricCharger:

    def __init__(self,
                 name: str,
                 rated_power_kw: float,
                 n_connectors: int = 1,
                 efficiency: float = 0.95,
                 max_current_a: float | None = None,
                 connection_type: str = "AC"):

        self.name = name
        self.rated_power_kw = rated_power_kw
        self.n_connectors = n_connectors
        self.efficiency = efficiency
        self.max_current_a = max_current_a
        self.connection_type = connection_type

        self.load_profile_kw = None
        self.energy_delivered_kwh = 0.0     # kumulierte Energie
        self.current_power_kw = 0.0         # aktuell abgegebene Ladeleistung

    def set_load_profile(self, load_profile_kw: pd.Series):
        """
        Setzt oder aktualisiert das Lastprofil für die Ladesäule.
        """
        if not isinstance(load_profile_kw, pd.Series):
            raise TypeError("load_profile_kw muss eine pandas.Series sein.")
        if not isinstance(load_profile_kw.index, pd.DatetimeIndex):
            raise TypeError("load_profile_kw muss einen DatetimeIndex besitzen.")
        if not load_profile_kw.index.is_monotonic_increasing:
            load_profile_kw = load_profile_kw.sort_index()

        self.load_profile_kw = load_profile_kw

    def charge(self, timestamp: pd.Timestamp, dt_h: float) -> float:
        """
        Berechnet die gelieferte Energie im gegebenen Zeitschritt anhand des Lastprofils.
        """
        if self.load_profile_kw is None:
            raise RuntimeError(f"{self.name} hat noch kein Lastprofil gesetzt.")

        timestamp = pd.Timestamp(timestamp)

        if timestamp not in self.load_profile_kw.index:
            nearest = self.load_profile_kw.index.asof(timestamp)
            if nearest is pd.NaT:
                raise ValueError(f"{timestamp} liegt außerhalb des Lastprofils von {self.name}.")
            timestamp = nearest

        # Ladeleistung übernehmen
        self.current_power_kw = float(self.load_profile_kw.loc[timestamp])

        # Energie berechnen
        delivered = self.current_power_kw * dt_h * self.efficiency
        self.energy_delivered_kwh += delivered

        return delivered


# ------------------- Optionaler Direktstart:------------------------------------------
if __name__ == "__main__":

        charger = ElectricCharger
        charger.charge()



