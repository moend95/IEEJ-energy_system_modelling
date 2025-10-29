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
                    max_current_a: float | None = None, connection_type: str = "AC")
        self.name = name
        self.rated_power_kw = rated_power_kw
        self.n_connectors = n_connectors
        self.efficiency = efficiency
        self.max_current_a = max_current_a
        self.connection_type = connection_type      #AC oder DC

        #dynamische Zustände
        self.connected_vehicles = []  # Liste von EVs (wenn du auch eine Vehicle-Klasse hast)
        self.current_power_kw = 0.0  # aktuell abgegebene Ladeleistung
        self.energy_delivered_kwh = 0.0  # kumulierte Energie

    def charge (self, duration_h: float)


        return 0.0


