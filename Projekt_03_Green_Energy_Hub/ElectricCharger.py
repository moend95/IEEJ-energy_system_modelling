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

    def __init__(self, name: str, rated_power_kw: float, n_connectors: int = 1, efficiency: float = 0.95,
                    max_current_a: float | None = None, connection_type: str = "AC", load_profile_kw = None)
        self.name = name
        self.rated_power_kw = rated_power_kw
        self.n_connectors = n_connectors
        self.efficiency = efficiency
        self.max_current_a = max_current_a
        self.connection_type = connection_type      #AC oder DC
        self.load_profile_kw = load_profile_kw

        #dynamische Zustände
        self.connected_vehicles = []  # Liste von EVs (wenn du auch eine Vehicle-Klasse hast)
        self.current_power_kw = 0.0  # aktuell abgegebene Ladeleistung
        self.energy_delivered_kwh = 0.0  # kumulierte Energie

    def set_load_profile (self, load_profile_kw):
        self.load_profile_kw = load_profile_kw

    def charge(self, timestamp, dt_h: float):
        """
        Berechnet die gelieferte Energie im gegebenen Zeitschritt anhand des Lastprofils.

        Args:
            timestamp: Zeitindex (z. B. datetime), für den die Ladeleistung gilt.
            dt_h: Zeitschrittdauer in Stunden (z. B. 0.25 für 15 min).
        """
        if self.load_profile_kw is None:
            raise RuntimeError(f"{self.name} hat kein Lastprofil gesetzt.")

        if timestamp not in self.load_profile_kw.index:
            raise ValueError(f"{timestamp} nicht im Lastprofil enthalten.")

        # Ladeleistung aus dem Profil lesen
        self.current_power_kw = self.load_profile_kw.loc[timestamp]

        # Gelieferte Energie berechnen (kWh)
        delivered = self.current_power_kw * dt_h * self.efficiency
        self.energy_delivered_kwh += delivered

        return delivered




